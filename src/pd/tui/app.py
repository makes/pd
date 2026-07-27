from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import TabbedContent, TabPane

from .. import db, mpv, paths
from .create_view import CreateView
from .list_view import ListTab


class PdApp(App):
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.mpv = mpv.Controller()
        self.conn = db.connect(paths.ProjectPaths(root).db)

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("List", id="list-tab"):
                yield ListTab(self.mpv, self.conn)
            with TabPane("Create", id="create-tab"):
                yield CreateView(self.root, self.mpv, self.conn)

    def on_unmount(self) -> None:
        self.mpv.close()
        self.conn.close()
