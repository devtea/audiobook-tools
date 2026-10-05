import shutil

from click.testing import CliRunner

import subcommands.files
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
