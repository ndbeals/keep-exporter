#!/usr/bin/env python3

import os, pathlib
import gkeepapi
import frontmatter
import click
from pathvalidate import sanitize_filename


def login(user_email: str, password: str) -> gkeepapi.Keep:
    keep = gkeepapi.Keep()
    try:
        keep.login(user_email, password)
    except Exception:
        raise click.BadParameter("Login failed.")

    return keep


def process_note(note: gkeepapi._node.Note) -> frontmatter.Post:
    metadata = {
        "id": note.id,
        "title": note.title,
        "pinned": note.pinned,
        "trashed": note.trashed,
        "deleted": note.deleted,
        "color": note.color.name,
        "type": note.type.name,
        "parent_id": note.parent_id,
        "sort": note.sort,
        "url": note.url,
        "timestamps": {
            "created": note.timestamps.created.timestamp(),
            "edited": note.timestamps.edited.timestamp(),
            "updated": note.timestamps.updated.timestamp(),
        },
    }

    if note.timestamps.trashed:
        metadata["timestamps"]["trashed"] = note.timestamps.trashed.timestamp()
    if note.timestamps.deleted:
        metadata["timestamps"]["deleted"] = note.timestamps.deleted.timestamp()

    return frontmatter.Post(note.text, handler=None, **metadata)


@click.command()
@click.option(
    "--directory",
    "-d",
    default="./gkeep-export",
    help="Output directory for exported notes",
)
@click.option(
    "--user",
    "-u",
    default=lambda: os.environ.get("GKEEP_USER"),
    prompt=True,
    help="Google account email (environment variable 'GKEEP_USER')",
)
@click.option(
    "--password",
    "-p",
    default=lambda: os.environ.get("GKEEP_PASSWORD"),
    prompt=True,
    help="Google account password (environment variable 'GKEEP_PASSWORD')",
    hide_input=True,
)
def main(directory, user, password):
    """A simple utility to export google keep notes to markdown files with metadata stored as a frontmatter header."""
    outpath = pathlib.Path(directory).resolve()

    click.echo(f"Output directory: {outpath}")
    click.echo("Logging in.")
    keep = login(user, password)

    click.echo("Beginning note export.")
    
    if not outpath.exists():
        click.echo("output directory does not exist, creating.")
        outpath.mkdir(parents=True)

    notes = keep.all()
    note_count = 0
    for note in notes:
        note_count += 1
        click.echo(f"Processing note #{note_count}")
        post = process_note(note)

        outfile = (
            outpath
            / f'{sanitize_filename(f"{note_count:04} - " + post.metadata["title"],max_len=135)} .md'
        )
        with outfile.open("wb") as fp:
            frontmatter.dump(post, fp)

    click.echo("Done.")


if __name__ == "__main__":
    main()