# 实验设计

[English](README_EN.md) | 中文

本目录保存两个阶段的机器可读实验设计。设计文件回答“测试了什么、变量怎样组合、结果可以支持什么范围的结论”；实际运行记录保存在 [results/](../results/)，完整分析见[中文实验报告](../reports/voice_to_ppt_experiment_report_zh.pdf)。

## 第一阶段：PPTArena GUI/CLI 探索

[stage1_pptarena_exploration.json](stage1_pptarena_exploration.json) 记录从 **PPTArena 数据集**选取的 10 个探索案例，其中 GUI 4 个、CLI 6 个。文件同时注明：这些案例的任务、模型和编辑轮数并不完全一致，因此用于复现检查、工程调试和失败模式观察，不构成严格配对的 GUI/CLI 性能比较。

对应的案例级结果见 [stage1_pptarena_exploration.csv](../results/stage1_pptarena_exploration.csv)。

## 第二阶段：ASR + Agent

[stage2_voice_agent_manifest.json](stage2_voice_agent_manifest.json) 定义第二阶段的完整实验网格：

- `id5`、`id20`、`id31`、`id47` 四个任务；
- 4 种口语表达、4 种声学条件和 2 种 ASR；
- 128 次首轮运行；
- 3 个任务/ASR 组合的 48 次定向二轮运行；
- 合计 176 个唯一运行条件。

以下命令只展开实验计划，不加载 ASR、调用编辑模型或重新运行实验：

```bash
voice-ppt plan-experiment
voice-ppt plan-experiment --format csv
```

176 条逐次结果见 [stage2_voice_agent_runs.csv](../results/stage2_voice_agent_runs.csv)。清单中的模型名称是实验端点当时提供的别名，并非可验证的固定模型修订号。
