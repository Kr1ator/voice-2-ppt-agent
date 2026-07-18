# Third-Party Provenance and Project Attribution

English | [中文](NOTICE.md)

Voice-to-PPT Agent is a SURF summer research project on the reproduction, engineering adaptation, and experimental evaluation of speech-driven PowerPoint editing.

## PPTArena / PPTPilot

The presentation parsing, planning, and editing framework in this project is adapted from **PPTArena / PPTPilot**, developed by Michael Ofengenden, Yunze Man, Ziqi Pang, Liang-Yan Gui, and Yu-Xiong Wang.

- Paper: <https://arxiv.org/abs/2512.03042>
- Upstream repository: <https://github.com/michaelofengenden/PPTArena>
- Dataset: <https://huggingface.co/datasets/mofengenden/PPTArena>

This project does not claim the underlying PPTPilot architecture as original work. Its contributions on top of that framework include local environment fixes, GUI reproduction, CLI refactoring, dual-ASR integration, DeepSeek-compatible API support, batch experimentation, result verification, and failure analysis.

The MIT terms in the root `LICENSE` apply to the integration code, experiment tools, tests, and documentation created for this repository. Portions adapted from upstream remain the work of their original authors and rights holders; this repository's license does not alter the rights attached to third-party material.

## Talk to Your Slides / TSBench

**Talk to Your Slides** is related work discussed in the experimental report and the source of the TSBench task identifiers and instruction design used in the second experimental stage.

- Paper: <https://arxiv.org/abs/2505.11604>
- Upstream repository: <https://github.com/KyuDan1/Talk-to-Your-Slides>

This repository does not include source code from Talk to Your Slides, and the Voice-to-PPT execution pipeline is not adapted from that codebase. The paper and TSBench are cited only for their actual roles in the research design.
