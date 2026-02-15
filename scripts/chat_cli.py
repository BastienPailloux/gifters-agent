#!/usr/bin/env python3
"""
Chat interactif dans le terminal avec l'agent Gifters.
Usage :
  python scripts/chat_cli.py
  JWT=eyJ... python scripts/chat_cli.py
"""
import os
import sys

# Pour importer httpx depuis le projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8000")


def main():
    try:
        import httpx
    except ImportError:
        print("Installez httpx : pip install httpx")
        sys.exit(1)

    jwt = os.environ.get("JWT", "").strip()
    if not jwt:
        jwt = input("Colle ton JWT (token de l'API Gifters) : ").strip()
    if not jwt:
        print("JWT requis. Connexion : POST /api/v1/login sur le backend Rails.")
        sys.exit(1)

    messages = []
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt}",
    }

    print("--- Chat agent Gifters (tape /quit pour quitter) ---\n")

    while True:
        try:
            line = input("Toi : ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line.lower() in ("/quit", "/exit", "/q"):
            print("À bientôt.")
            break

        messages.append({"role": "user", "content": line})

        try:
            r = httpx.post(
                f"{AGENT_URL}/chat",
                json={"messages": messages},
                headers=headers,
                timeout=120.0,
            )
            r.raise_for_status()
            data = r.json()
            content = (data.get("message") or {}).get("content", "")
        except httpx.HTTPStatusError as e:
            content = f"[Erreur HTTP {e.response.status_code}] {e.response.text[:200]}"
        except Exception as e:
            content = f"[Erreur] {e}"

        messages.append({"role": "assistant", "content": content})
        print(f"\nAgent : {content}\n")


if __name__ == "__main__":
    main()
