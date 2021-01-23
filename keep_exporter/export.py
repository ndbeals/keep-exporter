#!/usr/bin/env python3
import datetime
import mimetypes
import os
import pathlib
from typing import Dict, List, NamedTuple, Optional

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
    note: gkeepapi._node.Note,
    mediapath: pathlib.Path,
    skip_existing: bool,
) -> List[pathlib.Path]:
    if not note.images and not note.drawings and not note.audio:
        return []

    ret = []

    for media in note.images + note.drawings + note.audio:
        meta = media.blob.save()
        # ocr = meta["extracted_text"]  # TODO save ocr as metadata? in markdown or image?

        if meta.get("type", "") == "DRAWING":
            extension = mimetypes.guess_extension(
                meta.get("drawingInfo", {})
                .get("snapshotData", {})
                .get("mimetype", "image/png")
            )  # All drawings seem to be pngs
        elif meta.get("type") == "IMAGE":
            extension = mimetypes.guess_extension(meta.get("mimetype", "image/jpeg"))
            # .jpe just feels weird, but it's my default in testing
            if extension == ".jpe":
                extension = ".jpg"
        else:  # 'AUDIO'
            extension = mimetypes.guess_extension(meta.get("mimetype", "audio/3gpp"))

        # nest media files under folders named by the note's ID
        # this simplifies figuring out the note media files came from
        note_media_path = mediapath / note.id
        note_media_path.mkdir(exist_ok=True)

        media_file = (
            note_media_path
            / f"{sanitize_filename(media.server_id,max_len=135)}{extension}"
        )

        # checking size isn't perfect, and drawings don't have a size,
        # but it doesn't seem right to always re-download images that likely
        # haven't changed
        if (
            skip_existing
            and media_file.exists()
            and hasattr(media.blob, "byte_size")
            and media_file.stat().st_size == media.blob.byte_size
        ):
            click.echo(
                f"Media file f{media_file} exists and is same size as in Google Keep. Skipping."
            )
        else:
            print(
                f"Downloading media {meta.get('type')} {media.server_id} for note {note.id}"
            )

            url = keep._media_api.get(media)
            media_data = keep._media_api._session.get(url)
            with media_file.open("wb") as f:
                f.write(media_data.content)

        ret.append(media_file)

    return ret


