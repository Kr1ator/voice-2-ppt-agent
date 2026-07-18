# 实验结果

[English](README_EN.md) | 中文

本目录保存两阶段实验的结构化结果。实验设计见 [experiments/](../experiments/)，图表、解释和失败分析见[中文实验报告](../reports/voice_to_ppt_experiment_report_zh.pdf)。

| 文件 | 粒度 | 内容 |
|---|---:|---|
| [stage1_pptarena_exploration.csv](stage1_pptarena_exploration.csv) | 10 个案例 | 从 PPTArena 数据集选取的 GUI/CLI 探索任务、模型、轮次、提示词和双评价文本 |
| [stage2_voice_agent_runs.csv](stage2_voice_agent_runs.csv) | 176 条记录 | 128 条首轮与 48 条二轮运行的实验条件、路由、错误、输出和任务核验 |
| [stage2_voice_agent_summary.csv](stage2_voice_agent_summary.csv) | 46 条汇总 | 从 176 条逐次记录计算的总体、任务、ASR、轮次和失败类别统计 |

## 第一阶段结果

第一阶段结果表中的每一行代表一个从 PPTArena 数据集选取的历史探索案例。4 个 GUI 案例和 6 个 CLI 案例并非同任务、同模型、同轮次的配对实验，因此这张表用于呈现复现与重构期间观察到的成功、漏改、过度修改、版式损坏和评价者分歧，不用于计算 GUI 与 CLI 的总体胜负。

## 第二阶段逐次结果

[stage2_voice_agent_runs.csv](stage2_voice_agent_runs.csv) 是第二阶段的主要证据表，每一行对应一个唯一运行条件。关键字段分为四组：

- 实验条件：`run_id`、`phase`、`task_id`、`asr_id`、`round`、口语变体和声学条件；
- 执行过程：关键语义槽、编辑路径、自动重试和脚本错误；
- 输出核验：PPTX 产出、编辑信号、确定性规则和视觉状态；
- 来源追踪：输出文件名和历史日志来源。

`id31` 的图片数量、重叠率、边距差、间距差和人工核验说明直接保存在这张主表中，不再拆成单独的结果文件。

## 指标解释

- `pptx_produced`：生成了可读取的 PPTX；
- `edit_signal`：最终日志显示至少有一页发生编辑；
- `deterministic_rule_pass`：`id5`、`id20` 或 `id47` 通过对应任务规则；
- `visual_status`：`id31` 被判定为通过、重叠、错位或无输出；
- `retry_triggered` / `retry_count`：一次运行内部是否触发自动重试，以及重试事件数；
- `script_error_observed` / `script_error_count`：是否出现生成脚本错误，以及错误事件数。

文件产出和编辑信号属于过程指标，不能直接解释为任务正确。`round` 表示主动设置的第一轮或第二轮编辑，`retry_count` 表示同一次运行内部的自动恢复次数，两者含义不同。

## 汇总表与离线核对

[stage2_voice_agent_summary.csv](stage2_voice_agent_summary.csv) 是由 176 条逐次记录计算得到的汇总，方便快速读取报告中的主要数字。它不是另一轮实验；如需追溯单个结果，应以逐次记录表为准。

运行以下命令可以核对实验清单、10 个 PPTArena 案例、176 条逐次记录、46 条汇总记录以及 64 条 `id31` 布局状态之间的一致性：

```bash
voice-ppt validate-results
```

该命令只读取仓库内的 JSON 和 CSV，不调用模型，也不会重新执行实验。
