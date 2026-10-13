from collections import deque

from src.widgets.history_panel import HistoryPanel


def test_search_input_debounces(qapp):
    panel = HistoryPanel(None)
    panel.search_input.setText("search me")
    assert panel._current_search_text == "search me"
    assert panel._search_debounce_timer.isActive()


def test_search_matches_tags_and_prompt(qapp):
    panel = HistoryPanel(None)
    panel.history = deque(
        [
            {"task_id": "a", "prompt": "forest"},
            {"task_id": "b", "prompt": "city", "tags": "forest"},
            {"task_id": "c", "prompt": "sea"},
        ]
    )
    output = []
    panel._update_grid = lambda records: output.extend(records)
    panel._current_search_text = "forest"
    panel._apply_filters()
    assert {r["task_id"] for r in output} == {"a", "b"}


def test_platform_filter_excludes_other_sources(qapp):
    panel = HistoryPanel(None)
    panel.history = deque([{"task_id": "a", "platform_id": "openai"}, {"task_id": "b", "platform_id": "gemini"}])
    output = []
    panel._update_grid = lambda records: output.extend(records)
    panel._current_platform = "gemini"
    panel._apply_filters()
    assert [r["task_id"] for r in output] == ["b"]


def test_time_sort_handles_iso_strings(qapp):
    panel = HistoryPanel(None)
    panel.history = deque(
        [
            {"task_id": "new", "created_at": "2026-10-12T12:00:00"},
            {"task_id": "old", "created_at": "2026-10-11T12:00:00"},
        ]
    )
    output = []
    panel._update_grid = lambda records: output.extend(records)
    panel._current_sort = "时间正序"
    panel._apply_filters()
    assert [r["task_id"] for r in output] == ["old", "new"]
