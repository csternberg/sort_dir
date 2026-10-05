#!/usr/bin/env python3
import os
import shutil
import argparse
import re
import string
import sys
from datetime import datetime

BUCKETS = {"#", "Other"} | set(string.ascii_uppercase)

# Paths that a dry run has "reserved", so later items see them as taken.
_planned = set()


class Reporter:
    """
    Console output plus optional log file (-L) and an error log that is only
    created if something goes wrong. Logging problems never stop the run.
    """

    def __init__(self, log_path=None, stamp=None):
        self.stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = log_path
        self.error_path = f"sort_dir_errors_{self.stamp}.log"
        self.errors = 0
        self.moves = 0
        self._log_ok = log_path is not None
        self._err_ok = True

        if self._log_ok:
            self._append(self.log_path, "log", f"Started, cwd: {os.getcwd()}")

    def _append(self, path, kind, text):
        """Append a timestamped line to a log file; disable it on failure."""
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {text}\n")
            return True
        except Exception as e:
            print(f"[WARNING] Cannot write {kind} file '{path}': {e}")
            if kind == "log":
                self._log_ok = False
            else:
                self._err_ok = False
            return False

    def info(self, msg):
        print(msg)
        if self._log_ok:
            self._append(self.log_path, "log", msg)

    def error(self, msg):
        self.errors += 1
        print(f"[ERROR] {msg}")
        if self._log_ok:
            self._append(self.log_path, "log", f"[ERROR] {msg}")
        if self._err_ok:
            self._append(self.error_path, "error log", msg)

    def summary(self):
        self.info(f"Done. Moved: {self.moves}, errors: {self.errors}")
        if self.errors and self._err_ok:
            print(f"Errors were written to '{self.error_path}'")


def describe(e: Exception) -> str:
    """Short, human-friendly description of a filesystem error."""
    if isinstance(e, PermissionError):
        return "permission denied (read-only or protected?)"
    if isinstance(e, FileNotFoundError):
        return "not found (removed while running?)"
    return str(e) or e.__class__.__name__


def normalize_spaces(s: str) -> str:
    """Reduce multiple spaces to a single space and strip ends."""
    return re.sub(r"\s+", " ", s.strip())


def remove_mask(name: str, mask: str, keep_whitespace: bool = False) -> str:
    """
    Remove a mask prefix from name, ignoring case, handling multiple spaces
    between mask words, and ignoring additional spaces in name.

    By default the result has no leading/trailing white space. With
    keep_whitespace the white space following the mask is preserved
    (trailing white space is always removed).
    """
    if not mask:
        return name

    mask_parts = normalize_spaces(mask).split()
    if not mask_parts:
        return name

    # Mask at the start, ANY spaces between mask words, and it must be
    # followed by white space (so "The" does not match "Theatre").
    mask_regex = r"^\s*" + r"\s+".join(re.escape(part) for part in mask_parts) + r"(?=\s)"

    new_name = re.sub(mask_regex, "", name, count=1, flags=re.IGNORECASE)
    if keep_whitespace:
        return new_name.rstrip()
    return new_name.strip()


def target_folder(name: str) -> str:
    """
    '#'     -> first character is a digit 0-9
    'A'-'Z' -> first character is an ASCII letter (case-insensitive)
    'Other' -> anything else (kanji, accented letters, symbols, graphics, ...)
    """
    if not name:
        return "Other"

    first = name[0]
    if first in string.ascii_letters:
        return first.upper()
    if first in string.digits:
        return "#"
    return "Other"


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def is_taken(path: str) -> bool:
    return os.path.lexists(path) or _key(path) in _planned


def unique_name(parent: str, name: str, is_dir: bool) -> str:
    """
    Return `name` if free in `parent`, otherwise name_001, name_002, ...
    For files the counter goes before the extension: file_001.txt
    """
    if not is_taken(os.path.join(parent, name)):
        return name

    if is_dir:
        stem, ext = name, ""
    else:
        stem, ext = os.path.splitext(name)

    i = 1
    while True:
        candidate = f"{stem}_{i:03d}{ext}"
        if not is_taken(os.path.join(parent, candidate)):
            return candidate
        i += 1


