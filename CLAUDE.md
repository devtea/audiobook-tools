# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Click-based CLI for compiling and managing audiobooks: organizing `.m4b` files into an author/title directory tree, concatenating loose audio files into a single chaptered `.m4b`, and reading/writing MP4 metadata tags.

## Commands

The project uses `uv`.

- Run the CLI: `uv run ./audiobook_tools.py --help`
- Install deps (incl. dev): `uv sync`
- Format: `uv run black .`
- Run tests: `uv run pytest`
- Requires Python >= 3.14. External runtime dependency: `ffmpeg`/`ffprobe` must be on `PATH` (used by the `files concat` command).

Pytest config (`testpaths`, `pythonpath`) lives in `pyproject.toml`; shared fixtures in `tests/conftest.py`. The `foo/` directory holds local sample audio data and is gitignored scratch, not part of the package.

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
- Series tags are written to both the readable `----:com.apple.iTunes:series`/`series-part` atoms and the legacy `SRNM`/`SRSQ` atoms, and must be `.encode("utf-8")` byte values (freeform `----` atoms require bytes).
- Multi-value tags (genres, authors) are stored as one string joined by `TAG_DELIMITER`, not as multiple mutagen list entries.
- `files organize` derives author/title from tags first, falling back to filename parsing with the regex `^([^-]*) - (.*).m4b$` (so an author name containing a hyphen breaks the fallback). It refuses to overwrite an existing destination file.
- `files concat` expects source files numbered and alphabetically sortable (e.g. `01 Chapter 1.mp3`); the numeric prefix orders them and the remaining filename becomes the chapter title. It builds an ffmpeg FFMETADATA file for chapter markers, writes `files.txt`/`metadata.txt` scratch files into `--destination`, and always produces `output.m4b` there.
- `concat`'s bitrate branch: mixed bitrates or a single bitrate <= 64k re-encode to AAC at ffmpeg's default rate; anything higher is transcoded down with `-b:a 64k`.

## Known rough edges

Do not "fix" these incidentally, but be aware when changing nearby code:

- `get_file_list`'s non-recursive directory branch calls `os.path.isfile(file)` on a bare filename, which resolves against the CWD. Passing `--source` for a directory other than the CWD without `--recurse` silently yields no files.
- `concat_files` declares its own `--source`/`--destination` options *and* applies `@common_options`, which redeclares `--source`. It also ignores `recurse`, and probes bitrates with CWD-relative paths while probing durations with `--destination`-relative paths.
