"""提取器:把一天的对话文本交给 LLM(OpenAI 兼容),返回结构化 DayExtraction。"""
from __future__ import annotations

import json
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError
from rich.console import Console

from shiji.config import Config
from shiji.models import DayExtraction, SCHEMA_JSON

console = Console()
_PROMPT_PATH = Path(__file__).parent / "prompts" / "extract.md"


def _system_prompt() -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    schema_str = json.dumps(SCHEMA_JSON, ensure_ascii=False, indent=2)
    return template.replace("{{ schema }}", schema_str)


def extract_day(cfg: Config, day_text_content: str, date: str) -> DayExtraction:
    """对一天的对话文本做提取。失败重试 1 次。"""
    if not cfg.llm.api_key:
        raise RuntimeError(
            f"未设置 LLM API key。请设置环境变量 {cfg.llm.api_key_env}"
            f"（或修改 .trace/config.toml 的 [llm].api_key_env 指向你用的变量名）。"
        )

    client = OpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key)
    system = _system_prompt()
    user_msg = f"日期：{date}\n\n今日对话记录：\n{day_text_content}"

    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            resp = client.chat.completions.create(
                model=cfg.llm.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            raw = resp.choices[0].message.content or "{}"
            data = json.loads(raw)
            data["date"] = date  # 强制对齐日期，防止模型乱编
            return DayExtraction.model_validate(data)
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = e
            console.print(f"[yellow]提取第 {attempt} 次返回不合规：{e}[/]")
        except Exception as e:  # 网络 / API 错误
            last_err = e
            console.print(f"[yellow]提取第 {attempt} 次 API 调用失败：{e}[/]")

    raise RuntimeError(f"LLM 提取失败：{last_err}")
