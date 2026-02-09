#  脚本说明

## 文档处理脚本

### 1. Markdown 文件翻译 (`translate.py`)

使用 LLM 自动翻译 Markdown 文件。

**使用方法**:
```bash
python scripts/translate.py <path>
```

**示例**:
```bash
# 翻译单个文件
python scripts/translate.py beginner/chapter_1.md

# 翻译整个目录
python scripts/translate.py beginner/

# 翻译 advanced 目录
python scripts/translate.py advanced/
```

**详细文档**: [TRANSLATE_README.md](TRANSLATE_README.md)

---

### 2. 修复链接格式 (`fix_links.py`)

将推荐阅读部分的链接转换为标准 Markdown 格式。

**使用方法**:
```bash
python scripts/fix_links.py <directory>
```

**示例**:
```bash
# 修复 beginner 目录的链接
python scripts/fix_links.py beginner/

# 修复 advanced 目录的链接
python scripts/fix_links.py advanced/
```

**修复效果**:
- 修复前: `1. 标题 (来源) <https://example.com>`
- 修复后: `1. [标题](https://example.com) (来源)`

---

### 配置文件
- `.env`: 环境变量配置文件
  ```
  OPENROUTER_API_KEY=""
  OPENROUTER_BASE_URL=""
  ```


## 环境设置

1. 创建并激活虚拟环境：
   ```
   python3 -m venv myenv
   source myenv/bin/activate
   ```
2. 安装依赖：
   ```
   pip install -r requirements.txt
   ```

## 运行

在 myenv 环境下 执行 

```
python publish_article.py
```


