"""The glyph layout's footer separates groups of status-bar segments with │ and keeps · inside one.

The bar reads model │ context │ speed │ background work │ session │ mode instead of a dozen glyphs
joined by the same dot; the separators are the same width, so nothing new is trimmed.
"""
from hermes_cli.cli_modern_layout import SEGMENT_GROUPS
from hermes_cli.cli_status_bar_mixin import StatusSegment

WIDE = 400


def _footer(monkeypatch, *, field_set=None, vim="", stash="", yolo=False):
    from cli import HermesCLI

    cli = HermesCLI.__new__(HermesCLI)
    cli._modern_layout, cli._status_bar_visible = True, True
    snapshot = {"model_short": "m", "duration": "6h 43m", "context_percent": 7, "context_length": 1_000_000,
                "context_tokens": 73_200, "avg_latency_label": "9.0s", "avg_velocity_label": "61 t/s",
                "active_background_processes": 1, "git_branch": "main", "prompt_elapsed": "⏲ 41s",
                "idle_since": "✓ 53s"}
    monkeypatch.setattr(HermesCLI, "_get_status_bar_snapshot", lambda self: snapshot)
    monkeypatch.setattr(HermesCLI, "_get_tui_terminal_width", lambda self: WIDE)
    monkeypatch.setattr(HermesCLI, "_get_status_bar_field_set", lambda self: field_set)
    monkeypatch.setattr(HermesCLI, "_is_session_yolo_active", lambda self: yolo)
    monkeypatch.setattr(HermesCLI, "_vim_mode_label", lambda self: vim)
    monkeypatch.setattr(HermesCLI, "_cache_hit_rate", lambda self, snap, precision=1: (97.2, "◎ 97.2%"))
    monkeypatch.setattr("hermes_cli.cli_modern_layout.hint_pairs", lambda cli: [])
    monkeypatch.setattr("hermes_cli.cli_modern_layout._cwd_label", lambda: "~/dotfiles (main)")
    if stash:
        from types import SimpleNamespace
        monkeypatch.setattr(cli, "_prompt_stash", SimpleNamespace(indicator=lambda: stash), raising=False)
    return "".join(text for _, text in cli._get_status_bar_fragments()).strip()


def test_groups_are_split_by_a_bar_and_segments_inside_one_by_a_dot(monkeypatch):
    every = frozenset(SEGMENT_GROUPS) - {"vim", "stash", "cwd"}
    line = _footer(monkeypatch, field_set=every, vim="INSERT")
    assert line == ("☤ m │ 73.2K/1M · [█░░░░░░░░░] 7% · ◎ 97.2% │ ◷ 9.0s · ↑ 61 t/s │ ⚙ 1 │ "
                    "⎇ main · 6h 43m · ⏲ 41s · ✓ 53s │ INSERT"), line


def test_vi_mode_joins_the_mode_group_and_the_extras_start_their_own(monkeypatch):
    line = _footer(monkeypatch, vim="INSERT", stash="📌 2", yolo=True)
    assert "✓ 53s │ ⚠ YOLO │ 📌 2 │ INSERT │ ~/dotfiles (main)" in line, line
    line = _footer(monkeypatch, vim="INSERT", yolo=True)
    assert "⚠ YOLO · INSERT" in line, line


def test_grouping_keeps_the_footer_the_same_width(monkeypatch):
    grouped = _footer(monkeypatch, vim="INSERT")
    assert len(grouped) == len(grouped.replace(" │ ", " · "))
    assert " │ " in grouped


def test_segments_carry_their_field_and_still_compare_as_plain_lists():
    segment = StatusSegment("tps", [("class:status-bar-dim", "↑ 61 t/s")])
    assert segment.field == "tps"
    assert segment == [("class:status-bar-dim", "↑ 61 t/s")]
