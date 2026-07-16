# teach-me

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**AI 替你写的代码，你真的懂了吗？**

[English](README.md) | 中文

给编码智能体用的学习教练 skill。把 AI 时代的工作和阅读变成可观测的理解：
复盘刚交付的工作，或把一个主题学到可观测的理解程度，配套可恢复的检查点。
**只能显式调用** —— 绝不自动触发。

调用方式：`/teach-me`（Claude Code / Cursor / Antigravity）或 `$teach-me`（Codex /
OpenCode）。

> 可选的 Obsidian 归档复制/更新和开发工具（`scripts/`）需要 Python 3.8+；
> 教学 skill 本体完全运行在你的智能体内部，无需 Python。

## 教学模式

选择你想要的被教方式。模式只改变教学风格 —— 证据衡量方式永远不变
（能讲清 / 能应用 / 能迁移）。苏格拉底是默认模式，其余是可选旗标。

| 模式 | Flag（简写） | 风格 |
|---|---|---|
| socratic 苏格拉底（默认） | `--socratic`（`--soc`），或不加旗标 | 提问引导，自己推出结论 |
| feynman 费曼 | `--feynman`（`--fey`） | 你先讲，教练找漏洞并补最小缺口 |
| drill 刻意练习 | `--drill`（`--dri`） | 针对最弱子技能的重复训练 |

```bash
/teach-me TCP 拥塞控制                 # Claude Code / Cursor / Antigravity（默认苏格拉底）
/teach-me --fey                       # 费曼式复盘你刚完成的工作
$teach-me --dri 正则                  # Codex / OpenCode
```

会话中途直接说「换费曼式」（任何语言）即可切换，无需重新调用。

示例（示意）：

```text
> /teach-me
本次会话有 1 个候选：「为什么重试用指数退避 + 抖动」（agent 写的）。
一句话 —— 为什么要加抖动？
> 这样重试不会同时醒来
判定：正确 —— 避免惊群。
轮到你：去掉抖动只保留退避 —— 什么故障会回来，什么时候？
```

搭配 [grill-me](https://github.com/mattpocock/skills) 使用效果更佳：动工前用 grill-me
拷问你的方案，交付后用 teach-me 复盘 —— AI 给你的速度，不该以理解为代价。

## 你的学习数据

所有已 demonstrated（本会话通过讲清/应用/迁移证据）的内容都以纯 markdown 保存在同一个根目录下。共享同一个 OS 用户 home 的智能体默认共享这份记录；Windows 应用、WSL、SSH 远程机和 Dev Container 可能各有不同 home。如需跨环境共享，请设置 `TEACH_ME_HOME` 指向同一个学习目录。记录按主题（topic）分目录组织，来源项目作为每个文件内的元数据：

```text
${TEACH_ME_HOME:-~/.teach-me}/config.json  # 根目录配置在这里
<root>/records/<topic>/<concept>.md
<root>/checkpoints/<topic>.md
```

会话第一次需要保存时，teach-me 只问一次：用默认的 `~/.teach-me/`（或已设置的 `TEACH_ME_HOME`）还是你指定的目录。
答案记入 `${TEACH_ME_HOME:-~/.teach-me}/config.json`，之后不再询问。记录就是带 frontmatter 的 markdown
（`topic`、`project`、`state`、`evidence`），随意浏览或 grep。

没有数据库，也没有搜索索引 —— 你的智能体自带的 `grep` / `Glob` / `Read` 就是检索引擎。
想接着学某个主题，用 `/teach-me resume <主题>`；如果什么都没匹配上，它会如实说
「没找到」—— 绝不凭空编造你学过什么。

## 归档到 Obsidian（可选）

把已 demonstrated 的内容复制/更新进你自己的 vault。在 `${TEACH_ME_HOME:-~/.teach-me}/config.json` 里加一段 `archive`
配置 —— 配置了目的地即视为长期授权，每次保存后自动复制/更新：

```json
{
  "root": "~/.teach-me",
  "archive": {
    "obsidian": { "vault_path": "D:/vault", "folder": "teach-me" }
  }
}
```

- **Obsidian** —— 记录以纯 markdown 写入你的 vault（`teach-me/<topic>/…`），
  Obsidian 关着也能写。

归档是尽力而为：vault 路径缺失只提示一行，课程照常继续。随时可用
`python skills/teach-me/scripts/archive.py --dry-run` 预览。

## 安装

各平台安装方式不同。如果你同时用多个智能体，需要分别为每个安装。

### Claude Code

把本仓库注册为 marketplace，然后安装：

```bash
/plugin marketplace add young1lin/teach-me
/plugin install teach-me@teach-me-marketplace
```

### Codex

从本仓库安装：

```bash
/plugins install https://github.com/young1lin/teach-me
```

然后用 `$teach-me` 调用。

### Cursor

```text
/add-plugin teach-me
```

或在插件市场搜索 "teach-me"，指向 `https://github.com/young1lin/teach-me`。

### Kimi Code

```text
/plugins install https://github.com/young1lin/teach-me
```

### OpenCode

见 [`.opencode/INSTALL.md`](.opencode/INSTALL.md) —— 把本仓库的 `skills/` 加入
OpenCode 的 `skills.paths`，然后用 `$teach-me` 调用。

### Pi

```bash
pi install git:github.com/young1lin/teach-me
```

### Antigravity

```bash
agy plugin install https://github.com/young1lin/teach-me
```

### 任何兼容 `.agents/` 标准的工具（通用）

```bash
npx skills add young1lin/teach-me
```

这会把 skill 装进你智能体的 skills 目录（Claude Code、Cursor、Codex、OpenCode 等 70+）。

## 目录结构

- `skills/teach-me/` —— skill 本体（`SKILL.md`、`references/`、`agents/`、`scripts/`）。
- `.<agent>-plugin/`、`.agents/`、`.opencode/`、`package.json` —— 各平台打包清单。
- `scripts/` —— `validate.py`（打包）与 `validate_skill.py`（SKILL 标准）两道校验。
- `tests/` —— 行为场景 + 归档层的 pytest 测试。

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
