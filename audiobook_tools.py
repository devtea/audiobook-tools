#!/usr/bin/env python3
import functools
import os
import re
import shutil
import logging
import subprocess
from time import sleep
from typing import Any

import click
import mutagen
from mutagen.mp4 import MP4, MP4Cover

import util.mp4
from util.mp4 import GENRES, pprint_tags, Tag
from util.file import get_file_list, get_dirs_from_files

COMMON_CONTEXT: dict = dict(help_option_names=["-h", "--help"])
CWD: str = os.getcwd()
LOG: logging.Logger = logging.getLogger(__name__)
SHITTY_REJECT_CHARACTERS_WE_HATES: list[str] = [
    "'",
    '"',
]


def filter_path_name(path: str) -> str:
    return "".join([c for c in path if c not in SHITTY_REJECT_CHARACTERS_WE_HATES])


def str_to_mode(mode: str) -> int:
    # mode value is hexadecimal
    return int(mode, 8)


def prune_dir(dir: str) -> None:
    LOG.debug(f"Checking directory: '{dir}'")
    try:
        os.rmdir(dir)
        LOG.debug(f"Pruned empty directory '{dir}'")
    except OSError:
        LOG.warning(f"Directory not empty when trying to prune: '{dir}'")


# Decorator to add common options to click commands
def common_logging(f):
    @click.option(
        "--log-level",
        "-l",
        default="INFO",
        show_default=True,
        help="Logging level.",
        type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    )
    @functools.wraps(f)
    def log_wrapper(log_level: str, *args, **kwargs):
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S%Z",
        )
        return f(*args, **kwargs)

    return log_wrapper


def common_options(f):
    @click.option(
        "--source",
        "-s",
        default=CWD,
        show_default=False,
        help="Source file or directory to work on. Defaults to current directory.",
    )
    @click.option(
        "--recurse/--no-recurse",
        default=False,
        show_default=True,
        help="Recursively process subdirectories.",
    )
    @functools.wraps(f)
    def common_wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return common_wrapper


# decorator to add common tags as options to click commands
def common_tag_options(f):
    @click.option(
        "--author",
        help="Author of the audiobook.",
    )
    @click.option(
        "--title",
        help="Title of the audiobook.",
    )
    @click.option(
        "--date",
        help="Publish date of the audiobook. Usually just the year.",
    )
    @click.option(
        "--genre",
        help="Genre of the audiobook.",
        multiple=True,
        type=click.Choice(GENRES),
    )
    @click.option(
        "--description",
        help="Description of the audiobook.",
    )
    @click.option(
        "--narrator",
        help="Narrator of the audiobook.",
    )
    @click.option(
        "--series-name",
        help="Series name the audiobook belongs to.",
    )
    @click.option(
        "--series-part",
        help="Part number of the series the audiobook belongs to. Number only. Decimals are allowed.",
        type=float,
    )
    @functools.wraps(f)
    def tag_wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return tag_wrapper


@click.group(context_settings=COMMON_CONTEXT)
@common_logging
def cli():
    """CLI for automating common audiobook compilation tasks, file organization, etc."""
    pass


