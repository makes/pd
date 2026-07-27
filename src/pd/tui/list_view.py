import sqlite3

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label
from textual.widgets.option_list import Option

from .. import db, mpv, paths
from .browse_list import BrowseList
from .modals import ChangeSceneIdModal, ErrorModal
from .scene_view import SceneView


def _scene_label(scene: sqlite3.Row) -> str:
    return f"{scene['scene_id']}  {scene['title'] or '(untitled)'}"


def _clip_label(clip: sqlite3.Row) -> str:
    marker = "*" if clip["active"] else " "
    return f"{marker} {clip['clip_id']}  {clip['start_ts']}-{clip['end_ts']}"


class ListTab(Horizontal):
    BINDINGS = [
        ("h", "focus_scenes", "Focus scenes"),
        ("left", "focus_scenes", "Focus scenes"),
        ("l", "focus_clips", "Focus clips"),
        ("right", "focus_clips", "Focus clips"),
        ("p", "play", "Play"),
        ("i", "change_scene_id", "Change scene id"),
    ]

    def __init__(self, controller: mpv.Controller, conn: sqlite3.Connection):
        super().__init__()
        self.controller = controller
        self.conn = conn

    def compose(self) -> ComposeResult:
        with Vertical(id="scenes-pane"):
            yield Label("Scenes")
            yield BrowseList(id="scene_list")
        with Vertical(id="clips-pane"):
            yield Label("Clips")
            yield BrowseList(id="clip_list")

    def on_mount(self) -> None:
        self.reload_scenes()

    def reload_scenes(self, select_scene_id: str | None = None) -> None:
        scene_list = self.query_one("#scene_list", BrowseList)
        scene_list.clear_options()
        scenes = db.list_scenes(self.conn)
        for scene in scenes:
            scene_list.add_option(Option(_scene_label(scene), id=scene["scene_id"]))

        if not scenes:
            self.query_one("#clip_list", BrowseList).clear_options()
            return

        index = 0
        if select_scene_id is not None:
            for i, scene in enumerate(scenes):
                if scene["scene_id"] == select_scene_id:
                    index = i
                    break
        scene_list.highlighted = index
        self.reload_clips(scenes[index]["scene_id"])

    def reload_clips(self, scene_id: str) -> None:
        clip_list = self.query_one("#clip_list", BrowseList)
        clip_list.clear_options()
        clips = db.list_clips_for_scene(self.conn, scene_id)
        for clip in clips:
            clip_list.add_option(Option(_clip_label(clip), id=clip["clip_id"]))
        if clips:
            clip_list.highlighted = 0

    def action_focus_scenes(self) -> None:
        self.query_one("#scene_list", BrowseList).focus()

    def action_focus_clips(self) -> None:
        self.query_one("#clip_list", BrowseList).focus()

    def on_option_list_option_highlighted(self, event: BrowseList.OptionHighlighted) -> None:
        if event.option_list.id == "scene_list":
            self.reload_clips(event.option.id)

    def on_option_list_option_selected(self, event: BrowseList.OptionSelected) -> None:
        if event.option_list.id == "scene_list":
            self.app.push_screen(SceneView(self.conn, event.option.id))
        elif event.option_list.id == "clip_list":
            db.toggle_clip_active(self.conn, event.option.id)
            scene_id = self._current_scene_id()
            if scene_id is not None:
                self.reload_clips(scene_id)

    def _current_scene_id(self) -> str | None:
        option = self.query_one("#scene_list", BrowseList).highlighted_option
        return option.id if option is not None else None

    def _current_clip_id(self) -> str | None:
        option = self.query_one("#clip_list", BrowseList).highlighted_option
        return option.id if option is not None else None

    def action_play(self) -> None:
        if self.app.focused is not None and self.app.focused.id == "clip_list":
            clip_id = self._current_clip_id()
            clip_row = db.get_clip(self.conn, clip_id) if clip_id else None
        else:
            scene_id = self._current_scene_id()
            clip_row = db.get_latest_active_clip(self.conn, scene_id) if scene_id else None

        if clip_row is None:
            self.app.push_screen(ErrorModal("No active clip to play."))
            return

        source_path = paths.clip_source_path(clip_row)
        try:
            connection = self.controller.ensure_running()
        except mpv.MpvError as e:
            self.app.push_screen(ErrorModal(f"mpv error: {e}"))
            return
        connection.loadfile(str(source_path), start=float(clip_row["start_ts"]))

    def action_change_scene_id(self) -> None:
        if self.app.focused is None or self.app.focused.id != "clip_list":
            return
        clip_id = self._current_clip_id()
        if clip_id is None:
            return
        current_scene_id = self._current_scene_id()

        def handle_result(new_scene_id: str | None) -> None:
            if new_scene_id is None:
                return
            db.update_clip_scene_id(self.conn, clip_id, new_scene_id)
            self.reload_scenes(select_scene_id=current_scene_id)

        self.app.push_screen(ChangeSceneIdModal(self.conn, current_scene_id), handle_result)
