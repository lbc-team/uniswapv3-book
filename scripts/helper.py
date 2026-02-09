import os

def get_post_replacements():
    replacements = {}
    file_path = "post_replacement.csv"

    if not os.path.exists(file_path):
        return replacements

    with open(file_path, "r", encoding="utf-8") as file:
        next(file)  # 去除表头
        for line in file:
            original, replacement = line.strip().split(",")
            replacements[original] = replacement

    return replacements


def replace_some_terms(text):
    replacements = get_post_replacements()
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text