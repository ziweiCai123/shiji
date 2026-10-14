# `/trace` Skill — 完整功能规格 v1

> 拾迹 Trace 的 Claude Code skill 形态。会话自带的模型就是提取器，对话就在上下文里，
> 不解析 JSONL、不调外部 LLM。手动 `/trace` 触发，不加 hook。
> 2026-07-03

---

## 0. 文件结构

```
~/.claude/skills/trace/              ← 个人级 skill，任何 cwd 都能用
├── SKILL.md                         ← 主指令（runbook），Claude 照着执行
├── references/
│   ├── note-template.md             ← 每日笔记的标准结构
│   ├── extraction-guide.md          ← 提取规则：什么算"学到"、confidence 怎么打、踩坑怎么判
│   └── badges-rules.md              ← 徽章/技能/streak 规则（Claude 判断 + aggregate.py 对齐）
└── scripts/
    └── aggregate.py                 ← 确定性计算：读 notes/*.md frontmatter → 重算 README.md

C:\Users\R5519\shiji\                ← 笔记仓库（复用现有，app 和 skill 共享）
├── notes\YYYY-MM-DD.md              ← 每日笔记（带 YAML frontmatter）
├── notes\.today-marks.md            ← [D] 当天临时标记的暂存文件
└── README.md                        ← 成长轨迹（aggregate.py 重算）
```

**配置**：`SKILL.md` 顶部一行 `NOTES_REPO = C:\Users\R5519\shiji`，换路径改这一行即可。

---

## 1. 触发方式

| 触发 | 行为 |
|---|---|
| **`/trace`** | 完整流程：分析本次会话 → [A]问反思 → [B]查历史 → 写/合并今日笔记 → 跑 aggregate → [C]给建议 |
| **"记一下这个" / "这是个坑" / "mark this"**（auto-invoke） | [D] 轻量模式：只把该条追加到 `notes\.today-marks.md`，确认一句，不打笔记、不跑 aggregate |
| 其它无关对话 | 不触发（靠 description 精确匹配） |

> 说明：[D] 的"记一下"走的是 skill 正常的 description 自动匹配，**不是 hook**，符合"手动为主、不加 hook"。

---

## 2. `/trace` 核心 runbook（SKILL.md 要让 Claude 按此顺序执行）

1. **分析当前会话**——直接用上下文里的对话，按 `references/extraction-guide.md` 规则提取：
   - 技术/工具（带 confidence）
   - 问过的问题
   - 踩坑：问题 + 根因 + 是否解决（**最重要**）
   - 理解的概念
   - 一句话总结 + 挣扎度（low/medium/high）
   - 只抽**真实发生**的，禁止臆造

2. **[A] 交互式反思**——写笔记前，在对话里问用户**最多 2 个**问题（如"今天最有收获的是哪件事？""如果重来会怎么做？"）。
   - 若今日笔记已有反思内容，**跳过**避免重复问。
   - 用户可回"跳过"，则留空。

3. **[B] 读历史笔记**——读 `notes\*.md` 的 frontmatter（必要时读相关全文）：
   - 找今天技术在过去的出现记录，产出"🔗 与过去的连接"（如"这是 6/30 Docker volume 的进阶"）
   - 重复学习检测：某概念本周第 N 次出现 → 在对话里提示

4. **合并写入今日笔记** `notes\YYYY-MM-DD.md`：
   - 同一天多次 `/trace` → **合并**（frontmatter 取并集/求和，body 追加新会话内容），不是覆盖
   - frontmatter + 可读 body + 连接 + 反思答案
   - **保留** `<!-- user-notes -->` 手写区不覆盖
   - 读 `notes\.today-marks.md`，把当天临时标记一并纳入踩坑/学习

5. **跑 aggregate**——`python scripts\aggregate.py C:\Users\R5519\shiji`，重算 README（streak/技能条/徽章/热力图/攻克计数）

6. **[C] 给反馈**（写完笔记后在对话里说）：
   - **明天建议**：基于今天"待深入" + 技能树缺口（只出现过 1 次的技术），建议 1–2 个目标
   - **间隔复习**：把 3/7/14 天前学过、按 spaced-repetition 该复习的知识点抛给用户

---

## 3. 每日笔记格式

