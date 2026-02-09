#!/usr/bin/env python3
"""
Merge multiple markdown chapter files into a single file.

Usage:
    python mergemd.py <directory> <range>

Example:
    python mergemd.py beginner 1-5

This will merge chapter_1.md through chapter_5.md into chapter_1-5.md
and delete the original files.
"""

import os
import sys
from pathlib import Path


def merge_markdown_files(directory, start, end):
    """
    Merge markdown chapter files from start to end.

    Args:
        directory: The directory containing the chapter files
        start: Starting chapter number
        end: Ending chapter number
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"Error: Directory '{directory}' does not exist")
        return False

    # Validate range
    if start > end:
        print(f"Error: Start number ({start}) cannot be greater than end number ({end})")
        return False

    # Collect files to merge
    files_to_merge = []
    missing_files = []

    for i in range(start, end + 1):
        filename = f"chapter_{i}.md"
        filepath = dir_path / filename

        if filepath.exists():
            files_to_merge.append(filepath)
        else:
            missing_files.append(filename)

    if missing_files:
        print(f"Warning: The following files are missing:")
        for f in missing_files:
            print(f"  - {f}")

        if not files_to_merge:
            print("Error: No files found to merge")
            return False

        response = input(f"\nContinue with {len(files_to_merge)} available files? (y/n): ")
        if response.lower() != 'y':
            print("Merge cancelled")
            return False

    # Create merged content
    print(f"\nMerging {len(files_to_merge)} files...")
    merged_content = []

    for filepath in files_to_merge:
        print(f"  Reading: {filepath.name}")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            merged_content.append(content)

    # Join with double newlines between chapters
    final_content = "\n\n".join(merged_content)

    # Create output filename
    if start == end:
        output_filename = f"chapter_{start}.md"
    else:
        output_filename = f"chapter_{start}-{end}.md"

    output_path = dir_path / output_filename

    # Check if output file already exists (and it's not one of the source files)
    if output_path.exists() and output_path not in files_to_merge:
        print(f"\nWarning: Output file '{output_filename}' already exists")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Merge cancelled")
            return False

    # Write merged content
    print(f"\nWriting merged content to: {output_filename}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    # Delete original files (except if output file is one of them)
    print("\nDeleting original files...")
    for filepath in files_to_merge:
        if filepath != output_path:
            print(f"  Deleting: {filepath.name}")
            filepath.unlink()

    print(f"\n✓ Successfully merged {len(files_to_merge)} files into '{output_filename}'")
    return True


def parse_range(range_str):
    """
    Parse range string like "1-5" into start and end numbers.

    Args:
        range_str: String like "1-5" or "10-15"

    Returns:
        Tuple of (start, end) as integers, or None if invalid
    """
    try:
        if '-' not in range_str:
            # Single number
            num = int(range_str)
            return (num, num)

        parts = range_str.split('-')
        if len(parts) != 2:
            return None

        start = int(parts[0])
        end = int(parts[1])

        if start < 1 or end < 1:
            return None

        return (start, end)
    except ValueError:
        return None


def main():
    if len(sys.argv) != 3:
        print("Usage: python mergemd.py <directory> <range>")
        print("Example: python mergemd.py beginner 1-5")
        print("         python mergemd.py advanced 10-15")
        sys.exit(1)

    directory = sys.argv[1]
    range_str = sys.argv[2]

    # Parse range
    result = parse_range(range_str)
    if result is None:
        print(f"Error: Invalid range format '{range_str}'")
        print("Range should be in format 'start-end' (e.g., '1-5') or a single number (e.g., '5')")
        sys.exit(1)

    start, end = result

    print(f"Merging chapters {start} to {end} in directory '{directory}'")

    # Perform merge
    success = merge_markdown_files(directory, start, end)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
