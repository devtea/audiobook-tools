import logging

import pytest
from click.testing import CliRunner
from mutagen.mp4 import MP4

from audiobook_tools import cli

# Prompts in order: narrator, genre (blank to finish), series (decline), year,
# decline further changes, confirm saving, then accept the rename.
SET_TAGS_INPUT = "My Narrator\n\nn\n2020\nn\ny\ny\n"


def make_m4b(tmp_path, make_mp3):
    # A long comment keeps 'tags set' from opening an editor for the description.
    src = make_mp3(
        tmp_path / "Book.mp3",
        title="My Title",
        artist="My Author",
        comment="A long description. " * 10,
    )
    result = CliRunner().invoke(cli, ["files", "convert", "--source", str(src)])
    assert result.exit_code == 0, result.output
    return tmp_path / "Book.m4b"


def run_set_tags(path, input):
    return CliRunner().invoke(cli, ["tags", "set", "--source", str(path)], input=input)


def test_tags_print_reads_fixture_tags(test_book):
    result = CliRunner().invoke(cli, ["tags", "print", "--source", str(test_book)])

    assert result.exit_code == 0, result.output
    assert "Luminous" in result.output
    assert "Silvia Park" in result.output


def test_tags_set_rename_declined_overwrite_keeps_both_files(tmp_path, make_mp3):
    m4b = make_m4b(tmp_path, make_mp3)
    existing = tmp_path / "My Author - My Title.m4b"
    existing.write_bytes(b"keep me")

    result = run_set_tags(m4b, SET_TAGS_INPUT + "n\n")

    assert result.exit_code == 0, result.output
    assert "already exists" in result.output
    assert existing.read_bytes() == b"keep me"
    assert m4b.exists()


def test_tags_set_rename_confirmed_overwrite_replaces_file(tmp_path, make_mp3):
    m4b = make_m4b(tmp_path, make_mp3)
    existing = tmp_path / "My Author - My Title.m4b"
    existing.write_bytes(b"replace me")

    result = run_set_tags(m4b, SET_TAGS_INPUT + "y\n")

    assert result.exit_code == 0, result.output
    assert existing.read_bytes() != b"replace me"
    assert not m4b.exists()


SERIES_NAME = "----:com.apple.iTunes:series"
SERIES_NAME_LEGACY = "----:com.apple.iTunes:SRNM"
SERIES_PART = "----:com.apple.iTunes:series-part"
SERIES_PART_LEGACY = "----:com.apple.iTunes:SRSQ"
# Flags that answer every required-tag prompt except series.
NON_SERIES_FLAGS = ["--narrator", "N", "--genre", "Fantasy", "--date", "2020"]
# Decline further changes, save, then accept the rename.
FINISH_INPUT = "n\ny\ny\n"


def series_tags(path):
    m4b = MP4(path)
    return {
        key: bytes(m4b[key][0]).decode("utf-8")
        for key in (SERIES_NAME, SERIES_NAME_LEGACY, SERIES_PART, SERIES_PART_LEGACY)
        if key in m4b
    }


def renamed(tmp_path):
    return tmp_path / "My Author - My Title.m4b"


@pytest.mark.parametrize("part, expected", [("2", "2"), ("2.5", "2.5")])
def test_tags_set_series_part_flag_format(tmp_path, make_mp3, part, expected):
    m4b = make_m4b(tmp_path, make_mp3)
    args = ["--series-name", "Saga", "--series-part", part]

    result = CliRunner().invoke(
        cli,
        ["tags", "set", "--source", str(m4b), *NON_SERIES_FLAGS, *args],
        input=FINISH_INPUT,
    )

    assert result.exit_code == 0, result.output
    assert series_tags(renamed(tmp_path)) == {
        SERIES_NAME: "Saga",
        SERIES_NAME_LEGACY: "Saga",
        SERIES_PART: expected,
        SERIES_PART_LEGACY: expected,
    }


