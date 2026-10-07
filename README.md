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

When two files share an author and title but have different narrator tags, the
second is placed in a `Title {Narrator}` folder, as Audiobookshelf expects. Both
files need a narrator tag for this; otherwise the colliding file is skipped.

Audiobookshelf tag reference
----------------------------

Audiobookshelf (ABS) scans file tags with ffprobe and matches the resulting
keys case-insensitively. Only the first audio file of a book is used. Verified
against the ABS source (`server/utils/prober.js` and
`server/scanner/AudioFileScanner.js`, master at `743d915`) and by probing test
files with ffprobe. Where a library sets file metadata as its highest precedence
source, these tags win.

ABS looks for several ffprobe keys per field. The tables list the tag to write
for each file type, with the ffprobe key it produces in parentheses.

**m4b (mp4 atoms)**

Freeform atoms are written as `----:com.apple.iTunes:<name>` with UTF-8 bytes.

| ABS field      | Preferred tag                                | Fallback if empty                     |
|----------------|----------------------------------------------|---------------------------------------|
| Title          | `©alb` (`album`)                             | `©nam` (`title`)                      |
| Subtitle       | `----:com.apple.iTunes:subtitle` (`subtitle`)| none                                  |
| Authors        | `©ART` (`artist`)                            | `aART` (`album_artist`)               |
| Narrators      | `©wrt` (`composer`)                          | none                                  |
| Description    | `desc` (`description`)                       | `©cmt` (`comment`)                    |
| Publisher      | `----:com.apple.iTunes:publisher`            | none (`©pub` is not exposed)          |
| Published year | `©day` (`date`)                              | none                                  |
| Genres         | `©gen` (`genre`)                             | none                                  |
| Series name    | `----:com.apple.iTunes:series` (`series`)    | `tvsh` (`show`), then `©grp` (`grouping`, as `Series #N; Other #M`) |
| Series number  | `----:com.apple.iTunes:series-part`          | `tven` (`episode_id`), or freeform `part` |
| ISBN           | `----:com.apple.iTunes:isbn`                 | none                                  |
| Language       | `----:com.apple.iTunes:language`             | none                                  |
| ASIN           | `----:com.apple.iTunes:asin`                 | `audible_asin`                        |

**mp3 (ID3 frames)**

| ABS field      | Preferred frame                              | Fallback if empty                     |
|----------------|----------------------------------------------|---------------------------------------|
| Title          | `TALB` (`album`)                             | `TIT2` (`title`)                      |
| Subtitle       | `TIT3` (`TIT3`)                              | `TXXX:SUBTITLE` (`SUBTITLE`)          |
| Authors        | `TPE1` (`artist`)                            | `TPE2` (`album_artist`)               |
| Narrators      | `TCOM` (`composer`)                          | none                                  |
| Description    | `TXXX:DESCRIPTION` (`DESCRIPTION`)           | `COMM` (`comment`)                    |
| Publisher      | `TPUB` (`publisher`)                         | none                                  |
| Published year | `TDRC` or `TYER` (`date`)                    | none                                  |
| Genres         | `TCON` (`genre`)                             | none                                  |
| Series name    | `TXXX:SERIES` (`SERIES`)                     | `TIT1` (`grouping`, as `Series #N; Other #M`) |
| Series number  | `TXXX:SERIES-PART` (`SERIES-PART`)           | none                                  |
| ISBN           | `TXXX:ISBN` (`ISBN`)                         | none                                  |
| Language       | `TLAN` (`language`)                          | none                                  |
| ASIN           | `TXXX:ASIN` (`ASIN`)                         | none                                  |

Notes:

- Title source ranking: ABS uses `album` (`©alb`) first and only falls back to
  `title` (`©nam`) when the album is empty. Keep the two in sync, because ABS
  shows the album value even when `©nam` differs.
- Multiple series: `series` and `series-part` may both be semicolon-separated,
  but only when every series has a number.
- In m4b files the freeform atoms are `----:com.apple.iTunes:<name>`, for
  example `series`, `series-part`, `subtitle`, `isbn` and `asin`. ffprobe
  exposes the atom name as the key. The `subtitle` freeform atom is confirmed
  to populate the ABS subtitle after a rescan.
- m4b has no native subtitle atom, and ABS's own "embed metadata" does not write
  the subtitle to m4b files, so write the freeform `subtitle` atom yourself.
- Legacy series atoms: `----:com.apple.iTunes:SRNM` and `SRSQ` are not in ABS's
  key lists, so on their own they do not produce a series in ABS. This tool still
  writes them alongside `series` and `series-part` for other players, but ABS
  only uses `series` and `series-part`, `show`/`episode_id`, or `grouping`.
- ABS also lists `mvnm`, `mvin` and `grp1`, but ffmpeg 8 (`Lavf63`) did not expose
  the `MVNM`, `MVIN` or `GRP1` ID3 frames or the `©mvn`/`©mvi` mp4 atoms in
  testing, so do not rely on them. ABS bundles its own ffmpeg, which may differ.
- Read and stored per audio file but not used for book metadata: `title-sort`,
  `album-sort`, `artist-sort`, `track`, `discnumber`, `encoder`, `encoded_by`,
  `itunes-id`, `podcast-type`, `episode-type`, `originalyear`, `releasetime`,
  `releasecountry`, `releasestatus`, `releasetype`, `isrc`, the MusicBrainz IDs,
  and `OverDrive MediaMarkers` (chapters).
- Other sources ABS reads: embedded chapters in the first audio file,
  `metadata.json`, `.opf`, `.nfo`, `desc.txt` (description), `reader.txt`
  (narrator, first line only) and folder names. The folder-name subtitle is only
  parsed (split on ` - `) when `scannerParseSubtitle` is on, which is off by
  default.
