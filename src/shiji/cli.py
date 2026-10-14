"""拾迹 Trace 命令行入口。"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from shiji import aggregator, collector, extractor, generator, store
from shiji.config import Config, load_config
from shiji.models import DayExtraction

app = typer.Typer(
    help="拾迹 Trace — 从 Claude Code 对话自动生成学习笔记与成长轨迹",
    no_args_is_help=True,
)
console = Console()

_DEFAULT_CONFIG_TOML = """\
# 拾迹 Trace 配置 — 改完保存即可，下次运行生效
[llm]
# OpenAI 兼容接口。默认智谱 GLM（你 Claude Code 用的就是它）
base_url = "https://open.bigmodel.cn/api/paas/v4/"
# API key 从这个环境变量读取（不要把 key 写进文件）
api_key_env = "ZHIPUAI_API_KEY"
model = "glm-4.6"
# 想换 DeepSeek: base_url="https://api.deepseek.com"  model="deepseek-chat"  api_key_env="DEEPSEEK_API_KEY"
# 想换 Qwen:    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"  model="qwen-plus"  api_key_env="DASHSCOPE_API_KEY"

[streak]
# 每月最多断这么多天不让连续归零
grace_days = 3

[sources]
# 跳过这些工作目录的对话（比如含公司敏感代码的项目）
# exclude_cwds = ["C:\\\\Users\\\\me\\\\company-secrets"]
"""


@app.command()
def init():
    """在当前目录初始化：创建 .trace/config.toml 和 notes/。"""
    root = Path.cwd()
    trace_dir = root / ".trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "config.toml").write_text(_DEFAULT_CONFIG_TOML, encoding="utf-8")
    (root / "notes").mkdir(exist_ok=True)
    (root / ".gitignore").write_text(
        ".trace/trace.db\n.venv/\n__pycache__/\n", encoding="utf-8"
    )
    console.print(f"[green]已初始化：[/]{trace_dir / 'config.toml'}")
    console.print(f"[green]笔记目录：[/]{root / 'notes'}")
    console.print(
        f"\n下一步：设置环境变量后运行 [cyan]shiji today[/] 生成今天的学习笔记。"
    )


@app.command()
def collect(
    dry_run: bool = typer.Option(False, "--dry-run", help="只解析不调 LLM，打印统计"),
    date_filter: str = typer.Option(None, "--date", "-d", help="只看某天 YYYY-MM-DD"),
):
    """采集本地 Claude Code 对话并打印统计。"""
    cfg = load_config()
    files = collector.find_jsonl_files(cfg.claude_dir)
    if not files:
        console.print(f"[red]没找到对话文件：[/]{cfg.claude_dir}")
        console.print("确认 Claude Code 用过、且有 .jsonl 记录。")
        raise typer.Exit(1)

    sessions = [s for s in (collector.parse_session(f) for f in files) if s]
    by_day = collector.group_by_day(sessions)

    console.print(
        f"找到 [cyan]{len(files)}[/] 个会话文件 · "
        f"[cyan]{len(sessions)}[/] 个有效会话 · 跨 [cyan]{len(by_day)}[/] 天\n"
    )

    table = Table("日期", "会话数", "轮次", "工作目录")
    for d in sorted(by_day, reverse=True):
        if date_filter and d != date_filter:
            continue
        info = collector.summarize_day(by_day[d])
        cwds = "\n".join(info["cwds"]) or "—"
        table.add_row(d, str(info["sessions"]), str(info["turns"]), cwds)
    console.print(table)

    if dry_run:
        target = date_filter or date.today().isoformat()
        if target in by_day:
            text, turns = collector.day_text(by_day[target])
            console.print(
                f"\n[cyan]{target}[/] 将送给 LLM 的文本约 "
                f"[bold]{len(text)}[/] 字符 / {turns} 轮（dry-run，不调用 LLM）"
            )
        else:
            console.print(f"\n[yellow]{target} 没有对话记录。[/]")
        return


def _extract_and_store(cfg: Config, conn, target: str, force: bool) -> tuple[DayExtraction, int, int] | None:
    """采集 target 这天 → 提取(或读缓存) → 存库。返回 (extraction, sessions, turns)。"""
    files = collector.find_jsonl_files(cfg.claude_dir)
    sessions = [s for s in (collector.parse_session(f) for f in files) if s]
    by_day = collector.group_by_day(sessions)
    if target not in by_day:
        return None
    day_sessions = by_day[target]
    info = collector.summarize_day(day_sessions)
    turns = info["turns"]
    n_sessions = info["sessions"]
    text = collector.day_text(day_sessions)

    if not force and store.has_extraction(conn, target):
        console.print(f"[green]命中缓存[/]，{target} 已提取过，直接用（--force 可重跑）")
        payload = store.get_extraction(conn, target)
    else:
        console.print(f"调用 LLM 提取 [cyan]{target}[/] ……")
        extraction = extractor.extract_day(cfg, text, target)
        payload = extraction.model_dump()
        store.save_extraction(conn, target, payload, n_sessions, turns)
    return DayExtraction.model_validate(payload), n_sessions, turns


@app.command()
def today(
    target: str = typer.Option(None, "--date", "-d", help="指定日期，默认今天"),
    force: bool = typer.Option(False, "--force", help="强制重新调用 LLM"),
):
    """端到端：采集今天 → 提取 → 生成笔记 → 更新 README。"""
    cfg = load_config()
    if not cfg.config_path.exists():
        console.print("[yellow]当前目录还没初始化，先运行 [cyan]shiji init[/][/]")
        raise typer.Exit(1)
    target = target or date.today().isoformat()

    conn = store.connect(cfg.db_path)
    try:
        result = _extract_and_store(cfg, conn, target, force)
        if result is None:
            console.print(
                f"[yellow]{target} 没有对话记录。[/]今天还没和 Claude Code 聊过？"
            )
            raise typer.Exit(0)
        extraction, n_sessions, turns = result

        records = list(store.all_extractions(conn))
        ctx = aggregator.note_context(records, target, cfg.grace_days, cfg.llm.model)
        ctx["sessions"] = n_sessions
        ctx["turns"] = turns

        note_path = cfg.notes_dir / f"{target}.md"
        content = generator.render_note(extraction, ctx)
        generator.write_note(note_path, content)

        stats = aggregator.write_aggregates(cfg, conn)
    finally:
        conn.close()

    console.print(f"\n[green]✓ 已生成笔记：[/]{note_path}")
    console.print(f"[green]✓ 已更新成长轨迹：[/]{cfg.root / 'README.md'}")
    console.print(
        f"🔥 连续 {stats['streak']} 天 · 累计 {stats['total_days']} 天 · "
        f"🐛 攻克 {stats['problems_solved']} · 🧭 技术 {len(stats['tech_counter'])}"
    )
    if ctx["today_badges"]:
        console.print(f"[bold yellow]🏅 新徽章：[/]{' · '.join(ctx['today_badges'])}")


@app.command()
def aggregate():
    """只重算 README/STATS（不调 LLM）。"""
    cfg = load_config()
    conn = store.connect(cfg.db_path)
    try:
        stats = aggregator.write_aggregates(cfg, conn)
    finally:
        conn.close()
    console.print(
        f"[green]✓ README 已更新[/] · 🔥 {stats['streak']} · "
        f"累计 {stats['total_days']} 天 · 🐛 {stats['problems_solved']}"
    )
