import subprocess

from click.testing import CliRunner
from mutagen.mp4 import MP4

from audiobook_tools import cli
from util.mp4 import Tag


def run_convert(*args):
    return CliRunner().invoke(cli, ["files", "convert", *args])


def probe(path, entry):
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            f"stream={entry}",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def test_convert_single_file_without_numeric_prefix(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Plain Name.mp3")

    result = run_convert("--source", str(src))

    assert result.exit_code == 0, result.output
    out = tmp_path / "Plain Name.m4b"
    assert out.exists()
    assert probe(out, "codec_name") == "aac"


def test_convert_directory_converts_each_file_separately(tmp_path, make_mp3):
    make_mp3(tmp_path / "Book One.mp3")
    make_mp3(tmp_path / "Book Two.mp3")

    result = run_convert("--source", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert (tmp_path / "Book One.m4b").exists()
    assert (tmp_path / "Book Two.m4b").exists()
    assert not (tmp_path / "output.m4b").exists()


def test_convert_writes_to_destination(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Book.mp3")
    dest = tmp_path / "out"

    result = run_convert("--source", str(src), "--destination", str(dest))

    assert result.exit_code == 0, result.output
    assert (dest / "Book.m4b").exists()
    assert not (tmp_path / "Book.m4b").exists()


def test_convert_preserves_tags(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Book.mp3", title="My Title", artist="My Author")

    result = run_convert("--source", str(src))

    assert result.exit_code == 0, result.output
    tags = MP4(tmp_path / "Book.m4b")
    assert tags[Tag.TRACK_TITLE.value] == ["My Title"]
    assert tags[Tag.ARTIST.value] == ["My Author"]


def test_convert_transcodes_high_bitrate_down_to_64k(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Book.mp3", bitrate="192k")

    result = run_convert("--source", str(src))

    assert result.exit_code == 0, result.output
    assert int(probe(tmp_path / "Book.m4b", "bit_rate")) <= 70000


def test_convert_refuses_to_overwrite_existing_output(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Book.mp3")
    existing = tmp_path / "Book.m4b"
    existing.write_bytes(b"keep me")

    result = run_convert("--source", str(src))

    assert result.exit_code != 0
    assert existing.read_bytes() == b"keep me"


def test_convert_exits_nonzero_when_no_files_found(tmp_path):
    result = run_convert("--source", str(tmp_path))

    assert result.exit_code != 0


def test_convert_set_tags_flag_runs_tags_set_on_new_file(tmp_path, make_mp3):
    # A long comment keeps 'tags set' from opening an editor for the description.
    src = make_mp3(
        tmp_path / "Book.mp3",
        title="My Title",
        artist="My Author",
        comment="A long description. " * 10,
    )

    # Prompts in order: narrator, genre (blank to finish), series (decline),
    # year, decline further changes, confirm saving, then accept the rename.
    result = CliRunner().invoke(
        cli,
        ["files", "convert", "--source", str(src), "--set-tags"],
        input="My Narrator\n\nn\n2020\nn\ny\ny\n",
    )

    assert result.exit_code == 0, result.output
    tags = MP4(tmp_path / "My Author - My Title.m4b")
    assert tags[Tag.NARRATOR.value] == ["My Narrator"]
    assert tags[Tag.YEAR.value] == ["2020"]
    assert tags[Tag.ALBUM.value] == ["My Title"]


def test_convert_never_raises_bitrate_above_source(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Book.mp3", bitrate="32k")

    result = run_convert("--source", str(src))

    assert result.exit_code == 0, result.output
    assert int(probe(tmp_path / "Book.m4b", "bit_rate")) <= 40000


def test_convert_keeps_original_by_default(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Book.mp3")

    result = run_convert("--source", str(src))

    assert result.exit_code == 0, result.output
    assert src.exists()


def test_convert_cleanup_removes_original_after_success(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Book.mp3")

    result = run_convert("--source", str(src), "--cleanup")

    assert result.exit_code == 0, result.output
    assert (tmp_path / "Book.m4b").exists()
    assert not src.exists()


def test_convert_cleanup_keeps_original_when_conversion_fails(tmp_path):
    src = tmp_path / "Broken.mp3"
    src.write_bytes(b"not audio")

    result = run_convert("--source", str(src), "--cleanup")

    assert result.exit_code != 0
    assert src.exists()


def test_convert_cleanup_keeps_original_when_output_exists(tmp_path, make_mp3):
    src = make_mp3(tmp_path / "Book.mp3")
    (tmp_path / "Book.m4b").write_bytes(b"keep me")

    result = run_convert("--source", str(src), "--cleanup")

    assert result.exit_code != 0
    assert src.exists()


def run_concat(monkeypatch, directory):
    monkeypatch.chdir(directory)
    return CliRunner().invoke(
        cli, ["files", "concat", "--source", ".", "--destination", "."]
    )


def test_concat_never_raises_bitrate_above_source(tmp_path, make_mp3, monkeypatch):
    make_mp3(tmp_path / "01 One.mp3", bitrate="32k")

    result = run_concat(monkeypatch, tmp_path)

    assert result.exit_code == 0, result.output
    assert int(probe(tmp_path / "output.m4b", "bit_rate")) <= 40000


def test_concat_mixed_bitrates_use_lowest_source_bitrate(
    tmp_path, make_mp3, monkeypatch
):
    make_mp3(tmp_path / "01 One.mp3", bitrate="32k")
    make_mp3(tmp_path / "02 Two.mp3", bitrate="48k")

    result = run_concat(monkeypatch, tmp_path)

    assert result.exit_code == 0, result.output
    assert int(probe(tmp_path / "output.m4b", "bit_rate")) <= 40000


def test_concat_caps_high_bitrate_at_64k(tmp_path, make_mp3, monkeypatch):
    make_mp3(tmp_path / "01 One.mp3", bitrate="192k")

    result = run_concat(monkeypatch, tmp_path)

    assert result.exit_code == 0, result.output
    assert int(probe(tmp_path / "output.m4b", "bit_rate")) <= 70000


def test_concat_declares_each_option_once():
    concat = cli.commands["files"].commands["concat"]
    flags = [opt for param in concat.params for opt in param.opts]
    assert len(flags) == len(set(flags))


def chapter_titles(path):
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "chapter_tags=title",
            "-of", "csv=p=0", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.split()


def test_concat_works_when_source_and_destination_differ(
    tmp_path, make_mp3, monkeypatch
):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    cwd = tmp_path / "elsewhere"
    for d in (src, cwd):
        d.mkdir()
    make_mp3(src / "01 One.mp3", bitrate="32k")
    make_mp3(src / "02 Two.mp3", bitrate="32k")
    monkeypatch.chdir(cwd)

    result = CliRunner().invoke(
        cli,
        ["files", "concat", "--source", str(src), "--destination", str(dest)],
    )

    assert result.exit_code == 0, result.output
    assert chapter_titles(dest / "output.m4b") == ["One", "Two"]
    assert int(probe(dest / "output.m4b", "bit_rate")) <= 40000


def test_concat_recurse_includes_subdirectories(tmp_path, make_mp3):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    make_mp3(src / "01 One.mp3")
    make_mp3(src / "sub" / "02 Two.mp3")
    dest = tmp_path / "dest"

    result = CliRunner().invoke(
        cli,
        [
            "files", "concat", "--source", str(src), "--destination", str(dest),
            "--recurse",
        ],
    )

    assert result.exit_code == 0, result.output
    assert chapter_titles(dest / "output.m4b") == ["One", "Two"]
