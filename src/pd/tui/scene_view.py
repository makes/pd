import sqlite3

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label
from textual.widgets.option_list import Option

from .. import db
from .browse_list import BrowseList
from .modals import EditFieldModal, ErrorModal, TextInputModal

FIELD_LABELS = {
    "title": "Title",
    "category": "Category",
    "rating": "Rating",
    "imdb_url": "IMDB URL",
    "description": "Description",
}
FIELD_ORDER = ["title", "category", "rating", "imdb_url", "description"]


class SceneView(ModalScreen[None]):
    """Full-screen scene modal: main field pane, actor/actress panes, and a links pane."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("+", "add_item", "Add"),
        ("d", "delete_item", "Delete"),
        ("ctrl+up", "move_link_up", "Move link up"),
        ("ctrl+down", "move_link_down", "Move link down"),
        ("ctrl+k", "move_link_up", "Move link up"),
        ("ctrl+j", "move_link_down", "Move link down"),
    ]

    DEFAULT_CSS = """
    SceneView {
        align: center middle;
    }
    #scene-body {
        width: 100%;
        height: 100%;
    }
    #top-area {
        height: 80%;
    }
    #main-pane {
        width: 50%;
        border: solid $accent;
    }
    #right-column {
        width: 50%;
    }
    #actor-pane, #actress-pane {
        height: 50%;
        border: solid $accent;
    }
    #links-pane {
        height: 20%;
        border: solid $accent;
    }
    """

    def __init__(self, conn: sqlite3.Connection, scene_id: str):
        super().__init__()
        self.conn = conn
        self.scene_id = scene_id

    def compose(self) -> ComposeResult:
        with Vertical(id="scene-body"):
            with Horizontal(id="top-area"):
                with Vertical(id="main-pane"):
                    yield Label(f"Scene {self.scene_id}", id="scene-title-label")
                    yield BrowseList(id="field_list")
                with Vertical(id="right-column"):
                    with Vertical(id="actor-pane"):
                        yield Label("Actors")
                        yield BrowseList(id="actor_list")
                    with Vertical(id="actress-pane"):
                        yield Label("Actresses")
                        yield BrowseList(id="actress_list")
            with Vertical(id="links-pane"):
                yield Label("Links")
                yield BrowseList(id="link_list")

    def on_mount(self) -> None:
        self.reload_fields()
        self.reload_actors()
        self.reload_actresses()
        self.reload_links()
        self.query_one("#field_list", BrowseList).focus()

    def action_close(self) -> None:
        self.dismiss(None)

    # -- reloading ----------------------------------------------------------

    def reload_fields(self) -> None:
        scene = db.get_scene(self.conn, self.scene_id)
        field_list = self.query_one("#field_list", BrowseList)
        previous = field_list.highlighted
        field_list.clear_options()
        for field in FIELD_ORDER:
            value = scene[field]
            display = "" if value is None else str(value)
            field_list.add_option(Option(f"{FIELD_LABELS[field]}: {display}", id=field))
        field_list.highlighted = previous if previous is not None else 0

    def reload_actors(self) -> None:
        actor_list = self.query_one("#actor_list", BrowseList)
        actor_list.clear_options()
        for actor in db.list_scene_actors(self.conn, self.scene_id):
            actor_list.add_option(Option(actor["name"], id=str(actor["actor_id"])))

    def reload_actresses(self) -> None:
        actress_list = self.query_one("#actress_list", BrowseList)
        actress_list.clear_options()
        for actress in db.list_scene_actresses(self.conn, self.scene_id):
            actress_list.add_option(Option(actress["name"], id=str(actress["actress_id"])))

    def reload_links(self, select_index: int | None = None) -> None:
        link_list = self.query_one("#link_list", BrowseList)
        link_list.clear_options()
        links = db.get_scene_links(self.conn, self.scene_id)
        for i, url in enumerate(links):
            link_list.add_option(Option(url, id=str(i)))
        if links:
            link_list.highlighted = select_index if select_index is not None else 0

    # -- field editing --------------------------------------------------------

    def on_option_list_option_selected(self, event: BrowseList.OptionSelected) -> None:
        if event.option_list.id != "field_list":
            return
        field = event.option.id
        scene = db.get_scene(self.conn, self.scene_id)
        current = scene[field]
        self.app.push_screen(
            EditFieldModal(
                FIELD_LABELS[field],
                "" if current is None else str(current),
                multiline=(field == "description"),
            ),
            lambda value, field=field: self._handle_field_edit(field, value),
        )

    def _handle_field_edit(self, field: str, value: str | None) -> None:
        if value is None:
            return
        if field == "rating":
            value = value.strip()
            if value == "":
                db.update_scene_field(self.conn, self.scene_id, "rating", None)
            else:
                try:
                    rating = int(value)
                except ValueError:
                    self.app.push_screen(ErrorModal("rating must be an integer 0-100"))
                    return
                if not 0 <= rating <= 100:
                    self.app.push_screen(ErrorModal("rating must be between 0 and 100"))
                    return
                db.update_scene_field(self.conn, self.scene_id, "rating", rating)
        else:
            db.update_scene_field(self.conn, self.scene_id, field, value or None)
        self.reload_fields()

    # -- add / delete on list panes -----------------------------------------

    def _focused_id(self) -> str | None:
        return self.app.focused.id if self.app.focused is not None else None

    def action_add_item(self) -> None:
        focused = self._focused_id()
        if focused == "actor_list":
            self.app.push_screen(TextInputModal("Add actor (name)"), self._handle_add_actor)
        elif focused == "actress_list":
            self.app.push_screen(TextInputModal("Add actress (name)"), self._handle_add_actress)
        elif focused == "link_list":
            self.app.push_screen(TextInputModal("Add link (URL)"), self._handle_add_link)

    def _handle_add_actor(self, name: str | None) -> None:
        if not name:
            return
        actor_id = db.find_or_create_actor(self.conn, name)
        db.add_scene_actor(self.conn, self.scene_id, actor_id)
        self.reload_actors()

    def _handle_add_actress(self, name: str | None) -> None:
        if not name:
            return
        actress_id = db.find_or_create_actress(self.conn, name)
        db.add_scene_actress(self.conn, self.scene_id, actress_id)
        self.reload_actresses()

    def _handle_add_link(self, url: str | None) -> None:
        if not url:
            return
        links = db.get_scene_links(self.conn, self.scene_id)
        links.append(url)
        db.set_scene_links(self.conn, self.scene_id, links)
        self.reload_links(select_index=len(links) - 1)

    def action_delete_item(self) -> None:
        focused = self._focused_id()
        if focused == "actor_list":
            option = self.query_one("#actor_list", BrowseList).highlighted_option
            if option is not None:
                db.remove_scene_actor(self.conn, self.scene_id, int(option.id))
                self.reload_actors()
        elif focused == "actress_list":
            option = self.query_one("#actress_list", BrowseList).highlighted_option
            if option is not None:
                db.remove_scene_actress(self.conn, self.scene_id, int(option.id))
                self.reload_actresses()
        elif focused == "link_list":
            option = self.query_one("#link_list", BrowseList).highlighted_option
            if option is not None:
                links = db.get_scene_links(self.conn, self.scene_id)
                del links[int(option.id)]
                db.set_scene_links(self.conn, self.scene_id, links)
                self.reload_links()

    # -- link reordering ------------------------------------------------------

    def action_move_link_up(self) -> None:
        self._move_link(-1)

    def action_move_link_down(self) -> None:
        self._move_link(1)

    def _move_link(self, delta: int) -> None:
        if self._focused_id() != "link_list":
            return
        option = self.query_one("#link_list", BrowseList).highlighted_option
        if option is None:
            return
        index = int(option.id)
        new_index = index + delta
        links = db.get_scene_links(self.conn, self.scene_id)
        if not 0 <= new_index < len(links):
            return
        links[index], links[new_index] = links[new_index], links[index]
        db.set_scene_links(self.conn, self.scene_id, links)
        self.reload_links(select_index=new_index)
