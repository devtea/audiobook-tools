# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Click-based CLI for compiling and managing audiobooks: organizing `.m4b` files into an author/title directory tree, concatenating loose audio files into a single chaptered `.m4b`, and reading/writing MP4 metadata tags.

## Commands

The project uses `uv`.

- Run the CLI: `uv run ./audiobook_tools.py --help`
- Install deps (incl. dev): `uv sync`
- Install runtime deps only: `uv sync --no-dev`
- Format: `uv run black .`
- Run the full test suite: `uv run pytest`
- Run one test file: `uv run pytest tests/test_tags.py`
- Run one test: `uv run pytest tests/test_tags.py::test_tags_print_reads_fixture_tags`
- Requires Python >= 3.14. External runtime dependency: `ffmpeg`/`ffprobe` must be on `PATH` (used by the `files concat` command).

The `foo/` directory holds local sample audio data and is gitignored scratch, not part of the package.

## Testing

**TDD is required for all new work.** This is a legacy codebase that is retrofitting tests, so the rule applies going forward, not retroactively: write a failing test first, watch it fail for the right reason, then write the minimum code to make it pass. Do not write implementation code for a new feature or a bug fix before the test that covers it exists and fails. Never claim a test passes without having run it and seen the output.

Coverage is currently near zero by design - the harness was bootstrapped with a single seed test (`tests/test_tags.py`), and broad coverage is a separate, ongoing effort. Adding tests for code you touch is expected; do not treat the sparse suite as license to skip them.

Pytest config (`testpaths = ["tests"]`, `pythonpath = ["."]`) lives in `pyproject.toml`. The `pythonpath` entry is load-bearing: `util/`, `subcommands/`, and `audiobook_tools.py` are top-level modules at the repo root, so without it imports fail under pytest's default prepend import mode. Shared fixtures go in `tests/conftest.py`; `tests/` is a plain directory, not a package.

Prefer testing commands through `click.testing.CliRunner` against the real `cli` group in `audiobook_tools.py` rather than calling command functions directly - the Click decorators supply required params, so a direct call bypasses the wiring most likely to break.

### Test fixture

`tests/data/test_book.m4b` is the committed sample audiobook for automated tests: a 10-second clip cut from a random mid-book point of a real `.m4b`, carrying the full tag set (title, artist, album, album-artist, composer, date, genre, comment/description) plus a 20KB JPEG `covr` atom.

Two things to know about it:

- It was produced *with this tool's own dependencies* - `ffmpeg -c copy` for the audio, then mutagen to copy the `covr` atom across, because `-c copy` carries the cover only as an mjpeg stream and never writes the `covr` atom mutagen reads. So its tags are not independent of the code under test. Tests that need to verify tag *reading* against a known-good, externally produced file will eventually need a separate "virgin" fixture that this project never touched.
- `.gitignore` excludes `*.m4b` globally, with a negation for `tests/data/` so fixtures are tracked.

## CLI structure

`audiobook_tools.py` defines the top-level `click.group` and wires two subcommand groups:

- `tags` -> `subcommands/tags.py`: `set`, `print`, `verify` (verify is a stub).
- `files` -> `subcommands/files.py`: `organize`, `concat`, `autoname` (autoname is a stub).

Every command is a standalone `@click.command` in a subcommand module, registered on its group via `add_command` in `audiobook_tools.py`. Commands are named explicitly (`name="organize"`) so the function name and CLI name differ.

## Shared conventions

Reuse these rather than reimplementing:

- **Decorators** (`util/decorators.py`) supply shared options and must be applied to commands:
  - `@common_logging` adds `--log-level` and configures the root logger. Its wrapper consumes `log_level` and does not forward it, so command functions must not declare that param.
  - `@common_options` adds `--source`/`-s` and `--recurse` (the wrapped function must accept `source` and `recurse` params).
  - `@common_tag_options` adds the audiobook metadata flags (`--author`, `--title`, `--genre`, etc.) for tag commands.
- **File selection** goes through `get_file_list(path, ext, recurse)` in `util/file.py`, which handles the file-vs-directory and recursion logic uniformly. `filter_path_name` strips characters in `SHITTY_REJECT_CHARACTERS_WE_HATES` from any path built for the filesystem.
- **MP4 tags** are accessed via the `Tag` enum in `util/mp4.py`, which maps readable names to raw MP4 atom keys (e.g. `Tag.ARTIST.value` -> `"\xa9ART"`). Always index mutagen `MP4` objects with `Tag.<NAME>.value`, never raw atom strings. `pprint_tags` renders current tags plus the legend.
- **Constants** (`util/constants.py`): `LOG` (shared logger), `TAG_DELIMITER` (`;`, used to join multi-value tags like multiple authors/genres), `COMMON_CONTEXT` (Click help-flag settings).

## Domain notes

- Paired tags are kept in sync deliberately: title <-> album, artist <-> album-artist, and description <-> comment are always written together. Preserve this when editing tag logic.
- Series tags are written to both the readable `----:com.apple.iTunes:series`/`series-part` atoms and the legacy `SRNM`/`SRSQ` atoms, and must be `.encode("utf-8")` byte values (freeform `----` atoms require bytes). All series writes go through `set_series_tags` in `subcommands/tags.py`, which formats whole-number parts without a trailing `.0` because Audiobookshelf uses the `series-part` string verbatim as the sequence.
- Multi-value tags (genres, authors) are stored as one string joined by `TAG_DELIMITER`, not as multiple mutagen list entries. Audiobookshelf splits names on `&` or ` and ` before `;`, so `tags set` warns before saving an author or narrator containing either.
- `files organize` derives author/title from tags first (multi-author tags are trimmed and matched in any order; the first album-artist entry is used), falling back to filename parsing with the regex `^([^-]*) - (.*)\.m4b$`. Files whose author part contains a hyphen are skipped with a warning, and files with no resolvable author and title are skipped with an error. It never overwrites an existing destination file. When one exists with the same author and title but a different narrator (both narrator tags present and unequal), the incoming file goes to a `Title {Narrator}` folder (multiple narrators joined with `, `) per Audiobookshelf's folder rules; the existing file is left alone, and same-narrator or untagged collisions are skipped with an error. It leaves skipped files untouched, exits non-zero when no files are found, and `--prune` never removes directories above `--source`. It only moves `.m4b` files (case-sensitive match, with or without `--recurse`); adjunct files like PDFs or cover art are left behind and keep their directory from being pruned.
- `files concat` expects source files numbered and alphabetically sortable (e.g. `01 Chapter 1.mp3`); files are selected via `get_file_list` (honoring `--recurse`, exiting non-zero when none are found) and sorted by basename, so the numeric prefix orders them across directories, and the remaining filename becomes the chapter title. It builds an ffmpeg FFMETADATA file for chapter markers, writes `files.txt`/`metadata.txt` scratch files into `--destination`, and always produces `output.m4b` there. `--set-tags` runs `tags set` interactively on the output (which may rename it), and `--cleanup` removes the source files only after a non-empty output exists and tagging did not abort.
- `concat`'s bitrate: the AAC target is the lowest source bitrate capped at 64k, so sources are never upscaled.
