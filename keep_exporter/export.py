#!/usr/bin/env python3
import mimetypes
import pathlib
from typing import List

import click
import frontmatter
import gkeepapi
from mdutils.mdutils import MdUtils
from pathvalidate import sanitize_filename

mimetypes.add_type("audio/3gpp", ".3gp")


def login(user_email: str, password: str) -> gkeepapi.Keep:
    keep = gkeepapi.Keep()
    try:
        keep.login(user_email, password)
    except gkeepapi.exception.LoginException as ex:
        raise click.BadParameter(f"Login failed: {str(ex)}")

    return keep


def download_images(
    keep: gkeepapi.Keep,
    note_count: int,
    note: gkeepapi._node.Note,
    outpath: pathlib.Path,
) -> List[pathlib.Path]:
    if not note.images and not note.drawings and not note.audio:
        return []

    ret = []

    for media in note.images + note.drawings + note.audio:
        meta = media.blob.save()
        # ocr = meta["extracted_text"]  # TODO save ocr as metadata? in markdown or image?

        url = keep._media_api.get(media)
        print("Downloading %s" % url)

        if meta.get("type", "") == "DRAWING":
            extension = mimetypes.guess_extension(
                meta.get("drawingInfo", {})
                .get("snapshotData", {})
                .get("mimetype", "image/png")
            )  # All drawings seem to be pngs
        elif meta.get("type") == "IMAGE":
            extension = mimetypes.guess_extension(meta.get("mimetype", "image/jpeg"))
        else:  # 'AUDIO'
            extension = mimetypes.guess_extension(meta.get("mimetype", "audio/3gpp"))

        media_file = (
            outpath
            / f'{sanitize_filename(f"{note_count:04} - " + media.server_id,max_len=135)}{extension}'
        )

        media_data = keep._media_api._session.get(url)
        with media_file.open("wb") as f:
            f.write(media_data.content)

        ret.append(media_file)

    return ret


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
        "tags": [label.name for label in note.labels.all()],
        "timestamps": {
            "created": note.timestamps.created.timestamp(),
            "edited": note.timestamps.edited.timestamp(),
            "updated": note.timestamps.updated.timestamp(),
        },
    }

    # gkeepapi appears to be treating "0" as a timestamp rather than null. Sometimes the data structure does not have the key at all instead of 0.
    if note.timestamps.trashed and note.timestamps.trashed.year > 1970:
        metadata["timestamps"]["trashed"] = note.timestamps.trashed.timestamp()
    if note.timestamps.deleted and note.timestamps.deleted.year > 1970:
        metadata["timestamps"]["deleted"] = note.timestamps.deleted.timestamp()

    return frontmatter.Post(markdown, handler=None, **metadata)


def build_markdown(note: gkeepapi._node.Note, images: List[pathlib.Path]) -> str:
    doc = MdUtils(
        ""
    )  # mdutils requires a string file name. Since we're not using it to write files, we can ignore that.

    doc.new_header(1, note.title)
    doc.new_header(2, "Note")

    text = note.text
    text = text.replace("☑ ", "- [X] ")
    text = text.replace("☐ ", "- [ ] ")

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

    if images:
        doc.new_line()
        doc.new_header(2, "Attached Media")

        for image in images:
            doc.new_line(doc.new_inline_image("", image.name))

    return doc.file_data_text


@click.command(
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]}
)
@click.option(
    "--user",
    "-u",
    prompt=True,
    required=True,
    envvar="GKEEP_USER",
    show_envvar=True,
    help="Google account email (prompt if empty)",
)
@click.option(
    "--password",
    "-p",
    prompt=True,
    required=True,
    envvar="GKEEP_PASSWORD",
    show_envvar=True,
    help="Google account password (prompt if empty)",
    hide_input=True,
)
@click.option(
    "--directory",
    "-d",
    default="./gkeep-export",
    show_default=True,
    help="Output directory for exported notes",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
)
@click.option(
    "--header/--no-header",
    default=True,
    show_default=True,
    help="Choose to include or exclude the frontmatter header",
)
def main(directory, user, password, header):
    """A simple utility to export google keep notes to markdown files with metadata stored as a frontmatter header."""
    outpath = pathlib.Path(directory).resolve()

    click.echo(f"Output directory: {outpath}")
    click.echo("Logging in.")
    keep = login(user, password)

    click.echo("Beginning note export.")

    if not outpath.exists():
        click.echo("output directory does not exist, creating.")
        outpath.mkdir(parents=True)

    notes: List[gkeepapi.node.TopLevelNode] = keep.all()
    note_count = 0
    for note in notes:  # type: gkeepapi.node.TopLevelNode
        note_count += 1
        click.echo(f"Processing note #{note_count}")

        title = note.title.strip()
        if not len(title):
            title = "untitled"

        outfile = (
            outpath
            / f'{sanitize_filename(f"{note_count:04} - " + title,max_len=135)}.md'
        )

        images = download_images(keep, note_count, note, outpath)
        markdown = build_markdown(note, images)

        with outfile.open("wb+") as f:
            if header:
                fmatter = build_frontmatter(note, markdown)
                frontmatter.dump(fmatter, f)
            else:
                f.write(markdown.encode("utf-8"))

    click.echo("Done.")


if __name__ == "__main__":
    main()
