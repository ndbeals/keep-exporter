#!/usr/bin/env python3

import os, pathlib
import gkeepapi
import frontmatter
import click
from pathvalidate import sanitize_filename
from mdutils.mdutils import MdUtils
from tempfile import NamedTemporaryFile

def login(user_email: str, password: str) -> gkeepapi.Keep:
    keep = gkeepapi.Keep()
    try:
        keep.login(user_email, password)
    except Exception:
        raise click.BadParameter("Login failed.")

    return keep


def build_frontmatter(note: gkeepapi._node.Note, markdown: str) -> frontmatter.Post:
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

    # gkeepapi appears to be treating "0" as a timestamp rather than null
    if note.timestamps.trashed and note.timestamps.trashed.year > 1970:
        metadata["timestamps"]["trashed"] = note.timestamps.trashed.timestamp()
    if note.timestamps.deleted and note.timestamps.deleted.year > 1970:
        metadata["timestamps"]["deleted"] = note.timestamps.deleted.timestamp()

    return frontmatter.Post(markdown, handler=None, **metadata)

def build_markdown(note: gkeepapi._node.Note) -> str:
    # mdutils demands a filename to write to
    # and doesn't seem to support working in memory
    with NamedTemporaryFile() as f:
        doc = MdUtils(file_name=f.name)

        doc.new_header(1, note.title)
        doc.new_header(2, "Note")

        text = note.text
        text = text.replace('☑ ', '- [X] ')
        text = text.replace('☐ ', '- [ ] ')

        doc.new_paragraph(text)

        if note.annotations.links:
            doc.new_line()
            doc.new_line()
            doc.new_header(2, "Links")
            doc.new_list(
                [
                    doc.new_inline_link(link=link.url, text=link.title)
                    for link in note.annotations.links
                ]
            )

        # doc.create_md_file()
        # create_md_file writes out:
        #    data=self.title + self.table_of_contents + self.file_data_text + self.reference.get_references_as_markdown()
        # but we only care about file_data_text
        # since we're not generating a TOC or references
        # and the above adds unnecessary newlines and reading from disk
        return doc.file_data_text

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

        title = note.title.strip()
        if not len(title):
            title = "untitled"

        outfile = (
            outpath
            / f'{sanitize_filename(f"{note_count:04} - " + title,max_len=135)}.md'
        )

        markdown = build_markdown(note)
        fmatter = build_frontmatter(note, markdown)

        with open(outfile, "wb+") as f:
            frontmatter.dump(fmatter, f)

    click.echo("Done.")


if __name__ == "__main__":
    main()