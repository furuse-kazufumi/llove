# 用一个终端窗格"看现场的 LLM" — llove

> 我正在设计并实现 `llmesh-llove`：LLMesh 的 Artifact 终端。
> 我赌的是一个不显眼但很具体的细分：**用终端、可爱地、观测 LLM × 工业 IoT。**

## 为什么开始

说到 LLM dashboard，大家默认是 Streamlit / Grafana / 全新 Web UI。但在受监管现场、离线现场、SRE 操作间，有另一套共同的约束：

- 有些终端不能、或不愿装浏览器
- 通过 SSH 想在数秒内看到"现在"
- GUI 卡顿与过度动画反而妨碍运维判断
- 日志 / trace / SPC / RAG / 审计想要落在**同一时间轴**、同一屏幕

`llove` 是我在**一个终端窗格里**解掉这件事的个人尝试。它在基于 Textual 的 TUI 中观测 LLMesh 的数据 (SensorEvent / SPC / RAG / Audit / Trace)，整套布局由 TOML 完全用户定义。SSH 上也好、现场 PC 也好、开发机也好，都是同一个画面。

## 8 个设计支柱

1. **TUI 优先** — Textual 当下、Rust 加速在路线图。无需浏览器、SSH 友好、窄带也能秒级响应。
2. **一切通过 layout.toml** — SDI/MDI 切换、自由可调窗格、常驻锁定窗格、多显示器。可以想象成"终端版 Qt-ADS"。
3. **浏览器级渲染 (F15)** — Markdown / SVG / Mermaid / 图像 / 折叠 / 主题，统统在终端里。可视性五大柱。
4. **多游戏 LLM 对局竞技场 (F16)** — chess / go / mahjong / poker / connect4… 都跑在**同一抽象**上，可用于比较 LLM 策略。
5. **"LLM × 人协作"演示** — 打字、俄罗斯方块等。教学最小样本 (~200 行)、社交分享性强，适合做布道。
6. **嵌入式脚本 + IDE 模式 (F19)** — Python / Lua / Starlark / Janet / JS。Helix / Kakoune / Neovim 体感。
7. **PowerShell 兼容 shell + Claude Code 集成 (F23/F24)** — 现场运维工具的差异化轴。
8. **F25 家族联动** — `llmesh` 通过 MCP 中介 `llove ↔ llive`。BWT、路由 trace、记忆链路，都在 TUI 中可观测。

## 为什么这对我的职业很重要

炫酷 Web UI 在简历上很好看，但**运维易用性**是更深的问题。做 `llove` 留给我的，是更安静、更耐用的强项：

- 在 Web 当道的年代深挖 **TUI** — 这种直觉在 SRE、控制室、工厂现场（SSH 是日常）这类工作里相当好使。
- 设计了 **Textual + tree-sitter + LSP** 栈，把 IDE 级操作搬进终端。
- 以 **layout.toml 为中心**的 UX，让用户真正**拥有**自己的界面。
- 接出了一个 **多游戏 LLM 竞技场**，把比较 / 观测 / 教学放在同一个抽象上。
- 提炼出一条**家族设计原则**：后端职责保持最小，把"呈现的工艺"集中到 TUI 侧。

这些能力，在开发者工具、运维工具、DevRel、EUC 邻接岗位，都比看上去更值钱。

## 当前状态 (2026-05-14)

- **v0.6+** 开发中。F15 (浏览器级渲染) / F16 (LLM 竞技场) / F17 (窗口管理基础) / F19 (嵌入式脚本 + IDE) / F25 (llmesh × llive 桥接) 分阶段交付。
- **716 PASS + 1 skipped**（含 105 个 F25 测试），ruff 全清。
- PyPI: `pip install llmesh-llove`（v0.2.2 已发布，v0.3.0a1 进行中）。

## 走向哪里

`llove` 是一套栈的可视化层，配合 `llmesh`（本地 MCP 枢纽）+ `llive`（自演化模块化记忆 LLM），把 **LLM × 工业 IoT 的现场观测** 收拢到一块终端里。如果你想认真磨一下 TUI，或想真正**拥有**自己的运维工具，请来用一下。

> GitHub: <https://github.com/furuse-kazufumi/llove>
> PyPI: `pip install llmesh-llove`

#AI #LLM #TUI #Textual #开发者工具 #SRE #工业物联网 #开源 #个人项目 #职业发展
