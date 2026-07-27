import sqlite3
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from .. import capture, mpv, paths, timefmt
from .scene_view import SceneView

PLACEHOLDER = "--:--.---"


class CreateView(Vertical):
    BINDINGS = [
        ("p", "start_player", "Start player"),
        ("i", "set_start", "Set start"),
        ("o", "set_end", "Set end"),
        ("s", "set_screenshot", "Set screenshot"),
        ("enter", "create_clip", "Create scene"),
    ]

    can_focus = True

    def __init__(self, root: Path, controller: mpv.Controller, conn: sqlite3.Connection):
        super().__init__()
        self.project_paths = paths.ProjectPaths(root)
        self.controller = controller
        self.conn = conn
        self._last_mpv_path: str | None = None
        self.start_ts: float | None = None
        self.end_ts: float | None = None
        self.screenshot_ts: float | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="status")
        yield Static(id="marks")
        yield Static(id="info")

    def on_mount(self) -> None:
        self.set_interval(0.2, self._poll)
        self._refresh_display()

    def _poll(self) -> None:
        if not self.controller.is_running:
            if self._last_mpv_path is not None:
                self._last_mpv_path = None
                self._reset_marks()
            self._refresh_display()
            return

        current_path = self.controller.connection.get_property("path")
        if current_path != self._last_mpv_path:
            self._last_mpv_path = current_path
            self._reset_marks()

        self._refresh_display()

    def _reset_marks(self) -> None:
        self.start_ts = None
        self.end_ts = None
        self.screenshot_ts = None

    def _current_time_pos(self) -> float | None:
        conn = self.controller.connection
        if conn is None:
            return None
        pos = conn.get_property("time-pos")
        return float(pos) if pos is not None else None

    def _refresh_display(self) -> None:
        status = self.query_one("#status", Static)
        marks = self.query_one("#marks", Static)
        info = self.query_one("#info", Static)

        if not self.controller.is_running:
            status.update("Press 'p' to start player.")
            marks.update("")
            info.update("")
            return

        path = self.controller.connection.get_property("path")
        time_pos = self._current_time_pos()

        filename = Path(path).name if path else "(no file open)"
        time_str = timefmt.format_seconds(time_pos) if time_pos is not None else PLACEHOLDER
        status.update(f"{filename}   {time_str}")

        def fmt(ts: float | None) -> str:
            return timefmt.format_seconds(ts) if ts is not None else PLACEHOLDER

        marks.update(
            f"start: {fmt(self.start_ts)}   "
            f"end: {fmt(self.end_ts)}   "
            f"screenshot: {fmt(self.screenshot_ts)}"
        )

        info.update(self._info_text())

    def _info_text(self) -> str:
        lines = []
        if self.start_ts is not None and self.end_ts is not None:
            duration = self.end_ts - self.start_ts
            if duration > 0:
                lines.append(f"Duration: {timefmt.format_seconds(duration)}")
            else:
                lines.append("Duration: end must be after start")

        if self.start_ts is not None and self.end_ts is not None and self.screenshot_ts is not None:
            error = self._validation_error()
            lines.append(error if error else "Ready — press Enter to create scene.")

        return "\n".join(lines)

    def _validation_error(self) -> str | None:
        if not self.start_ts < self.end_ts:
            return "start must be before end"
        if not self.start_ts <= self.screenshot_ts <= self.end_ts:
            return "screenshot must be between start and end"
        return None

    def action_start_player(self) -> None:
        if self.controller.is_running:
            return
        try:
            self.controller.ensure_running()
        except mpv.MpvError as e:
            self.app.bell()
            self.query_one("#status", Static).update(f"error: {e}")
            return
        self._refresh_display()

    def action_set_start(self) -> None:
        self._set_mark("start_ts")

    def action_set_end(self) -> None:
        self._set_mark("end_ts")

    def action_set_screenshot(self) -> None:
        self._set_mark("screenshot_ts")

    def _set_mark(self, attr: str) -> None:
        pos = self._current_time_pos()
        if pos is None:
            return
        setattr(self, attr, pos)
        self._refresh_display()

    def action_create_clip(self) -> None:
        if self.start_ts is None or self.end_ts is None or self.screenshot_ts is None:
            return

        error = self._validation_error()
        if error:
            self._show_error(error)
            return

        source_path = self.controller.connection.get_property("path")
        if not source_path:
            return

        new_scene_id, clip_id = capture.create_scene_and_clip(
            self.conn,
            self.project_paths,
            Path(source_path),
            start_ts=str(self.start_ts),
            end_ts=str(self.end_ts),
            screenshot_ts=str(self.screenshot_ts),
        )
        self._reset_marks()
        self._refresh_display()
        self.query_one("#status", Static).update(f"Created scene {new_scene_id} / clip {clip_id}")
        self.app.push_screen(SceneView(self.conn, new_scene_id))

    def _show_error(self, message: str) -> None:
        self.app.bell()
        self.query_one("#info", Static).update(f"error: {message}")
