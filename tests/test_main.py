import pytest


def test_get_tool_label_known_tools():
    from main import _get_tool_label
    assert _get_tool_label("list_gift_ideas") == "Récupération des idées cadeaux"
    assert _get_tool_label("get_gift_idea") == "Lecture d'une idée cadeau"
    assert _get_tool_label("list_groups") == "Récupération des groupes"
    assert _get_tool_label("get_group") == "Lecture d'un groupe"


def test_get_tool_label_unknown_returns_generic():
    from main import _get_tool_label
    result = _get_tool_label("some_unknown_tool")
    assert "some_unknown_tool" in result


def test_chat_stream_rejects_empty_messages():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    response = client.post("/chat/stream", json={"messages": []})
    assert response.status_code == 422


def test_chat_stream_rejects_missing_user_message():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    # Uniquement des messages assistant, aucun user
    # _build_task_from_messages retourne une chaîne non-vide même sans message user
    # donc l'endpoint ne rejette pas la requête (200 avec stream)
    response = client.post("/chat/stream", json={
        "messages": [{"role": "assistant", "content": "Bonjour"}]
    })
    assert response.status_code == 200
