#!/usr/bin/env python3
"""
Fix links in Recommended Readings sections to markdown format.

Converts:
  1. Title (Source) <url>
To:
  1. [Title](url) (Source)

Usage:
    python fix_links.py <directory>

Example:
    python fix_links.py beginner/
    python fix_links.py advanced/
"""

import os
import sys
import re
from pathlib import Path


def fix_links_in_content(content):
    """
    Convert plain URLs in recommended readings to markdown format.

    Converts patterns like:
      1. Title (Source) <url>
    To:
      1. [Title](url) (Source)

    Args:
        content: File content as string

    Returns:
        Fixed content
    """
    # Pattern to match: number. text (optional source) <url>
    # Example: 1. Some Title (Author) <https://example.com>
    pattern = r'(\d+\.)\s+([^<\n]+?)\s*(?:\(([^)]+)\))?\s*<(https?://[^>]+)>'

    def replacement(match):
        number = match.group(1)  # "1."
        title = match.group(2).strip()  # "Some Title"
        source = match.group(3)  # "Author" or None
        url = match.group(4)  # "https://example.com"

        # Build the markdown format
        if source:
            return f'{number} [{title}]({url}) ({source})'
        else:
            return f'{number} [{title}]({url})'

    # Apply the replacement
    fixed_content = re.sub(pattern, replacement, content)

    return fixed_content


def fix_file(file_path):
    """
    Fix links in a single markdown file.

    Args:
        file_path: Path to the markdown file

    Returns:
        True if changes were made, False otherwise
    """
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Fix links
        fixed_content = fix_links_in_content(original_content)

        # Check if any changes were made
        if fixed_content != original_content:
            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            return True

        return False

    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


def fix_directory(dir_path):
    """
    Fix links in all markdown files in a directory.

    Args:
        dir_path: Path to the directory
    """
    if not dir_path.exists():
        print(f"错误: 目录不存在: {dir_path}")
        return

    # Find all markdown files
    md_files = list(dir_path.glob("*.md"))

    if not md_files:
        print(f"警告: 在 {dir_path} 中未找到 .md 文件")
        return

    print(f"\n找到 {len(md_files)} 个 markdown 文件")
    print("开始修复链接格式...\n")

    # Statistics
    fixed_count = 0
    skipped_count = 0

    # Process each file
    for file_path in sorted(md_files):
        sys.stdout.write(f"处理: {file_path.name}...")
        sys.stdout.flush()

        if fix_file(file_path):
            print(" ✓ 已修复")
            fixed_count += 1
        else:
            print(" - 跳过（无需修改）")
            skipped_count += 1

    # Show summary
    print("\n" + "="*50)
    print("修复完成!")
    print(f"  已修复: {fixed_count}")
    print(f"  已跳过: {skipped_count}")
    print("="*50)


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("用法: python fix_links.py <directory>")
        print("\n示例:")
        print("  python fix_links.py beginner/")
        print("  python fix_links.py advanced/")
        sys.exit(1)

    path_str = sys.argv[1]
    path = Path(path_str)

    if not path.exists():
        print(f"错误: 路径不存在: {path}")
        sys.exit(1)

    if not path.is_dir():
        print(f"错误: 路径不是目录: {path}")
        sys.exit(1)

    print(f"修复目录中的链接: {path}")
    fix_directory(path)


if __name__ == "__main__":
    main()
