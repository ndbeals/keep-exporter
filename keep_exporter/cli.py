#!/usr/bin/env python3
"""keep_exporter command line interface module. Provides the actual user interactions to `export.py`."""
__version__ = "2.0.0"
__author__ = "Nathan Beals, Matthew Bafford"

APP_NAME = "Keep Exporter"

import pathlib
from typing import Any, Optional, Tuple, Union

import click
import click_config_file
import frontmatter
import gkeepapi
from configobj import ConfigObj


from keep_exporter.export import (
    LocalNote,
    build_markdown,
    build_note_unique_path,
    delete_local_only_files,
    download_media,
    index_existing_files,
    try_rename_note,
    write_note,
)


def login(
    user_email: str, password: Optional[str], token: Optional[str] = None
) -> gkeepapi.Keep:
    """Logs in with the given email and password or token.

    Args:
        user_email (str): user's google email address
        password (Optional[str]): account password, either this or `token` are *required*
        token (Optional[str], optional): account token, either this or `password` are **required**. Defaults to None.

    Raises:
        click.BadParameter: Login failed

    Returns:
        gkeepapi.Keep: the `keep <gkeepapi.Keep>` object
    """
    keep = gkeepapi.Keep()
    if token:
        try:
            click.echo("Logging in with token")
            keep.resume(user_email, token)

            return keep
        except gkeepapi.exception.LoginException as ex:
            raise click.BadParameter(f"Token login (resume) failed: {str(ex)}")

    if password:
        try:
            click.echo("Logging in with password")
            keep.login(user_email, password)

            return keep
        except gkeepapi.exception.LoginException as ex:
            raise click.BadParameter(f"Password login failed: {str(ex)}")

    raise click.BadParameter(f"Neither password nor token provided to login.")


def get_click_supplied_value(ctx: click.core.Context, param_name: str) -> Any:
    """Find the value passed to Click through the following priority:

    #1 - a parameter passed on the command line
    #2 - a config value passed through @click_config_file
    #3 - None
    """

    # I didn't find in the docs for Click a simpler way to get the
    # parameter if specified, fall back to the default_map if not, None if neither
    # but this feels like a standard thing that should be built-in

    if param_name in ctx.params:
        return ctx.params[param_name]

    if ctx.default_map:
        return ctx.default_map.get(param_name)

    return None


def token_callback_password_or_token(
    ctx: click.core.Context,
    param: Union[click.core.Option, click.core.Parameter],
    value: Any,
) -> Any:
    """
    On the token param (after password), ensure that either a password
    or token were supplied, and if neither was, prompt for the password.
    """
    if value:
        token = value
    else:
        token = get_click_supplied_value(ctx, "token")
    password = get_click_supplied_value(ctx, "password")

    if not token and not password:
        click.echo("Neither password nor token provided. Prompting for password")
        password = click.prompt("Password", hide_input=True)
        ctx.params["password"] = password
        return None

    return token


def date_format_handler(
    ctx: click.core.Context,
    param: Union[click.core.Option, click.core.Parameter],
    value: Any,
) -> str:

    if param.name == "date_format":
        if (
            ctx.params.get("date_format") and param.default == value
        ):  # If date_format is already set by some other flag, return that same data
            return ctx.params.get("date_format")
        else:
            return value  # otherwise, set the format to the passed value
    else:
        if value:
            ctx.params["date_format"] = param.metavar

            return value


