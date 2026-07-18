# 更新日志

本文件记录 **teach-me** 的所有重要变更。格式基于
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。

[English](CHANGELOG.md) | 中文

## [0.0.2] - 2026-07-18

### 新增

- **复习与留存层** —— 闭合留存循环：概念不再只是在单次会话内教到可观测的理解，而是
  排期做后续回忆检查，并追踪其衰减。通过一个小的确定性引擎激活 schema 中早已预留、却
  一直未用的字段（`deps`、`retained`/`stale` 状态、每条记录的日期），而非新增子系统。
  - **间隔重复** —— Leitner 盒子阶梯（间隔 `[1, 3, 7, 21, 60]` 天）：复习通过则概念升
    一格（间隔拉长），未通过则打回第 1 格。
  - **`/teach-me review`**（`$teach-me review`）—— 用概念存储的自测题抽查到期概念并更新
    排期；单批上限 5 个，受常规防疲劳规则约束。到期项也会在会话结尾或 `resume` 时以单行
    被动提示浮出 —— 绝不自动开始，绝不在非调用会话中浮现。
  - **前置知识（`deps`）** —— 概念记录其先修概念，用于给复习排序（先修先于后修），并在
    复习未通过时优先提议检查不牢的先修概念。
  - `store.py` 新增 `due`、`review`、`save-record --deps`；所有排期计算都是确定性的，有
    离线单元测试覆盖。既有记录在首次复习时自动迁移（无破坏性变更）。

## [0.0.1] - 2026-07-14

### 新增

- **teach-me skill 本体** —— 编码智能体的学习教练，只能显式调用：`/teach-me`
  （Claude Code / Cursor / Antigravity）或 `$teach-me`（Codex / OpenCode），绝不自动
  触发。两条分支：无主题时复盘刚完成的工作，带主题时把主题学到可观测的理解程度
  （能讲清 / 能应用 / 能迁移），配套防疲劳规则、经同意的持久化、检查点与 `resume` 恢复。
- **教学模式**：`socratic` 苏格拉底（不加旗标时的默认）、`feynman` 费曼
  （`--feynman`/`--fey`）、`drill` 刻意练习（`--drill`/`--dri`）—— 模式只改风格，
  证据标准不变；会话中途任何语言均可切换；模式随检查点持久化。另有仓库实操练习
  （先预测再运行 / 不看原码重写 / 定位埋入的 bug，含同意与清理安全规则）。
- **统一学习存储** —— 单一可自定义根目录（默认 `~/.teach-me/`，通过
  `~/.teach-me/config.json` 发现，首次保存时只问一次），记录按主题分目录
  （`records/<topic>/<concept>.md`），来源项目作为 frontmatter 元数据；检查点位于
  `checkpoints/`。检索是 grep 优先 —— 没有数据库也没有索引；什么都没匹配上就如实说，
  绝不凭空编造学过什么。
- **归档层**（`skills/teach-me/scripts/archive.py`，Python 3.8+）—— 把记录复制/更新到
  **Obsidian**（markdown 写入 vault）。配置了目的地即视为长期授权；尽力而为 ——
  归档绝不阻塞教学。
- **多智能体打包**：Claude Code、Codex、Cursor、Kimi、OpenCode、Pi，以及通用
  `.agents/` 标准（`npx skills add`）。
- **工具链与测试**：`scripts/validate.py` 打包门禁与 `scripts/validate_skill.py`
  SKILL 标准门禁、`scripts/bump-version.py` 单源版本管理、发布工作流（PR 时校验，
  `v*` tag 时发布）、行为场景，以及归档层/存储层的 pytest 测试套件。

[0.0.2]: https://github.com/young1lin/teach-me/releases/tag/v0.0.2
[0.0.1]: https://github.com/young1lin/teach-me/releases/tag/v0.0.1
