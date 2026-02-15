#!/usr/bin/env bash
# Test rapide de l'agent : health + chat (avec JWT)
# Usage :
#   ./scripts/test_agent.sh                    # health seulement
#   ./scripts/test_agent.sh <JWT>               # health + 1 message
#   export JWT="eyJ..."; ./scripts/test_agent.sh # idem avec JWT en env

set -e
AGENT_URL="${AGENT_URL:-http://localhost:8000}"
JWT="${JWT:-$1}"

echo "=== Agent: $AGENT_URL ==="
echo ""

echo "1. Health..."
curl -s "$AGENT_URL/health" | head -c 200
echo ""
echo ""

if [ -z "$JWT" ]; then
  echo "2. Chat: pas de JWT fourni."
  echo "   Pour tester le chat :"
  echo "   - Obtenez un JWT (login API Rails : POST /api/v1/login avec email/password)"
  echo "   - Puis :  JWT='eyJ...' $0"
  echo "   - Ou :    $0 'eyJ...'"
  exit 0
fi

echo "2. Chat (POST /chat avec JWT)..."
curl -s -X POST "$AGENT_URL/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"messages":[{"role":"user","content":"Liste mes groupes"}]}' | head -c 500
echo ""
echo ""
echo "Done."
