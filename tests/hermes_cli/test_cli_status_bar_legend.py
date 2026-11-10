"""The classic CLI's status-bar legend: F1 or ``/statusbar legend`` toggles a panel above the composer.

It names each segment the bar can show under ``display.status_bar.fields`` (opt-in segments only
when listed), and opening it never hides the bar itself.
"""
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import set_app
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.output import DummyOutput

from hermes_cli import cli_status_bar_legend as legend

COLUMNS = 120


def _cli(monkeypatch):
    monkeypatch.setenv("HERMES_DEFER_AGENT_STARTUP", "1")
    from cli import HermesCLI

    cli = HermesCLI(model="fixture", provider="openai-compat", api_key="fixture", base_url="http://127.0.0.1:1/v1")
    cli._tui_init_run_state()
    monkeypatch.setattr(cli, "_get_tui_terminal_width", lambda *args, **kwargs: COLUMNS)
    return cli


def test_default_fields_leave_out_the_opt_in_segments():
    fields = legend.visible_fields(None)
    assert fields[0] == "model" and "cache_hit" in fields and "prompt_elapsed" in fields
    assert "git_branch" not in fields and "total_tokens" not in fields


def test_an_explicit_field_list_shows_only_its_fields_in_bar_order():
    fields = legend.visible_fields(frozenset({"git_branch", "tps", "model"}))
    assert fields == ("model", "tps", "git_branch")


def test_every_row_has_a_sample_and_a_translated_meaning():
    for sample, meaning, field in legend.legend_rows(None):
        assert sample.strip(), field
        assert meaning and not meaning.startswith("cli.status_bar."), f"{field} has no catalog entry"


def test_statusbar_legend_toggles_the_panel_and_leaves_the_bar_visible(monkeypatch):
    cli = _cli(monkeypatch)
    assert cli._status_bar_visible and not legend.is_open(cli)
    cli._cmd_statusbar("/statusbar legend")
    assert legend.is_open(cli) and cli._status_bar_visible
    cli._cmd_statusbar("/statusbar LEGEND")
    assert not legend.is_open(cli) and cli._status_bar_visible
    cli._cmd_statusbar("/statusbar")  # the bare command still hides the bar
    assert not cli._status_bar_visible and not legend.is_open(cli)


def test_f1_toggles_the_panel(monkeypatch):
    cli = _cli(monkeypatch)
    kb = cli._tui_build_key_bindings()
    bindings = [binding for binding in kb.bindings if binding.keys == (Keys.F1,)]
    assert len(bindings) == 1
    bindings[0].handler(None)
    assert legend.is_open(cli)
    bindings[0].handler(None)
    assert not legend.is_open(cli)


def test_the_panel_sits_above_the_composer_and_names_the_visible_segments(monkeypatch):
    from prompt_toolkit.layout import Window
    from prompt_toolkit.layout.controls import BufferControl

    cli = _cli(monkeypatch)
    kb = KeyBindings()
    layout, style = cli._tui_build_layout(kb)
    children = layout.container.children
    widget = cli._status_bar_legend_widget
    assert widget in children
    composer = next(child for child in children
                    if isinstance(child, Window) and isinstance(child.content, BufferControl))
    assert children.index(widget) < children.index(composer)

    legend.toggle(cli)
    with create_pipe_input() as pipe:
        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False,
                          input=pipe, output=DummyOutput())
        with set_app(app):
            text = "".join(fragment[1] for fragment in legend.legend_fragments(cli))
    rows = text.split("\n")
    assert len(rows) == len(legend.visible_fields(cli._get_status_bar_field_set())) + 2  # heading + note
    assert all(len(row) <= COLUMNS for row in rows)
    assert "◎ 48.4%" in text and "cache_hit" in text
