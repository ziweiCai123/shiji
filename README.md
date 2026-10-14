# 拾迹 Trace

从 Claude Code 对话自动生成**每日学习笔记**与**游戏化成长轨迹**。口号:**多对话 · 多犯错 · 多学习**——正面化"生产性失败"。

- **零摩擦**:直接读本地 `~/.claude/projects/**/*.jsonl`,你照常用 Claude Code,剩下的它记。
- **智能提取**:用 LLM(GLM/DeepSeek/Qwen 等 OpenAI 兼容端点任选)抽出技术、问题、踩坑、概念。
- **游戏化成长**:连续天数(含宽限)、技能进度条、徽章、攻克问题计数,全部渲染成 Markdown。
- **Obsidian 友好**:daily note 带 YAML frontmatter + `[[双链]]`,装 Dataview 即成知识图谱。
- **本地优先**:笔记 + 数据全在你自己的仓库,learn-in-public 随你便。

## 两种形态

| 形态 | 说明 |
|---|---|
| **Standalone app**(本仓库) | Python 包,读 Claude Code 会话日志 → LLM 提取 → 每日笔记 + 成长轨迹聚合。适合历史批量回填、无人值守运行。 |
| **Claude Code skill**(我的主用法) | `/trace` 直接分析当前会话上下文生成笔记,另有 `weekly`(周报聚合)、`daily`(工作日报四版本)两种模式。skill 本体不在本仓库,方法论见 `docs/skill功能规格.md`。 |

## 快速开始

```bash
# 1. 安装
git clone https://github.com/ziweiCai123/shiji.git
cd shiji
uv sync

# 2. 设置 LLM key(默认智谱 GLM,可在 config.toml 换任意 OpenAI 兼容端点)
#    Windows PowerShell:
$env:ZHIPUAI_API_KEY = "你的key"
#    Linux/macOS:
export ZHIPUAI_API_KEY=你的key

# 3. 在笔记仓库初始化(创建 .trace/config.toml + notes/)
uv run shiji init

# 4. 生成今天的学习笔记
uv run shiji today

# 5. 只看采集统计(不调 LLM)
uv run shiji collect --dry-run
```

产出:`notes/YYYY-MM-DD.md`(每日笔记,frontmatter 供统计)+ `notes/README.md`(成长轨迹总览)。

## 每日笔记长什么样

```markdown
# 📅 2026-07-03 · 学习笔记
> 第 1 天 · 🔥 连续 1 天 · 🐛 攻克 1 个 · 涉及技术 4 个

## 🎯 今天学到了什么
- **Claude Code skills 机制**(confidence 0.95)
  - description 是 skill 的激活入口,会话启动时加载……

## 🐛 今天踩的坑
- 加模式时只改了 SKILL.md 正文,漏了 frontmatter description
  → 根因:description 才是激活入口,正文是激活后才读的 ✅

## ✨ 三段反思
- **做得好**:把一个想法落成能跑的工具——调研 → 设计 → 建文件 → mock 验证
```

## 文档

- [功能设计文档](docs/功能设计文档.md) — 完整产品定义、架构、游戏化规则
- [调研报告](docs/调研报告.md) / [痛点调研第二轮](docs/实习生痛点调研-第二轮.md) — 为什么做它
- [skill 功能规格](docs/skill功能规格.md) — Claude Code skill 形态的设计规格
