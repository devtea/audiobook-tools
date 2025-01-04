#!/usr/bin/env python3
import functools
import os
import re
import shutil
import logging
import subprocess
from typing import Any


import click

COMMON_CONTEXT: dict = dict(help_option_names=["-h", "--help"])
CWD: str = os.getcwd()
DIR_MODE: int = 0o777
FILE_MODE: int = 0o666
LOG: logging.Logger = logging.getLogger(__name__)
SHITTY_REJECT_CHARACTERS_WE_HATES: list[str] = [
    "'",
    '"',
]


def filter_path_name(path: str) -> str:
    return "".join([c for c in path if c not in SHITTY_REJECT_CHARACTERS_WE_HATES])


def prune_dir(dir: str) -> None:
    LOG.debug(f"Checking directory: '{dir}'")
    try:
        os.rmdir(dir)
        LOG.debug(f"Pruned empty directory '{dir}'")
    except OSError:
        LOG.warning(f"Directory not empty when trying to prune: '{dir}'")


# decorator to add common logging level argument to click commands
def with_log_level(f):
    @click.option(
        "--log-level",
        "-l",
        default="INFO",
        show_default=True,
        help="Logging level.",
        type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    )
    @functools.wraps(f)
    def wrapper(log_level, *args, **kwargs):
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S%Z",
        )
        return f(*args, **kwargs)

    return wrapper


@click.group(context_settings=COMMON_CONTEXT)
@with_log_level
def cli():
    """CLI for automating file organization."""
    pass


@cli.group(context_settings=COMMON_CONTEXT)
@with_log_level
def tags():
    """CLI for editing audiobook tags."""
    pass


# move all files in current directory and subdirectories to a new directory
# based on splitting the file name by a delimiter (" - ") and using the first
# part of the split as the new directory name, second part as the subdirectory,
# and the file name as the new file.
@cli.command(context_settings=COMMON_CONTEXT, name="organize")
@click.option(
    "--source",
    "-s",
    default=CWD,
    show_default=False,
    help="Source directory to organize files from. Defaults to current directory.",
)
@click.option(
    "--destination",
    "-d",
    default=CWD,
    show_default=False,
    help="Destination directory to organize files to. Defaults to current directory.",
)
def organize_files(source: str, destination: str):
    """Organize files from source directory to destination directory based on file name parsing."""
    LOG.debug(f"Destination: '{destination}'")

    # create destination directory if it does not exist
    try:
        os.mkdir(destination)
    except FileExistsError:
        # This is fine, continue
        pass
    os.chmod(destination, DIR_MODE)

    # pattern to match
    pattern: re.Pattern = re.compile(r"^([^-]*) - (.*).m4b$")

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
                os.chmod(author_dir, DIR_MODE)
                try:
                    os.mkdir(title_dir)
                except FileExistsError:
                    # This is fine, continue
                    pass
                os.chmod(title_dir, DIR_MODE)

                # move the file to the destination
                LOG.info(
                    f"Moving file '{old_file_path}' to '{new_file_path}'. This may take a while...."
                )
                # use shutil.copy because we don't really care about keeping metadata
                # that shutil.copy2 would keep, and it can cause unnecessary issues on
                # some filesystems
                try:
                    shutil.move(old_file_path, new_file_path, copy_function=shutil.copy)
                    # Set file permisisons
                    os.chmod(new_file_path, FILE_MODE)
                    LOG.info(f"Done moving file '{old_file_path}'.")
                except Exception as e:
                    LOG.error(f"Error moving file '{old_file_path}': {e}")
                    continue

        LOG.debug("pruning empty directories.")
        for dir in dirs:
            prune_dir(os.path.join(root, dir))
        # prune the roots of each directory so long as it's not the cwd or the source dir
        if root not in [CWD, source]:
            prune_dir(root)


@tags.command(context_settings=COMMON_CONTEXT, name="set")
def set_tags():
    """Set audiobook tags interactively."""
    pass


@tags.command(context_settings=COMMON_CONTEXT, name="verify")
def verify_tags():
    """Verify audiobook tags."""
    pass


@cli.command(context_settings=COMMON_CONTEXT, name="concat")
@click.option(
    "--source",
    "-s",
    default=CWD,
    show_default=False,
    help="Source directory to concatenate files from. Defaults to current directory.",
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
def concat_files(source: str, destination: str, format: str):
    """Concatenate audio files from source directory to destination .m4b file. Expects files to be in alphabetical order with a prepended number. The remaining filename gets used as chapter titles. e.g. '01 - Chapter 1.mp3'"""

    def make_chapters_metadata(files: list, destination: str, format: str):
        print(f"Making metadata source file")

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
            chapter_index = n
            next_chapter_index = n + 1
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
        # last_chapter = f"{len(chapters):04d}"
        # chapters[last_chapter]["end"] = chapters[last_chapter]["start"] + chapters[last_chapter]["duration"]

        metadatafile = os.path.join(destination, "metadata.txt")

        with open(metadatafile, "w+") as m:
            m.writelines(";FFMETADATA1\n")
            for chapter_index in chapters:
                ch_meta = """
[CHAPTER]
TIMEBASE=1/1000000
START={}
END={}
title={}""".format(
                    chapter_index["start"], chapter_index["end"], chapter_index["title"]
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
    make_chapters_metadata(files=audio_files, destination=destination, format=format)

    LOG.info(f"Generating file list for ffmpeg")
    with open(os.path.join(destination, "files.txt"), "w+") as f:
        for file in audio_files:
            f.write(f"file '{file}'\n")

    LOG.info(f"Concatenating files: {audio_files}")
    ffmpeg_cmd: str = (
        "ffmpeg -y "
        "-f concat "
        "-safe 0 "
        f"-i {os.path.join(destination, 'files.txt')} "
        f"-i {os.path.join(destination, 'metadata.txt')} "
        "-map_metadata 1 "
        "-c copy "
        f"{os.path.join(destination, 'output.mp4')}"
    )
    LOG.debug(f"ffmpeg command: {ffmpeg_cmd}")

    try:
        s = subprocess.run(ffmpeg_cmd, shell=True)
        LOG.debug(f"ffmpeg output: {s}")
    except Exception as e:
        LOG.error(f"Error running ffmpeg: {e}")

    shutil.move(
        os.path.join(destination, "output.mp4"), os.path.join(destination, "output.m4b")
    )

    LOG.info(
        f"Done concatenating files. Output file: {os.path.join(destination, 'output.m4b')}"
    )


if __name__ == "__main__":
    cli()
