from pathlib import Path

from voice_ppt_agent.evaluation import validate_result_snapshot
from voice_ppt_agent.experiment import load_experiment_plan


def test_experiment_results_are_consistent() -> None:
    root = Path(__file__).resolve().parents[1]
    assert validate_result_snapshot(root) == {
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
    }


def test_stage2_manifest_expands_to_unique_run_ids() -> None:
    root = Path(__file__).resolve().parents[1]
    plan = load_experiment_plan(root)
    assert len(plan) == 176
    assert len({item.run_id for item in plan}) == 176
