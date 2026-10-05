#!/usr/bin/env python3
import os
import shutil
import argparse
import re
import string
import sys

def normalize_spaces(s: str) -> str:
    """Reduce multiple spaces to a single space and strip ends."""
    return re.sub(r"\s+", " ", s.strip())

def remove_mask(name: str, mask: str) -> str:
    """
    Remove a mask prefix from name, ignoring case, handling multiple spaces
    between mask words, and ignoring additional spaces in name.
    """
    if not mask:
        return name

    mask_norm = normalize_spaces(mask)
    mask_parts = mask_norm.split()

    # Regex to match mask at the start, allowing ANY spaces between mask words
    mask_regex = r"^\s*" + r"\s+".join(re.escape(part) for part in mask_parts) + r"\s+"

    new_name = re.sub(mask_regex, "", name, flags=re.IGNORECASE)
    return new_name.strip()

def target_folder(name: str) -> str:
    """Determine the folder based on first character of the processed name."""
    if not name:
        return "Other"

    first = name[0]

    if first.isalpha():
        return first.upper()
    elif first.isdigit():
        return "#"
    else:
        return "Other"

def safe_move(src: str, dest: str, dry_run: bool):
    """Move with error handling and dry-run mode."""
    try:
        if dry_run:
            print(f"[DRY-RUN] Would move '{src}' → '{dest}'")
            return

        # If destination exists, fail gracefully
        if os.path.exists(dest):
            print(f"[ERROR] Destination already exists: {dest}")
            return

        shutil.move(src, dest)
        print(f"Moved '{src}' → '{dest}'")

    except PermissionError:
        print(f"[ERROR] Permission denied while moving '{src}' → '{dest}'")
    except FileNotFoundError:
        print(f"[ERROR] Missing file or folder: '{src}'")
    except Exception as e:
        print(f"[ERROR] Unexpected error while moving '{src}' → '{dest}': {e}")

def safe_mkdir(path: str, dry_run: bool):
    """Create a directory safely with error handling."""
    try:
        if dry_run:
            if not os.path.exists(path):
                print(f"[DRY-RUN] Would create folder '{path}'")
            return

        os.makedirs(path, exist_ok=True)

    except PermissionError:
        print(f"[ERROR] Permission denied while creating folder '{path}'")
    except Exception as e:
        print(f"[ERROR] Unexpected error while creating folder '{path}': {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Sort directories into A–Z/#/Other based on processed names."
    )
    parser.add_argument(
        "-M", "--mask",
        help="Mask prefix to remove before sorting (case-insensitive).",
        default=None
    )
    parser.add_argument(
        "--dry-run",
        help="Show what would happen without making any changes.",
        action="store_true"
    )

    args = parser.parse_args()
    mask = args.mask
    dry_run = args.dry_run

    try:
        entries = os.listdir(".")
    except Exception as e:
        print(f"[FATAL ERROR] Could not list directory contents: {e}")
        sys.exit(1)

    dirs = [d for d in entries if os.path.isdir(d)]

    for d in dirs:
        processed = remove_mask(d, mask)
        folder = target_folder(processed)

        dest_dir = folder
        safe_mkdir(dest_dir, dry_run)

        dest = os.path.join(dest_dir, d)
        safe_move(d, dest, dry_run)

if __name__ == "__main__":
    main()