def safe_move(src: str, dest: str, dry_run: bool, rep: Reporter) -> bool:
    """Move with error handling and dry-run mode. Returns True on success."""
    try:
        if dry_run:
            _planned.add(_key(dest))
            rep.moves += 1
            rep.info(f"[DRY-RUN] Would move '{src}' -> '{dest}'")
            return True

        if os.path.lexists(dest):
            rep.error(f"Destination already exists: '{dest}' (skipped '{src}')")
            return False

        shutil.move(src, dest)
        rep.moves += 1
        rep.info(f"Moved '{src}' -> '{dest}'")
        return True

    except Exception as e:
        rep.error(f"Could not move '{src}' -> '{dest}': {describe(e)}")
        # A cross-device move copies first; mention if a partial copy may remain.
        if os.path.lexists(dest) and os.path.lexists(src):
            rep.error(f"Both '{src}' and '{dest}' exist; check for a partial copy")
    return False


def safe_mkdir(path: str, dry_run: bool, rep: Reporter) -> bool:
    """Create a directory safely with error handling. Returns True if usable."""
    try:
        if os.path.isdir(path):
            return True
        if os.path.lexists(path):
            rep.error(f"'{path}' exists but is not a folder; skipping its entries")
            return False

        if dry_run:
            if _key(path) not in _planned:
                _planned.add(_key(path))
                rep.info(f"[DRY-RUN] Would create folder '{path}'")
            return True

        os.makedirs(path, exist_ok=True)
        return True

    except Exception as e:
        rep.error(f"Could not create folder '{path}': {describe(e)}")
    return False


def merge_into(src: str, dest: str, dry_run: bool, rep: Reporter):
    """
    Merge the contents of folder `src` into existing folder `dest`.
    Name clashes (files and sub folders alike) get _001, _002, ... suffixes.
    """
    try:
        items = sorted(os.listdir(src))
    except Exception as e:
        rep.error(f"Could not read '{src}': {describe(e)}")
        return

    all_moved = True
    for item in items:
        s = os.path.join(src, item)
        is_dir = os.path.isdir(s) and not os.path.islink(s)
        name = unique_name(dest, item, is_dir)
        if not safe_move(s, os.path.join(dest, name), dry_run, rep):
            all_moved = False

    if not all_moved:
        rep.error(f"'{src}' not fully merged; left in place")
        return

    if dry_run:
        rep.info(f"[DRY-RUN] Would remove emptied folder '{src}'")
        return

    try:
        os.rmdir(src)
    except Exception as e:
        rep.error(f"Could not remove emptied folder '{src}': {describe(e)}")


def place(src: str, new_name: str, dest_dir: str, merge: bool, dry_run: bool,
          rep: Reporter):
    """Move folder `src` into `dest_dir` as `new_name`, handling existing folders."""
    dest = os.path.join(dest_dir, new_name)

    if merge and os.path.isdir(dest) and not os.path.islink(dest):
        rep.info(f"Merging '{src}' into '{dest}'")
        merge_into(src, dest, dry_run, rep)
        return

    name = unique_name(dest_dir, new_name, True)
    safe_move(src, os.path.join(dest_dir, name), dry_run, rep)


def normalize_argv(argv):
    """Make long options case-insensitive (--MASK == --mask). Values are untouched."""
    out = []
    for i, a in enumerate(argv):
        if a == "--":
            out.extend(argv[i:])
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            a = name.lower() + eq + val
        out.append(a)
    return out


