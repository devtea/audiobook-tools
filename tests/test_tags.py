from click.testing import CliRunner

from audiobook_tools import cli


def test_tags_print_reads_fixture_tags(test_book):
    result = CliRunner().invoke(cli, ["tags", "print", "--source", str(test_book)])

    assert result.exit_code == 0, result.output
    assert "Luminous" in result.output
    assert "Silvia Park" in result.output
