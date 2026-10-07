import os
import shutil
from time import sleep
from typing import Any

import click
from mutagen.mp4 import MP4, MP4Cover

from util.constants import COMMON_CONTEXT, LOG, TAG_DELIMITER
from util.decorators import common_logging, common_options, common_tag_options
from util.file import get_file_list, filter_path_name
from util.mp4 import GENRES, Tag, pprint_tags, tag_value


def set_description_tags(m4b: MP4, description: str = "", prompt: bool = True) -> None:
    """Set description/comment tags. Prompt user for input if not provided."""

    def query_for_description() -> None:
        # Open an editor for full multiline tag editing
        instruction = f"# Enter new value for the Comment/Description:\n"
        new_tag_value: str | None = click.edit(instruction)
        if new_tag_value:
            try:
                # strip out the instruction if it's still there
                stripped_tag_value: str = new_tag_value.split(instruction)[1].strip()

                # Always set both description and comment tags at the same time
                m4b[Tag.DESCRIPTION.value] = stripped_tag_value
                m4b[Tag.COMMENT.value] = stripped_tag_value
            except:
                # if the instruction is not there, try to remove any lines that start with '#'
                stripped_tag_value = "\n".join(
                    [
                        line.strip()
                        for line in new_tag_value.splitlines()
                        if not line.startswith("#")
                    ]
                ).strip()
                # Always set both description and comment tags at the same time
                m4b[Tag.DESCRIPTION.value] = stripped_tag_value
                m4b[Tag.COMMENT.value] = stripped_tag_value

    if description:
        # Always set both description and comment tags at the same time
        m4b[Tag.DESCRIPTION.value] = description
        m4b[Tag.COMMENT.value] = description
    elif prompt:
        query_for_description()
    else:
        # TODO Also prompt if the description is shorter than 100 characters.
        # Check both description and comment
        tag_description: str | None = tag_value(m4b, Tag.DESCRIPTION)
        tag_comment: str | None = tag_value(m4b, Tag.COMMENT)

        # Fill in missing tags first
        if tag_description:
            if len(tag_description) < 100:
                LOG.warning(
                    f"Description tag '{tag_description}' is less than 100 characters."
                )
                sleep(2)
                query_for_description()
            elif not tag_comment:
                m4b[Tag.COMMENT.value] = tag_description
            elif tag_comment != tag_description:
                LOG.warning(
                    f"Description tag '{tag_description}' does not match comment '{tag_comment}'."
                )
                sleep(2)
                query_for_description()
        elif tag_comment:
            if len(tag_comment) < 100:
                LOG.warning(f"Comment tag '{tag_comment}' is less than 100 characters.")
                sleep(2)
                query_for_description()
            else:
                m4b[Tag.DESCRIPTION.value] = tag_comment
        else:
            query_for_description()


def set_series_tags(
    m4b: MP4, name: str | None = None, part: float | None = None
) -> None:
    """Set series name and/or part on both the readable and legacy SRNM/SRSQ atoms."""
    if name is not None:
        m4b[Tag.SERIES_NAME.value] = name.encode("utf-8")
        m4b["----:com.apple.iTunes:SRNM"] = name.encode("utf-8")
    if part is not None:
        # ABS uses the part string verbatim, so whole numbers must not end in ".0".
        value: str = str(int(part)) if part.is_integer() else str(part)
        m4b[Tag.SERIES_PART.value] = value.encode("utf-8")
        m4b["----:com.apple.iTunes:SRSQ"] = value.encode("utf-8")


def warn_abs_name_split(m4b: MP4) -> None:
    """Warn when Audiobookshelf would split an author or narrator name on '&' or ' and '."""
    for tag in (Tag.ARTIST, Tag.NARRATOR):
        value: str = tag_value(m4b, tag) or ""
        if "&" in value or " and " in value:
            LOG.warning(
                f"{tag.name} '{value}' contains '&' or ' and '. Audiobookshelf splits "
                f"names on these before '{TAG_DELIMITER}', so it will read them as separate people."
            )


