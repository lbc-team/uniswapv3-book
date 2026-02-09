import re
from pathlib import Path


# https://img.learnblockchain.cn/how_to_defi/advanced/media/PG_146.png
def add_image_prefix(content, prefix="https://img.learnblockchain.cn/how_to_defi/read_write_own/"):
    """
    给 markdown 内容中的图片链接添加前缀

    参数:
        content: markdown 文本内容
        prefix: 要添加的前缀 URL

    返回:
        处理后的内容
    """
    # 匹配 markdown 图片语法: ![alt text](path)
    # 只处理相对路径，不处理已经是 http:// 或 https:// 开头的链接
    pattern = r'!\[([^\]]*)\]\((?!https?://)([^)]+)\)'

    def replace_func(match):
        alt_text = match.group(1)
        image_path = match.group(2)
        # 添加前缀
        new_url = f"{prefix}{image_path}"
        return f"![{alt_text}]({new_url})"

    # 执行替换
    updated_content = re.sub(pattern, replace_func, content)
    return updated_content


def process_markdown_files(src_dir="src", backup=True):
    """
    处理指定目录下的所有 markdown 文件

    参数:
        src_dir: 源文件目录
        backup: 是否备份原文件
    """
    src_path = Path(src_dir)

    if not src_path.exists():
        print(f"错误: {src_dir} 目录不存在")
        return

    # 统计信息
    total_files = 0
    processed_files = 0
    skipped_files = 0

    # 遍历所有 .md 文件
    for file_path in src_path.rglob("*.md"):
        total_files += 1

        try:
            print(f"\n正在处理文件: {file_path}")

            # 读取文件内容
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 处理内容
            updated_content = add_image_prefix(content)

            # 检查是否有变化
            if updated_content == content:
                print(f"  ⏭️  跳过: 文件中没有需要更新的图片链接")
                skipped_files += 1
                continue

            # 备份原文件（如果需要）
            if backup:
                backup_path = str(file_path) + ".bak"
                # 如果备份文件已存在，不覆盖
                if not Path(backup_path).exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        original_content = f.read()
                    with open(backup_path, "w", encoding="utf-8") as f:
                        f.write(original_content)
                    print(f"  💾 已备份到: {backup_path}")

            # 写入更新后的内容
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            print(f"  ✅ 成功处理文件")
            processed_files += 1

        except Exception as e:
            print(f"  ❌ 处理文件时发生错误: {e}")

    # 打印统计信息
    print(f"\n{'='*60}")
    print(f"处理完成!")
    print(f"总文件数: {total_files}")
    print(f"已处理: {processed_files}")
    print(f"已跳过: {skipped_files}")
    print(f"失败: {total_files - processed_files - skipped_files}")
    print(f"{'='*60}")


if __name__ == "__main__":
    # 可以通过修改这里的参数来自定义行为
    # backup=False 表示不备份原文件
    process_markdown_files(src_dir="read_write_own", backup=True)
