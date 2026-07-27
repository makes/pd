from pathlib import Path

DB_FILENAME = "pd.sqlite"


class ProjectPaths:
    def __init__(self, root: Path):
        self.root = root
        self.db = root / DB_FILENAME

        self.content = root / "content"
        self.image = self.content / "image"
        self.actors_image = self.image / "actors"
        self.actresses_image = self.image / "actresses"
        self.screenshots = self.image / "screenshots"
        self.thumbnails = self.content / "thumbnails"
        self.video = self.content / "video"

        self.report = root / "report"

        self.trash = root / "trash"
        self.trash_screenshots = self.trash / "screenshots"
        self.trash_video = self.trash / "video"

    def all_dirs(self) -> list[Path]:
        return [
            self.content,
            self.image,
            self.actors_image,
            self.actresses_image,
            self.screenshots,
            self.thumbnails,
            self.video,
            self.report,
            self.trash,
            self.trash_screenshots,
            self.trash_video,
        ]


def find_project_root(start: Path | None = None) -> Path | None:
    root = start or Path.cwd()
    return root if (root / DB_FILENAME).is_file() else None


def clip_source_path(clip_row) -> Path:
    source_dir = clip_row["source_dir"]
    return Path(source_dir) / clip_row["source_filename"] if source_dir else Path(
        clip_row["source_filename"]
    )


def screenshot_filename(scene_id: str, seq: int, clip_id: str) -> str:
    return f"{scene_id}_{seq:03d}_{clip_id}.jpg"


def video_filename(scene_id: str, seq: int, clip_id: str) -> str:
    return f"{scene_id}_{seq:03d}_{clip_id}.mp4"