def drop_audiobook_genre(m4b: MP4) -> list[str]:
    """Remove the generic 'Audiobook' genre and return the genres that remain."""
    current: str = tag_value(m4b, Tag.GENRE) or ""
    genres: list[str] = [g.strip() for g in current.split(TAG_DELIMITER) if g.strip()]
    kept: list[str] = [g for g in genres if g.lower() != "audiobook"]
    if kept != genres:
        if kept:
            m4b[Tag.GENRE.value] = TAG_DELIMITER.join(kept)
        else:
            del m4b[Tag.GENRE.value]
    return kept


def set_cover_tag(m4b: MP4, cover: Any = None) -> None:
    click.echo("Cover images not supported yet.")
    # prompt for path to cover image
    # TODO test aaaaaaaall this shit
    # cover_path: str = click.prompt(
    #     text="Enter path to cover image",
    #     type=click.Path(
    #         exists=True, file_okay=True, dir_okay=False
    #     ),
    # )
    # LOG.debug(f"Cover file: '{cover_path}'")

    # # quick check file type png or jpg
    # if (
    #     not cover_path.endswith(".png")
    #     and not cover_path.endswith(".jpg")
    #     and not cover_path.endswith(".jpeg")
    # ):
    #     LOG.error(f"Invalid file type: '{cover_path}'")
    #     continue

    # if cover_path.endswith(".png"):
    #     imageFormat = MP4Cover.FORMAT_PNG
    # else:
    #     imageFormat = MP4Cover.FORMAT_JPEG

    # cover: MP4Cover = MP4Cover(
    #     cover_path, imageformat=imageFormat
    # )
    # m4b[Tag.COVER.value] = [cover]