def build_parser():
    # Both cases are registered for every short switch, since argparse is
    # case-sensitive; long switches are lower-cased in normalize_argv().
    parser = argparse.ArgumentParser(
        prog="sort_dir.py",
        usage="%(prog)s [-M MASK] [-S [-W]] [-G] [-D] [-L [FILE]] [-H]",
        description=(
            "Sort the sub folders of the current directory into the folders "
            "'#' (names starting with 0-9), 'A'-'Z' (names starting with a "
            "letter) and 'Other' (anything else, e.g. kanji, symbols). "
            "Sorting uses the folder name with the mask removed. "
            "Hidden folders (starting with '.') and the target folders "
            "themselves are never moved."
        ),
        epilog=(
            "name clashes:\n"
            "  If the target folder already exists, the moved folder is renamed\n"
            "  name_001, name_002, ... until the name is unique. With --merge the\n"
            "  contents are merged into the existing folder instead; clashing\n"
            "  files and sub folders get the same _001, _002 suffix (file_001.txt).\n"
            "\n"
            "switches:\n"
            "  Short switches work in upper and lower case (-M = -m), and long\n"
            "  switches too (--MASK = --mask). The value of --mask keeps its case.\n"
            "\n"
            "logging:\n"
            "  --log writes sort_dir_<timestamp>.log. If any error occurs (e.g.\n"
            "  write protected target, unreadable source), sort_dir_errors_<timestamp>.log\n"
            "  is written as well. Errors never stop the run; exit code is 1 if any occurred.\n"
            "\n"
            "examples:\n"
            "  sort_dir.py --dry-run                 preview the result\n"
            "  sort_dir.py -M \"The old\"              sort 'The old shed' under S, name unchanged\n"
            "  sort_dir.py -M \"The old\" -S           ... and rename it to 'shed'\n"
            "  sort_dir.py -M \"The old\" -S -W        ... keep leading white space: ' shed'\n"
            "  sort_dir.py -G -L                     merge same-name folders and write a log\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        allow_abbrev=False,
    )
    parser.add_argument(
        "-M", "-m", "--mask", dest="mask", default=None, metavar="MASK",
        help="Mask prefix (case-insensitive, whole words) ignored when sorting, "
             "e.g. -M \"The old\"."
    )
    parser.add_argument(
        "-S", "-s", "--strip", dest="strip", action="store_true",
        help="Also remove the mask (and all white space after it) from the name of "
             "the moved folder: 'The old special' -> 'special'. Requires --mask."
    )
    parser.add_argument(
        "-W", "-w", "--whitespace", dest="whitespace", action="store_true",
        help="With --strip, allow the new folder name to start with white space. "
             "By default all leading white space is removed."
    )
    parser.add_argument(
        "-G", "-g", "--merge", dest="merge", action="store_true",
        help="Merge into an existing folder of the same name instead of "
             "creating name_001, name_002, ..."
    )
    parser.add_argument(
        "-D", "-d", "--dry-run", dest="dry_run", action="store_true",
        help="Show what would happen without making any changes."
    )
    parser.add_argument(
        "-L", "-l", "--log", dest="log", nargs="?", const=True, default=None,
        metavar="FILE",
        help="Write a log file (default name: sort_dir_<timestamp>.log). "
             "An error log is always written if errors occur."
    )
    parser.add_argument(
        "-H", "-h", "--help", action="help",
        help="Show this help message and exit."
    )
    return parser


def main():
    # Avoid UnicodeEncodeError on consoles that can't show some folder names.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    args = build_parser().parse_args(normalize_argv(sys.argv[1:]))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = None
    if args.log is True:
        log_path = f"sort_dir_{stamp}.log"
    elif args.log:
        log_path = args.log
    rep = Reporter(log_path, stamp)

    if args.strip and not args.mask:
        rep.info("[WARNING] --strip has no effect without --mask")
    if args.whitespace and not args.strip:
        rep.info("[WARNING] --whitespace has no effect without --strip")

    try:
        entries = os.listdir(".")
    except Exception as e:
        rep.error(f"Could not list directory contents: {describe(e)}")
        sys.exit(1)

    dirs = [
        d for d in sorted(entries)
        if os.path.isdir(d)
        and d not in BUCKETS          # don't re-sort our own target folders
        and not d.startswith(".")     # never touch .git and other hidden folders
    ]

    for d in dirs:
        try:
            # Sorting always ignores leading white space after the mask.
            folder = target_folder(remove_mask(d, args.mask))

            new_name = d
            if args.strip:
                stripped = remove_mask(d, args.mask, args.whitespace)
                # Never rename to nothing (or only white space).
                if stripped.strip():
                    new_name = stripped

            if not safe_mkdir(folder, args.dry_run, rep):
                continue
            place(d, new_name, folder, args.merge, args.dry_run, rep)
        except KeyboardInterrupt:
            rep.error("Interrupted by user")
            break
        except Exception as e:
            # One bad folder must never abort the rest of the run.
            rep.error(f"Unexpected problem with '{d}': {describe(e)}")

    rep.summary()
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
