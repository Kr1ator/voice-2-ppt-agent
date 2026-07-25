# 项目贡献与来源说明

本文档说明 Voice-to-PPT Agent 使用了哪些已有研究与团队材料，以及本人在 SURF 项目中具体完成了什么。项目的目标不是把 PPTArena、PPTPilot 或 TSBench 主张为原创成果，而是展示从论文代码复现到语音驱动实验、可靠性评价和失败分析的完整研究过程。

## 项目关系

| 来源或参与方 | 在本项目中的作用 | 本项目没有主张的内容 |
|---|---|---|
| [PPTArena / PPTPilot](https://github.com/michaelofengenden/PPTArena) | 提供真实 PowerPoint 编辑基准、PPTX 解析与编辑框架，以及规划—执行—检查的 Agent 基础 | PPTPilot 的基础架构、PPTArena 数据集与上游算法贡献 |
| [Talk to Your Slides / TSBench](https://github.com/KyuDan1/Talk-to-Your-Slides) | 提供第二阶段所参考的任务编号、指令设计与研究背景 | Talk to Your Slides 的系统实现和 TSBench 数据集 |
| SURF 数据团队 | 整理 379 条指令的口语表达和声学变体，形成项目内部音频材料 | 音频采集与全部数据准备工作 |
| 本人 | 完成本地复现、系统改造、双 ASR 接入、批量实验、结果核验、失败分析和项目整理 | 不将上游框架或团队材料改写为个人原创成果 |

第三方论文、仓库和数据集链接另见 [NOTICE.md](NOTICE.md)。公开仓库不包含完整音频语料、第三方 PPT 数据集、批量生成的 PPTX、API 密钥或模型文件。

## 本人完成的主要工作

1. **本地化与故障修复**：处理绝对路径、依赖、模型配置、API 调用和输出目录等环境耦合问题，使论文代码能够在本地运行。
2. **GUI 复现与 CLI 重构**：先复现原始图形界面以理解执行链路，再移除 Web、会话和部署依赖，整理出适合单例和批量实验的命令行流程。
3. **语音入口与模型接口**：接入 faster-whisper large-v3-turbo 和 Qwen3-ASR-1.7B，保存独立转写，并将规划与编辑调用适配到 DeepSeek 兼容接口。
4. **端到端实验执行**：围绕 4 类 PowerPoint 编辑任务、16 种口语/声学条件和 2 种 ASR 完成 128 次首轮运行，并对困难任务补充 48 次定向二轮运行。
5. **分层可靠性评价**：区分 PPTX 可读性、编辑信号、确定性任务规则、对象几何和页面渲染结果，避免把“文件已生成”直接视为任务成功。
6. **证据整理与失败分析**：将实验条件、转写、编辑路径、脚本错误、重试事件和任务核验整理为可追溯结果，分析 ASR 信息损失、对象定位、布局规划、生成代码和无条件二次编辑等失败来源。
7. **研究报告与公开整理**：完成中英文实验报告，并将核心代码、实验清单、结构化结果、测试和来源说明整理为当前仓库。

## 系统演化过程

```text
PPTArena-main
  论文代码本地化与基础修复
        ↓
PPTArena_GUI
  复现交互流程并验证基本编辑能力
        ↓
PPTArena_CLI
  去除 Web 依赖，建立单例与批量入口
        ↓
PPTAgent
  接入 faster-whisper 与 Qwen3-ASR
        ↓
Agent / run.py
  统一端到端流程、DeepSeek 接口、日志、输出与实验执行
        ↓
当前仓库
  可复核的实验设计、176 条运行记录、分层评价、测试与报告
```

## 当前仓库中的实现边界

| 目录或模块 | 主要性质 | 说明 |
|---|---|---|
| `src/voice_ppt_agent/ppt/`、`llm/prompt.py`、`llm_handler.py`、`orchestrator.py` | 上游框架基础上的改造 | 保留 PPTPilot 的 PPTX 解析、规划与编辑思路，并加入本地适配、路径处理、输出验证和实验所需改造 |
| `src/voice_ppt_agent/asr/` | 本项目集成 | 双 ASR 的统一接口、模型加载、转写结果与错误记录 |
| `src/voice_ppt_agent/cli.py`、`config.py` | 公开仓库整理 | 将历史 `run.py` 流程包装为可安装、可复核的命令行工具；不改变报告中的实验入口 |
| `src/voice_ppt_agent/experiment.py`、`evaluation.py` | 本项目实验与评价 | 展开实验条件并核对保存的结构化结果 |
| `experiments/`、`results/` | 本项目研究证据 | 机器可读实验设计、10 个探索案例、176 条运行记录及汇总统计 |
| `tests/`、`.github/workflows/ci.yml` | 公开仓库整理 | 离线回归、安全边界和实验结果一致性检查 |
| `reports/` | 本项目报告 | 中英文实验报告、LaTeX 源文件和两张真实布局核验示例 |

## 结论边界

当前结果只覆盖 4 类任务、2 种 ASR 和 1 个基于 PPTPilot 改造的编辑 Agent。它们能够支持对本项目中 ASR 信息保留、Agent 执行失败和分层核验价值的分析，但不代表完整 PPTArena、TSBench 或生产级 PowerPoint 自动化系统的总体性能。
