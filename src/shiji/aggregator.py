"""聚合器:从所有提取结果重算成长轨迹(连续天数/技能/徽章/热力图),写出 README.md。"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from shiji import store

_WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


def _weekday_zh(date_str: str) -> str:
    try:
        return _WEEKDAYS[date.fromisoformat(date_str).weekday()]
    except Exception:
        return "?"


def streak_with_grace(dates_set: set[str], cutoff_iso: str, grace: int) -> tuple[int, int]:
    """从 cutoff 往回数连续学习天数;gap 消耗 grace,耗尽即断。
    今天(cutoff 当天)若还没笔记,算免费跳过一天,不消耗 grace。"""
    cutoff = date.fromisoformat(cutoff_iso)
    streak = 0
    grace_used = 0
    for i in range(0, 366):
        d = (cutoff - timedelta(days=i)).isoformat()
        if d in dates_set:
            streak += 1
        else:
            if streak == 0 and i == 0:
                continue  # 今天还没生成,免费跳过
            if grace_used < grace:
                grace_used += 1
            else:
                break
    return streak, grace_used


def compute_badges(
    streak: int,
    tech_counter: Counter,
    tech_days: dict[str, set],
    problems_solved: int,
) -> list[str]:
    b: list[str] = []
    n_tech = len(tech_counter)
    if streak >= 30:
        b.append("🔥🔥 30 天连击")
    elif streak >= 7:
        b.append("🔥 7 天连击")
    if n_tech >= 15:
        b.append("🧭🧭 老练探索者（15+ 技术）")
    elif n_tech >= 5:
        b.append("🧭 探索者（5+ 技术）")
    for lvl, thresh in ((3, 20), (2, 10), (1, 5)):
        if problems_solved >= thresh:
            b.append(f"🐛 Debug 侦探 Lv.{lvl}（攻克 {thresh}+ 问题）")
            break
    deep = sorted(n for n, days in tech_days.items() if len(days) >= 3)
    if deep:
        b.append(f"📖 深挖者（{deep[0]} 跨 3+ 天）")
    return b


def aggregate(records: Iterable[tuple[str, dict]], cutoff: str, grace: int) -> dict:
    recs = [(d, p) for d, p in records if d <= cutoff]
    dates_set = {d for d, _ in recs}
    tech_counter: Counter = Counter()
    tech_days: dict[str, set] = defaultdict(set)
    problems_solved = 0
    for d, p in recs:
        for t in p.get("technologies", []):
            name = (t.get("name") or "").strip()
            if name:
                tech_counter[name] += 1
                tech_days[name].add(d)
        for m in p.get("mistakes_and_debugging", []):
            if m.get("resolved"):
                problems_solved += 1
    streak, grace_used = streak_with_grace(dates_set, cutoff, grace)
    badges = compute_badges(streak, tech_counter, tech_days, problems_solved)
    return {
        "dates_set": dates_set,
        "dates_sorted": sorted(dates_set),
        "tech_counter": tech_counter,
        "tech_days": tech_days,
        "problems_solved": problems_solved,
        "total_days": len(dates_set),
        "streak": streak,
        "grace_used": grace_used,
        "badges": badges,
        "cutoff": cutoff,
    }


def today_new_badges(records: list[tuple[str, dict]], date_str: str, grace: int) -> list[str]:
    through_today = aggregate(records, date_str, grace)["badges"]
    yesterday = (date.fromisoformat(date_str) - timedelta(days=1)).isoformat()
    through_yesterday = aggregate(records, yesterday, grace)["badges"]
    return sorted(set(through_today) - set(through_yesterday))


def note_context(
    records: list[tuple[str, dict]], date_str: str, grace: int, model: str
) -> dict:
    stats = aggregate(records, date_str, grace)
    day_index = sum(1 for d, _ in records if d <= date_str)
    today_payload = next((p for d, p in records if d == date_str), {})
    resolved = sum(
        1 for m in today_payload.get("mistakes_and_debugging", []) if m.get("resolved")
    )
    return {
        "day_index": day_index,
        "streak": stats["streak"],
        "grace_used": stats["grace_used"],
        "grace_days": grace,
        "weekday": _weekday_zh(date_str),
        "mistakes_resolved": resolved,
        "today_badges": today_new_badges(records, date_str, grace),
        "model": model,
    }


def _heatmap(dates_set: set[str], cutoff_iso: str, weeks: int = 8) -> str:
    end = date.fromisoformat(cutoff_iso)
    monday = end - timedelta(days=end.weekday())
    start_monday = monday - timedelta(weeks=weeks - 1)
    rows = []
    for w in range(weeks):
        cells = []
        for dow in range(7):
            d = (start_monday + timedelta(weeks=w, days=dow)).isoformat()
            cells.append("🟩" if d in dates_set else "⬜")
        rows.append("".join(cells))
    header = "".join(_WEEKDAYS)
    return f"近 {weeks} 周活跃（🟩=有学习 ⬜=无）：\n\n```\n{header}\n" + "\n".join(rows) + "\n```"


def _skill_table(tech_counter: Counter, cap: int = 8) -> str:
    if not tech_counter:
        return "_（还没有技术被记录，去和 AI 多聊聊吧）_"
    lines = []
    for name, cnt in tech_counter.most_common():
        filled = min(cap, cnt)
        bar = "█" * filled + "░" * (cap - filled)
        lines.append(f"- `{bar}` {filled}/{cap}  **{name}** · 出现 {cnt} 次")
    return "\n".join(lines)


def _recent_notes(dates_sorted: list[str], notes_dir: Path, limit: int = 7) -> str:
    recent = list(reversed(dates_sorted))[:limit]
    if not recent:
        return "_（还没有笔记）_"
    rel = notes_dir.relative_to(notes_dir.parents[0]) if notes_dir.parents else Path("notes")
    lines = [f"- [{d}]({rel}/{d}.md)" for d in recent]
    return "\n".join(lines)


def build_readme(stats: dict, notes_dir: Path) -> str:
    parts = [
        "# 🚀 我的成长轨迹",
        "",
        "> 多对话 · 多犯错 · 多学习 — 由 **拾迹 Trace** 自动记录",
        "",
        f"🔥 连续 **{stats['streak']}** 天 · 累计学习 **{stats['total_days']}** 天 "
        f"· 🐛 已攻克问题 **{stats['problems_solved']}** · 🧭 已点亮技术 **{len(stats['tech_counter'])}**",
        "",
        _heatmap(stats["dates_set"], stats["cutoff"]),
        "",
        "## 🌳 技能进度",
        "",
        _skill_table(stats["tech_counter"]),
        "",
        "## 🏅 徽章墙",
        "",
        "\n".join(f"- {b}" for b in stats["badges"]) if stats["badges"] else "_（继续学习解锁第一个徽章）_",
        "",
        "## 📝 最近笔记",
        "",
        _recent_notes(stats["dates_sorted"], notes_dir),
        "",
    ]
    return "\n".join(parts)


def write_aggregates(cfg, conn: sqlite3.Connection) -> dict:
    records = list(store.all_extractions(conn))
    cutoff = date.today().isoformat()
    stats = aggregate(records, cutoff, cfg.grace_days)
    readme = build_readme(stats, cfg.notes_dir)
    (cfg.root / "README.md").write_text(readme, encoding="utf-8")
    return stats
