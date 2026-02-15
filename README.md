# Agent Gifters (SmolAgent + MCP)

Service agent qui expose un chat utilisant le serveur MCP Gifters (idées de cadeaux, groupes) et un modèle via l’**API Inference Hugging Face** (InferenceClientModel, pas de téléchargement local).

## Prérequis

- Python 3.10+
- Serveur MCP accessible (Rails sur `mcp.lvh.me:3000` en local ou `https://mcp.gifters.fr` en prod)
- **Token Hugging Face** avec accès aux [Inference Providers](https://huggingface.co/settings/inference-providers) (obligatoire pour l’API serverless)

## Installation

```bash
./setup.sh
source .venv/bin/activate   # ou .venv\Scripts\activate sur Windows
```

## Démarrer

1. **Lancer le serveur MCP** (dans un autre terminal)  
   Depuis la racine du projet Gifters :
   ```bash
   cd backend-gifters && bundle exec rails s
   ```
   Le MCP est alors disponible sur `http://mcp.lvh.me:3000` (utilisez cette URL en local dans `.env`).

2. **Lancer l’agent**
   ```bash
   source .venv/bin/activate
   uvicorn main:app --reload --port 8000
   ```

3. **Tester**
   - Health : `curl http://localhost:8000/health`
   - Chat : il faut un JWT (voir ci-dessous).

## Tester le chat

L’agent attend un **JWT** (même token que l’app) dans le header `Authorization: Bearer <token>`, qu’il transmet au serveur MCP.

### 1. Obtenir un JWT

Connexion via l’API Rails :

```bash
curl -s -X POST http://localhost:3000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"user":{"email":"ton@email.com","password":"ton_mot_de_passe"}}'
```

Dans la réponse, récupère le champ `token` (ou `data.token`).

### 2. Appeler l’agent

```bash
export JWT="eyJ..."   # le token obtenu ci-dessus

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"messages":[{"role":"user","content":"Liste mes groupes"}]}'
```

Ou avec le script :

```bash
./scripts/test_agent.sh "$JWT"
```

### Exemples de messages

- « Liste mes groupes »
- « Quelles sont mes idées de cadeaux ? »
- « Donne-moi le détail de l’idée de cadeau numéro 1 »

## Variables d’environnement (.env)

| Variable         | Description                                          | Défaut                          |
|------------------|------------------------------------------------------|----------------------------------|
| `MCP_SERVER_URL` | URL du serveur MCP                                   | `http://mcp.lvh.me:3000`        |
| `HF_TOKEN`       | Token Hugging Face (obligatoire pour l’API Inference) | -                               |
| `MODEL_ID`       | Modèle HF utilisé via l’API Inference (function calling) | `mistralai/Mistral-7B-Instruct-v0.2` (ou `Qwen/Qwen3-8B`) |
| `HF_PROVIDER`    | Provider optionnel (ex. `together`, `fireworks`, `fal`) | auto |

Mistral : seul le **v0.2** est encore supporté sur les Inference Providers ; le v0.3 renvoie *410 Gone*. Autre option : `Qwen/Qwen3-8B`.

## Intégration avec l’app

Aujourd’hui le **frontend** appelle `POST /api/v1/chat` sur le **backend Rails** ; celui-ci utilise encore le service Ruby (OpenAI + MCP). Pour faire répondre l’**agent Python** depuis l’app, il faudrait que Rails appelle ce service (variable `AGENT_SERVICE_URL`) au lieu de `ChatWithMcpService`.
