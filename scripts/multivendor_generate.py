"""
跨廠商生成模組（回應教授原始表格需求）：
讓 Claude / GPT-4o / Gemini 三個模型都能「生成」保險顧問回應（不只當評審），
搭配三種文件處理策略（全文 / 切割段落+profile / Docling切割無profile），
組成 4（生成引擎：LLM1/LLM2/LLM3/SBERT）× 3（文件策略）矩陣。

沿用 backend/services/claude_service.py 的 SYSTEM_PROMPT，確保三廠商使用相同指令，
僅生成參數依各自 API 介面調整（均嘗試 temperature=0）。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")

from anthropic import Anthropic, AsyncAnthropic
from openai import OpenAI
from google import genai as ggenai
from google.genai import types as gtypes

from services.claude_service import SYSTEM_PROMPT

claude_client = Anthropic(api_key=os.environ["CLAUDE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
gemini_client = ggenai.Client(api_key=os.environ["Google_AI_Studio_API_key"])


def _system_with_context(context: str) -> str:
    return f"{SYSTEM_PROMPT}\n\n{context}" if context else SYSTEM_PROMPT


def generate_claude(message: str, context: str) -> str:
    resp = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
        system=_system_with_context(context),
        messages=[{"role": "user", "content": message}],
    )
    return resp.content[0].text


def generate_gpt4o(message: str, context: str) -> str:
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        temperature=0,
        messages=[
            {"role": "system", "content": _system_with_context(context)},
            {"role": "user", "content": message},
        ],
    )
    return resp.choices[0].message.content


def generate_gemini(message: str, context: str) -> str:
    resp = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=message,
        config=gtypes.GenerateContentConfig(
            temperature=0,
            max_output_tokens=1024,
            system_instruction=_system_with_context(context),
            thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
        ),
    )
    return resp.text


GENERATORS = {
    "LLM1_Claude": generate_claude,
    "LLM2_GPT4o": generate_gpt4o,
    "LLM3_Gemini": generate_gemini,
}
