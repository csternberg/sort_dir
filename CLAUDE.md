# CLAUDE.md

Single-file Python 3 CLI (`sort_dir.py`, stdlib only) that sorts the sub folders of the current directory into `#`, `A`-`Z` and `Other`. See `README.md` for user-facing behaviour and switches.

## Testing

No test suite. Verify changes in a throw-away folder (never in the repo itself, the script moves sub folders of the cwd):

```
mkdir t && cd t && mkdir Apple "The old shed" 9lives
python ../sort_dir.py --dry-run -M "The old" -S
```

Always try `--dry-run` first, then a real run, then a second real run (must be a no-op).

## Rules to keep

- **Switches:** every switch has a short and a long form, and both cases of the short form are registered (`-M`/`-m`). Long switches are lower-cased in `normalize_argv()`, so `--MASK` works; option values must not be altered. Add new switches the same way and update the help epilog and README.
- **Bucket logic:** `target_folder()` uses ASCII only (`string.ascii_letters` / `string.digits`). Do not use `isalpha()`/`isdigit()`; Unicode letters belong in `Other`.
- **Skipped folders:** hidden folders (`.`-prefixed) and the bucket names are never processed.
- **Name clashes:** go through `unique_name()` (`name_001`, files `name_001.ext`). `--merge` is handled in `merge_into()`; sub folder clashes are renamed, not merged recursively.
- **Mask:** `remove_mask()` matches whole words, case-insensitive. Sorting always uses the fully stripped name. `--strip` renames to that name; leading white space is only kept with `--whitespace`. Never rename to an empty name.
- **Dry run:** must not touch the file system. Planned destinations are tracked in `_planned` so later items see them as taken.
- **Errors:** report through `Reporter.error()` (console, log, lazily created error log). Never let one folder abort the run; exit code is 1 if any error occurred. Print with ASCII `->`, not `→` (Windows consoles).
- **Docs:** keep `--help` (epilog in `build_parser()`), `README.md` and this file in sync with any behaviour change.
- **Line endings:** the repo uses LF. Take care that editing scripts do not rewrite the file with CRLF.
