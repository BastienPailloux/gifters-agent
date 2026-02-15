#!/usr/bin/env bash
# Setup agent-gifters : venv, dépendances, .env
# Usage : ./setup.sh   ou   bash setup.sh

set -e
cd "$(dirname "$0")"

echo "=== Setup agent-gifters ==="

# Python 3.10+ recommandé
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
  echo "Erreur : $PYTHON introuvable. Installez Python 3.10+ (pyenv, brew, etc.)."
  exit 1
fi

VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
if [ -z "$VERSION" ]; then
  echo "Impossible de détecter la version de Python."
  exit 1
fi
echo "  Python : $PYTHON ($VERSION)"

# Venv
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "  Création du venv dans $VENV_DIR..."
  "$PYTHON" -m venv "$VENV_DIR"
else
  echo "  Venv trouvé : $VENV_DIR"
fi

# Activation selon l'OS
if [ -f "$VENV_DIR/bin/activate" ]; then
  source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
  source "$VENV_DIR/Scripts/activate"
else
  echo "  Erreur : activate introuvable dans $VENV_DIR"
  exit 1
fi

# Dépendances
echo "  Installation des dépendances (pip install -r requirements.txt)..."
pip install --upgrade pip -q
pip install -r requirements.txt

# .env
if [ ! -f .env ] && [ -f .env.example ]; then
  echo "  Copie de .env.example vers .env"
  cp .env.example .env
  echo "  → Éditez .env si besoin (MCP_SERVER_URL, HF_TOKEN)."
else
  if [ ! -f .env ]; then
    echo "  Pas de .env.example trouvé ; vous pouvez créer un .env avec MCP_SERVER_URL, etc."
  fi
fi

# Vérification rapide
echo ""
echo "  Vérification de l'import..."
python -c "
from fastapi import FastAPI
from smolagents import ToolCallingAgent
from smolagents import TransformersModel
print('    OK (FastAPI, smolagents, TransformersModel)')
" 2>/dev/null || {
  echo "    Import échoué (normal si dépendances lourdes pas encore résolues)."
}

echo ""
echo "=== Setup terminé ==="
echo ""
echo "Pour démarrer :"
echo "  1. Activer le venv :  source $VENV_DIR/bin/activate   (ou .venv\\\\Scripts\\\\activate sur Windows)"
echo "  2. Lancer le serveur MCP (Rails) sur mcp.lvh.me:3000 ou définir MCP_SERVER_URL dans .env"
echo "  3. Lancer l'agent :  uvicorn main:app --reload --port 8000"
echo ""
echo "Variables utiles (dans .env ou export) :"
echo "  MCP_SERVER_URL  → URL du serveur MCP (défaut: http://mcp.lvh.me:3000)"
echo "  HF_TOKEN       → optionnel (modèles gated)"
echo "  MODEL_ID       → optionnel (défaut: mistralai/Mistral-7B-Instruct-v0.3)"
echo ""
