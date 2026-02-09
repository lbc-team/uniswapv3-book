#!/usr/bin/env python3
"""
Translate markdown files using LLM.

Usage:
    python translate.py <path>

Arguments:
    path: Directory or file path to translate
          - If directory: translates all .md files recursively
          - If file: translates only that file

Example:
    python translate.py beginner/
    python translate.py beginner/chapter_1.md
    python translate.py advanced/chapter_10.md
"""

import llm_translator
from config import OPENROUTER_MODEL_GEMINI_20_FLASH
import os
import sys
from pathlib import Path
from helper import replace_some_terms


def translate_markdown(content):
    """
    Translate markdown content using LLM.

    Args:
        content: The markdown content to translate

    Returns:
        Translated content or None if failed
    """
    try:
        translator = llm_translator.LLMTranslator(OPENROUTER_MODEL_GEMINI_20_FLASH)
        result = translator.translate_markdown(content)
        if result:
            return result
    except Exception as e:
        print(f"翻译失败: {e}")
    return None


def translate_file(file_path):
    """
    Translate a single markdown file.

    Args:
        file_path: Path to the markdown file

    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\n正在处理文件: {file_path}")

        # 如果已经有 .bak 的同名文件，跳过翻译
        bak_path = file_path.with_suffix(file_path.suffix + ".bak")
        if bak_path.exists():
            print(f"⊘ 跳过翻译: {file_path}（已存在备份文件）")
            return False

        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查文件是否为空
        if not content.strip():
            print(f"⊘ 跳过空文件: {file_path}")
            return False

        # 翻译内容
        print(f"  翻译中...")
        translated_content = translate_markdown(content)
        translated_content = replace_some_terms(translated_content)

        if translated_content:
            # 备份原文件
            backup_path = str(file_path) + ".bak"
            os.rename(file_path, backup_path)
            print(f"  ✓ 已备份原文件: {backup_path}")

            # 写入翻译后的内容
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(translated_content)
            print(f"  ✓ 翻译成功: {file_path}")
            return True
        else:
            print(f"  ✗ 翻译失败: {file_path}")
            return False

    except Exception as e:
        print(f"  ✗ 处理文件时发生错误: {e}")
        return False


def translate_directory(dir_path):
    """
    Translate all markdown files in a directory recursively.

    Args:
        dir_path: Path to the directory
    """
    if not dir_path.exists():
        print(f"错误: 目录不存在: {dir_path}")
        return

    # 查找所有 markdown 文件
    md_files = list(dir_path.rglob("*.md"))

    if not md_files:
        print(f"警告: 在 {dir_path} 中未找到 .md 文件")
        return

    print(f"\n找到 {len(md_files)} 个 markdown 文件")

    # 统计
    success_count = 0
    skip_count = 0
    fail_count = 0

    # 遍历所有文件
    for file_path in md_files:
        result = translate_file(file_path)
        if result:
            success_count += 1
        elif file_path.with_suffix(file_path.suffix + ".bak").exists():
            skip_count += 1
        else:
            fail_count += 1

    # 显示总结
    print("\n" + "="*50)
    print("翻译完成!")
    print(f"  成功: {success_count}")
    print(f"  跳过: {skip_count}")
    print(f"  失败: {fail_count}")
    print("="*50)


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("用法: python translate.py <path>")
        print("\n示例:")
        print("  python translate.py beginner/")
        print("  python translate.py beginner/chapter_1.md")
        print("  python translate.py advanced/chapter_10.md")
        sys.exit(1)

    path_str = sys.argv[1]
    path = Path(path_str)

    if not path.exists():
        print(f"错误: 路径不存在: {path}")
        sys.exit(1)

    # 判断是文件还是目录
    if path.is_file():
        # 检查是否是 markdown 文件
        if path.suffix != ".md":
            print(f"错误: 只支持 .md 文件，当前文件: {path}")
            sys.exit(1)

        print(f"翻译单个文件: {path}")
        translate_file(path)

    elif path.is_dir():
        print(f"翻译目录: {path}")
        translate_directory(path)

    else:
        print(f"错误: 无效的路径类型: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()

