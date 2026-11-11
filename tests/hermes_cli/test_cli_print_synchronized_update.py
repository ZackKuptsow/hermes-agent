"""A print above the running classic CLI reaches the terminal as one synchronized update.

``_cprint`` erases the chrome, prints the line and repaints the chrome. ``_coalesced_output``
sends that as one write, but the pseudo-terminal still hands it over in pieces (1 KB at a time
on macOS), and a terminal that paints between two of them shows the chrome erased: the prompt
bar blinks on every streamed line. Wrapped in a DEC 2026 synchronized update, the terminal keeps
the previous frame until the update ends. Only where the terminal is known to support it, and
never inside tmux or Zellij (#66490).
"""
import asyncio
import threading

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.output.vt100 import Vt100_Output

import cli

BEGIN, END = "\x1b[?2026h", "\x1b[?2026l"
ERASE_DOWN = "\x1b[J"
TERMINAL_ENVIRONMENT = ("TERM", "TERM_PROGRAM", "TMUX", "ZELLIJ", "KITTY_WINDOW_ID", "ZED_TERM", "WT_SESSION",
                        "VTE_VERSION")


class _Tty:
    """What the terminal receives: one entry per write."""
    encoding = "utf-8"

    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    def flush(self):
        pass

    def isatty(self):
        return True

    def fileno(self):
        return 1


def _print_above_running_app(tty) -> None:
    """Run a non-full-screen app with a chrome row; ``_cprint`` a line from another thread, as the
    agent's streaming does; return once the chrome is painted again."""
    output = Vt100_Output(tty, lambda: Size(rows=24, columns=80), term="xterm-256color", enable_cpr=False)

    async def run():
        with create_pipe_input() as pipe:
            app = Application(layout=Layout(Window(FormattedTextControl("STATUS BAR"), height=1)),
                              full_screen=False, input=pipe, output=output)
            renders = asyncio.Queue()
            app.after_render += lambda _: renders.put_nowait(None)
            task = asyncio.create_task(app.run_async())
            await asyncio.wait_for(renders.get(), 5)
            threading.Thread(target=cli._cprint, args=("printed line",)).start()
            while not any("printed line" in write for write in tty.writes):
                await asyncio.wait_for(renders.get(), 5)
            app.exit()
            await asyncio.wait_for(task, 3)

    asyncio.run(run())


@pytest.fixture(autouse=True)
def no_output_history():
    cli._configure_output_history(False, 200)
    yield
    cli._configure_output_history(True, 200)


@pytest.mark.parametrize("environment, synchronized", [
    pytest.param({"TERM_PROGRAM": "ghostty"}, True, id="ghostty"),
    pytest.param({"TERM": "xterm-kitty"}, True, id="kitty"),
    pytest.param({"TERM": "xterm-256color", "VTE_VERSION": "7600"}, True, id="vte"),
    pytest.param({"TERM_PROGRAM": "ghostty", "TMUX": "/tmp/tmux-501/default,1,0"}, False, id="tmux-in-ghostty"),
    pytest.param({"TERM_PROGRAM": "WezTerm", "ZELLIJ": "0"}, False, id="zellij-in-wezterm"),
    pytest.param({"TERM": "xterm-256color"}, False, id="unknown-terminal"),
])
def test_a_print_and_the_chrome_repaint_arrive_as_one_synchronized_update(monkeypatch, environment, synchronized):
    for name in TERMINAL_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    tty = _Tty()

    _print_above_running_app(tty)

    painted = [write for write in tty.writes if "printed line" in write]
    assert len(painted) == 1, "the erase, the line and the repaint are one write"
    write = painted[0]
    assert ERASE_DOWN in write and write.rindex("STATUS BAR") > write.index("printed line"), \
        "the write erases the chrome, prints the line, then paints the chrome again"
    if synchronized:
        assert write.startswith(BEGIN) and write.endswith(END), "the terminal holds its screen for all of it"
    else:
        assert BEGIN not in "".join(tty.writes) and END not in "".join(tty.writes)