def test_tags_set_prompted_series_part_has_no_trailing_zero(tmp_path, make_mp3):
    m4b = make_m4b(tmp_path, make_mp3)

    result = CliRunner().invoke(
        cli,
        ["tags", "set", "--source", str(m4b), *NON_SERIES_FLAGS],
        input="y\nSaga\n3\n" + FINISH_INPUT,
    )

    assert result.exit_code == 0, result.output
    assert series_tags(renamed(tmp_path)) == {
        SERIES_NAME: "Saga",
        SERIES_NAME_LEGACY: "Saga",
        SERIES_PART: "3",
        SERIES_PART_LEGACY: "3",
    }


def test_tags_set_menu_series_edits_update_legacy_atoms(tmp_path, make_mp3):
    m4b = make_m4b(tmp_path, make_mp3)
    args = ["--series-name", "Old", "--series-part", "1"]
    menu = "y\nSERIES_NAME\nNew\nSERIES_PART\n4\n\n"

    result = CliRunner().invoke(
        cli,
        ["tags", "set", "--source", str(m4b), *NON_SERIES_FLAGS, *args],
        input=menu + "y\ny\n",
    )

    assert result.exit_code == 0, result.output
    assert series_tags(renamed(tmp_path)) == {
        SERIES_NAME: "New",
        SERIES_NAME_LEGACY: "New",
        SERIES_PART: "4",
        SERIES_PART_LEGACY: "4",
    }


def test_tags_set_prompted_series_part_rejects_blank_and_non_numbers(
    tmp_path, make_mp3
):
    m4b = make_m4b(tmp_path, make_mp3)

    result = CliRunner().invoke(
        cli,
        ["tags", "set", "--source", str(m4b), *NON_SERIES_FLAGS],
        input="y\nSaga\n\nthree\n3\n" + FINISH_INPUT,
    )

    assert result.exit_code == 0, result.output
    assert series_tags(renamed(tmp_path))[SERIES_PART] == "3"


@pytest.mark.parametrize(
    "flag, value",
    [("--author", "Tom & Jerry"), ("--narrator", "Full Cast and Crew")],
)
def test_tags_set_warns_when_abs_would_split_a_name(
    tmp_path, make_mp3, caplog, flag, value
):
    m4b = make_m4b(tmp_path, make_mp3)
    args = [*NON_SERIES_FLAGS, flag, value]

    with caplog.at_level(logging.WARNING):
        result = CliRunner().invoke(
            cli,
            ["tags", "set", "--source", str(m4b), *args],
            input="n\n" + FINISH_INPUT,
        )

    assert result.exit_code == 0, result.output
    assert f"'{value}'" in caplog.text
    assert "Audiobookshelf" in caplog.text


def test_tags_set_no_split_warning_for_semicolon_names(tmp_path, make_mp3, caplog):
    m4b = make_m4b(tmp_path, make_mp3)
    args = [*NON_SERIES_FLAGS, "--author", "A. Author;B. Author"]

    with caplog.at_level(logging.WARNING):
        result = CliRunner().invoke(
            cli,
            ["tags", "set", "--source", str(m4b), *args],
            input="n\n" + FINISH_INPUT,
        )

    assert result.exit_code == 0, result.output
    assert "Audiobookshelf" not in caplog.text


def test_tags_set_rename_uses_first_author_of_multi_author_tag_on_disk(
    tmp_path, make_mp3
):
    m4b = make_m4b(tmp_path, make_mp3)
    tags = MP4(m4b)
    tags["\xa9ART"] = ["A. Author;B. Author"]
    tags["aART"] = ["A. Author;B. Author"]
    tags.save()

    result = CliRunner().invoke(
        cli,
        ["tags", "set", "--source", str(m4b), *NON_SERIES_FLAGS],
        input="n\n" + FINISH_INPUT,
    )

    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in tmp_path.glob("*.m4b")) == [
        "A. Author - My Title.m4b"
    ]


def test_tags_set_menu_shows_whole_value_of_tag_set_this_run(tmp_path, make_mp3):
    m4b = make_m4b(tmp_path, make_mp3)
    # Open the menu on NARRATOR, abort the edit, then leave the menu.
    menu = "y\nNARRATOR\n\n\n\n"
    flags = ["--narrator", "Jane Doe", "--genre", "Fantasy", "--date", "2020"]

    result = CliRunner().invoke(
        cli,
        ["tags", "set", "--source", str(m4b), *flags],
        input="n\n" + menu + "y\ny\n",
    )

    assert result.exit_code == 0, result.output
    assert "Current value for 'NARRATOR': Jane Doe\n" in result.output