def build_frontmatter(note: gkeepapi._node.Note, markdown: str) -> frontmatter.Post:
    metadata = {
        "google_keep_id": note.id,
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


MarkdownFile = NamedTuple(
    "MarkdownFile",
    [
        ("path", pathlib.Path),
        ("timestamp_updated", Optional[datetime.datetime]),
        ("google_keep_id", Optional[str]),
    ],
)

MediaFile = NamedTuple(
    "MediaFile",
    [
        ("path", pathlib.Path),
        ("parent_id", Optional[str]),
        ("google_keep_id", Optional[str]),
    ],
)


def index_existing_files(directory: pathlib.Path) -> Dict[str, MarkdownFile]:
    index = {}

    keep_notes = 0
    unknown_notes = 0
    errors = 0
    media = 0

    for file in directory.rglob("*"):
        # markdown file
        if file.name.endswith(".md"):
            try:
                with open(file, "r") as f:
                    fm = frontmatter.load(f)

                    info = MarkdownFile(
                        file,
                        fm.metadata.get("timestamps").get("updated"),
                        fm.metadata.get("google_keep_id"),
                    )

                    if info.google_keep_id:
                        keep_notes += 1
                        index[info.google_keep_id] = info
                    else:
                        unknown_notes += 1
            except IOError as ex:
                errors = 0
                click.echo(
                    "Unable to open Markdown file [{os.path.join(root, file)}]. Skipping: {str(ex)}",
                    err=True,
                )

        # media file
        else:
            media += 1
            click.echo(f"Ignoring media file [{file}]")

    click.echo(
        f"Indexed local files: {keep_notes} Google Keep notes, {unknown_notes} unknown markdown files, {media} media files, {errors} errors"
    )

    return index


def try_rename_note(note: MarkdownFile, target_file: pathlib.Path) -> pathlib.Path:
    """
    Attempts to rename an existing note to the new canonical filename,
    but accepts failures to rename. Returns the path the note now exists
    in, either the old path or the new renamed path.
    """
    click.echo(f"Renaming [{note.path}] to [{target_file}]")

    try:
        note.path.rename(target_file)
        return target_file
    except Exception as ex:
        click.echo(f"Unable to rename note. Using existing name: %s" % ex, err=True)
        return note.path


def build_note_unique_path(
    notepath: pathlib.Path,
    note: gkeepapi._node.Note,
    date_format: str,
    local_index: Dict[str, MarkdownFile],
) -> pathlib.Path:
    title = note.title.strip()
    if not len(title):
        title = "untitled"

    date_str = note.timestamps.created.strftime(date_format)
    filename = f'{sanitize_filename(f"{date_str} - " + title,max_len=135)}.md'
    target_path = notepath / filename

    if note.id in local_index:
        # if the note filename matches the current filename for that note, then we're good
        if local_index[note.id].path == target_path:
            return local_index[note.id].path

        # if re-naming would result in having to de-dupe the target filename, keep the
        # exising filename - initial pass at fixing this just resulted in bouncing between
        # two different filenames each pass
        if target_path.exists():
            click.echo(
                f"Note {note.id} will not be renamed. Target file [{target_path}] exists."
            )
            return local_index[note.id].path

    # otherwise, if the file already exists avoid overwriting it
    # put the unique note ID and an incrementing index at the end of the filename
    dedupe_index = 1
    while target_path.exists():
        filename = f'{sanitize_filename(f"{date_str} - " + title,max_len=135)}.{note.id}.{dedupe_index}.md'
        target_path = notepath / filename
        dedupe_index += 1

    return target_path


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
@click.option(
    "--delete-local/--no-delete-local",
    default=False,
    show_default=True,
    help="Choose to delete or leave as-is any notes that exist locally but not in Google Keep",
)
@click.option(
    "--rename-local/--no-rename-local",
    default=False,
    show_default=True,
    help="Choose to rename or leave as-is any notes that change titles in Google Keep",
)
@click.option(
    "--date-format",
    default="%Y-%m-%d",
    show_default=True,
    help="Date format to use for the prefix of the note filenames. Reflects the created date of the note.",
)
@click.option(
    "--skip-existing-media/--no-skip-existing-media",
    default=True,
    show_default=True,
    help="Skip existing media if it appears unchanged from the local copy.",
)
def main(
    directory: str,
    user: str,
    password: str,
    header: bool,
    delete_local: bool,
    rename_local: bool,
    date_format: str,
    skip_existing_media: bool,
):
    """A simple utility to export google keep notes to markdown files with metadata stored as a frontmatter header."""
    notepath = pathlib.Path(directory).resolve()
    mediapath = notepath.joinpath("media/")

    click.echo(f"Notes directory: {notepath}")
    click.echo(f"Media directory: {mediapath}")

    click.echo("Logging in.")
    keep = login(user, password)

    if not notepath.exists():
        click.echo("Notes directory does not exist, creating.")
        notepath.mkdir(parents=True)

    if not mediapath.exists():
        click.echo("Media directory does not exist, creating.")
        mediapath.mkdir(parents=True)

    click.echo("Indexing local files.")
    local_index = index_existing_files(notepath)

    click.echo("Indexing remote notes.")
    keep_notes = dict([(note.id, note) for note in keep.all()])

    deleted_notes = set(local_index.keys()).difference(set(keep_notes.keys()))

    if deleted_notes:
        if not delete_local:
            click.echo(
                f"{len(deleted_notes)} notes exist locally, but not in Google Keep. Add argument [--delete-local] to delete."
            )
        else:
            click.echo(
                f"{len(deleted_notes)} notes exist locally, but not in Google Keep. Trashing local files."
            )
            for note_id in deleted_notes:
                click.echo(
                    f"    Deleting unknown local note [{note_id}] file [{local_index[note_id].path}]"
                )
                local_index[note_id].path.unlink()

    for note in keep_notes.values():  # type: gkeepapi.node.TopLevelNode
        if note.id in local_index:
            click.echo(f"Updating existing file for note {note.id}")
        else:
            click.echo(f"Downloading new note {note.id}")

        target_path = build_note_unique_path(notepath, note, date_format, local_index)

        if note.id in local_index:
            if rename_local and local_index[note.id].path != target_path:
                target_path = try_rename_note(local_index[note.id], target_path)
            else:
                target_path = local_index[note.id].path

        images = download_images(keep, note, mediapath, skip_existing_media)
        markdown = build_markdown(note, images)

        with target_path.open("wb+") as f:
            if header:
                fmatter = build_frontmatter(note, markdown)
                frontmatter.dump(fmatter, f)
            else:
                f.write(markdown.encode("utf-8"))

    click.echo("Done.")


if __name__ == "__main__":
    main()
