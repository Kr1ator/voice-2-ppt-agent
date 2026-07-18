# 实验报告

[English](README_EN.md) | 中文

本目录保存项目的正式中英文实验报告。两份报告采用相同的研究范围、数据口径和结论，分别面向中文和英文读者。

- [中文实验报告 PDF](voice_to_ppt_experiment_report_zh.pdf)
- [English Experimental Report PDF](voice_to_ppt_experiment_report_en.pdf)

报告系统整理了以下内容：

- 从 PPTArena/PPTPilot 本地适配、GUI 复现到 CLI 重构的开发过程；
- 双 ASR 接入和以 `run.py` 为入口的端到端链路；
- 128 次首轮实验与 48 次定向二轮实验；
- 确定性规则、图片几何和页面渲染核验；
- ASR、Agent 规划、生成代码和循环控制的失败分析；
- 项目局限、研究结论和后续可验证方向。

报告附录中的第一阶段材料明确记录为：从 PPTArena 数据集选取的 10 个 GUI/CLI 探索案例。它们用于呈现早期复现和重构现象，不构成严格配对的界面对比实验。

逐次实验数据见 [results/](../results/)，机器可读实验设计见 [experiments/](../experiments/)。

## LaTeX 源文件

- [中文 LaTeX](source/report_zh.tex)
- [English LaTeX](source/report_en.tex)
- [id31 重叠失败示例](source/id31_layout_overlap.png)
- [id31 布局通过示例](source/id31_layout_pass.png)

两份报告使用 XeLaTeX 编译。图片与 `.tex` 文件位于同一目录：

```bash
cd reports/source
xelatex report_zh.tex
xelatex report_zh.tex
xelatex report_en.tex
xelatex report_en.tex
```

仓库中的 PDF 由上述源文件生成。
