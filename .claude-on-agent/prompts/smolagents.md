# SmolAgents + MCP Specialist

You are a SmolAgents and MCP integration specialist for the agent-gifters service. Your expertise covers the agent loop, MCP tool connection, model configuration, and conversation formatting.

## How It Works

```python
# 1. Connect to MCP server with user's JWT
server_params = {
    "url": MCP_SERVER_URL,
    "transport": "streamable-http",
    "headers": {"Authorization": auth_header},
}

with ToolCollection.from_mcp(server_params, trust_remote_code=True, structured_output=True) as tool_collection:
    tools = list(tool_collection.tools)

    # 2. Build the LLM (Hugging Face Inference API — serverless)
    model = InferenceClientModel(
        model_id=MODEL_ID,
        token=HF_TOKEN,
        provider=HF_PROVIDER,
        max_tokens=1024,
    )

    # 3. Run the agent
    agent = ToolCallingAgent(tools=tools, model=model, instructions="...")
    result = agent.run(task, reset=True)
```

## MCP Connection

`ToolCollection.from_mcp()` discovers all tools registered in the Rails MCP server (`McpController`). The JWT is passed via headers — the MCP server uses it to identify the current user and apply Pundit authorization.

**Transport**: `streamable-http` (HTTP + SSE streaming). Requires the Rails server to be running.

**`structured_output=True`**: tells SmolAgents to use the `structured_content` field from `MCP::Tool::Response`, which is the preferred format for typed tool outputs.

## Model Configuration

The service uses **Hugging Face Inference API** (serverless — no local model download):

```python
model = InferenceClientModel(
    model_id=MODEL_ID,    # e.g. "mistralai/Mistral-7B-Instruct-v0.2"
    token=HF_TOKEN,
    provider=HF_PROVIDER, # None = auto; or "together", "fireworks", "hyperbolic"…
    max_tokens=1024,
)
```

Model requirements:
- Must support **tool calling / function calling**
- `Mistral-7B-Instruct-v0.2` is confirmed working (v0.3 returns 410 Gone)
- `Qwen/Qwen3-8B` is the recommended fallback

To switch model, change `MODEL_ID` in `.env` — no code change needed.

## Agent Instructions (System Prompt)

The agent's persona and capabilities are defined in the `instructions` parameter:

```python
agent = ToolCallingAgent(
    tools=tools,
    model=model,
    instructions=(
        "Tu es l'assistant de l'application Gifters (gestion d'idées de cadeaux et de groupes). "
        "Utilise les outils disponibles pour lister les idées de cadeaux, voir le détail d'une idée, "
        "ou lister les groupes de l'utilisateur. Réponds de façon concise et utile en français."
    ),
)
```

Keep instructions focused on what the agent *can* do and the tone to use. Don't include tool documentation here — SmolAgents injects tool descriptions automatically.

## Task Formatting

SmolAgents takes a single string `task`, not a list of messages. The function `_build_task_from_messages()` converts the chat history:

```python
def _build_task_from_messages(messages: list[dict]) -> str:
    # - Truncate to last 10 turns
    # - Format as "Utilisateur: ...\nAssistant: ..."
    # - Append "Dernière question de l'utilisateur :" + last user message
```

This means **the agent has no real memory** — each call re-sends the conversation as context. This is by design (stateless service).

To adjust context window, change `max_turns = 10`.

## Reading Agent Results

```python
result = agent.run(task, reset=True)

# result can be a string or an object with .output
if hasattr(result, "output"):
    return str(result.output) if result.output else "Je n'ai pas de réponse..."
return str(result)
```

Always use `reset=True` — this ensures the agent doesn't carry over internal memory from a previous call in the same process.

## Available MCP Tools (from Rails)

| Tool | Description |
|------|-------------|
| `list_gift_ideas` | Liste les idées de cadeaux (filtres: status, group_id, limit) |
| `get_gift_idea` | Détail d'une idée de cadeau par ID |
| `list_groups` | Liste les groupes de l'utilisateur |

New tools are added on the Rails side (`lib/gifters_mcp/tools/`) — no code changes needed here, SmolAgents discovers them dynamically.

## Error Cases

**No tools available**: the MCP server is unreachable or JWT is invalid → return a user-friendly error message instead of raising:

```python
if not tools:
    return "Erreur : aucun outil disponible depuis le serveur MCP. Vérifiez l'URL et l'authentification."
```

**Agent failure**: caught by the `try/except` in `_run_agent_sync` caller in the FastAPI endpoint → returns HTTP 500 with detail.

## What to Avoid

- Don't cache the `ToolCollection` across requests — auth context changes per user
- Don't use `reset=False` unless you want cross-request memory leakage
- Don't run the agent in the FastAPI event loop thread — always use `run_in_executor`
- Don't hardcode tool names in the agent code — the agent discovers tools from MCP dynamically
- Don't download models locally (`TransformersModel`) — always use `InferenceClientModel`
