"""Expand and validate the recorded experiment design without external models."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PlannedRun:
    """One condition in the first round or a targeted loop follow-up."""

    run_id: str
    phase: str
    task_id: str
    asr_id: str
    round: int
    spoken_variant: str
    audio_condition: str
    audio_stem: str
    output_filename: str
    source_log: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_experiment_manifest(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    path = root / "experiments" / "stage2_voice_agent_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Experiment manifest is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _task_number(task_id: str) -> str:
    match = re.fullmatch(r"id(\d+)", task_id)
    if not match:
        raise ValueError(f"Unsupported task ID: {task_id}")
    return match.group(1)


def _planned_run(
    *,
    phase: str,
    task_id: str,
    asr_id: str,
    round_number: int,
    spoken_variant: str,
    audio_condition: str,
) -> PlannedRun:
    condition_tag = (
        spoken_variant
        if audio_condition == "none"
        else f"{spoken_variant}_{audio_condition}"
    )
    audio_stem = f"{task_id}_{condition_tag}"
    asr_slug = asr_id.lower().replace("-", "")
    run_id = (
        f"{phase}:{task_id}:{asr_id}:r{round_number}:"
        f"{spoken_variant}:{audio_condition}"
    )
    return PlannedRun(
        run_id=run_id,
        phase=phase,
        task_id=task_id,
        asr_id=asr_id,
        round=round_number,
        spoken_variant=spoken_variant,
        audio_condition=audio_condition,
        audio_stem=audio_stem,
        output_filename=(
            f"slide_{_task_number(task_id)}_r{round_number}_"
            f"{asr_id}_{condition_tag}.pptx"
        ),
        source_log=f"{asr_slug}_r{round_number}_{task_id}.txt",
    )


def expand_experiment_plan(manifest: dict[str, Any]) -> list[PlannedRun]:
    """Expand the compact manifest into the exact 176 planned conditions."""

    design = manifest["design"]
    first = design["first_round"]
    task_ids = [task["task_id"] for task in manifest["tasks"]]
    spoken_variants = list(first["spoken_variants"])
    acoustic_conditions = list(first["acoustic_conditions"])
    asr_systems = list(first["asr_systems"])

    runs: list[PlannedRun] = []
    for task_id in task_ids:
        for asr_id in asr_systems:
            for spoken_variant in spoken_variants:
                for audio_condition in acoustic_conditions:
                    runs.append(
                        _planned_run(
                            phase="first_round",
                            task_id=task_id,
                            asr_id=asr_id,
                            round_number=1,
                            spoken_variant=spoken_variant,
                            audio_condition=audio_condition,
                        )
                    )

    for followup in design["targeted_loop_followups"]:
        expected_runs = len(spoken_variants) * len(acoustic_conditions)
        if int(followup["runs"]) != expected_runs:
            raise ValueError(
                "Each targeted follow-up must cover the same spoken/acoustic grid: "
                f"expected {expected_runs}, found {followup['runs']}."
            )
        for spoken_variant in spoken_variants:
            for audio_condition in acoustic_conditions:
                runs.append(
                    _planned_run(
                        phase="loop_followup",
                        task_id=followup["task"],
                        asr_id=followup["asr"],
                        round_number=int(followup["round"]),
                        spoken_variant=spoken_variant,
                        audio_condition=audio_condition,
                    )
                )

    expected_first = int(first["runs"])
    actual_first = sum(run.phase == "first_round" for run in runs)
    if actual_first != expected_first:
        raise ValueError(
            f"First-round design expands to {actual_first} runs, not {expected_first}."
        )
    expected_total = int(design["total_runs"])
    if len(runs) != expected_total:
        raise ValueError(
            f"Experiment design expands to {len(runs)} runs, not {expected_total}."
        )
    run_ids = [run.run_id for run in runs]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("Experiment design contains duplicate run IDs.")
    return runs


def load_experiment_plan(workspace: str | Path) -> list[PlannedRun]:
    return expand_experiment_plan(load_experiment_manifest(workspace))
