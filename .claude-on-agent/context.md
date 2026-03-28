# ClaudeOnAgent Context

This is the AI agent service for Gifters — a FastAPI server that exposes a `/chat` endpoint backed by a SmolAgents `ToolCallingAgent` connected to the Gifters MCP server (Rails backend).

## Stack

- **Python 3.11+**
- **FastAPI** — HTTP API (single endpoint `POST /chat`)
- **SmolAgents** (`smolagents[mcp,transformers]`) — agent framework
- **Hugging Face Inference API** — serverless LLM (no local model download)
- **python-dotenv** — `.env` file loading

## Entry Point

Everything lives in a single file: `main.py`.

## Request Flow

```
Frontend → POST /chat (JWT in Authorization header)
  → FastAPI extracts auth header
  → _build_task_from_messages() → formats message history as a task string
  → asyncio run_in_executor → _run_agent_sync() (blocking, in ThreadPoolExecutor)
      → ToolCollection.from_mcp() → connects to MCP server with JWT
      → InferenceClientModel → Hugging Face Inference API
      → ToolCallingAgent.run(task) → agentic loop (tool calls to MCP)
  → ChatResponse { role: "assistant", content: "..." }
```

## Environment Variables

```
MCP_SERVER_URL=http://mcp.lvh.me:3000    # URL du serveur MCP Rails
HF_TOKEN=hf_...                          # Token Hugging Face (requis)
MODEL_ID=mistralai/Mistral-7B-Instruct-v0.2  # Modèle HF (doit supporter tool calling)
HF_PROVIDER=                             # Provider optionnel (together, fireworks…)
```

Loaded from `.env` in the project root via `python-dotenv`.

## Key Design Decisions

- The agent runs **synchronously** in a `ThreadPoolExecutor` (SmolAgents is not async-native); FastAPI delegates via `run_in_executor`
- The JWT from the incoming request is forwarded **as-is** to the MCP server via the `Authorization` header, so tools execute in the user's security context
- The conversation history is **flattened** to a single task string (`_build_task_from_messages`) — SmolAgents doesn't natively support multi-turn chat memory
- A max of 10 turns of conversation history is kept to avoid context overflow

## Development Guidelines

- Keep the service focused: one file, one endpoint, one agent
- Don't add new endpoints unless strictly necessary — the `/health` and `/chat` pair is intentional
- Don't download models locally — always use `InferenceClientModel` (serverless HF API)
- Don't add auth logic here — auth is handled by forwarding the JWT to the MCP server
- Write tests for pure functions (`_build_task_from_messages`); mock SmolAgents for integration tests
