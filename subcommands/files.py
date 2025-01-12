import os
import re
import shutil
import subprocess
from typing import Any

import click
from mutagen.mp4 import MP4

from util.constants import (
    COMMON_CONTEXT,
    LOG,
    SHITTY_REJECT_CHARACTERS_WE_HATES,
    TAG_DELIMITER,
)
from util.decorators import common_logging, common_options
from util.file import CWD, get_file_list
from util.mp4 import GENRES, Tag, pprint_tags


# move all files in source directory and subdirectories to a new directory
# based on splitting the file name by a delimiter (" - ") and using the first
# part of the split as the new directory name, second part as the subdirectory,
# and the file name as the new file.
@click.command(context_settings=COMMON_CONTEXT, name="organize")
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

    def filter_path_name(path: str) -> str:
        return "".join([c for c in path if c not in SHITTY_REJECT_CHARACTERS_WE_HATES])

    def str_to_mode(mode: str) -> int:
        # mode value is hexadecimal
        return int(mode, 8)

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

    # dirs to prune after
    prune_list: list[str] = []

    # os walk through current dir and all subdirectories
    for file in get_file_list(source, "m4b", recurse):
        LOG.debug(f"Processing file: '{file}'")

        title_name: str = ""
        author_name: str = ""

        # read author and title from tags, if available
        try:
            m4b: MP4 = MP4(file)
            LOG.debug(f"Album artist: {m4b[Tag.ALBUM_ARTIST.value]}")
            LOG.debug(f"Artist: {m4b[Tag.ARTIST.value]}")
            LOG.debug(f"Album: {m4b[Tag.ALBUM.value]}")
            LOG.debug(f"Title: {m4b[Tag.TRACK_TITLE.value]}")
        except Exception as e:
            LOG.error(f"Error reading tags: {e}\nFalling back to filename parsing.")

        try:
            # split the tags by delimiter in case there are multiple authors
            # we are NOT handling multiple tag entries for the same MP4 tag
            album_artist_tag: list[str] = m4b[Tag.ALBUM_ARTIST.value][0].split(
                TAG_DELIMITER
            )
            artist_tag: list[str] = m4b[Tag.ARTIST.value][0].split(TAG_DELIMITER)

            album_artist_tag.sort()
            artist_tag.sort()

            if album_artist_tag == artist_tag:
                author_name = album_artist_tag[0]
            else:
                LOG.error(
                    f"Album artist and artist tags do not match: {album_artist_tag}, {artist_tag}. "
                    "Falling back to filename parsing."
                )
        except KeyError:
            LOG.error(
                "No album artist or artist tag found. Falling back to filename parsing."
            )
        except Exception as e:
            LOG.error(f"Error reading tags: {e}")

        try:
            title_name_tag: str = m4b[Tag.TRACK_TITLE.value][0]
            album: str = m4b[Tag.ALBUM.value][0]
            if title_name_tag == album:
                title_name = title_name_tag
            else:
                LOG.error(
                    f"Title name and album tags do not match: {title_name_tag}, {album}. "
                    "Falling back to filename parsing."
                )
        except KeyError:
            LOG.error("No title tag found. Falling back to filename parsing.")
        except Exception as e:
            LOG.error(f"Error reading tags: {e}")

        if title_name and author_name:
            # Got both from tags
            pass
        else:
            # otherwise fall back to filename parsing
            matches: list[Any] = pattern.findall(os.path.basename(file))
            LOG.debug(f"Matches: '{matches}'")
            if len(matches) > 1:
                raise Exception("More than one match found")
            elif matches and len(matches[0]) == 2:
                LOG.debug(f"File split: '{matches[0]}'")
                # LOG.debug(f"Root: '{root}'")
                # create the new directory name
                author_name = filter_path_name(matches[0][0])
                LOG.debug(f"Extracted author name: '{author_name}'")
                # create the new subdirectory name
                title_name = filter_path_name(matches[0][1])
                LOG.debug(f"Extracted title name: '{title_name}'")
                # create the new file name, filtering out annoying characters
        new_file: str = filter_path_name(f"{author_name} - {title_name}.m4b")
        LOG.debug(f"New file name: '{new_file}'")
        author_dir: str = os.path.join(destination, filter_path_name(author_name))
        LOG.debug(f"Generated author directory: '{author_dir}'")
        title_dir: str = os.path.join(author_dir, filter_path_name(title_name))
        LOG.debug(f"Generated title directory: '{title_dir}'")
        old_file_path: str = file
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
                LOG.error(f"File '{new_file_path}' already exists, skipping....")
            else:
                shutil.move(old_file_path, new_file_path, copy_function=shutil.copy)
                # Set file permisisons
                os.chmod(new_file_path, file_mode_int)
                LOG.info(f"Done moving file '{old_file_path}'.")
        except Exception as e:
            LOG.error(f"Error moving file '{old_file_path}': {e}")
            continue

        # add the directory to the prune list
        parent_dir: str = os.path.dirname(old_file_path)
        if parent_dir not in prune_list:
            prune_list.append(parent_dir)

    if prune:
        LOG.debug("pruning empty directories.")
        LOG.debug(f"Prune list: '{prune_list}'")
        for dir in prune_list:
            try:
                LOG.debug(f"Pruning directory: '{dir}'")
                os.removedirs(dir)
            except Exception as e:
                LOG.error(f"Error pruning directory '{dir}': {e}")


@click.command(context_settings=COMMON_CONTEXT, name="concat")
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
# TODO use recurse / new file list function
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


@click.command(context_settings=COMMON_CONTEXT, name="autoname")
@common_logging
@common_options
def autoname_files(source: str, recurse: bool):
    """
    Automatically name files based on their metadata (Not implemented yet).
    """
    pass
