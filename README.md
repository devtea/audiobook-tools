Audiobook Tools
===============

A collection of python tools for audiobook organization and management.

Requires Python 3.14 or newer and [uv](https://docs.astral.sh/uv/). The `files
concat` command additionally needs `ffmpeg` and `ffprobe` on your `PATH`.

Installing
----------

For non development - clone the repo and run `uv sync --no-dev`

For development - clone the repo and run `uv sync`

Usage
-----

Launch the utility to read the help text:

```shell
$> uv run ./audiobook_tools.py --help
```

Alternatively activate the venv and run the utility directly.

Commands are grouped by what they operate on:

- `tags` - read and write audiobook metadata. `set` edits tags from flags or
  interactive prompts, `print` dumps the tags of the selected files.
- `files` - `organize` moves `.m4b` files into an `Author/Title` tree, `concat`
  joins numbered audio files into a single chaptered `.m4b`.
