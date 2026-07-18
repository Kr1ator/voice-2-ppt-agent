# Experimental Reports

English | [中文](README.md)

This directory contains the formal Chinese and English experimental reports. Both versions use the same research scope, data definitions, and conclusions, with language and presentation adapted for their respective readers.

- [Chinese experimental report PDF](voice_to_ppt_experiment_report_zh.pdf)
- [English experimental report PDF](voice_to_ppt_experiment_report_en.pdf)

The reports cover:

- the development path from PPTArena/PPTPilot local adaptation and GUI reproduction to CLI refactoring;
- dual-ASR integration and the end-to-end pipeline exposed through `run.py`;
- 128 first-round runs and 48 targeted second-round runs;
- deterministic-rule, image-geometry, and rendered-slide verification;
- failure analysis across ASR, agent planning, generated code, and loop control;
- limitations, research conclusions, and testable directions for future work.

The appendix identifies the first-stage material as 10 GUI/CLI exploratory cases selected from the PPTArena dataset. These cases document early reproduction and refactoring behavior and do not constitute a controlled or paired interface comparison.

Run-level evidence is available in [results/](../results/), and machine-readable experiment designs are available in [experiments/](../experiments/).

## LaTeX Sources

- [Chinese LaTeX](source/report_zh.tex)
- [English LaTeX](source/report_en.tex)
- [`id31` overlap failure example](source/id31_layout_overlap.png)
- [`id31` passing layout example](source/id31_layout_pass.png)

Both reports are compiled with XeLaTeX. The figures are stored alongside the `.tex` files:

```bash
cd reports/source
xelatex report_zh.tex
xelatex report_zh.tex
xelatex report_en.tex
xelatex report_en.tex
```

The PDFs in this repository are generated from these sources.
