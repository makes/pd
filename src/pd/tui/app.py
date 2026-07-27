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

    def on_mount(self) -> None:
        self.query_one(ListTab).action_focus_scenes()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        # Widgets can't reliably self-focus from their own on_show: focusing a widget
        # while its pane isn't yet the active one can itself fight the tab switch and
        # revert TabbedContent.active back to the previous tab. Handling focus/reload
        # centrally here, once activation has actually completed, avoids that.
        if event.pane.id == "list-tab":
            list_tab = self.query_one(ListTab)
            list_tab.reload_scenes()
            list_tab.action_focus_scenes()
        elif event.pane.id == "create-tab":
            self.query_one(CreateView).focus()

    def on_unmount(self) -> None:
        self.mpv.close()
        self.conn.close()