def set_genre_on_disk(path, value):
    tags = MP4(path)
    tags["\xa9gen"] = [value]
    tags.save()


def run_set_tags_without_genre_flag(m4b, input):
    return CliRunner().invoke(
        cli,
        ["tags", "set", "--source", str(m4b), "--narrator", "N", "--date", "2020"],
        input=input,
    )


@pytest.mark.parametrize("genre", ["Audiobook", "audiobook", "Audiobook; "])
def test_tags_set_prompts_for_genres_when_only_audiobook_remains(
    tmp_path, make_mp3, genre
):
    m4b = make_m4b(tmp_path, make_mp3)
    set_genre_on_disk(m4b, genre)

    # Pick Fantasy, finish genres, decline series, then finish.
    result = run_set_tags_without_genre_flag(m4b, "Fantasy\n\nn\n" + FINISH_INPUT)

    assert result.exit_code == 0, result.output
    assert "Available genres:" in result.output
    assert MP4(renamed(tmp_path))["\xa9gen"] == ["Fantasy"]


def test_tags_set_drops_audiobook_genre_and_keeps_the_rest(tmp_path, make_mp3):
    m4b = make_m4b(tmp_path, make_mp3)
    set_genre_on_disk(m4b, "Audiobook;Fantasy; Horror")

    # Decline series, then finish; no genre prompt expected.
    result = run_set_tags_without_genre_flag(m4b, "n\n" + FINISH_INPUT)

    assert result.exit_code == 0, result.output
    assert "Available genres:" not in result.output
    assert MP4(renamed(tmp_path))["\xa9gen"] == ["Fantasy;Horror"]


def set_names_on_disk(path, author, narrator):
    tags = MP4(path)
    tags["\xa9ART"] = [author]
    tags["aART"] = [author]
    tags["\xa9wrt"] = [narrator]
    tags.save()


def test_tags_set_spaces_out_initials_in_existing_names(tmp_path, make_mp3, caplog):
    m4b = make_m4b(tmp_path, make_mp3)
    set_names_on_disk(m4b, "J.R.R. Tolkien;A.Author", "A.B.C. Reader")
    flags = ["--genre", "Fantasy", "--date", "2020"]

    with caplog.at_level(logging.WARNING):
        result = CliRunner().invoke(
            cli,
            ["tags", "set", "--source", str(m4b), *flags],
            input="n\n" + FINISH_INPUT,
        )

    assert result.exit_code == 0, result.output
    tags = MP4(tmp_path / "J. R. R. Tolkien - My Title.m4b")
    assert tags["\xa9ART"] == ["J. R. R. Tolkien;A.Author"]
    assert tags["aART"] == ["J. R. R. Tolkien;A.Author"]
    assert tags["\xa9wrt"] == ["A. B. C. Reader"]
    assert "initials" not in caplog.text


@pytest.mark.parametrize(
    "flag, value",
    [("--author", "J.R.R. Tolkien"), ("--narrator", "A.B. Reader")],
)
def test_tags_set_warns_on_entered_name_with_unspaced_initials(
    tmp_path, make_mp3, caplog, flag, value
):
    m4b = make_m4b(tmp_path, make_mp3)
    args = [*NON_SERIES_FLAGS, flag, value]

    with caplog.at_level(logging.WARNING):
        result = CliRunner().invoke(
            cli,
            ["tags", "set", "--source", str(m4b), *args],
            input="n\n" + FINISH_INPUT,
        )

    assert result.exit_code == 0, result.output
    assert f"'{value}'" in caplog.text
    assert "initials" in caplog.text


def test_tags_set_no_initials_warning_for_spaced_initials(tmp_path, make_mp3, caplog):
    m4b = make_m4b(tmp_path, make_mp3)
    args = [*NON_SERIES_FLAGS, "--author", "J. R. R. Tolkien"]

    with caplog.at_level(logging.WARNING):
        result = CliRunner().invoke(
            cli,
            ["tags", "set", "--source", str(m4b), *args],
            input="n\n" + FINISH_INPUT,
        )

    assert result.exit_code == 0, result.output
    assert "initials" not in caplog.text
