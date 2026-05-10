# TOOLS.md - 量化工作环境

## 环境信息

- **Python 环境：** /quant_venv/bin/python （外部独立环境，禁止在知识库目录下建 venv）
- **代码目录：** 01_codebase/
- **知识库：** QMD 记忆库（qmd update / qmd embed）

## Skills 已安装

- **pyautogui** (v1.2.0) — 跨平台键鼠自动化
  - 位置: `skills/pyautogui/`
  - 核心脚本: `scripts/keyboard_mouse.py`
  - 截图: `screenshot`, `screenshot_region`
  - 图像查找: `scripts/image_finder.py` (需 opencv/rapidocr)
  - 依赖: pyautogui, Pillow, pyperclip (已安装)
  - 安全: FAILSAFE 模式已开启（鼠标移到左上角终止）

- **skill-vetter** (v1.0.0) — Skills 强制安全审查协议
  - 位置: `skills/skill-vetter/`
  - 所有 Skills 安装前必须先审查

- **pua** (v2.9.0) — 大厂 PUA 驱动的高能动性调试技能
  - 位置: `skills/pua/`
  - 来源: https://github.com/tanweai/pua（探微安全实验室）
  - 自动触发：连续失败 2 次+、用户沮丧短语、被动行为
  - 手动触发：输入 `/pua`
  - 压力等级：L0→L4（温和失望→毕业警告）
  - 14 种大厂风味：阿里、字节、华为、腾讯、Musk、Jobs 等
  - 参考：完整版含 methodology 文件在 GitHub 仓库

- **browser-harness** (v0.1.0) — CDP 浏览器直接控制
  - 位置: `skills/browser-harness/`
  - 源码: `~/Developer/browser-harness/`
  - 安装方式: `uv tool install -e .`（可编辑安装，全局可用）
  - 命令: `browser-harness`（全局可用）
  - 用法: `browser-harness -c '你的Python代码'`
  - 支持的浏览器: **默认用 Google Chrome**（Way 1 或 Way 2）
  - 特点: 像素坐标点击（穿透 iframe/shadow DOM）、截图先行、社区 domain skills
  - 连接方式: 启动 Chrome 后用 `BU_CDP_URL=http://127.0.0.1:9222` 指定端口

- **superpowers** (v5.1.0) — 完整软件开发方法论
  - 位置: `skills/superpowers/`
  - 来源: https://github.com/obra/superpowers（Jesse Vincent, 17.8k ⭐）
  - 风险等级: 🟢 LOW（已审查）
  - 包含 14 个技能:
    - `brainstorming` — 创意设计讨论（含视觉伴侣功能）
    - `dispatching-parallel-agents` — 并行子任务分配
    - `executing-plans` — 分离 session 执行计划
    - `finishing-a-development-branch` — 开发完成收尾
    - `receiving-code-review` — 接收代码审查反馈
    - `requesting-code-review` — 请求代码审查
    - `subagent-driven-development` — 子代理驱动开发
    - `systematic-debugging` — 系统性调试方法论
    - `test-driven-development` — RED-GREEN-REFACTOR TDD
    - `using-git-worktrees` — 隔离工作区管理
    - `using-superpowers` — Superpowers 技能系统入口
    - `verification-before-completion` — 完成后验证
    - `writing-plans` — 详细实施计划
    - `writing-skills` — 创建/编辑技能的最佳实践
  - 核心哲学: 先设计后编码、TDD 优先、系统性而非临时方案

## 开发规范

- 变量命名 PEP8 英文，核心逻辑/Docstring/日志强制全中文
- 异常处理：try-except + 断线重连 + Exponential Backoff
- 日志：logging 模块，禁止 print
- Key 安全：.env 管理，禁止硬编码，禁止日志打印
- 调试：最多 5 次修复尝试，失败出【报错尸检报告】

## QMD 铁律

- 新建/修改文件时打生命周期标签：[P0] [P1|expire:日期] [P2|expire:日期]
- 完成后执行 qmd update && qmd embed
