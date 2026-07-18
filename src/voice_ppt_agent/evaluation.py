"""Offline consistency checks for the saved experiment evidence."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .experiment import load_experiment_plan


class SnapshotValidationError(ValueError):
    """Raised when the saved experiment files disagree with one another."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotValidationError(message)


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SnapshotValidationError(f"Required result file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _count_true(rows: list[dict[str, str]], field: str) -> int:
    return sum(row[field] == "true" for row in rows)


def _metric_numerator(rows: list[dict[str, str]], metric: str) -> int:
    if metric == "pptx_produced":
        return _count_true(rows, "pptx_produced")
    if metric == "edit_signal":
        return _count_true(rows, "edit_signal")
    if metric == "rule_correct":
        return _count_true(rows, "deterministic_rule_pass")
    if metric == "visual_pass":
        return sum(row["visual_status"] == "pass" for row in rows)
    if metric == "retry_events":
        return sum(int(row["retry_count"]) for row in rows)
    raise SnapshotValidationError(f"Unsupported grouped metric: {metric}")


def validate_result_snapshot(workspace: str | Path) -> dict[str, int]:
    """Cross-check both experiment stages and their result tables."""

    root = Path(workspace).expanduser().resolve()
    stage1 = _csv_rows(root / "results" / "stage1_pptarena_exploration.csv")
    summary = _csv_rows(root / "results" / "stage2_voice_agent_summary.csv")
    runs = _csv_rows(root / "results" / "stage2_voice_agent_runs.csv")
    plan = load_experiment_plan(root)

    _require(len(stage1) == 10, f"Stage 1 must contain 10 cases; found {len(stage1)}.")
    _require(
        len({row["case"] for row in stage1}) == 10,
        "Stage 1 contains duplicate case labels.",
    )
    interfaces = Counter(row["interface"] for row in stage1)
    _require(
        interfaces == {"GUI": 4, "CLI": 6},
        f"Stage 1 must contain 4 GUI and 6 CLI cases; found {dict(interfaces)}.",
    )
    rounds = Counter(row["rounds"] for row in stage1)
    _require(
        rounds == {"1": 5, "2": 5},
        f"Stage 1 must contain five one-round and five two-round cases; found {dict(rounds)}.",
    )
    for index, row in enumerate(stage1, start=2):
        _require(row["rounds"] in {"1", "2"}, f"Stage 1 row {index} has invalid rounds.")
        for field in (
            "case",
            "model",
            "prompt",
            "chatgpt_evaluation_zh",
            "gemini_evaluation_zh",
        ):
            _require(bool(row[field].strip()), f"Stage 1 row {index} is missing {field}.")

    _require(len(plan) == 176, "The experiment manifest must expand to 176 runs.")
    _require(len(runs) == 176, f"The run snapshot must contain 176 rows; found {len(runs)}.")
    _require(len(summary) == 46, f"The Stage 2 summary must contain 46 rows; found {len(summary)}.")
    plan_by_id = {item.run_id: item for item in plan}
    run_ids = [row["run_id"] for row in runs]
    _require(len(set(run_ids)) == 176, "The run snapshot contains duplicate run IDs.")
    _require(set(run_ids) == set(plan_by_id), "Run IDs do not match the recorded design.")

    boolean_fields = (
        "retry_triggered",
        "script_error_observed",
        "pptx_produced",
        "edit_signal",
    )
    for index, row in enumerate(runs, start=2):
        item = plan_by_id[row["run_id"]]
        expected = {
            "phase": item.phase,
            "task_id": item.task_id,
            "asr_id": item.asr_id,
            "round": str(item.round),
            "spoken_variant": item.spoken_variant,
            "audio_condition": item.audio_condition,
            "output_filename": item.output_filename,
            "source_log": item.source_log,
        }
        for field, value in expected.items():
            _require(
                row[field] == value,
                f"stage2_voice_agent_runs.csv row {index} disagrees in {field}.",
            )
        for field in boolean_fields:
            _require(
                row[field] in {"true", "false"},
                f"stage2_voice_agent_runs.csv row {index} has invalid {field}.",
            )
        retry_count = int(row["retry_count"])
        script_error_count = int(row["script_error_count"])
        _require(retry_count >= 0, f"Stage 2 row {index} has a negative retry count.")
        _require(
            script_error_count >= 0,
            f"Stage 2 row {index} has a negative script-error count.",
        )
        _require(
            (retry_count > 0) == (row["retry_triggered"] == "true"),
            f"Stage 2 row {index} has inconsistent retry fields.",
        )
        _require(
            (script_error_count > 0) == (row["script_error_observed"] == "true"),
            f"Stage 2 row {index} has inconsistent script-error fields.",
        )
        if row["pptx_produced"] == "false":
            _require(
                row["edit_signal"] == "false",
                f"Stage 2 row {index} claims an edit signal without an output.",
            )

        geometry_fields = (
            "embedded_images",
            "max_overlap_ratio",
            "left_right_margin_diff_ratio",
            "gap_diff_ratio",
            "visual_note",
        )
        if row["task_id"] == "id31":
            _require(
                row["visual_status"]
                in {"pass", "fail_overlap", "fail_alignment", "missing_output"},
                f"Stage 2 row {index} has an invalid visual status.",
            )
            _require(
                bool(row["visual_note"].strip()),
                f"Stage 2 row {index} lacks a visual note.",
            )
            embedded_images = int(row["embedded_images"])
            if row["visual_status"] == "missing_output":
                _require(
                    row["pptx_produced"] == "false" and embedded_images == 0,
                    f"Stage 2 row {index} has inconsistent missing-output geometry.",
                )
                _require(
                    all(not row[field] for field in geometry_fields[1:4]),
                    f"Stage 2 row {index} has geometry ratios without an output.",
                )
            else:
                _require(
                    row["pptx_produced"] == "true" and embedded_images == 3,
                    f"Stage 2 row {index} must retain three images.",
                )
                for field in geometry_fields[1:4]:
                    _require(
                        Decimal(row[field]) >= 0,
                        f"Stage 2 row {index} has invalid {field}.",
                    )
        else:
            _require(
                not row["visual_status"],
                f"Stage 2 row {index} has an unexpected visual status.",
            )
            _require(
                all(not row[field] for field in geometry_fields),
                f"Stage 2 row {index} has geometry fields for a non-layout task.",
            )

    flattened = "\n".join(value for row in runs for value in row.values()).lower()
    for forbidden in ("/users/", "credentials.env", "deepseek_api_key", "sk-"):
        _require(forbidden not in flattened, f"Run snapshot contains private marker: {forbidden}")

    rule_rows = [row for row in runs if row["deterministic_rule_pass"]]
    visual_rows = [row for row in runs if row["task_id"] == "id31"]
    _require(len(rule_rows) == 112, "Deterministic rules must cover exactly 112 runs.")
    _require(len(visual_rows) == 64, "Merged geometry fields must cover exactly 64 id31 runs.")

    totals = {
        "stage1_cases": len(stage1),
        "stage1_gui": interfaces["GUI"],
        "stage1_cli": interfaces["CLI"],
        "runs": len(runs),
        "pptx_produced": _count_true(runs, "pptx_produced"),
        "edit_signal": _count_true(runs, "edit_signal"),
        "rule_correct": _count_true(runs, "deterministic_rule_pass"),
        "visual_pass": sum(row["visual_status"] == "pass" for row in runs),
        "runs_with_retry": _count_true(runs, "retry_triggered"),
        "retry_events": sum(int(row["retry_count"]) for row in runs),
        "runs_with_script_error": _count_true(runs, "script_error_observed"),
        "script_error_events": sum(int(row["script_error_count"]) for row in runs),
    }
    _require(
        totals
        == {
            "stage1_cases": 10,
            "stage1_gui": 4,
            "stage1_cli": 6,
            "runs": 176,
            "pptx_produced": 168,
            "edit_signal": 135,
            "rule_correct": 73,
            "visual_pass": 37,
            "runs_with_retry": 25,
            "retry_events": 27,
            "runs_with_script_error": 24,
            "script_error_events": 26,
        },
        f"Unexpected run-level totals: {totals}",
    )

    for index, row in enumerate(summary, start=2):
        numerator = int(row["numerator"])
        denominator = int(row["denominator"])
        _require(denominator > 0, f"Stage 2 summary row {index} has a zero denominator.")
        expected_rate = (
            Decimal(numerator) * 100 / Decimal(denominator)
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        _require(
            Decimal(row["rate_percent"]) == expected_rate,
            f"Stage 2 summary row {index} has an inconsistent percentage.",
        )

    aggregate = {
        row["metric"]: (int(row["numerator"]), int(row["denominator"]))
        for row in summary
        if row["section"] == "aggregate"
    }
    _require(
        aggregate
        == {
            "pptx_produced": (168, 176),
            "edit_signal": (135, 176),
            "rule_correct": (73, 112),
            "visual_pass": (37, 64),
            "runs_with_retry": (25, 176),
            "retry_events": (27, 176),
        },
        "Aggregate metrics do not match the run-level evidence.",
    )

    grouped_rows = [
        row for row in summary if row["section"] in {"first_round", "loop_followup"}
    ]
    for row in grouped_rows:
        selected = [
            run
            for run in runs
            if run["phase"] == row["section"]
            and run["task_id"] == row["task_id"]
            and run["asr_id"] == row["asr_id"]
            and run["round"] == row["round"]
        ]
        _require(len(selected) == 16, f"Unexpected condition size for {row}.")
        _require(
            int(row["denominator"]) == 16,
            f"Grouped metric denominator must be 16 for {row}.",
        )
        actual = _metric_numerator(selected, row["metric"])
        _require(
            actual == int(row["numerator"]),
            f"Grouped metric does not match run rows for {row}.",
        )

    visual_keys = {
        (
            row["asr_id"],
            row["round"],
            row["spoken_variant"],
            row["audio_condition"],
        )
        for row in visual_rows
    }
    _require(
        len(visual_keys) == 64,
        "Merged id31 geometry rows contain duplicate conditions.",
    )
    status = Counter(row["visual_status"] for row in visual_rows)
    _require(
        status
        == {
            "pass": 37,
            "fail_overlap": 17,
            "fail_alignment": 3,
            "missing_output": 7,
        },
        f"Unexpected id31 status counts: {dict(status)}.",
    )
    by_condition: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    acoustic_passes: Counter[str] = Counter()
    for row in visual_rows:
        by_condition[(row["asr_id"], row["round"])][row["visual_status"]] += 1
        if row["visual_status"] == "pass":
            acoustic_passes[row["audio_condition"]] += 1
    expected_passes = {
        ("ASR-2", "1"): 10,
        ("ASR-2", "2"): 8,
        ("ASR-6", "1"): 10,
        ("ASR-6", "2"): 9,
    }
    for condition, expected in expected_passes.items():
        _require(
            by_condition[condition]["pass"] == expected,
            f"Unexpected visual-pass count for {condition}.",
        )
    _require(
        acoustic_passes == {"none": 9, "bandlimit": 12, "noise": 7, "reverb": 9},
        f"Unexpected acoustic-condition totals: {dict(acoustic_passes)}.",
    )

    asr2_id20 = [
        row for row in runs if row["task_id"] == "id20" and row["asr_id"] == "ASR-2"
    ]
    _require(len(asr2_id20) == 32, "ASR-2 id20 must contain 32 first/follow-up rows.")
    _require(
        sum(row["critical_slot_preserved"] == "false" for row in asr2_id20) == 26,
        "Strict 32+pt critical-slot failure count must be 26/32.",
    )
    missing_outputs = Counter(
        row["task_id"] for row in runs if row["pptx_produced"] == "false"
    )
    _require(
        missing_outputs == {"id31": 7, "id47": 1},
        f"Unexpected missing-output attribution: {dict(missing_outputs)}.",
    )
    return totals


def format_validation_summary(totals: dict[str, int]) -> str:
    """Return a stable one-line summary for the CLI and CI logs."""

    return (
        "Saved experiment results validated: "
        f"{totals['stage1_cases']} exploratory cases; "
        f"{totals['runs']} runs, {totals['pptx_produced']} PPTX outputs, "
        f"{totals['edit_signal']} log edit signals, "
        f"{totals['rule_correct']} rule successes, "
        f"{totals['visual_pass']} visual passes."
    )
