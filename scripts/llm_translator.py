import openai
import os
import json
from spliter import split_text

from dotenv import load_dotenv

load_dotenv(".env")

from config import OPENROUTER_MODEL_GEMINI_20_FLASH, OPENROUTER_PREFIX

TRANSLATE_PROMPT = """
用户将提供给你 Uniswap V3 Development Book 书中的某一章节的 markdown内容，请你将内容翻译成中文，注意只做翻译，不要删减内容，不要添加解释和演绎。
输出格式保持 markdown 格式。

你必须严格遵循以下规则：
1. 遇到一些暂时没有合适翻译的专业术语或产品名称，保留英文原文，例如 Uniswap 
2. 翻译后的内容必须保持原文的结构，包括标题、段落、列表、表格、空行等和原文一致
3. 代码块处理规则：
   - 只翻译代码注释，代码本身保持不变
   - 所有的 json 代码，保持原文不变
   - 保持代码块的语言标记，如 ```solidity 等
   - 保持单行代码标记，如 `code`

4. 格式转换规则：
   - 保持所有链接标记 [text](url) 的格式不变，仅翻译其中的文本内容
"""

class LLMTranslator:
    def __init__(self, model=OPENROUTER_MODEL_GEMINI_20_FLASH):
        self.model = model

        # 初始化客户端，API密钥从环境变量读取
        if model.startswith("gpt-"):
            api_key=os.getenv("OPENAI_API_KEY")
            base_url=os.getenv("OPENAI_BASE_URL")

            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        elif model.startswith("deepseek"):
            api_key = os.getenv("ALI_AI_API_KEY")
            base_url = os.getenv("ALI_AI_BASE_URL")

            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        elif model.startswith(OPENROUTER_PREFIX):
            api_key = os.getenv("OPENROUTER_API_KEY")
            base_url = os.getenv("OPENROUTER_BASE_URL")

            colIndex = model.find(":")
            self.model = model[colIndex+1:]
            print(f"使用 OpenRouter 模型: {self.model}")
            self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def simple_translate(self, text):
        system_prompt = "你是一个精通中文的与英文的DeFi领域的专家，请将以下英文内容翻译成中文，仅返回翻译后的中文内容，不要添加任何解释。"

        request_params = {
            "model": self.model,
            "temperature": 1, 
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        }

        response = self.client.chat.completions.create(**request_params)
        return response.choices[0].message.content

    def translate_markdown(self, markdown_text):

        translated_text = ""
        chunks = split_text(markdown_text)

        for chunk in chunks:
            translated_chunk = self.translate(chunk)
            translated_text += translated_chunk

        return translated_text

    def translate(self, markdown_text):
        request_params = {
            "model": self.model,
            "temperature": 1.1, 
            "messages": [
                {"role": "system", "content": TRANSLATE_PROMPT},
                {"role": "user", "content": markdown_text}
            ]
        }


        response = self.client.chat.completions.create(**request_params)
        return response.choices[0].message.content
