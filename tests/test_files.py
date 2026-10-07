import shutil
from pathlib import Path

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


def test_organize_creates_nested_destination(test_book, tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "a" / "b"
    src.mkdir()
    shutil.copy(test_book, src / "book.m4b")

    result = organize("-s", str(src), "-d", str(dst), "--recurse")

    assert result.exit_code == 0, result.output
    assert (dst / "Silvia Park" / "Luminous" / "Silvia Park - Luminous.m4b").is_file()


def test_organize_fails_when_no_files_found(tmp_path):
    result = organize("-s", str(tmp_path), "-d", str(tmp_path / "dst"), "--recurse")

    assert result.exit_code != 0
    assert "No files found" in result.output


def test_organize_rejects_invalid_mode(tmp_path):
    result = organize("-s", str(tmp_path), "--dir-mode", "0999")

    assert result.exit_code == 2
    assert "Invalid value for '--dir-mode'" in result.output


def test_organize_finds_files_in_other_dir_without_recurse(test_book, tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    shutil.copy(test_book, src / "book.m4b")

    result = organize("-s", str(src), "-d", str(dst))

    assert result.exit_code == 0, result.output
    assert (dst / "Silvia Park" / "Luminous" / "Silvia Park - Luminous.m4b").is_file()


def test_organize_warns_and_skips_hyphenated_author(tmp_path, caplog):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    book = src / "Jean-Luc Picard - Book.m4b"
    book.write_text("not an mp4")

    result = organize("-s", str(src), "-d", str(dst))

    assert result.exit_code == 0, result.output
    assert book.is_file()
    assert list(dst.iterdir()) == []
    assert any(
        r.levelname == "WARNING" and "hyphen" in r.getMessage() for r in caplog.records
    )


def test_organize_in_place_skips_already_organized_file_quietly(
    test_book, tmp_path, caplog
):
    book = tmp_path / "Silvia Park" / "Luminous" / "Silvia Park - Luminous.m4b"
    book.parent.mkdir(parents=True)
    shutil.copy(test_book, book)

    result = organize("-s", str(tmp_path), "-d", str(tmp_path), "--recurse")

    assert result.exit_code == 0, result.output
    assert book.is_file()
    assert not any(r.levelname == "ERROR" for r in caplog.records)


def make_book(test_book, path, narrator):
    """Copy the fixture to path, setting (or clearing) its narrator tag."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(test_book, path)
    m4b = MP4(path)
    if narrator is None:
        del m4b[Tag.NARRATOR.value]
    else:
        m4b[Tag.NARRATOR.value] = narrator
    m4b.save()
    return path


PLAIN = Path("Silvia Park") / "Luminous" / "Silvia Park - Luminous.m4b"


def test_organize_uses_narrator_folder_when_narrator_differs(test_book, tmp_path):
    dst = tmp_path / "dst"
    existing = make_book(test_book, dst / PLAIN, "Narrator One")
    incoming = make_book(test_book, tmp_path / "src" / "book.m4b", "Narrator Two")

    result = organize("-s", str(tmp_path / "src"), "-d", str(dst), "--recurse")

    assert result.exit_code == 0, result.output
    assert existing.is_file()
    assert not incoming.exists()
    assert (
        dst / "Silvia Park" / "Luminous {Narrator Two}" / "Silvia Park - Luminous.m4b"
    ).is_file()


def test_organize_joins_multiple_narrators_in_folder_name(test_book, tmp_path):
    dst = tmp_path / "dst"
    make_book(test_book, dst / PLAIN, "Narrator One")
    make_book(test_book, tmp_path / "src" / "book.m4b", "Narrator Two;Narrator Three")

    result = organize("-s", str(tmp_path / "src"), "-d", str(dst), "--recurse")

    assert result.exit_code == 0, result.output
    assert (
        dst
        / "Silvia Park"
        / "Luminous {Narrator Two, Narrator Three}"
        / "Silvia Park - Luminous.m4b"
    ).is_file()


def test_organize_skips_collision_with_same_narrator(test_book, tmp_path, caplog):
    dst = tmp_path / "dst"
    make_book(test_book, dst / PLAIN, "Narrator One")
    incoming = make_book(test_book, tmp_path / "src" / "book.m4b", "Narrator One")

    result = organize("-s", str(tmp_path / "src"), "-d", str(dst), "--recurse")

    assert result.exit_code == 0, result.output
    assert incoming.is_file()
    assert [p.name for p in (dst / "Silvia Park").iterdir()] == ["Luminous"]
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_organize_skips_collision_when_a_narrator_is_missing(
    test_book, tmp_path, caplog
):
    dst = tmp_path / "dst"
    make_book(test_book, dst / PLAIN, None)
    incoming = make_book(test_book, tmp_path / "src" / "book.m4b", "Narrator Two")

    result = organize("-s", str(tmp_path / "src"), "-d", str(dst), "--recurse")

    assert result.exit_code == 0, result.output
    assert incoming.is_file()
    assert [p.name for p in (dst / "Silvia Park").iterdir()] == ["Luminous"]
    assert any("narrator" in r.getMessage() for r in caplog.records)


def test_organize_in_place_leaves_both_recordings_alone(test_book, tmp_path, caplog):
    plain = make_book(test_book, tmp_path / PLAIN, "Narrator One")
    other = make_book(
        test_book,
        tmp_path
        / "Silvia Park"
        / "Luminous {Narrator Two}"
        / "Silvia Park - Luminous.m4b",
        "Narrator Two",
    )

    result = organize("-s", str(tmp_path), "-d", str(tmp_path), "--recurse")

    assert result.exit_code == 0, result.output
    assert plain.is_file() and other.is_file()
    assert not any(r.levelname == "ERROR" for r in caplog.records)


def test_organize_separates_two_recordings_moved_in_one_run(test_book, tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    make_book(test_book, src / "a" / "book.m4b", "Narrator One")
    make_book(test_book, src / "b" / "book.m4b", "Narrator Two")

    result = organize("-s", str(src), "-d", str(dst), "--recurse")

    assert result.exit_code == 0, result.output
    narrators = sorted(MP4(p)[Tag.NARRATOR.value][0] for p in dst.rglob("*.m4b"))
    assert narrators == ["Narrator One", "Narrator Two"]
    folders = [p.name for p in (dst / "Silvia Park").iterdir()]
    assert "Luminous" in folders
    assert len(folders) == 2 and any(f.startswith("Luminous {") for f in folders)