```markdown
---
date: 2026-07-03
technologies: [Docker, WSL2, git]
questions: 3
mistakes_resolved: 2
mistakes_total: 3
struggle: medium
summary: "搞懂了 Docker 多阶段构建 + WSL2 网络"
sessions: 2
---

# 📅 2026-07-03 · 学习笔记

> 第 N 天 · 🔥 连续 M 天（宽限 x/3）· 本周第 ? 天
> 今日：2 个会话 · 🐛 攻克 2 个 · 涉及技术 3 个

## 🎯 今天学到了什么
- **Docker** — 多阶段构建（confidence 0.9）
  - 要点：…
## 🤔 我问过的问题
- …
## 🐛 今天踩的坑（最有价值！）
- `permission denied` → 根因：volume 权限 → 解决 ✅
## 🔗 与过去的连接
- 今天的 Docker 多阶段构建，是 6/30「第一次跑起容器」的进阶
## ✨ 三段反思
- **做得好**：（来自交互问答的用户回答）
- **可改进**：…
- **学到了**：…
## 📚 明天可以试试
- [ ] git rebase（技能树缺口）
## 🔁 该复习了
- [ ] 6/26 的 useEffect 依赖（7 天前）
<!-- user-notes -->
（手写区，不被覆盖）
<!-- /user-notes -->
```

**frontmatter 是 aggregate.py 的数据源**——markdown 单一真相，frontmatter 让统计可靠。

---

## 4. 各增强功能行为细则

| 功能 | 触发时机 | 产出位置 | 关键约束 |
|---|---|---|---|
| **[A] 交互反思** | `/trace` 第 2 步，写笔记前 | 答案进笔记"三段反思" | 最多 2 问；已有反思则跳过；可拒答 |
| **[B] 跨笔记连接** | `/trace` 第 3 步 | 笔记"🔗 与过去的连接" + 对话提示重复学习 | 读 frontmatter 为主，全文按需；防读太多 |
| **[C] 主动引导** | `/trace` 第 6 步，写完后 | 笔记"明天可以试试"+"该复习了" + 对话口播 | 明天建议 ≤2；复习按 3/7/14 天间隔 |
| **D 对话内标记** | 用户说"记一下/这是个坑" | 追加到 `notes\.today-marks.md` | 轻量，不写笔记不跑 aggregate；`/trace` 时纳入 |

---

## 5. `scripts/aggregate.py` 职责

输入：`notes\*.md` 的 frontmatter。输出：重写 `README.md`。逻辑（独立实现，不依赖 shiji 包，保证 skill 可移植）：
- 连续天数（含宽限 3，今天没笔记则免费跳过一天）
- 累计学习天数、已攻克问题总数、已点亮技术数
- 技能进度条（每技术按出现天数算 `███░░░░░ n/8`）
- 徽章墙（探索者/连击/Debug 侦探/深挖者，规则见 `references/badges-rules.md`）
- 8 周活跃热力图（🟩/⬜）
- 最近笔记链接

调用：`python scripts\aggregate.py <NOTES_REPO>`

---

## 6. 边界与取舍

- **只覆盖 Claude Code 会话**——ChatGPT/Cursor 对话抓不到（你的主力是 Claude Code，可接受；非 CC 源仍由现有 app 处理）。
- **[D] 标记存暂存文件** `notes\.today-marks.md`——防会话压缩/多 /trace 丢失；`/trace` 后可清空。
- **历史批量回填**仍用现有 Python app（一次性跑几十天），skill 负责"从今天起每天"。
- **aggregate 与 app 的 aggregator 逻辑有重叠**（streak/徽章公式）——v1 各自维护，后续可统一。
- **会话太长**：Claude 用上下文分析，超长会话可能丢早期内容；必要时让 Claude 先读 `transcript_path` 指向的 JSONL 补全（SKILL.md 里给 fallback）。

---

## 7. 验证方式（做完后）

1. 跑一次 `/trace` → 检查 `notes\今日.md` frontmatter + body 合理、反思区填了用户答的内容
2. 同天再 `/trace` → 笔记**合并**而非覆盖，frontmatter 计数累加
3. 说一句"记一下这个" → 确认追加到 `.today-marks.md`；再 `/trace` → 标记进笔记
4. 跑 aggregate → README 的 streak/技能条/徽章/热力图正确
5. 手改 `<!-- user-notes -->` 区 → 再 `/trace` → 该区不被覆盖
6. [B] 造两天同技术数据 → 检查"连接"是否正确关联
