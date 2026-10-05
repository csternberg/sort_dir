# sort_dir

Sorts the sub folders of the current directory into alphabetical bucket folders.

| Bucket | Receives folders whose (mask-stripped) name starts with |
|---|---|
| `#` | a digit `0`-`9` |
| `A`-`Z` | an ASCII letter (case-insensitive) |
| `Other` | anything else: kanji, accented letters, symbols, graphics, ... |

Hidden folders (starting with `.`) and the bucket folders themselves are never moved, so the script can safely be run repeatedly. Requires Python 3.7+, no dependencies.

## Usage

```
python sort_dir.py [-M MASK] [-S [-W]] [-G] [-D] [-L [FILE]] [-H]
```

Run it from inside the folder you want sorted. Use `--dry-run` first to preview.

| Short | Long | Description |
|---|---|---|
| `-M` `-m` | `--mask MASK` | Prefix ignored when sorting (case-insensitive, whole words, any amount of spaces between words). With `-M "The old"`, `The old shed` is sorted under `S`. |
| `-S` `-s` | `--strip` | Also remove the mask from the moved folder's name: `The old shed` becomes `S/shed`. All leading white space is removed. Needs `--mask`. |
| `-W` `-w` | `--whitespace` | With `--strip`, keep the white space after the mask, so the new name may start with a space. Off by default. |
| `-G` `-g` | `--merge` | Merge into an existing folder with the same name (see below). |
| `-D` `-d` | `--dry-run` | Show what would happen; change nothing. |
| `-L` `-l` | `--log [FILE]` | Write a log file (default `sort_dir_<timestamp>.log`). |
| `-H` `-h` | `--help` | Show help. |

All switches work in upper and lower case, short and long (`-M` = `-m`, `--MASK` = `--mask`). The mask value itself keeps its case.

## Name clashes

If the destination folder already exists, the moved folder is renamed `name_001`, `name_002`, ... until the name is unique.

With `--merge` the contents are merged into the existing folder instead. Clashing files and sub folders inside it get the same suffix (`report.txt` becomes `report_001.txt`, `sub` becomes `sub_001`). Once everything is moved, the emptied source folder is removed; if anything could not be moved it is left in place.

## Logging and errors

- `--log` writes `sort_dir_<timestamp>.log` with everything that is printed.
- If errors occur (write-protected target, unreadable source, a file blocking a bucket name, ...) they are reported, the run continues with the next folder, and `sort_dir_errors_<timestamp>.log` is written. It is only created when there are errors, with or without `--log`.
- Exit code is `0` on success, `1` if any error occurred.

## Examples

```
python sort_dir.py --dry-run
python sort_dir.py -M "The old" -S
python sort_dir.py -G -L
```
