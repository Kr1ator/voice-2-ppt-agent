# 第三方来源与项目归属

[English](NOTICE_EN.md) | 中文

Voice-to-PPT Agent 是一个 SURF 暑期研究项目，围绕语音驱动的 PowerPoint 编辑展开复现、工程改造和实验分析。

## PPTArena / PPTPilot

本项目的幻灯片解析、规划和编辑框架改编自 **PPTArena / PPTPilot**。上游工作由 Michael Ofengenden、Yunze Man、Ziqi Pang、Liang-Yan Gui 和 Yu-Xiong Wang 完成。

- 论文：<https://arxiv.org/abs/2512.03042>
- 上游仓库：<https://github.com/michaelofengenden/PPTArena>
- 数据集：<https://huggingface.co/datasets/mofengenden/PPTArena>

本项目不将 PPTPilot 的基础架构主张为原创成果。在上游框架之上，本项目完成了本地环境修复、GUI 复现、CLI 重构、双 ASR 接入、DeepSeek 兼容接口适配、批量实验、结果核验和失败分析。

根目录 `LICENSE` 中的 MIT 条款适用于本仓库作者新增的集成代码、实验工具、测试和文档。改编自上游项目的部分仍归原作者及相应权利人所有；本仓库的许可证不改变这些第三方材料原有的权利归属。

## Talk to Your Slides / TSBench

**Talk to Your Slides** 是本项目实验报告讨论的相关研究，也是第二阶段任务编号和指令设计所参考的 TSBench 来源。

- 论文：<https://arxiv.org/abs/2505.11604>
- 上游仓库：<https://github.com/KyuDan1/Talk-to-Your-Slides>

本仓库不包含 Talk to Your Slides 的源代码，Voice-to-PPT Agent 的执行核心也不是从该仓库改编而来。相关论文和 TSBench 仅按其在研究设计中的实际作用进行引用。
