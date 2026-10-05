import os
import re
import shlex
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
from util.file import CWD, chmod_and_continue, get_file_list, filter_path_name
from util.mp4 import GENRES, Tag, pprint_tags
from subcommands.tags import set_tags


def octal_mode(ctx: click.Context, param: click.Parameter, value: str) -> int:
    try:
        return int(value, 8)
    except ValueError:
        raise click.BadParameter(f"'{value}' is not an octal mode.")


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
    "--perms/--no-perms",
    default=True,
    show_default=True,
    help="Manage permissions on dirs and files",
)
@click.option(
    "--dir-mode",
    default="0775",
    show_default=True,
    callback=octal_mode,
    help="Directory permissions mode to enforce.",
)
@click.option(
    "--file-mode",
    default="0664",
    show_default=True,
    callback=octal_mode,
    help="File permissions mode to enforce.",
)
@common_logging
@common_options
def organize_files(
    source: str,
    destination: str,
    prune: bool,
    perms: bool,
    dir_mode: int,
    file_mode: int,
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
    LOG.debug(f"Manage Permissions: '{perms}'")
    LOG.debug(f"Dir mode: '{dir_mode:o}'")
    LOG.debug(f"File mode: '{file_mode:o}'")

    # create destination directory if it does not exist
    os.makedirs(destination, exist_ok=True)
    if perms: 
        chmod_and_continue(destination, dir_mode)

    # pattern to match
    pattern: re.Pattern = re.compile(r"^([^-]*) - (.*)\.m4b$")

    # dirs to prune after, never climbing above this root
    prune_list: list[str] = []
    prune_root: str = os.path.abspath(
        source if os.path.isdir(source) else os.path.dirname(source)
    )

    # os walk through current dir and all subdirectories
    files: list[str] = get_file_list(source, "m4b", recurse)
    if len(files) == 0:
        raise click.ClickException(f"No files found in '{source}'.")

    for file in files:
        LOG.debug(f"Processing file: '{file}'")

        title_name: str = ""
        author_name: str = ""
        m4b: MP4 | None = None

        # read author and title from tags, if available
        try:
            m4b = MP4(file)
            LOG.debug(f"Album artist: {m4b[Tag.ALBUM_ARTIST.value]}")
            LOG.debug(f"Artist: {m4b[Tag.ARTIST.value]}")
            LOG.debug(f"Album: {m4b[Tag.ALBUM.value]}")
            LOG.debug(f"Title: {m4b[Tag.TRACK_TITLE.value]}")
        except Exception as e:
            LOG.error(f"Error reading tags: {e}\nFalling back to filename parsing.")

        if m4b is not None:
            try:
                # split the tags by delimiter in case there are multiple authors
                # we are NOT handling multiple tag entries for the same MP4 tag
                album_artist_tag: list[str] = [
                    a.strip()
                    for a in m4b[Tag.ALBUM_ARTIST.value][0].split(TAG_DELIMITER)
                ]
                artist_tag: list[str] = [
                    a.strip() for a in m4b[Tag.ARTIST.value][0].split(TAG_DELIMITER)
                ]

                if sorted(album_artist_tag) == sorted(artist_tag):
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
            match: re.Match | None = pattern.match(os.path.basename(file))
            LOG.debug(f"Match: '{match}'")
            if match:
                author_name, title_name = match.groups()
                LOG.debug(f"Author name: '{author_name}'")
                LOG.debug(f"Title name: '{title_name}'")
            elif "-" in os.path.basename(file).split(" - ")[0]:
                LOG.warning(
                    f"Author in '{file}' appears to contain a hyphen, which filename "
                    "parsing cannot handle. Skipping."
                )
                continue
        if not (title_name and author_name):
            LOG.error(f"Could not determine author and title for '{file}', skipping.")
            continue

        # create the new file name, filtering out annoying characters
        new_file: str = filter_path_name(f"{author_name} - {title_name}.m4b")
        LOG.debug(f"Built file name: '{new_file}'")
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
        if perms: 
            chmod_and_continue(author_dir, dir_mode)
        try:
            os.mkdir(title_dir)
        except FileExistsError:
            # This is fine, continue
            pass
        if perms: 
            chmod_and_continue(title_dir, dir_mode)

        if os.path.abspath(old_file_path) == os.path.abspath(new_file_path):
            LOG.debug(f"File '{old_file_path}' is already organized, skipping.")
            continue

        if os.path.isfile(new_file_path):
            LOG.error(f"File '{new_file_path}' already exists, skipping....")
            continue

        if perms:
            # set perms locally before moving file
            chmod_and_continue(old_file_path, file_mode)

        # move the file to the destination
        LOG.info(
            f"Moving file '{old_file_path}' to '{new_file_path}'. This may take a while...."
        )
        try:
            # use shutil.copy because we don't really care about keeping metadata
            # that shutil.copy2 would keep, and it can cause unnecessary issues on
            # some filesystems
            shutil.move(old_file_path, new_file_path, copy_function=shutil.copy)
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
            dir = os.path.abspath(dir)
            while os.path.commonpath([dir, prune_root]) == prune_root:
                try:
                    LOG.debug(f"Pruning directory: '{dir}'")
                    os.rmdir(dir)
                except OSError as e:
                    LOG.debug(f"Stopped pruning at '{dir}': {e}")
                    break
                dir = os.path.dirname(dir)


@click.command(context_settings=COMMON_CONTEXT, name="convert")
@click.option(
    "--destination",
    "-d",
    default=None,
    show_default=False,
    help="Directory to write .m4b files to. Defaults to alongside each source file.",
)
@click.option(
    "--format",
    "-f",
    default="mp3",
    show_default=True,
    help="Input file extension to look for when source is a directory.",
)
@click.option(
    "--set-tags",
    "set_tags_after",
    is_flag=True,
    default=False,
    help="Run 'tags set' interactively on each new file after converting it.",
)
@common_logging
@common_options
def convert_files(
    source: str,
    recurse: bool,
    destination: str | None,
    format: str,
    set_tags_after: bool,
):
    """
    Convert each audio file individually to its own .m4b file.

    Unlike concat, files are not joined and need no particular naming. Tags
    are carried over. Existing output files are never overwritten.
    """
    files: list[str] = get_file_list(source, format, recurse)
    if not files:
        raise click.ClickException(f"No files found in '{source}'.")

    failed: bool = False
    for file in files:
        out_dir: str = destination or os.path.dirname(os.path.abspath(file))
        os.makedirs(out_dir, exist_ok=True)
        out_path: str = os.path.join(
            out_dir, os.path.splitext(os.path.basename(file))[0] + ".m4b"
        )
        if os.path.exists(out_path):
            LOG.error(f"Refusing to overwrite existing file '{out_path}'")
            failed = True
            continue

        probe: subprocess.CompletedProcess = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "stream=bit_rate",
                "-select_streams", "a", "-of", "default=noprint_wrappers=1:nokey=1",
                file,
            ],
            capture_output=True,
        )
        try:
            bitrate: int | None = int(probe.stdout)
        except ValueError:
            bitrate = None

        # Cap at 64k, but never encode above the source bitrate
        target_bitrate: int = min(bitrate or 64000, 64000)
        LOG.info(f"Converting '{file}' to '{out_path}'")
        s: subprocess.CompletedProcess = subprocess.run(
            [
                "ffmpeg", "-n", "-i", file, "-map", "0:a", "-map_metadata", "0",
                "-c:a", "aac", "-b:a", str(target_bitrate), "-f", "mp4", out_path,
            ],
            capture_output=True,
        )
        if s.returncode != 0:
            LOG.error(f"ffmpeg failed for '{file}': {s.stderr.decode()}")
            failed = True
        elif set_tags_after:
            click.get_current_context().invoke(set_tags, source=out_path)

    if failed:
        raise click.ClickException("One or more files could not be converted.")


