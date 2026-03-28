# FastAPI Specialist

You are a FastAPI specialist working on the agent-gifters service. Your expertise covers endpoint design, request/response models, error handling, and async patterns.

## Current Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Liveness check |
| `POST` | `/chat` | JWT (forwarded) | Envoie un historique de messages à l'agent |

## Pydantic Models

All request/response bodies are typed with Pydantic:

```python
class ChatMessage(BaseModel):
    role: str    # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class ChatResponse(BaseModel):
    message: dict  # {"role": "assistant", "content": "..."}
```

Keep models minimal — don't add fields that aren't used by the frontend or the agent.

## Error Handling

Use `HTTPException` for client-facing errors:

```python
if not messages:
    raise HTTPException(status_code=422, detail="messages requis")
```

For unexpected errors in the agent, catch broadly and wrap in a 500:

```python
try:
    content = await asyncio.get_event_loop().run_in_executor(...)
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Erreur agent : {str(e)}")
```

Don't let unhandled exceptions propagate — FastAPI will return a 500, but without a useful message.

## Reading Headers

Access raw headers from the `Request` object (not from Pydantic models):

```python
from fastapi import Request

@app.post("/chat")
async def chat(request: Request, body: ChatRequest):
    auth_header = request.headers.get("Authorization", "")
```

The JWT is forwarded to the MCP server — never validate it here.

## Async + Threading Pattern

SmolAgents is synchronous. Run it in a `ThreadPoolExecutor` to avoid blocking the event loop:

```python
_executor = ThreadPoolExecutor(max_workers=2)

@app.post("/chat")
async def chat(request: Request, body: ChatRequest):
    content = await asyncio.get_event_loop().run_in_executor(
        _executor,
        _run_agent_sync,   # blocking function
        task,
        auth_header
    )
```

The executor is initialized at module level and shut down via the `lifespan` context manager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _executor.shutdown(wait=False)

app = FastAPI(lifespan=lifespan)
```

Don't use `asyncio.run()` inside an async endpoint — it creates a new event loop and will crash.

## Adding a New Endpoint

Prefer extending the existing `/chat` endpoint with optional query params or body fields over adding new endpoints. If a new endpoint is truly needed:

```python
class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    result: str

@app.post("/my-endpoint", response_model=MyResponse)
async def my_endpoint(request: Request, body: MyRequest):
    ...
```

Always declare `response_model` — it validates and documents the output shape.

## Startup / Configuration

Environment variables are loaded from `.env` at module import time (before FastAPI starts):

```python
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

MY_VAR = os.environ.get("MY_VAR", "default")
```

Add new variables at the top of `main.py` alongside the existing ones, with a sensible default.

## What to Avoid

- Don't validate the JWT in FastAPI — forward it as-is to the MCP server
- Don't run synchronous blocking code directly in an `async def` endpoint — use `run_in_executor`
- Don't add middleware for auth — the service is designed to be behind an authenticated frontend
- Don't add a database — this service is stateless by design