# move all files in source directory and subdirectories to a new directory
# based on splitting the file name by a delimiter (" - ") and using the first
# part of the split as the new directory name, second part as the subdirectory,
# and the file name as the new file.
@cli.command(context_settings=COMMON_CONTEXT, name="organize")
@click.option(
    "--destination",
    "-d",
    default=CWD,
    show_default=False,
    help="Destination directory to organize files to. Defaults to current directory.",
)
@click.option(
    "--prune/--no-prune",
    default=False,
    show_default=True,
    help="Prune empty directories after moving files.",
)
@click.option(
    "--dir-mode",
    default="0775",
    show_default=True,
    help="Directory permissions mode to enforce.",
)
@click.option(
    "--file-mode",
    default="0664",
    show_default=True,
    help="File permissions mode to enforce.",
)
@common_logging
@common_options
# TODO use new file list function
def organize_files(
    source: str,
    destination: str,
    prune: bool,
    dir_mode: str,
    file_mode: str,
    recurse: bool,
):
    """
    Move files from source directory to destination directory.

    By default, this will parse filenames using the first part as main folder name,
    second part as subfolder name, and " - " as the split. Files are then moved into
    the subfolder.
    """
    LOG.debug(f"Source: '{source}'")
    LOG.debug(f"Destination: '{destination}'")
    LOG.debug(f"Prune: '{prune}'")
    LOG.debug(f"Dir mode: '{dir_mode}'")
    LOG.debug(f"File mode: '{file_mode}'")

    dir_mode_int: int = str_to_mode(dir_mode)
    LOG.debug(f"Calculated dir mode: '{dir_mode_int}'")
    file_mode_int: int = str_to_mode(file_mode)
    LOG.debug(f"Calculated file mode: '{file_mode_int}'")

    # create destination directory if it does not exist
    try:
        os.mkdir(destination)
    except FileExistsError:
        # This is fine, continue
        pass
    os.chmod(destination, dir_mode_int)

    # pattern to match
    pattern: re.Pattern = re.compile(r"^([^-]*) - (.*).m4b$")

    # TODO use new util.file function to get file list
    # os walk through current dir and all subdirectories
    for root, dirs, files in os.walk(source, topdown=False):
        for file in files:
            LOG.debug(f"Processing file: '{file}'")
            matches: list[Any] = pattern.findall(file)
            LOG.debug(f"Matches: '{matches}'")
            if len(matches) > 1:
                raise Exception("More than one match found")
            elif matches and len(matches[0]) == 2:
                LOG.debug(f"File split: '{matches[0]}'")
                LOG.debug(f"Root: '{root}'")
                # create the new directory name
                author_name: str = filter_path_name(matches[0][0])
                LOG.debug(f"Extracted author name: '{author_name}'")
                # create the new subdirectory name
                title_name: str = filter_path_name(matches[0][1])
                LOG.debug(f"Extracted title name: '{title_name}'")
                # create the new file name, filtering out annoying characters
                new_file: str = filter_path_name(file)
                LOG.debug(f"New file name: '{new_file}'")
                author_dir: str = os.path.join(destination, author_name)
                LOG.debug(f"Generated author directory: '{author_dir}'")
                title_dir: str = os.path.join(author_dir, title_name)
                LOG.debug(f"Generated title directory: '{title_dir}'")
                old_file_path: str = os.path.join(root, file)
                LOG.debug(f"Old file path: '{old_file_path}'")
                new_file_path: str = os.path.join(title_dir, new_file)
                LOG.debug(f"New file path: '{new_file_path}'")

                # Create destination directories as needed
                try:
                    os.mkdir(author_dir)
                except FileExistsError:
                    # This is fine, continue
                    pass
                os.chmod(author_dir, dir_mode_int)
                try:
                    os.mkdir(title_dir)
                except FileExistsError:
                    # This is fine, continue
                    pass
                os.chmod(title_dir, dir_mode_int)

                # move the file to the destination
                LOG.info(
                    f"Moving file '{old_file_path}' to '{new_file_path}'. This may take a while...."
                )
                # use shutil.copy because we don't really care about keeping metadata
                # that shutil.copy2 would keep, and it can cause unnecessary issues on
                # some filesystems
                try:
                    if os.path.isfile(new_file_path):
                        LOG.error(
                            f"File '{new_file_path}' already exists, skipping...."
                        )
                    else:
                        shutil.move(
                            old_file_path, new_file_path, copy_function=shutil.copy
                        )
                        # Set file permisisons
                        os.chmod(new_file_path, file_mode_int)
                        LOG.info(f"Done moving file '{old_file_path}'.")
                except Exception as e:
                    LOG.error(f"Error moving file '{old_file_path}': {e}")
                    continue

        if prune:
            LOG.debug("pruning empty directories.")
            for dir in dirs:
                prune_dir(os.path.join(root, dir))
            # prune the roots of each directory so long as it's not the cwd or the source dir
            if root not in [CWD, source]:
                prune_dir(root)


@cli.group(context_settings=COMMON_CONTEXT)
@common_logging
def tags():
    """Commands for editing audiobook tags."""
    pass


@tags.command(context_settings=COMMON_CONTEXT, name="set")
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


@tags.command(context_settings=COMMON_CONTEXT, name="print")
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


@tags.command(context_settings=COMMON_CONTEXT, name="verify")
@common_logging
@common_options
def verify_tags(source: str, recurse: bool):
    """Verify required audiobook tags are set and automatically set some (e.g. title and album) if missing. (not implemented)"""


