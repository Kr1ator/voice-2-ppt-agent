# Experiment Results

English | [中文](README.md)

This directory contains structured results for both experimental stages. See [experiments/](../experiments/) for the designs and the [English experimental report](../reports/voice_to_ppt_experiment_report_en.pdf) for figures, interpretation, and failure analysis.

| File | Granularity | Contents |
|---|---:|---|
| [stage1_pptarena_exploration.csv](stage1_pptarena_exploration.csv) | 10 cases | GUI/CLI exploratory tasks selected from the PPTArena dataset, including models, passes, prompts, and evaluations from two judges |
| [stage2_voice_agent_runs.csv](stage2_voice_agent_runs.csv) | 176 records | Conditions, routes, errors, outputs, and task verification for 128 first-round and 48 second-round runs |
| [stage2_voice_agent_summary.csv](stage2_voice_agent_summary.csv) | 46 summaries | Aggregate, task, ASR, round, and failure-category statistics calculated from the 176 run-level records |

## Stage 1 Results

Each row in the Stage 1 table is a historical exploratory case selected from the PPTArena dataset. The four GUI cases and six CLI cases do not form task-, model-, or pass-matched pairs. The table therefore documents successes, missed edits, over-editing, layout damage, and judge disagreement observed during reproduction and refactoring; it is not intended to produce an overall GUI-versus-CLI ranking.

## Stage 2 Run-Level Results

[stage2_voice_agent_runs.csv](stage2_voice_agent_runs.csv) is the primary evidence table for the second stage. Each row represents one unique run condition. Its fields fall into four groups:

- experiment condition: `run_id`, `phase`, `task_id`, `asr_id`, `round`, spoken variant, and acoustic condition;
- execution trace: critical semantic slots, edit route, automatic retries, and script errors;
- output verification: PPTX production, edit signal, deterministic rule, and visual status;
- provenance: output filename and source log.

The image count, overlap ratio, margin difference, spacing difference, and review note for `id31` are stored directly in the run-level table rather than in a separate audit file.

## Metric Definitions

- `pptx_produced`: a readable PPTX was produced;
- `edit_signal`: the final log reports at least one edited slide;
- `deterministic_rule_pass`: `id5`, `id20`, or `id47` passed its task-specific rule;
- `visual_status`: `id31` was classified as pass, overlap, misalignment, or missing output;
- `retry_triggered` / `retry_count`: whether automatic recovery occurred within a run and how many retry events were recorded;
- `script_error_observed` / `script_error_count`: whether generated-script errors occurred and how many events were recorded.

File production and edit signals are process indicators, not direct measures of task correctness. `round` denotes the intentionally configured first or second editing pass, whereas `retry_count` records automatic recovery attempts within one run.

## Summary Table and Offline Validation

[stage2_voice_agent_summary.csv](stage2_voice_agent_summary.csv) is calculated from the 176 run-level records so that the main report figures can be read quickly. It is not another experiment; individual outcomes should be traced back to the run-level table.

The following command checks consistency across the experiment manifests, the 10 PPTArena cases, 176 run-level records, 46 summary records, and 64 `id31` layout assessments:

```bash
voice-ppt validate-results
```

The command reads only the JSON and CSV files in this repository. It does not call a model or rerun an experiment.