@click.command(context_settings=COMMON_CONTEXT, name="set")
@common_options
@common_logging
@common_tag_options
def set_tags(
    source: str,
    recurse: bool,
    author: str,
    date: str,
    description: str,
    genre: list[str],
    narrator: str,
    series_name: str,
    series_part: float,
    title: str,
):
    """Set audiobook tags on the command line or interactively."""
    files: list[str] = get_file_list(source, ext="m4b", recurse=recurse)
    required_tags: list[Tag] = [
        Tag.ARTIST,
        Tag.NARRATOR,
        Tag.COVER,
        Tag.DESCRIPTION,
        Tag.GENRE,
        Tag.SERIES_NAME,
        Tag.TRACK_TITLE,
        Tag.YEAR,
    ]

    for file in files:
        LOG.debug(f"Processing file: '{file}'")
        m4b: MP4 = MP4(file)

        # Print current tags
        pprint_tags(m4b, pause=False)

        tag: Tag
        for tag in required_tags:
            match tag:
                case Tag.TRACK_TITLE:
                    if title:
                        # set both track title and album
                        m4b[Tag.TRACK_TITLE.value] = title
                        m4b[Tag.ALBUM.value] = title
                    else:
                        # check both track title and album
                        track_title: str | None = tag_value(m4b, tag)
                        album_title: str | None = tag_value(m4b, Tag.ALBUM)

                        if track_title:
                            if not album_title:
                                m4b[Tag.ALBUM.value] = track_title
                            elif album_title != track_title:
                                LOG.warning(
                                    f"Track title '{track_title}' does not match album title '{album_title}'."
                                )
                                if click.confirm(
                                    "Do you want to change the titles?",
                                    prompt_suffix="",
                                ):
                                    new_title: str = click.prompt("Enter new title")
                                    m4b[Tag.ALBUM.value] = new_title
                                    m4b[Tag.TRACK_TITLE.value] = new_title
                        else:
                            if album_title:
                                m4b[Tag.TRACK_TITLE.value] = album_title
                            else:
                                # prompt user for track title
                                new_title: str = click.prompt("Enter book title")
                                m4b[Tag.TRACK_TITLE.value] = new_title
                                m4b[Tag.ALBUM.value] = new_title
                case Tag.ARTIST:
                    if author:
                        # set both artist and album artist
                        m4b[Tag.ARTIST.value] = author
                        m4b[Tag.ALBUM_ARTIST.value] = author
                    else:
                        # check both artist and album artist
                        tag_artist: str | None = tag_value(m4b, tag)
                        album_artist: str | None = tag_value(m4b, Tag.ALBUM_ARTIST)

                        if tag_artist:
                            if not album_artist:
                                m4b[Tag.ALBUM_ARTIST.value] = tag_artist
                            elif album_artist != tag_artist:
                                LOG.warning(
                                    f"Artist tag '{tag_artist}' does not match album artist '{album_artist}'."
                                )
                                if click.confirm(
                                    "Do you want to change the artists?",
                                    prompt_suffix="",
                                ):
                                    new_artist: str = click.prompt(
                                        "Enter new Author names separated by semicolons(;)"
                                    )
                                    m4b[Tag.ALBUM_ARTIST.value] = new_artist
                                    m4b[Tag.ARTIST.value] = new_artist
                        else:
                            if album_artist:
                                m4b[Tag.ARTIST.value] = album_artist
                            else:
                                # prompt user for artist
                                new_artist: str = click.prompt("Enter artist (author)")
                                m4b[Tag.ARTIST.value] = new_artist
                                m4b[Tag.ALBUM_ARTIST.value] = new_artist
                case Tag.COVER:
                    pass
                    # set_cover_tag(m4b=m4b)
                case Tag.DESCRIPTION:
                    if description:
                        set_description_tags(m4b=m4b, description=description)
                    else:
                        set_description_tags(m4b=m4b, prompt=False)
                case Tag.GENRE:
                    if genre:
                        m4b[tag.value] = TAG_DELIMITER.join(genre)
                    elif not drop_audiobook_genre(m4b):
                        # prompt user for genre if not set
                        new_genres: list[str] = []
                        while True:
                            click.clear()
                            click.echo("Available genres:")
                            click.echo(
                                [genre for genre in GENRES if genre not in new_genres]
                            )

                            # TODO Include "custom" genre option
                            new_genre: str = click.prompt(
                                text="Enter a genre from the list, or 'enter' to continue",
                                default="",
                            )

                            if new_genre in GENRES and new_genre not in new_genres:
                                new_genres.append(new_genre)
                            elif not new_genre:
                                # break out of loop if user hits enter
                                break
                            else:
                                click.echo("Invalid genre, try again.")
                                sleep(2)

                        m4b[tag.value] = TAG_DELIMITER.join(new_genres)
                case Tag.SERIES_NAME:
                    # get tag values
                    tag_series_name: str | None = tag_value(m4b, tag)
                    tag_series_part: str | None = tag_value(m4b, Tag.SERIES_PART)

                    if series_name and series_part:
                        # if both are provided, just set the tags.
                        set_series_tags(m4b, name=series_name, part=series_part)
                    elif series_name or series_part:
                        # otherwise, if one is provided, check for the other
                        if series_name and not tag_series_part:
                            new_series_part: float = click.prompt(
                                text=(
                                    "Series name provided, but no existing tag value for series part number. \n"
                                    "Please enter series part number"
                                ),
                                type=float,
                            )
                            set_series_tags(m4b, name=series_name, part=new_series_part)
                        elif series_part and not tag_series_name:
                            new_series_name: str = click.prompt(
                                text=(
                                    "Series part provided, but no existing tag value for series name. \n"
                                    "Please enter series name"
                                )
                            )
                            set_series_tags(m4b, name=new_series_name, part=series_part)
                        else:
                            LOG.critical(
                                "There is a flaw in application logic. This code should never be reached. "
                                "trying to continue."
                            )
                    else:
                        # If neither are provided, prompt user for any currently missing
                        if tag_series_name:
                            if tag_series_part:
                                # Both series name and part exist
                                continue
                            else:
                                # Only series name exists, get part
                                new_series_part: float = click.prompt(
                                    "Enter series part number", type=float
                                )
                                set_series_tags(m4b, part=new_series_part)
                        else:
                            if tag_series_part:
                                # Only series part exists, get name
                                new_series_name: str = click.prompt("Enter series name")
                                set_series_tags(m4b, name=new_series_name)
                            else:
                                # Neither tag exists
                                if click.confirm(
                                    "Do you want to set series tags?", prompt_suffix=""
                                ):
                                    new_series_name: str = click.prompt(
                                        "Enter series name"
                                    )
                                    new_series_part: float = click.prompt(
                                        "Enter series part number", type=float
                                    )
                                    set_series_tags(
                                        m4b, name=new_series_name, part=new_series_part
                                    )
                case _:
                    if not tag_value(m4b, tag):
                        tag_input_map: dict[Tag, str] = {
                            Tag.YEAR: date,
                            Tag.NARRATOR: narrator,
                        }
                        # check if the tag has a user provided value
                        if tag in tag_input_map and tag_input_map[tag]:
                            m4b[tag.value] = tag_input_map[tag]
                        elif not tag_value(m4b, tag):
                            # only set unset tags
                            value: str = click.prompt(f"Enter {tag.name}")
                            m4b[tag.value] = value

        # Show updated tags
        pprint_tags(m4b, pause=False)

        # Prompt loop for user to change additional tags
        if click.confirm("Are there any tags you want to change?", prompt_suffix=""):
            while True:
                tag_to_chg: str = click.prompt(
                    text="Enter tag name to change (e.g. 'ALBUM'), or 'enter' to continue",
                    default="",
                )
                if tag_to_chg:
                    # get tag enum
                    try:
                        tag_enum: Tag = Tag[tag_to_chg.upper()]
                    except KeyError:
                        LOG.error(f"Invalid tag: '{tag_to_chg}'")
                        continue

                    match tag_enum:
                        case Tag.COVER:
                            set_cover_tag(m4b=m4b)
                        case Tag.GENRE:
                            # prompt for genre
                            new_genres: list[str] = []
                            while True:
                                click.clear()
                                click.echo("Available genres:")
                                click.echo(
                                    [
                                        genre
                                        for genre in GENRES
                                        if genre not in new_genres
                                    ]
                                )

                                new_genre: str = click.prompt(
                                    text="Enter a genre from the list, or 'enter' to continue",
                                    default="",
                                )

                                if new_genre in GENRES and new_genre not in new_genres:
                                    new_genres.append(new_genre)
                                elif not new_genre:
                                    # break out of loop if user hits enter
                                    break
                                else:
                                    click.echo("Invalid genre, try again.")
                                    sleep(2)

                            m4b[tag_enum.value] = TAG_DELIMITER.join(new_genres)
                        case e if e in [Tag.DESCRIPTION, Tag.COMMENT]:
                            set_description_tags(m4b=m4b)
                        case e if e in [Tag.ARTIST, Tag.ALBUM_ARTIST]:
                            # Update both artist and album artist at the same time
                            new_artist: str = click.prompt(
                                text=f"Enter new Author name or 'Enter' to abort",
                                default="",
                            )
                            if new_artist:
                                m4b[Tag.ARTIST.value] = new_artist
                                m4b[Tag.ALBUM_ARTIST.value] = new_artist
                            else:
                                click.prompt(
                                    text="Aborted. Press 'enter' to continue.",
                                    default="",
                                )
                        case e if e in [Tag.ALBUM, Tag.TRACK_TITLE]:
                            # Update both album and track title at the same time
                            new_title: str = click.prompt(
                                text=f"Enter new Title or 'Enter' to abort",
                                default="",
                            )
                            if new_title:
                                m4b[Tag.ALBUM.value] = new_title
                                m4b[Tag.TRACK_TITLE.value] = new_title
                            else:
                                click.prompt(
                                    text="Aborted. Press 'enter' to continue.",
                                    default="",
                                )
                        case Tag.SERIES_NAME:
                            new_series_name: str = click.prompt(
                                text="Enter new series name or 'Enter' to abort",
                                default="",
                            ).strip()
                            if new_series_name:
                                set_series_tags(m4b, name=new_series_name)
                            else:
                                click.prompt(
                                    text="Aborted. Press 'enter' to continue.",
                                    default="",
                                )
                        case Tag.SERIES_PART:
                            new_series_part: str = click.prompt(
                                text="Enter new series part number or 'Enter' to abort",
                                default="",
                            ).strip()
                            if not new_series_part:
                                click.prompt(
                                    text="Aborted. Press 'enter' to continue.",
                                    default="",
                                )
                            else:
                                try:
                                    set_series_tags(m4b, part=float(new_series_part))
                                except ValueError:
                                    LOG.error(
                                        f"Invalid series part number: '{new_series_part}'"
                                    )
                        case _:
                            current: str | None = tag_value(m4b, tag_enum)
                            if current is None:
                                click.echo(f"Tag '{tag_enum.name}' is empty.")
                            else:
                                click.echo(
                                    f"Current value for '{tag_enum.name}': {current}"
                                )

                            new_tag_value = click.prompt(
                                text=f"Enter new value for '{tag_enum.name}' or 'Enter' to abort",
                                default="",
                            ).strip()
                            if new_tag_value:
                                try:
                                    m4b[tag_enum.value] = new_tag_value.encode("utf-8")
                                except Exception as e:
                                    LOG.error(
                                        f"Error setting tag '{tag_enum.name}': {e}"
                                    )
                                    m4b[tag_enum.value] = new_tag_value
                            else:
                                click.prompt(
                                    text="Aborted. Press 'enter' to continue.",
                                    default="",
                                )

                else:
                    break

                # Show updated tags for user to review
                pprint_tags(m4b, pause=False)

        # Prompt to save tags to file
        pprint_tags(m4b, pause=False)
        warn_abs_name_split(m4b)
        if click.confirm("Do you want to save these tags?", abort=True):
            m4b.save()
            click.echo(f"Tags saved for file: {file}")

        # TODO add option to rename to  "Author - Title.m4b"
        file_title: str = tag_value(m4b, Tag.TRACK_TITLE)  # type: ignore
        file_artist: str = tag_value(m4b, Tag.ARTIST).split(TAG_DELIMITER)[0]  # type: ignore

        new_file: str = os.path.join(
            os.path.dirname(source),
            filter_path_name(f"{file_artist} - {file_title}.m4b"),
        )

        if file != new_file and click.confirm(
            f"Do you want to auto-rename the file ('{file}' --> '{new_file}')?",
            abort=True,
        ):
            if os.path.exists(new_file) and not click.confirm(
                f"'{new_file}' already exists. Overwrite it?", default=False
            ):
                LOG.warning(f"Not renaming '{file}'; '{new_file}' already exists")
            else:
                # Rename file as "author - title.m4b"
                shutil.move(file, new_file)


@click.command(context_settings=COMMON_CONTEXT, name="print")
@common_options
def print_tags(source: str, recurse: bool):
    """Print audiobook tags to the console."""
    files = get_file_list(source, ext="m4b", recurse=recurse)
    for file in files:
        m4b = MP4(file)
        click.echo(f"Tags for file: {file}")
        pprint_tags(m4b, pause=False)
        click.echo(f"")
        click.echo(f"")


@click.command(context_settings=COMMON_CONTEXT, name="verify")
@common_logging
@common_options
def verify_tags(source: str, recurse: bool):
    """Verify required audiobook tags are set and automatically set some (e.g. title and album) if missing. (not implemented)"""
