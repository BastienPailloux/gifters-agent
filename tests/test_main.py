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
