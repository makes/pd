import sqlite3

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, TextArea

from .. import db


class ErrorModal(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Close"), ("enter", "close", "Close")]

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Vertical(Label(self.message), id="error-dialog")

    def action_close(self) -> None:
        self.dismiss(None)


class ChangeSceneIdModal(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, conn: sqlite3.Connection, current_scene_id: str):
        super().__init__()
        self.conn = conn
        self.current_scene_id = current_scene_id

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"Move clip from scene {self.current_scene_id} to:"),
            Input(placeholder="scene id", id="scene-id-input"),
            Label("", id="scene-id-error"),
            id="change-scene-id-dialog",
        )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        new_scene_id = event.value.strip().upper()
        if not db.scene_id_exists(self.conn, new_scene_id):
            self.query_one("#scene-id-error", Label).update(f"no such scene: {new_scene_id}")
            return
        self.dismiss(new_scene_id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextInputModal(ModalScreen[str | None]):
    """Single-line prompt used for the '+' action on actor/actress/link list panes."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str, placeholder: str = ""):
        super().__init__()
        self.prompt = prompt
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.prompt),
            Input(placeholder=self.placeholder, id="text-input"),
            id="text-input-dialog",
        )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class EditFieldModal(ModalScreen[str | None]):
    """Edits one scene main-pane field; a plain Input for short fields, a TextArea for
    the multi-line description field."""

    BINDINGS = [("escape", "cancel", "Cancel"), ("ctrl+s", "submit", "Save")]

    def __init__(self, label: str, current_value: str, multiline: bool = False):
        super().__init__()
        self.label = label
        self.current_value = current_value
        self.multiline = multiline

    def compose(self) -> ComposeResult:
        editor: Input | TextArea
        if self.multiline:
            editor = TextArea(self.current_value, id="field-editor")
        else:
            editor = Input(value=self.current_value, id="field-editor")
        yield Vertical(Label(self.label), editor, id="edit-field-dialog")

    def on_mount(self) -> None:
        self.query_one("#field-editor").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_submit(self) -> None:
        editor = self.query_one("#field-editor")
        self.dismiss(editor.text if isinstance(editor, TextArea) else editor.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