@cli.command(context_settings=COMMON_CONTEXT, name="concat")
@click.option(
    "--source",
    "-s",
    default=CWD,
    show_default=False,
    help="Source directory to pull audio files from. Not recursive. Defaults to current directory.",
)
@click.option(
    "--destination",
    "-d",
    default=CWD,
    show_default=False,
    help="Destination directory to concatenate files to. Defaults to current directory.",
)
@click.option(
    "--format",
    "-f",
    default="mp3",
    show_default=True,
    help="File format to concatenate.",
)
@common_logging
@common_options
# TODO use rescurse / new file list function
def concat_files(source: str, recurse: bool, destination: str, format: str):
    """
    Concatenate audio files from source directory to destination .m4b
    file.

    Expects files to be in alphabetical order with a prepended number.
    The remaining filename gets used as chapter titles. '
    e.g. '01 Chapter 1.mp3', '0005 Chapter 5 - Riddles in the Dark.mp3'
    """

    def generate_metadata_file(files: list, destination: str, format: str):
        """Generate metadata file for ffmpeg to use for chapter markers."""
        LOG.debug(f"Generating metadata file for ffmpeg")
        LOG.debug(f"Files: '{files}'")
        LOG.debug(f"Destination: '{destination}'")
        LOG.debug(f"Format: '{format}'")

        chapters: list[dict[str, Any]] = []

        for file in files:
            LOG.debug(f"Processing file: '{file}'")
            file_path: str = os.path.join(destination, file)
            # extract chapter number from filename
            # ch_pattern: re.Pattern = re.compile(r"[^\d]*(\d+)\....$")
            ch_pattern: re.Pattern = re.compile(r"^(\d+)(.+)\.[^\.]+$")
            m = ch_pattern.match(file)
            LOG.debug(f"Match: {m}")
            number: str = m[1]
            title: str = m[2]
            LOG.debug(f"Extracted chapter number: '{number}'")

            # Build cmd
            cmd: str = (
                f"ffprobe -v quiet -of csv=p=0 -show_entries format=duration '{file_path}'"
            )
            LOG.debug(f"Running command: '{cmd}'")

            probe: subprocess.CompletedProcess = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
            )
            duration_in_microseconds = int(
                probe.stdout.decode().strip().replace(".", "")
            )
            LOG.debug(f"Duration in microseconds: {duration_in_microseconds}")
            chapters.append({"duration": duration_in_microseconds})
            chapters[-1]["title"] = title

        chapters[0]["start"] = 0
        for n in range(len(chapters)):
            chapter_index: int = n
            next_chapter_index: int = n + 1
            chapters[chapter_index]["end"] = (
                chapters[chapter_index]["start"] + chapters[chapter_index]["duration"]
            )
            try:
                chapters[next_chapter_index]["start"] = (
                    chapters[chapter_index]["end"] + 1
                )
            except IndexError:
                # last one, continue on
                pass

        metadata_path = os.path.join(destination, "metadata.txt")

        # Metadata file format spec https://ffmpeg.org/ffmpeg-formats.html#Metadata-2
        with open(metadata_path, "w+") as m:
            m.writelines(";FFMETADATA1\n")
            chapter: dict[str, Any]
            for chapter in chapters:
                ch_meta = """
[CHAPTER]
TIMEBASE=1/1000000
START={}
END={}
title={}""".format(
                    chapter["start"], chapter["end"], chapter["title"]
                )
                m.writelines(ch_meta)

    ##########################
    # Start of command logic #
    ##########################

    # create destination directory if it does not exist
    try:
        os.mkdir(destination)
    except FileExistsError:
        # This is fine, continue
        pass

    # list all files in source dir only (no subdirectories) for files to search through
    files: list[str] = os.listdir(source)
    LOG.debug(f"Files: '{files}'")

    # filter for the correct files
    audio_files: list[str] = [f for f in files if f.endswith(format)]

    # sort files by name
    audio_files.sort()

    LOG.info(f"generating metadata file for: {audio_files}")
    generate_metadata_file(files=audio_files, destination=destination, format=format)

    file_list_path: str = os.path.join(destination, "files.txt")
    mp4_path: str = os.path.join(destination, "output.mp4")
    m4b_path: str = os.path.join(destination, "output.m4b")
    metadata_path: str = os.path.join(destination, "metadata.txt")

    LOG.info(f"Generating file list for ffmpeg")
    with open(file_list_path, "w+") as f:
        for file in audio_files:
            f.write(f"file '{file}'\n")

    LOG.info(f"Concatenating files: {audio_files}")
    ffmpeg_cmd: str = (
        "ffmpeg -y "
        "-f concat "
        "-safe 0 "
        f"-i {file_list_path} "
        f"-i {metadata_path} "
        "-map_metadata 1 "
        "-c copy "
        f"{mp4_path}"
    )
    LOG.debug(f"ffmpeg command: {ffmpeg_cmd}")

    # run ffmpeg command
    try:
        s = subprocess.run(ffmpeg_cmd, shell=True)
        LOG.debug(f"ffmpeg output: {s}")
    except Exception as e:
        LOG.error(f"Error running ffmpeg: {e}")

    # rename output file to m4b
    shutil.move(
        os.path.join(destination, "output.mp4"), os.path.join(destination, "output.m4b")
    )

    LOG.info(
        f"Done concatenating files. Output file: {os.path.join(destination, 'output.m4b')}"
    )


if __name__ == "__main__":
    cli()
