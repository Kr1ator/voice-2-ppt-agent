"""Command-line interface for Voice-to-PPT workflows and experiment checks."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__
from .config import load_runtime_environment


AUDIO_NAME_RE = re.compile(
    r"^(?P<instruction_key>id\d+(?:-\d+)?)_"
    r"(?P<spoken_variant>clean|spoken|connected|self_repair)"
    r"(?:_(?P<audio_condition>noise|reverb|bandlimit))?$"
)


def _resolve_path(path_text: str, fallback_root: Path) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.exists():
        return candidate.resolve()

    fallback = fallback_root / path_text
    if fallback.exists():
        return fallback.resolve()

    if candidate.parent == Path(".") and fallback_root.exists():
        matches = [path for path in fallback_root.rglob(path_text)]
        if len(matches) == 1:
            return matches[0].resolve()
    return fallback


def _engine_name(engine: Any) -> str:
    return getattr(engine, "asr_id", getattr(engine, "model_size", "unknown"))


def _build_engine(args: argparse.Namespace):
    cache_text = args.model_cache or os.environ.get("VOICE_PPT_MODEL_CACHE")
    cache = Path(cache_text).expanduser() if cache_text else None
    if args.asr == "faster-whisper":
        from .asr.engines.faster_whisper import FasterWhisperEngine

        return FasterWhisperEngine(
            model_size=args.whisper_model,
            model_root=cache,
            device=args.device,
            compute_type=args.compute_type,
        )
    if args.asr == "qwen-asr":
        from .asr.engines.qwen_asr import QwenASREngine

        return QwenASREngine(
            model_id=args.qwen_model,
            cache_dir=cache,
            device=args.device,
        )
    raise ValueError(f"Unknown ASR engine: {args.asr}")


def _condition_tag(audio_path: Path) -> str:
    match = AUDIO_NAME_RE.match(audio_path.stem)
    if not match:
        return audio_path.stem
    spoken = match.group("spoken_variant")
    acoustic = match.group("audio_condition")
    return f"{spoken}_{acoustic}" if acoustic else spoken


def _transcript_path(audio_path: Path, engine: Any, output_root: Path) -> Path:
    folder = output_root / "transcripts" / audio_path.parent.name
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{audio_path.stem}_{_engine_name(engine)}.txt"


def _ppt_output_path(
    audio_path: Path,
    pptx_path: Path,
    engine: Any,
    rounds: int,
    output_root: Path,
) -> Path:
    folder = output_root / "ppt" / audio_path.parent.name
    folder.mkdir(parents=True, exist_ok=True)
    suffix = f"r{rounds}_{_engine_name(engine)}_{_condition_tag(audio_path)}"
    return folder / f"{pptx_path.stem}_{suffix}.pptx"


def _transcribe(
    audio_path: Path,
    engine: Any,
    output_root: Path,
    reuse: bool = False,
) -> tuple[str, Path] | None:
    transcript_path = _transcript_path(audio_path, engine, output_root)
    if reuse and transcript_path.exists():
        transcript = transcript_path.read_text(encoding="utf-8").strip()
        if transcript:
            print(f"Reusing transcript: {transcript_path}")
            return transcript, transcript_path

    print(f"ASR {_engine_name(engine)}: {audio_path}")
    started = time.time()
    result = engine.transcribe(str(audio_path))
    print(f"ASR completed in {time.time() - started:.1f}s")
    if result.error:
        print(f"ASR error: {result.error}", file=sys.stderr)
        return None
    transcript = result.transcript.strip()
    if not transcript:
        print("ASR returned an empty transcript.", file=sys.stderr)
        return None
    transcript_path.write_text(transcript, encoding="utf-8")
    print(f"Transcript: {transcript}")
    print(f"Saved: {transcript_path}")
    return transcript, transcript_path


def _configure_runtime(args: argparse.Namespace, output_root: Path) -> None:
    os.environ["VOICE_PPT_OUTPUT_DIR"] = str(output_root / "ppt")
    if args.editor_model:
        os.environ["VOICE_PPT_EDITOR_MODEL"] = args.editor_model
    if args.planner_model:
        os.environ["VOICE_PPT_PLANNER_MODEL"] = args.planner_model


def _edit(
    pptx_path: Path,
    instruction: str,
    output_path: Path,
    args: argparse.Namespace,
    request_id: str,
) -> bool:
    output_root = output_path.parent.parent if output_path.parent.name == "ppt" else output_path.parent
    _configure_runtime(args, output_root)
    from .llm.utils import load_api_keys
    from .orchestrator import process_presentation_hybrid

    api_key = load_api_keys().get("deepseek")
    if not api_key:
        print("DEEPSEEK_API_KEY is not configured.", file=sys.stderr)
        return False

    if args.allow_generated_code:
        print(
            "WARNING: model-generated Python is enabled and runs with your user permissions. "
            "Use an isolated environment and trusted inputs only."
        )

    result = process_presentation_hybrid(
        original_filepath=str(pptx_path),
        prompt_text=instruction,
        api_key=api_key,
        request_id=request_id,
        loop_mode=args.rounds > 1,
        loop_max_iterations=args.rounds,
        output_filepath=output_path,
        force_xml=args.execution_mode == "xml",
        force_python_pptx=args.execution_mode == "python",
        allow_generated_code=args.allow_generated_code,
    )
    if not isinstance(result, dict) or result.get("error"):
        error = result.get("error") if isinstance(result, dict) else type(result).__name__
        print(f"Agent error: {error}", file=sys.stderr)
        return False
    produced = result.get("modified_pptx_filepath")
    if not produced:
        print("Agent produced no PPTX.", file=sys.stderr)
        return False
    print(f"Edited PPTX: {produced}")
    return True


def command_inspect(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    pptx_path = _resolve_path(args.pptx, workspace / "data" / "pptx")
    if not pptx_path.is_file():
        print(f"PPTX not found: {pptx_path}", file=sys.stderr)
        return 2

    from .ppt import pptx_to_json

    data = pptx_to_json(str(pptx_path))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    shapes = sum(len(slide.get("shapes", [])) for slide in data.get("slides", []))
    print(f"File: {pptx_path}")
    print(f"Slides: {len(data.get('slides', []))}")
    print(f"Shapes: {shapes}")
    print(f"Size: {data.get('slide_width')}pt × {data.get('slide_height')}pt")
    return 0


def command_transcribe(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    audio_path = _resolve_path(args.audio, workspace / "data" / "audio")
    if not audio_path.is_file():
        print(f"Audio not found: {audio_path}", file=sys.stderr)
        return 2
    output_root = Path(args.output_dir).expanduser().resolve()
    engine = _build_engine(args)
    return 0 if _transcribe(audio_path, engine, output_root, reuse=args.reuse_transcript) else 1


def _read_instruction(args: argparse.Namespace) -> str:
    if args.instruction:
        return args.instruction.strip()
    return Path(args.transcript_file).expanduser().read_text(encoding="utf-8").strip()


def command_edit(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    pptx_path = _resolve_path(args.pptx, workspace / "data" / "pptx")
    if not pptx_path.is_file():
        print(f"PPTX not found: {pptx_path}", file=sys.stderr)
        return 2
    try:
        instruction = _read_instruction(args)
    except OSError as exc:
        print(f"Could not read transcript file: {exc}", file=sys.stderr)
        return 2
    if not instruction:
        print("Instruction is empty.", file=sys.stderr)
        return 2
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (workspace / "outputs" / "ppt" / f"{pptx_path.stem}_edited.pptx")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    return 0 if _edit(pptx_path, instruction, output, args, "text_instruction") else 1


def command_run(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    pptx_path = _resolve_path(args.pptx, workspace / "data" / "pptx")
    if not pptx_path.is_file():
        print(f"PPTX not found: {pptx_path}", file=sys.stderr)
        return 2
    output_root = Path(args.output_dir).expanduser().resolve()
    engine = _build_engine(args)

    if args.audio:
        audio_paths = [_resolve_path(args.audio, workspace / "data" / "audio")]
    else:
        audio_dir = _resolve_path(args.audio_dir, workspace / "data" / "audio")
        if not audio_dir.is_dir():
            print(f"Audio directory not found: {audio_dir}", file=sys.stderr)
            return 2
        audio_paths = sorted(path for path in audio_dir.glob(args.pattern) if path.is_file())
        if args.limit:
            audio_paths = audio_paths[: args.limit]

    if not audio_paths or any(not path.is_file() for path in audio_paths):
        print("No matching audio files found.", file=sys.stderr)
        return 2

    failures = 0
    for index, audio_path in enumerate(audio_paths, start=1):
        print(f"\n[{index}/{len(audio_paths)}] {audio_path.name}")
        item = _transcribe(
            audio_path,
            engine,
            output_root,
            reuse=args.reuse_transcript,
        )
        if item is None:
            failures += 1
            continue
        transcript, _ = item
        output = _ppt_output_path(audio_path, pptx_path, engine, args.rounds, output_root)
        ok = _edit(
            pptx_path,
            transcript,
            output,
            args,
            f"asr_{_engine_name(engine)}_{audio_path.stem}",
        )
        failures += int(not ok)

    print(f"\nSummary: {len(audio_paths) - failures}/{len(audio_paths)} completed")
    return 0 if failures == 0 else 1


def command_validate_results(args: argparse.Namespace) -> int:
    """Check the saved experiment tables without models or API access."""

    from .evaluation import (
        SnapshotValidationError,
        format_validation_summary,
        validate_result_snapshot,
    )

    try:
        totals = validate_result_snapshot(Path(args.workspace))
    except (OSError, KeyError, ValueError, SnapshotValidationError) as exc:
        print(f"Experiment result validation failed: {exc}", file=sys.stderr)
        return 1
    print(format_validation_summary(totals))
    return 0


def command_plan_experiment(args: argparse.Namespace) -> int:
    """Expand the recorded experiment design without running any models."""

    from .experiment import load_experiment_plan

    runs = load_experiment_plan(args.workspace)
    if args.format == "json":
        print(json.dumps([run.as_dict() for run in runs], ensure_ascii=False, indent=2))
        return 0
    if args.format == "csv":
        fieldnames = list(runs[0].as_dict())
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(run.as_dict() for run in runs)
        return 0

    first_round = sum(run.phase == "first_round" for run in runs)
    followups = len(runs) - first_round
    print(f"Experiment plan: {len(runs)} runs")
    print(f"First round: {first_round}")
    print(f"Targeted loop follow-ups: {followups}")
    groups: dict[tuple[str, str, str], int] = {}
    for run in runs:
        key = (run.phase, run.task_id, run.asr_id)
        groups[key] = groups.get(key, 0) + 1
    for (phase, task_id, asr_id), count in groups.items():
        print(f"- {phase}: {task_id} × {asr_id}: {count}")
    return 0


def _add_workspace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", default=".", help="Workspace root (default: current directory).")


def _add_env_file(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Local environment file (default: .env; process variables take precedence).",
    )


def _add_asr_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--asr", choices=["faster-whisper", "qwen-asr"], default="faster-whisper")
    parser.add_argument("--model-cache", help="ASR model cache directory.")
    parser.add_argument("--device", default="auto", help="ASR device, e.g. auto, cpu, mps, cuda:0.")
    parser.add_argument("--compute-type", default="auto", help="faster-whisper compute type.")
    parser.add_argument("--whisper-model", default="large-v3-turbo")
    parser.add_argument("--qwen-model", default="Qwen/Qwen3-ASR-1.7B")


def _add_agent_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--editor-model", help="Editor model ID exposed by the configured endpoint.")
    parser.add_argument("--planner-model", help="Router/planner model ID exposed by the endpoint.")
    parser.add_argument(
        "--execution-mode",
        choices=["xml", "auto", "python"],
        default="xml",
        help="xml is the safe default; auto reproduces router behavior.",
    )
    parser.add_argument(
        "--allow-generated-code",
        action="store_true",
        help="Opt in to executing model-generated Python with current-user permissions.",
    )


def _configure_run_parser(run_parser: argparse.ArgumentParser) -> None:
    """Add the historical ``run.py`` options to an argument parser."""

    _add_workspace(run_parser)
    _add_env_file(run_parser)
    _add_asr_options(run_parser)
    _add_agent_options(run_parser)
    audio_group = run_parser.add_mutually_exclusive_group(required=True)
    audio_group.add_argument("--audio")
    audio_group.add_argument("--audio-dir")
    run_parser.add_argument("--pptx", required=True)
    run_parser.add_argument("--output-dir", default="outputs")
    run_parser.add_argument("--pattern", default="*.wav")
    run_parser.add_argument("--limit", type=int, default=0)
    run_parser.add_argument(
        "--reuse-transcript",
        "--reuse-transcripts",
        dest="reuse_transcript",
        action="store_true",
        help="Reuse a saved transcript when available.",
    )
    run_parser.set_defaults(func=command_run)


def build_run_parser() -> argparse.ArgumentParser:
    """Build the public parser used by the repository-root ``run.py``."""

    parser = argparse.ArgumentParser(
        prog="python run.py",
        description="Audio + PPTX -> transcript + edited PPTX.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    _configure_run_parser(parser)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voice-ppt",
        description="Edit PowerPoint files from spoken or written instructions.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect", help="Offline PPTX structure check.")
    _add_workspace(inspect_parser)
    inspect_parser.add_argument("--pptx", required=True)
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.set_defaults(func=command_inspect)

    transcribe_parser = sub.add_parser("transcribe", help="Run one local ASR backend.")
    _add_workspace(transcribe_parser)
    _add_env_file(transcribe_parser)
    _add_asr_options(transcribe_parser)
    transcribe_parser.add_argument("--audio", required=True)
    transcribe_parser.add_argument("--output-dir", default="outputs")
    transcribe_parser.add_argument("--reuse-transcript", action="store_true")
    transcribe_parser.set_defaults(func=command_transcribe)

    edit_parser = sub.add_parser("edit", help="Edit a PPTX from text or a saved transcript.")
    _add_workspace(edit_parser)
    _add_env_file(edit_parser)
    _add_agent_options(edit_parser)
    edit_parser.add_argument("--pptx", required=True)
    instruction_group = edit_parser.add_mutually_exclusive_group(required=True)
    instruction_group.add_argument("--instruction")
    instruction_group.add_argument("--transcript-file")
    edit_parser.add_argument("--output")
    edit_parser.set_defaults(func=command_edit)

    run_parser = sub.add_parser("run", help="Run ASR followed by PPT editing.")
    _configure_run_parser(run_parser)

    validate_parser = sub.add_parser(
        "validate-results",
        help="Check consistency across the saved experiment design and results.",
    )
    _add_workspace(validate_parser)
    validate_parser.set_defaults(func=command_validate_results)

    plan_parser = sub.add_parser(
        "plan-experiment",
        help="Expand the recorded 176-run design without running models.",
    )
    _add_workspace(plan_parser)
    plan_parser.add_argument(
        "--format",
        choices=["summary", "json", "csv"],
        default="summary",
    )
    plan_parser.set_defaults(func=command_plan_experiment)

    return parser


def _dispatch(args: argparse.Namespace) -> int:
    args.rounds = max(1, int(getattr(args, "rounds", 1)))
    if hasattr(args, "env_file"):
        try:
            load_runtime_environment(args.env_file)
        except OSError as exc:
            print(f"Could not read environment file: {exc}", file=sys.stderr)
            return 2
    if getattr(args, "execution_mode", None) == "python" and not args.allow_generated_code:
        print("--execution-mode python requires --allow-generated-code.", file=sys.stderr)
        return 2
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


def run_main(argv: list[str] | None = None) -> int:
    """Entry point matching the final experiment's ``python run.py`` interface."""

    return _dispatch(build_run_parser().parse_args(argv))


def main(argv: list[str] | None = None) -> int:
    return _dispatch(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
