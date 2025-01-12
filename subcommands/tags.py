from time import sleep

import click
from mutagen.mp4 import MP4, MP4Cover

from util.constants import COMMON_CONTEXT, LOG
from util.decorators import common_logging, common_options, common_tag_options
from util.file import get_file_list
from util.mp4 import GENRES, Tag, pprint_tags


@click.command(context_settings=COMMON_CONTEXT, name="set")
@common_options
# @common_logging
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
                        track_title: str = m4b.get(tag.value, [None])[0]  # type: ignore
                        album_title: str = m4b.get(Tag.ALBUM.value, [None])[0]  # type: ignore

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
                                    new_title: str = click.prompt("Enter new title: ")
                                    m4b[Tag.ALBUM.value] = new_title
                                    m4b[Tag.TRACK_TITLE.value] = new_title
                        else:
                            if album_title:
                                m4b[Tag.TRACK_TITLE.value] = album_title
                            else:
                                # prompt user for track title
                                new_title: str = click.prompt("Enter book title: ")
                                m4b[Tag.TRACK_TITLE.value] = new_title
                                m4b[Tag.ALBUM.value] = new_title
                case Tag.ARTIST:
                    if author:
                        # set both artist and album artist
                        m4b[Tag.ARTIST.value] = author
                        m4b[Tag.ALBUM_ARTIST.value] = author
                    else:
                        # check both artist and album artist
                        tag_artist: str = m4b.get(tag.value, [None])[0]  # type: ignore
                        album_artist: str = m4b.get(Tag.ALBUM_ARTIST.value, [None])[0]  # type: ignore

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
                                        "Enter new Author names separated by semicolons(;): "
                                    )
                                    m4b[Tag.ALBUM_ARTIST.value] = new_artist
                                    m4b[Tag.ARTIST.value] = new_artist
                        else:
                            if album_artist:
                                m4b[Tag.ARTIST.value] = album_artist
                            else:
                                # prompt user for artist
                                new_artist: str = click.prompt("Enter artist: ")
                                m4b[Tag.ARTIST.value] = new_artist
                                m4b[Tag.ALBUM_ARTIST.value] = new_artist
                case Tag.DESCRIPTION:
                    if description:
                        m4b[tag.value] = description
                    else:
                        # Check both description and comment
                        tag_description: str = m4b.get(tag.value, [None])[0]  # type: ignore
                        tag_comment: str = m4b.get(Tag.COMMENT.value, [None])[0]  # type: ignore

                        if tag_description:
                            if not tag_comment:
                                m4b[Tag.COMMENT.value] = tag_description
                            elif tag_comment != tag_description:
                                LOG.warning(
                                    f"Description tag '{tag_description}' does not match comment '{tag_comment}'."
                                )
                                if click.confirm(
                                    "Do you want to change the descriptions?",
                                    prompt_suffix="",
                                ):
                                    new_description: str = click.prompt(
                                        "Enter new description: "
                                    )
                                    m4b[Tag.COMMENT.value] = new_description
                                    m4b[Tag.DESCRIPTION.value] = new_description
                        else:
                            if tag_comment:
                                m4b[Tag.DESCRIPTION.value] = tag_comment
                            else:
                                # prompt user for description
                                new_description: str = click.prompt(
                                    "Enter description: "
                                )
                                m4b[Tag.DESCRIPTION.value] = new_description
                                m4b[Tag.COMMENT.value] = new_description
                case Tag.GENRE:
                    if genre:
                        m4b[tag.value] = ";".join(genre)
                    elif not m4b.get(tag.value, [None])[0]:  # type: ignore
                        # prompt user for genre if not set
                        new_genres: list[str] = []
                        while True:
                            click.clear()
                            click.echo("Available genres:")
                            click.echo(
                                [genre for genre in GENRES if genre not in new_genres]
                            )

                            new_genre: str = click.prompt(
                                text="Enter a genre from the list, or 'enter' to continue: ",
                                default="",
                            )

                            if new_genre in GENRES and new_genre not in new_genres:
                                new_genres.append(new_genre)
                            elif not new_genre:
                                # break out of loop if user hits enter
                                break
                            else:
                                click.echo("Invalid genre, try again.")
                                sleep(3)

                        m4b[tag.value] = ";".join(new_genres)
                case Tag.SERIES_NAME:
                    # get tag values
                    tag_series_name: str = m4b.get(tag.value, [None])[0]  # type: ignore
                    tag_series_part: str = m4b.get(Tag.SERIES_PART.value, [None])[0]  # type: ignore

                    if series_name and series_part:
                        # if both are provided, just set the tags.
                        m4b[Tag.SERIES_NAME.value] = series_name.encode("utf-8")
                        m4b[Tag.SERIES_PART.value] = str(series_part).encode("utf-8")
                    elif series_name or series_part:
                        # otherwise, if one is provided, check for the other
                        if series_name and not tag_series_part:
                            new_series_part: str = click.prompt(
                                text=(
                                    "Series name provided, but no existing tag value for series part number. \n"
                                    "Please enter series part number: "
                                ),
                                type=float,
                            )
                            m4b[Tag.SERIES_NAME.value] = series_name.encode("utf-8")
                            m4b[Tag.SERIES_PART.value] = new_series_part.encode("utf-8")
                        elif series_part and not tag_series_name:
                            new_series_name: str = click.prompt(
                                text=(
                                    "Series name provided, but no existing tag value for series part number. \n"
                                    "Please enter series part number: "
                                )
                            )
                            m4b[Tag.SERIES_NAME.value] = new_series_name.encode("utf-8")
                            m4b[Tag.SERIES_PART.value] = str(series_part).encode(
                                "utf-8"
                            )
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
                                new_series_part: str = click.prompt(
                                    "Enter series part number", float
                                )
                                m4b[Tag.SERIES_PART.value] = new_series_part.encode(
                                    "utf-8"
                                )
                        else:
                            if tag_series_part:
                                # Only series part exists, get name
                                new_series_name: str = click.prompt("Enter series name")
                                m4b[Tag.SERIES_NAME.value] = new_series_name.encode(
                                    "utf-8"
                                )
                            else:
                                # Neither tag exists
                                if click.confirm(
                                    "Do you want to set series tags?", prompt_suffix=""
                                ):
                                    new_series_name: str = click.prompt(
                                        "Enter series name"
                                    )
                                    new_series_part: str = click.prompt(
                                        "Enter series part number", float
                                    )
                                    m4b[Tag.SERIES_NAME.value] = new_series_name.encode(
                                        "utf-8"
                                    )
                                    m4b[Tag.SERIES_PART.value] = new_series_part.encode(
                                        "utf-8"
                                    )
                case _:
                    if not m4b.get(tag.value, [None])[0]:  # type: ignore
                        tag_input_map: dict[Tag, str] = {
                            Tag.YEAR: date,
                            Tag.NARRATOR: narrator,
                        }
                        # check if the tag has a user provided value
                        if tag_input_map[tag]:
                            m4b[tag.value] = tag_input_map[tag]
                        elif not m4b.get(tag.value, [None])[0]:  # type: ignore
                            # only set unset tags
                            value: str = click.prompt(f"Enter {tag.name}: ")
                            m4b[tag.value] = value

        # Show updated tags
        pprint_tags(m4b, pause=False)

        if click.confirm("Are there any tags you want to change?", prompt_suffix=""):
            while True:
                # TODO when updating artist or album artist, the other should also be updated
                # TODO when updating title or album, the other should also be updated
                tag_to_chg: str = click.prompt(
                    text="Enter tag name to change (e.g. 'ALBUM'), or 'enter' to continue: ",
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
                            # prompt for path to cover image
                            # TODO test aaaaaaaall this shit
                            cover_path: str = click.prompt(
                                text="Enter path to cover image: ",
                                type=click.Path(
                                    exists=True, file_okay=True, dir_okay=False
                                ),
                            )
                            LOG.debug(f"Cover file: '{cover_path}'")

                            # quick check file type png or jpg
                            if (
                                not cover_path.endswith(".png")
                                and not cover_path.endswith(".jpg")
                                and not cover_path.endswith(".jpeg")
                            ):
                                LOG.error(f"Invalid file type: '{cover_path}'")
                                continue

                            if cover_path.endswith(".png"):
                                imageFormat = MP4Cover.FORMAT_PNG
                            else:
                                imageFormat = MP4Cover.FORMAT_JPEG

                            cover: MP4Cover = MP4Cover(
                                cover_path, imageformat=imageFormat
                            )
                            m4b[Tag.COVER.value] = [cover]
                        case e if e in [Tag.DESCRIPTION, Tag.COMMENT]:
                            # Open an editor for full multiline tag editing
                            instruction = (
                                f"# Enter new value for the Comment/Description:\n"
                            )
                            new_tag_value: str | None = click.edit(instruction)
                            if new_tag_value:
                                try:
                                    # strip out the instruction if it's still there
                                    stripped_tag_value: str = new_tag_value.split(
                                        instruction
                                    )[1].strip()

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
                        case _:
                            match len(m4b.get(tag_enum.value, [])):  # type: ignore
                                case 0:
                                    click.echo(f"Tag '{tag_enum.name}' is empty.")
                                case 1:
                                    click.echo(
                                        f"Current value for '{tag_enum.name}': {m4b[tag_enum.value][0]}"
                                    )
                                case _:
                                    click.echo(f"Current values for '{tag_enum.name}':")
                                    click.echo(m4b[tag_enum.value])

                            new_tag_value = click.prompt(
                                text=f"Enter new value for '{tag_enum.name}' or 'Enter' to abort: ",
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

                # Show updated tags
                pprint_tags(m4b, pause=False)

        pprint_tags(m4b, pause=False)
        if click.confirm("Do you want to save these tags?", abort=True):
            m4b.save()
            click.echo(f"Tags saved for file: {file}")

        # TODO add option to rename to  "Author - Title.m4b"
        if click.confirm("Do you want to rename the file?", abort=True):
            # TODO
            pass


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
