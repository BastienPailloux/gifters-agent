"""
Service agent Gifters : expose un endpoint chat qui délègue à un agent SmolAgent
connecté au serveur MCP (mcp.gifters.fr) avec les outils idées de cadeaux / groupes.
"""
import asyncio
import os
from pathlib import Path

# Charger .env depuis le répertoire du projet (avant lecture des variables)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Variables d'environnement
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp.lvh.me:3000")
# Token HF requis pour l'API Inference (serverless) : https://huggingface.co/settings/tokens
HF_TOKEN = os.environ.get("HF_TOKEN")
# Modèle utilisé via l'API Inference HF (doit supporter le tool calling)
# Mistral-7B-Instruct-v0.2 est supporté (v0.3 déprécié → 410 Gone). Sinon : Qwen/Qwen3-8B
MODEL_ID = os.environ.get("MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.2")
# Provider optionnel (auto par défaut) : "together", "fireworks", "fal", "hyperbolic", etc.
HF_PROVIDER = os.environ.get("HF_PROVIDER") or None


def _get_tool_label(tool_name: str) -> str:
    """Convertit un nom d'outil MCP en libellé lisible en français."""
    labels = {
        "list_gift_ideas": "Récupération des idées cadeaux",
        "get_gift_idea": "Lecture d'une idée cadeau",
        "list_groups": "Récupération des groupes",
        "get_group": "Lecture d'un groupe",
    }
    return labels.get(tool_name, f"Appel de l'outil {tool_name}")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    message: dict  # {"role": "assistant", "content": "..."}


def _build_task_from_messages(messages: list[dict]) -> str:
    """Construit la tâche pour l'agent à partir de l'historique de conversation."""
    if not messages:
        return ""
    # On ne garde que les N derniers échanges pour limiter la taille du contexte
    max_turns = 10
    recent = messages[-max_turns * 2 :] if len(messages) > max_turns * 2 else messages
    parts = []
    for m in recent:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            parts.append(f"Utilisateur : {content}")
        elif role == "assistant":
            parts.append(f"Assistant : {content}")
    if len(recent) < len(messages):
        parts.insert(0, "(Conversation précédente tronquée.)")
    parts.append("")
    parts.append("Dernière question de l'utilisateur (à laquelle tu dois répondre maintenant) :")
    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if last_user:
        parts.append(last_user.get("content", "").strip())
    return "\n".join(parts) or "Dis bonjour et propose ton aide pour les idées de cadeaux et groupes."


def _run_agent_sync(task: str, auth_header: str) -> str:
    """Lance l'agent (bloquant). Isolé pour pouvoir être exécuté dans un thread si besoin."""
    from smolagents import ToolCallingAgent
    from smolagents.tools import ToolCollection
    from smolagents import InferenceClientModel

    # Connexion au serveur MCP avec auth (JWT de l'utilisateur)
    server_params = {
        "url": MCP_SERVER_URL,
        "transport": "streamable-http",
        "headers": {"Authorization": auth_header or ""},
    }

    with ToolCollection.from_mcp(
        server_params,
        trust_remote_code=True,
        structured_output=True,
    ) as tool_collection:
        tools = list(tool_collection.tools)
        if not tools:
            return "Erreur : aucun outil disponible depuis le serveur MCP. Vérifiez l'URL et l'authentification."

        # API Inference Hugging Face (serverless) : pas de téléchargement de modèle local
        model = InferenceClientModel(
            model_id=MODEL_ID,
            token=HF_TOKEN,
            provider=HF_PROVIDER,
            max_tokens=1024,
        )
        agent = ToolCallingAgent(
            tools=tools,
            model=model,
            instructions=(
                "Tu es l'assistant de l'application Gifters (gestion d'idées de cadeaux et de groupes). "
                "Utilise les outils disponibles pour lister les idées de cadeaux, voir le détail d'une idée, "
                "ou lister les groupes de l'utilisateur. Réponds de façon concise et utile en français."
            ),
        )
        result = agent.run(task, reset=True)
        if hasattr(result, "output"):
            return str(result.output) if result.output else "Je n'ai pas de réponse à te donner pour le moment."
        return str(result)