@click.command(context_settings=COMMON_CONTEXT, name="concat")
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
def concat_files(source: str, recurse: bool, destination: str, format: str):
    """
    Concatenate audio files from source directory to destination .m4b
    file.

    Expects files to be in alphabetical order with a prepended number.
    The remaining filename gets used as chapter titles. '
    e.g. '01 Chapter 1.mp3', '0005 Chapter 5 - Riddles in the Dark.mp3'
    """

    def clean_ffmpeg_filename(filename: str) -> str:
        safe_chars: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
        # escape all characters that are not safe
        return "".join([c if c in safe_chars else f"\\{c}" for c in filename])

    def generate_metadata_file(files: list, destination: str, format: str):
        """Generate metadata file for ffmpeg to use for chapter markers."""
        LOG.debug(f"Generating metadata file for ffmpeg")
        LOG.debug(f"Files: '{files}'")
        LOG.debug(f"Destination: '{destination}'")
        LOG.debug(f"Format: '{format}'")

        chapters: list[dict[str, Any]] = []

        for file in files:
            LOG.debug(f"Processing file: '{file}'")
            file_path: str = file
            # extract chapter number from filename
            # ch_pattern: re.Pattern = re.compile(r"[^\d]*(\d+)\....$")
            ch_pattern: re.Pattern = re.compile(r"^(\d+)(.+)\.[^\.]+$")
            m = ch_pattern.match(os.path.basename(file))
            LOG.debug(f"Match: {m}")
            try:
                number: str = m[1]
                title: str = m[2]
            except TypeError as e:
                raise RuntimeError(
                    f"Error extracting chapter number from '{file}' - check your naming?"
                ) from e
            LOG.debug(f"Extracted chapter number: '{number}'")

            cmd: list[str] = [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-of",
                    "csv=p=0",
                    "-show_entries",
                    "format=duration",
                    file_path,
            ]
            LOG.debug(f"Running command: {cmd}")

            # Build cmd
            probe: subprocess.CompletedProcess = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
            )
            LOG.debug(f"Probe: {probe}")
            LOG.debug(f"Probe stdout: {probe.stdout}")
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
                    chapter["start"], chapter["end"], chapter["title"].strip()
                )
                m.writelines(ch_meta)

    ##########################
    # Start of command logic #
    ##########################

    # create destination directory if it does not exist
    os.makedirs(destination, exist_ok=True)

    # absolute paths, sorted by file name so the numeric prefix orders chapters
    audio_files: list[str] = sorted(
        (os.path.abspath(f) for f in get_file_list(source, format, recurse)),
        key=os.path.basename,
    )
    if not audio_files:
        raise click.ClickException(f"No files found in '{source}'.")

    LOG.info(f"generating metadata file for: {audio_files}")
    generate_metadata_file(files=audio_files, destination=destination, format=format)

    file_list_path: str = os.path.join(destination, "files.txt")
    mp4_path: str = os.path.join(destination, "output.mp4")
    m4b_path: str = os.path.join(destination, "output.m4b")
    metadata_path: str = os.path.join(destination, "metadata.txt")

    LOG.info(f"Generating file list for ffmpeg")
    with open(file_list_path, "w+") as f:
        for file in audio_files:
            f.write(f"file {clean_ffmpeg_filename(file)}\n")

    # check current bitrate of audio files
    bitrates: list[int] = []
    LOG.info(f"Checking bitrate of audio files: {audio_files}")
    for file in audio_files:
        cmd: list[str] = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=bit_rate",
            "-select_streams",
            "a",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file,
        ]
        LOG.debug(f"Running command: {cmd}")

        s: subprocess.CompletedProcess = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
        )
        LOG.debug(f"Output: {s}")
        try:
            bitrate = int(s.stdout)
            LOG.debug(f"Bitrate: {bitrate}")
            bitrates.extend([bitrate] if bitrate not in bitrates else [])
        except Exception as e:
            LOG.error(f"Error checking bitrate: {e}")
    LOG.debug(f"Bitrates: {bitrates}")

    LOG.info(f"Concatenating files: {audio_files}")
    # Cap at 64kbps, but never encode above the lowest source bitrate
    if len(bitrates) > 1:
        LOG.warning("Audio files have different bitrates.")
    target_bitrate: int = min([*bitrates, 64000])
    ffmpeg_cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        file_list_path,
        "-i",
        metadata_path,
        "-map_metadata",
        "1",
        "-c:a",
        "aac",
        "-b:a",
        str(target_bitrate),
        mp4_path,
    ]
    LOG.debug(f"ffmpeg command: {ffmpeg_cmd}")

    # run ffmpeg command
    try:
        s = subprocess.run(
            ffmpeg_cmd,
            shell=False,
            capture_output=True
        )
        LOG.debug(f"ffmpeg output: {s}")
    except Exception as e:
        LOG.error(f"Error running ffmpeg: {e}")

    # check command exit code
    if s.returncode != 0:
        raise RuntimeError(f"ffmpeg command failed with exit code {s.returncode}")

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
