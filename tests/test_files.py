import shutil

from click.testing import CliRunner

import subcommands.files
from mutagen.mp4 import MP4
from util.mp4 import Tag
from audiobook_tools import cli


def test_organize_unreadable_file_falls_back_to_filename(
    test_book, tmp_path, monkeypatch
):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    good = src / "good.m4b"
    shutil.copy(test_book, good)
    bad = src / "Jane Doe - Other Book.m4b"
    bad.write_text("not an mp4")
    # Readable file first so stale tags from it would leak into the unreadable one.
    monkeypatch.setattr(
        subcommands.files, "get_file_list", lambda *_: [str(good), str(bad)]
    )

    result = CliRunner().invoke(
        cli, ["files", "organize", "-s", str(src), "-d", str(dst), "--no-perms"]
    )

    assert result.exit_code == 0, result.output
    assert (dst / "Jane Doe" / "Other Book" / "Jane Doe - Other Book.m4b").is_file()


def test_organize_prune_stops_at_source(test_book, tmp_path):
    outer = tmp_path / "outer"
    src = outer / "books"
    dst = tmp_path / "dst"
    src.mkdir(parents=True)
    shutil.copy(test_book, src / "book.m4b")

    result = CliRunner().invoke(
        cli,
        [
            "files",
            "organize",
            "-s",
            str(src),
            "-d",
            str(dst),
            "--recurse",
            "--prune",
            "--no-perms",
        ],
    )

    assert result.exit_code == 0, result.output
    assert outer.is_dir()


def organize(*args):
    return CliRunner().invoke(cli, ["files", "organize", "--no-perms", *args])


def test_organize_skips_file_without_author_or_title(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    bad = src / "unparseable.m4b"
    bad.write_text("not an mp4")

    result = organize("-s", str(src), "-d", str(dst), "--recurse")

    assert result.exit_code == 0, result.output
    assert bad.is_file()
    assert list(dst.iterdir()) == []


def test_organize_leaves_skipped_file_permissions_alone(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    book = src / "Jane Doe - Book.m4b"
    book.write_text("not an mp4")
    book.chmod(0o600)
    existing = dst / "Jane Doe" / "Book" / "Jane Doe - Book.m4b"
    existing.parent.mkdir(parents=True)
    existing.write_text("already here")

    result = CliRunner().invoke(
        cli, ["files", "organize", "-s", str(src), "-d", str(dst), "--recurse"]
    )

    assert result.exit_code == 0, result.output
    assert book.stat().st_mode & 0o777 == 0o600


def test_organize_uses_first_listed_of_multiple_authors(test_book, tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    book = src / "book.m4b"
    shutil.copy(test_book, book)
    m4b = MP4(book)
    m4b[Tag.ALBUM_ARTIST.value] = "B Author; A Author"
    m4b[Tag.ARTIST.value] = "A Author;B Author"
    m4b.save()

    result = organize("-s", str(src), "-d", str(dst), "--recurse")

    assert result.exit_code == 0, result.output
    assert (dst / "B Author" / "Luminous" / "B Author - Luminous.m4b").is_file()
