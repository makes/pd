from pathlib import Path

import typer

from . import db, paths

app = typer.Typer(no_args_is_help=True)


@app.callback()
def callback() -> None:
    pass


@app.command()
def init() -> None:
    """Initialize a new pd project in the current directory."""
    root = Path.cwd()
    if (root / paths.DB_FILENAME).exists():
        typer.echo(f"error: {paths.DB_FILENAME} already exists in {root}", err=True)
        raise typer.Exit(1)

    for d in paths.ProjectPaths(root).all_dirs():
        d.mkdir(parents=True, exist_ok=True)

    db.init_db(root)
    typer.echo(f"Initialized pd project in {root}")


@app.command()
def ui() -> None:
    """Launch the pd TUI."""
    root = require_project()
    from .tui.app import PdApp

    PdApp(root).run()


@app.command()
def sync() -> None:
    """Sync generated video/screenshot files to match database contents."""
    root = require_project()
    from . import sync as sync_mod

    sync_mod.run(root)


@app.command()
def site(category: str | None = typer.Option(None, "--category")) -> None:
    """Generate the static HTML site."""
    root = require_project()
    from . import site as site_mod

    site_mod.run(root, category=category)


@app.command()
def report() -> None:
    """Print and save a database/filesystem report."""
    root = require_project()
    from . import report as report_mod

    report_mod.run(root)


def require_project() -> Path:
    root = Path.cwd()
    if not (root / paths.DB_FILENAME).is_file():
        typer.echo(
            f"error: no {paths.DB_FILENAME} found in {root} (run 'pd init' first)",
            err=True,
        )
        raise typer.Exit(1)
    return root
