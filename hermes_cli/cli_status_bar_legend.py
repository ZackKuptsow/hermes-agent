"""Status-bar legend panel for the classic CLI: ``F1`` or ``/statusbar legend`` toggles it.

The bar stays compact (``◎ 48%``, ``◷ 4.8s``, ``↑ 55 t/s``, ``⏲ 12s``); the legend opens above the
composer and names each segment the bar can show under the current ``display.status_bar.fields``,
with what it means and the field name that hides it. It stays open until toggled again, so the
glyphs can be read against the live bar. The meanings and samples follow #140687's
``/statusbar legend`` table.
"""
from __future__ import annotations

import time

from agent.i18n import t

# Bar order; the meaning of each is ``cli.status_bar.legend_<field>``.
LEGEND_FIELDS = (
    "model", "context_detail", "context_pct", "cache_hit", "latency", "tps", "compressions",
    "bg_tasks", "bg_processes", "bg_subagents", "goal", "git_branch", "duration", "prompt_elapsed",
    "idle_since", "focus", "yolo", "total_tokens", "stash", "battery", "title")
# Shown only when ``display.status_bar.fields`` names them (``_status_bar_segments``).
OPT_IN_FIELDS = frozenset({"git_branch", "total_tokens"})
_INDENT = "  "
_COLUMN_GAP = "  "


def _samples() -> dict[str, str]:
    """One example of each segment in the form the bar paints it (timers through the bar's own
    formatters, so the legend shows the same glyphs)."""
    from hermes_cli.cli_status_bar_mixin import CLIStatusBarMixin as bar
    from hermes_cli.focus_view import focus_statusbar_segment
    timers = f"{bar._format_prompt_elapsed(None, 12.0, live=True)} · {bar._format_prompt_elapsed(None, 63.0)}"
    return {
        "model": "☤ claude-sonnet-4", "context_detail": "~15.7K/1M", "context_pct": "[██░░░░░░░░] 21%",
        "cache_hit": "◎ 48.4%", "latency": "◷ " + t("cli.status_bar.latency_label", value="4.8"),
        "tps": "↑ " + t("cli.status_bar.velocity_label", value="55"), "compressions": "🗜️ 2",
        "bg_tasks": "▶ 1", "bg_processes": "⚙ 1", "bg_subagents": "⛓ 2",
        "goal": t("cli.status_bar.goal_turns", used=3, max=20), "git_branch": "⎇ main", "duration": "2m",
        "prompt_elapsed": timers, "idle_since": bar._format_idle_since(time.time() - 240, turn_live=False),
        "focus": focus_statusbar_segment(True), "yolo": t("cli.status_bar.yolo_badge"),
        "total_tokens": "Σ1.2M", "stash": "📌 2", "battery": "🔋 82%", "title": "─ weekly-digest"}


def visible_fields(field_set: frozenset | None) -> tuple[str, ...]:
    """Fields the bar can show: every default one without a list, else the listed ones, in bar order."""
    if field_set is None:
        return tuple(field for field in LEGEND_FIELDS if field not in OPT_IN_FIELDS)
    return tuple(field for field in LEGEND_FIELDS if field in field_set)


def legend_rows(field_set: frozenset | None) -> list[tuple[str, str, str]]:
    """``(sample, meaning, field)`` for every segment the bar can show, in bar order."""
    samples = _samples()
    return [(samples[field], t(f"cli.status_bar.legend_{field}"), field) for field in visible_fields(field_set)]


def is_open(cli) -> bool:
    return bool(getattr(cli, "_status_bar_legend_open", False))


def toggle(cli) -> None:
    cli._status_bar_legend_open = not is_open(cli)
    invalidate = getattr(cli, "_invalidate", None)
    if callable(invalidate):
        invalidate()


def legend_fragments(cli) -> list:
    """The panel: a heading rule, one row per segment, then where the fields are configured."""
    from hermes_cli.cli_modern_layout import _skin_hex, rule_style
    width = max(10, cli._get_tui_terminal_width())
    display_width, trim = cli._status_bar_display_width, cli._trim_status_bar_text
    strong, dim = "class:status-bar-strong bg:default", "class:status-bar-dim bg:default"
    rule, accent = rule_style(), f"fg:{_skin_hex('ui_accent', '#FFBF00')} bold"

    heading, hint = t("cli.status_bar.legend_heading"), t("cli.status_bar.legend_close_hint")
    used = display_width(f"── {heading} · {hint} ")
    lines = [[(rule, "── "), (accent, heading), (rule, " · "), (dim, hint), (rule, " " + "─" * max(0, width - used))]]
    rows = legend_rows(cli._get_status_bar_field_set())
    sample_width = max((display_width(sample) for sample, _, _ in rows), default=0)
    field_width = max((len(field) for _, _, field in rows), default=0)
    for sample, meaning, field in rows:  # meaning last: the only column of uneven length
        padded = sample + " " * (sample_width - display_width(sample))
        lines.append([("", _INDENT), (strong, padded), ("", _COLUMN_GAP), (dim, field.ljust(field_width)),
                      ("", _COLUMN_GAP + meaning)])
    lines.append([(dim, _INDENT + t("cli.status_bar.legend_note"))])

    fragments: list = []
    for line in lines:
        if fragments:
            fragments.append(("", "\n"))
        if sum(display_width(text) for _, text in line) <= width:
            fragments.extend(line)
        else:  # a narrow terminal keeps each row on one line rather than wrapping the panel
            fragments.append((line[0][0] if len(line) == 1 else "", trim("".join(text for _, text in line), width)))
    return fragments


def legend_widget(cli):
    """Hidden until toggled; sits above the composer like the stash browse panel."""
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.layout import ConditionalContainer, FormattedTextControl, Window
    return ConditionalContainer(Window(FormattedTextControl(lambda: legend_fragments(cli)), wrap_lines=False),
                                filter=Condition(lambda: is_open(cli)))
