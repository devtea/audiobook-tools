from click.testing import CliRunner

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
