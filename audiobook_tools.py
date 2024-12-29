#!/usr/bin/env python3
import functools
import os
import re
import shutil
import logging

import click

COMMON_CONTEXT = dict(help_option_names=["-h", "--help"])
CWD = os.getcwd()
DIR_MODE = 0o777
FILE_MODE = 0o666
LOG = logging.getLogger(__name__)
SHITTY_REJECT_CHARACTERS_WE_HATES = [
    "'",
    '"',
]


def filter_path_name(path: str) -> str:
    return "".join([c for c in path if c not in SHITTY_REJECT_CHARACTERS_WE_HATES])


def prune_dir(dir: str):
    LOG.debug(f"Checking directory: {dir}")
    try:
        os.rmdir(dir)
        LOG.info(f"Pruned empty directory {dir}")
    except OSError:
        LOG.info(f"Directory not empty when trying to prune: {dir}")


# decorator to add common logging level argument to click commands
def with_log_level(f):
    @click.option(
        "--log-level",
        "-l",
        default="ERROR",
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
    """Organize files from source directory to destination directory."""
    LOG.debug(f"Destination: {destination}")

    os.umask(0o000)  # Eww.... but it's how the systems are currently configured to work

    # create destination directory if it does not exist
    try:
        os.mkdir(destination)
    except FileExistsError:
        # This is fine, confirm perms
        os.chmod(destination, DIR_MODE)

    # pattern to match
    pattern = re.compile(r"^([^-]*) - (.*).m4b$")

    # os walk through current dir and all subdirectories
    for root, dirs, files in os.walk(source, topdown=False):
        for file in files:
            LOG.info(f"Processing file: {file}")
            matches = pattern.findall(file)
            LOG.debug(f"Matches: {matches}")
            if len(matches) > 1:
                raise Exception("More than one match found")
            elif matches and len(matches[0]) == 2:
                LOG.debug(f"File split: {matches[0]}")
                LOG.debug(f"Root: {root}")
                # create the new directory name
                author_name = filter_path_name(matches[0][0])
                LOG.debug(f"Extracted author name: {author_name}")
                # create the new subdirectory name
                title_name = filter_path_name(matches[0][1])
                LOG.debug(f"Extracted title name: {title_name}")
                # create the new file name, filtering out annoying characters
                new_file = filter_path_name(file)
                LOG.debug(f"New file name: {new_file}")
                author_dir = os.path.join(destination, author_name)
                LOG.debug(f"Generated author directory: {author_dir}")
                title_dir = os.path.join(author_dir, title_name)
                LOG.debug(f"Generated title directory: {title_dir}")
                old_file_path = os.path.join(root, file)
                LOG.debug(f"Old file path: {old_file_path}")
                new_file_path = os.path.join(title_dir, new_file)
                LOG.debug(f"New file path: {new_file_path}")

                # Create destination directories as needed
                try:
                    os.mkdir(author_dir)
                except FileExistsError:
                    # This is fine, confirm perms
                    os.chmod(author_dir, DIR_MODE)
                try:
                    os.mkdir(title_dir)
                except FileExistsError:
                    # This is fine, confirm perms
                    os.chmod(title_dir, DIR_MODE)

                # move the file to the destination
                LOG.info(f"Moving file {old_file_path} to {new_file_path}")
                shutil.move(old_file_path, new_file_path)
                # Set file permisisons
                os.chmod(new_file_path, FILE_MODE)

        LOG.debug("pruning empty directories.")
        for dir in dirs:
            prune_dir(os.path.join(root, dir))
        # prune the roots of each directory so long as it's not the cwd
        if root != CWD:
            prune_dir(root)


if __name__ == "__main__":
    cli(auto_envvar_prefix="CLI")
