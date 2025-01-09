"""Utilities for mp4 files."""

import enum
import click
from mutagen.mp4 import MP4

GENRES = [
    "Apocalyptic & Dystopian",
    "Art",
    "Biography & Memoir",
    "Body, Mind, & Spirit",
    "Business",
    "Children's",
    "Classics",
    "Cooking",
    "Education",
    "Environment & Nature",
    "Erotica",
    "Essays",
    "Family & Relationships",
    "Fantasy",
    "Fiction - Literary",
    "Fiction",
    "Health",
    "Historical Fiction",
    "History",
    "Horror",
    "Humor",
    "LGBTQIA+ Fiction",
    "LGBTQIA+ Nonfiction",
    "Language",
    "Law",
    "Literary Criticism",
    "Medicine",
    "Music",
    "Mystery & Thriller",
    "Nonfiction",
    "Performance",
    "Perspectives on Disability",
    "Philosophy",
    "Poetry",
    "Politics & Economy",
    "Psychology",
    "Religion",
    "Romance",
    "Science & Technology",
    "Science Fiction",
    "Self-Improvement",
    "Short Stories",
    "Social Science",
    "Sports & Recreation",
    "Travel",
    "True Crime",
    "Westerns",
    "YA Fiction",
    "YA Nonfiction",
]


# Enum to map human readable tag names to mp4 tag names.
# Mostly stolen from Mutagen's docs
class Tag(enum.Enum):
    ALBUM = "\xa9alb"
    ALBUM_ARTIST = "aART"
    ARTIST = "\xa9ART"
    COMMENT = "\xa9cmt"
    COVER = "covr"
    DESCRIPTION = "desc"
    GENRE = "\xa9gen"
    # Technically COMPOSER tag, but it's always the narrator for books.
    NARRATOR = "\xa9wrt"
    SERIES_NAME = "----:com.apple.iTunes:SRNM"
    SERIES_PART = "----:com.apple.iTunes:SRSQ"
    TRACK_TITLE = "\xa9nam"
    YEAR = "\xa9day"


# function to print current tags
def pprint_tags(file: MP4, pause: bool = True) -> None:
    click.clear()
    click.echo("Tags for file: {file}")
    click.echo("Current tags:")
    click.echo("-------------")
    click.echo(file.tags.pprint())  # type: ignore
    click.echo("")
    if pause:
        click.echo("Press 'enter' to continue.")
        click.prompt("")
    else:
        click.echo("")
