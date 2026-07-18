# Experiment Designs

English | [中文](README.md)

This directory contains machine-readable designs for both experimental stages. The design files state what was tested, how variables were combined, and what scope of conclusions the evidence can support. Observed runs are stored in [results/](../results/), and the full analysis appears in the [English experimental report](../reports/voice_to_ppt_experiment_report_en.pdf).

## Stage 1: PPTArena GUI/CLI Exploration

[stage1_pptarena_exploration.json](stage1_pptarena_exploration.json) describes 10 exploratory cases selected from the **PPTArena dataset**: four GUI cases and six CLI cases. The tasks, models, and editing-pass counts were not identical, so the cases support reproduction checks, engineering diagnosis, and failure-mode analysis rather than a controlled or paired GUI-versus-CLI performance comparison.

The corresponding case-level observations are in [stage1_pptarena_exploration.csv](../results/stage1_pptarena_exploration.csv).

## Stage 2: ASR + Agent

[stage2_voice_agent_manifest.json](stage2_voice_agent_manifest.json) defines the complete second-stage experiment grid:

- four tasks: `id5`, `id20`, `id31`, and `id47`;
- four spoken variants, four acoustic conditions, and two ASR systems;
- 128 first-round runs;
- 48 targeted second-round runs across three task/ASR groups;
- 176 unique run conditions in total.

The following commands expand the plan only. They do not load an ASR model, call an editing model, or rerun an experiment:

```bash
voice-ppt plan-experiment
voice-ppt plan-experiment --format csv
```

The 176 observed runs are stored in [stage2_voice_agent_runs.csv](../results/stage2_voice_agent_runs.csv). Model names in the manifest are aliases exposed by the experimental endpoint at the time of the runs, not independently verifiable immutable model revisions.
