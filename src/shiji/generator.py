"""生成器:把提取结果 + 当日游戏化上下文,渲染成 notes/YYYY-MM-DD.md。"""
from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from shiji.models import DayExtraction

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_USER_NOTES_RE = re.compile(r"<!-- user-notes -->.*?<!-- /user-notes -->", re.S)

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_note(extraction: DayExtraction, ctx: dict) -> str:
    """ctx 需含 day_index/streak/grace_used/grace_days/weekday/sessions/turns/
    mistakes_resolved/today_badges/model。"""
    tpl = _env.get_template("note.md.j2")
    return tpl.render(**extraction.model_dump(), **ctx)


def write_note(path: Path, content: str) -> None:
    """写笔记；若文件已存在，保留旧的 user-notes 区块不覆盖。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = path.read_text(encoding="utf-8")
        m = _USER_NOTES_RE.search(old)
        if m:
            old_block = m.group(0)
            content = _USER_NOTES_RE.sub(lambda _: old_block, content, count=1)
    path.write_text(content, encoding="utf-8")
