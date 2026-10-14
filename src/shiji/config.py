"""配置加载:在「笔记仓库根目录」(含 .trace/) 运行,读取 .trace/config.toml。"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMConfig:
    base_url: str
    api_key_env: str
    model: str

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass
class Config:
    root: Path
    trace_dir: Path
    db_path: Path
    badges_path: Path
    config_path: Path
    notes_dir: Path
    claude_dir: Path
    llm: LLMConfig
    grace_days: int
    exclude_cwds: list[str] = field(default_factory=list)
    local_model: bool = False


def find_root(start: Path | None = None) -> Path:
    """从 start 向上找含 .trace/ 的目录;找不到就用当前目录。"""
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / ".trace").is_dir():
            return cand
    return p


def load_config(root: Path | None = None) -> Config:
    root = find_root(root)
    trace_dir = root / ".trace"
    config_path = trace_dir / "config.toml"
    data: dict = {}
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

    llm_section = data.get("llm", {})
    streak_section = data.get("streak", {})

    llm = LLMConfig(
        base_url=llm_section.get("base_url", "https://open.bigmodel.cn/api/paas/v4/"),
        api_key_env=llm_section.get("api_key_env", "ZHIPUAI_API_KEY"),
        model=llm_section.get("model", "glm-4.6"),
    )

    claude_dir = Path(data.get("claude_dir", str(Path.home() / ".claude" / "projects"))).expanduser()

    return Config(
        root=root,
        trace_dir=trace_dir,
        db_path=trace_dir / "trace.db",
        badges_path=trace_dir / "badges.json",
        config_path=config_path,
        notes_dir=root / data.get("notes_dir", "notes"),
        claude_dir=claude_dir,
        llm=llm,
        grace_days=int(streak_section.get("grace_days", 3)),
        exclude_cwds=list(data.get("exclude_cwds", [])),
        local_model=bool(llm_section.get("local_model", False)),
    )