@click.group(
    invoke_without_command=True,
    # invoke_without_command=False,
    context_settings={"max_content_width": 160, "help_option_names": ["-h", "--help"]},
)
@click.pass_context
@click_config_file.configuration_option(
    config_file_name=click.get_app_dir(APP_NAME),
    default=click.get_app_dir(APP_NAME),
    show_default=True,
    expose_value=True,
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
    envvar="GKEEP_PASSWORD",
    show_envvar=True,
    help="Google account password (prompt if empty). Either this or token is required.",
    hide_input=True,
)
@click.option(
    "--token",
    "-t",
    envvar="GKEEP_TOKEN",
    help="Google account token from prior run. Either this or password is required.",
    callback=token_callback_password_or_token,
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
@click.option(  # Other date-options (e.g --iso8601) must come after this one
    "--date-format",
    "date_format",
    default="%Y-%m-%d",
    is_flag=False,
    show_default=True,
    help="Date format to prefix the note filenames. Reflects the created date of the note. uses strftime()",
    callback=date_format_handler,
)
@click.option(
    "--iso8601",
    metavar="%Y-%m-%dT%H:%M:%S",  # use `metavar` for the format instead of default or flag_value, hack around click stuff
    default=False,
    is_flag=True,
    help="Format dates in ISO8601 format.",
    callback=date_format_handler,
)
@click.option(
    "--skip-existing-media/--no-skip-existing-media",
    default=True,
    show_default=True,
    help="Skip existing media if it appears unchanged from the local copy.",
)
def main(
    ctx,
    directory: str,
    user: str,
    password: Optional[str],
    token: Optional[str],
    header: bool,
    delete_local: bool,
    rename_local: bool,
    date_format: str,
    skip_existing_media: bool,
    iso8601: Any,
    config: str,  # required to be here, despite being as-of-yet unused.
):
    """A simple utility to export google keep notes to markdown files with metadata stored as a frontmatter header."""

    notepath = pathlib.Path(directory).resolve()
    mediapath = notepath.joinpath("media/")
    if ctx.invoked_subcommand is not None:
        return False

    click.echo(f"Notes directory: {notepath}")
    click.echo(f"Media directory: {mediapath}")

    keep = login(user, password, token)

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

    skipped_notes, updated_notes, new_notes = 0, 0, 0
    downloaded_media = 0
    deleted_notes, deleted_media = delete_local_only_files(
        local_index, keep_notes, delete_local
    )

    for note in keep_notes.values():  # type: gkeepapi._node.Note
        local_note = local_index.get(note.id)
        if not local_note:
            click.echo(f"Downloading new note {note.id}")
            new_notes += 1

        target_path = build_note_unique_path(notepath, note, date_format, local_index)

        local_path = local_index.get(note.id, LocalNote(note.id)).path
        if local_path:
            if rename_local and local_path != target_path:
                target_path = try_rename_note(local_index[note.id], target_path)
            else:
                target_path = local_path

        # decide to skip after the rename (due to date format change) has a chance
        if local_note:
            if local_note.timestamp_updated == note.timestamps.updated:
                skipped_notes += 1
                continue
            else:
                updated_notes += 1
                click.echo(f"Updating existing file for note {note.id}")

        images, downloaded = download_media(keep, note, mediapath, skip_existing_media)
        markdown = build_markdown(note, images)

        downloaded_media += downloaded

        write_note(target_path, header, note, markdown)

    click.echo("Finished syncing.")
    click.echo(
        f"Notes: {skipped_notes} unchanged, {updated_notes} updated, {new_notes} new, {deleted_notes} deleted"
    )
    click.echo(f"Media: {downloaded_media} downloaded, {deleted_media} deleted")


@main.command()
@click.pass_context
def savetoken(ctx):
    """Saves the master token to your configuration file. Avoids re-logging in every time an export happens."""
    user, password, token = (
        ctx.parent.params.get("user", ""),
        ctx.parent.params.get("password", ""),
        ctx.parent.params.get("token", ""),
    )

    keep = login(user, password)
    click.echo("Saving master token.")

    config_file = ctx.parent.params.get("config", None)

    if config_file:
        config_obj = ConfigObj(config_file, unrepr=True)

        if keep.getMasterToken() != config_obj.get("token", ""):
            config_obj["token"] = keep.getMasterToken()
            config_obj.write()

            click.echo("Master token written to configuration file.")


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
