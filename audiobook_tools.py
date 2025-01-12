#!/usr/bin/env python3
from time import sleep

import click

from util.constants import COMMON_CONTEXT, LOG
from subcommands.files import organize_files, concat_files, autoname_files
from subcommands.tags import set_tags, print_tags, verify_tags
from util.file import CWD
from util.decorators import common_logging


@click.group(context_settings=COMMON_CONTEXT)
@common_logging
def cli():
    """CLI for automating common audiobook compilation tasks, file organization, etc."""
    pass


@cli.group(context_settings=COMMON_CONTEXT)
@common_logging
def tags():
    """Commands for editing audiobook tags."""
    pass


# tags subcommands
tags.add_command(print_tags)
tags.add_command(set_tags)
tags.add_command(verify_tags)


@cli.group(context_settings=COMMON_CONTEXT)
@common_logging
def files():
    """Commands for working with audio files."""
    pass


# files subcommands
files.add_command(organize_files)
files.add_command(concat_files)
files.add_command(autoname_files)

if __name__ == "__main__":
    cli()
