#!/usr/bin/env python3
import functools
import io
import os
from pathlib import Path
import re
import shutil
import sys
import logging

import click

CWD = os.getcwd()
COMMON_CONTEXT = dict(help_option_names=["-h", "--help"])
LOG = logging.getLogger(__name__)


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
        logging.basicConfig(level=log_level)
        return f(*args, **kwargs)

    return wrapper


def prune_dir(dir: str):
    LOG.info(f"Checking directory: {dir}")
    try:
        os.rmdir(dir)
        LOG.info(f"Pruned empty directory {dir}")
    except OSError:
        LOG.warning(f"Directory not empty when trying to prune: {dir}")


@click.group(context_settings=COMMON_CONTEXT, invoke_without_command=True)
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
    LOG.info(f"Destination: {destination}")

    # os walk through current dir and all subdirectories
    for root, dirs, files in os.walk(source, topdown=False):
        for file in files:
            LOG.info(f"Processing file: {file}")
            # pattern to match
            pattern = re.compile(r"^(.*) - (.*).m4b$")
            matches = pattern.findall(file)
            LOG.info(f"Matches: {matches}")
            if len(matches) > 1:
                raise Exception("More than one match found")
            elif matches and len(matches[0]) == 2:
                LOG.info(f"File split: {matches[0]}")
                LOG.info(f"Root: {root}")
                # create the new directory name
                new_dir = matches[0][0]
                # create the new subdirectory name
                new_subdir = matches[0][1]
                # create the new file name
                new_file = file
                # create the new file path
                new_file_path = os.path.join(destination, new_dir, new_subdir, new_file)
                # create the new directory path
                new_dir_path = os.path.join(destination, new_dir, new_subdir)
                # if the new directory does not exist, create it
                if not os.path.exists(new_dir_path):
                    os.makedirs(new_dir_path)
                # move the file to the new file path
                shutil.move(os.path.join(root, file), new_file_path)

                # chmod the directories as 755
                os.chmod(new_dir_path, 0o755)
                # chmod the files as 644
                os.chmod(new_file_path, 0o644)

        LOG.info("pruning empty directories.")
        for dir in dirs:
            prune_dir(os.path.join(root, dir))
        # prune the roots of each directory so long as it's not the cwd
        if root != CWD:
            prune_dir(root)


# main
if __name__ == "__main__":
    cli(auto_envvar_prefix="CLI")
