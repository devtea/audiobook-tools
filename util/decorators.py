import functools
import logging

import click

from util.file import CWD
from util.mp4 import GENRES


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
