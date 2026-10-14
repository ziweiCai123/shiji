"""采集器:扫描本地 Claude Code JSONL,解析 user/assistant 轮次,按本地日期分组。"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_KEEP_TYPES = {"user", "assistant"}


@dataclass
class Turn:
    role: str
    text: str
    tools: list[str] = field(default_factory=list)
    timestamp: str = ""
    cwd: str = ""
    git_branch: str = ""
    is_human: bool = True


@dataclass
class Session:
    path: str
    cwd: str
    git_branch: str
    turns: list[Turn]

    @property
    def text(self) -> str:
        out = []
        for t in self.turns:
            tag = "🙋 用户" if t.role == "user" else "🤖 助手"
            body = t.text
            if t.tools:
                body += f"  [调用工具: {', '.join(t.tools)}]"
            out.append(f"{tag}: {body}".strip())
        return "\n".join(out)


def find_jsonl_files(claude_dir: Path) -> list[Path]:
    if not claude_dir.exists():
        return []
    return sorted(claude_dir.rglob("*.jsonl"))


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(p for p in parts if p)
    return ""


def _content_tools(content) -> list[str]:
    tools: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = block.get("name", "")
                if name:
                    tools.append(name)
    return tools


def parse_session(path: Path) -> Session | None:
    turns: list[Turn] = []
    cwd = ""
    git_branch = ""
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = obj.get("type")
            if t not in _KEEP_TYPES:
                continue
            msg = obj.get("message") or {}
            content = msg.get("content")
            text = _content_text(content)
            tools = _content_tools(content)
            if not text and not tools:
                continue
            origin = obj.get("origin") or {}
            cwd = obj.get("cwd") or cwd
            git_branch = obj.get("gitBranch") or git_branch
            turns.append(
                Turn(
                    role=t,
                    text=text,
                    tools=tools,
                    timestamp=obj.get("timestamp", ""),
                    cwd=cwd,
                    git_branch=git_branch,
                    is_human=origin.get("kind") != "tool",
                )
            )
    if not turns:
        return None
    return Session(path=str(path), cwd=cwd, git_branch=git_branch, turns=turns)


def _to_local_date(ts: str) -> str | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date().isoformat()


def group_by_day(sessions: list[Session]) -> dict[str, list[Session]]:
    by_day: dict[str, list[Session]] = defaultdict(list)
    for s in sessions:
        if not s.turns:
            continue
        date = _to_local_date(s.turns[-1].timestamp) or _to_local_date(s.turns[0].timestamp)
        if date:
            by_day[date].append(s)
    return by_day


def day_text(
    sessions: list[Session],
    max_chars: int = 24000,
    max_turn_chars: int = 800,
    max_turns: int = 120,
) -> str:
    """拼成喂给 LLM 的当天文本。真实一天可能有数十万字,这里做代表性抽取:
    每轮截断、过多则均匀采样、整体按字符上限截断,保证便宜且聚焦。"""
    items: list[tuple[str, str, str]] = []  # (cwd, role, text)
    for s in sessions:
        for t in s.turns:
            txt = t.text
            if t.tools and not txt:
                txt = f"[调用工具: {', '.join(t.tools)}]"
            if not txt:
                continue
            if len(txt) > max_turn_chars:
                txt = txt[:max_turn_chars] + " …(截断)"
            items.append((s.cwd, t.role, txt))

    if len(items) > max_turns:
        step = len(items) / max_turns
        items = [items[int(i * step)] for i in range(max_turns)]

    parts: list[str] = []
    cur_cwd: str | None = None
    total = 0
    for cwd, role, txt in items:
        if cwd != cur_cwd:
            parts.append(f"### 会话 (cwd: {cwd or '?'})")
            cur_cwd = cwd
        line = f"{'🙋 用户' if role == 'user' else '🤖 助手'}: {txt}"
        if total + len(line) > max_chars and len(parts) > 1:
            parts.append("…（当日对话过长，已截断，仅取代表性部分）")
            break
        parts.append(line)
        total += len(line)
    return "\n".join(parts)


def summarize_day(sessions: list[Session]) -> dict:
    cwds: set[str] = set()
    turns = 0
    for s in sessions:
        if s.cwd:
            cwds.add(s.cwd)
        turns += len(s.turns)
    return {"sessions": len(sessions), "turns": turns, "cwds": sorted(cwds)}