def _run_agent_stream(
    task: str,
    auth_header: str,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Lance l'agent et pousse des événements SSE dans la queue."""

    def emit(event_type: str, data: dict) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"event": event_type, "data": json.dumps(data, ensure_ascii=False)},
        )

    from smolagents import ToolCallingAgent
    from smolagents.tools import ToolCollection
    from smolagents import InferenceClientModel

    try:
        emit("step", {"label": "Connexion au serveur MCP", "status": "running"})

        server_params = {
            "url": MCP_SERVER_URL,
            "transport": "streamable-http",
            "headers": {"Authorization": auth_header or ""},
        }

        with ToolCollection.from_mcp(
            server_params,
            trust_remote_code=True,
            structured_output=True,
        ) as tool_collection:
            tools = list(tool_collection.tools)
            if not tools:
                emit("error", {"message": "Aucun outil disponible depuis le serveur MCP."})
                return

            emit("step", {"label": "Connexion au serveur MCP", "status": "done"})
            emit("step", {"label": "Analyse de votre demande", "status": "running"})

            model = InferenceClientModel(
                model_id=MODEL_ID,
                token=HF_TOKEN,
                provider=HF_PROVIDER,
                max_tokens=1024,
            )

            def step_callback(step_log) -> None:  # noqa: ANN001
                if hasattr(step_log, "tool_calls") and step_log.tool_calls:
                    for tc in step_log.tool_calls:
                        name = getattr(tc, "name", "")
                        emit("step", {"label": _get_tool_label(name), "status": "done"})

            agent = ToolCallingAgent(
                tools=tools,
                model=model,
                instructions=(
                    "Tu es l'assistant de l'application Gifters (gestion d'idées de cadeaux et de groupes). "
                    "Utilise les outils disponibles pour lister les idées de cadeaux, voir le détail d'une idée, "
                    "ou lister les groupes de l'utilisateur. Réponds de façon concise et utile en français."
                ),
                step_callbacks=[step_callback],
            )

            result = agent.run(task, reset=True)
            content = (
                str(result.output)
                if hasattr(result, "output") and result.output
                else str(result)
            )
            emit("final", {"content": content or "Je n'ai pas de réponse pour le moment."})

    except Exception as e:
        emit("error", {"message": str(e)})
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel


_executor = ThreadPoolExecutor(max_workers=2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _executor.shutdown(wait=False)


app = FastAPI(
    title="Gifters Agent",
    description="Agent SmolAgent connecté au serveur MCP Gifters",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    """
    Envoie les messages au service agent. Le header Authorization (JWT) est transmis
    au serveur MCP pour que les outils s'exécutent au nom de l'utilisateur.
    """
    auth_header = request.headers.get("Authorization", "")
    messages = [m.model_dump() for m in body.messages]
    if not messages:
        raise HTTPException(status_code=422, detail="messages requis")

    task = _build_task_from_messages(messages)
    if not task.strip():
        raise HTTPException(status_code=422, detail="Aucun message utilisateur")

    try:
        content = await asyncio.get_event_loop().run_in_executor(
            _executor, _run_agent_sync, task, auth_header
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur agent : {str(e)}")

    return ChatResponse(message={"role": "assistant", "content": content})


@app.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest):
    """
    Endpoint SSE : streame les étapes de réflexion puis la réponse finale.
    Envoyer les messages dans le body JSON, le JWT dans Authorization: Bearer <token>.
    """
    auth_header = request.headers.get("Authorization", "")
    messages = [m.model_dump() for m in body.messages]

    if not messages:
        raise HTTPException(status_code=422, detail="messages requis")

    task = _build_task_from_messages(messages)
    if not task.strip():
        raise HTTPException(status_code=422, detail="Aucun message utilisateur")

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    _executor.submit(_run_agent_stream, task, auth_header, queue, loop)

    async def generator():
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                if event is None:
                    break
                yield event
        except asyncio.TimeoutError:
            yield {"event": "error", "data": json.dumps({"message": "Timeout : l'agent n'a pas répondu à temps."})}

    return EventSourceResponse(generator())
