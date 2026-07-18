import os
from pathlib import Path
from types import SimpleNamespace

from voice_ppt_agent import orchestrator
from voice_ppt_agent.cli import (
    _condition_tag,
    build_parser,
    build_run_parser,
    main,
)
from voice_ppt_agent.config import load_runtime_environment


def test_cli_defaults_to_xml_execution() -> None:
    args = build_parser().parse_args(
        ["edit", "--pptx", "deck.pptx", "--instruction", "Fix typos."]
    )
    assert args.execution_mode == "xml"
    assert args.allow_generated_code is False
    assert args.rounds == 1


def test_run_py_parser_preserves_historical_interface() -> None:
    args = build_run_parser().parse_args(
        [
            "--audio-dir",
            "id31_layout_image",
            "--pptx",
            "slide_31.pptx",
            "--rounds",
            "2",
            "--reuse-transcripts",
        ]
    )
    assert args.audio_dir == "id31_layout_image"
    assert args.pptx == "slide_31.pptx"
    assert args.rounds == 2
    assert args.reuse_transcript is True
    assert args.execution_mode == "xml"


def test_python_mode_requires_explicit_opt_in(capsys) -> None:
    exit_code = main(
        [
            "edit",
            "--pptx",
            "deck.pptx",
            "--instruction",
            "Fix typos.",
            "--execution-mode",
            "python",
        ]
    )
    assert exit_code == 2
    assert "requires --allow-generated-code" in capsys.readouterr().err


def test_audio_condition_parsing() -> None:
    assert _condition_tag(Path("id31_clean.wav")) == "clean"
    assert _condition_tag(Path("id31_self_repair_bandlimit.wav")) == "self_repair_bandlimit"


def test_asr_package_has_no_eager_heavy_imports() -> None:
    import voice_ppt_agent.asr as asr

    assert hasattr(asr, "ASRResult")
    assert hasattr(asr, "BaseASREngine")


def test_router_selected_python_is_blocked_without_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "pptx_to_json", lambda _: {"slides": []})
    monkeypatch.setattr(
        orchestrator,
        "decide_editing_strategy",
        lambda *_args, **_kwargs: "PYTHON_PPTX_EDIT",
    )

    def should_not_execute(**_kwargs):
        raise AssertionError("generated code route must remain blocked")

    monkeypatch.setattr(orchestrator, "_execute_python_pptx_edit", should_not_execute)
    result = orchestrator._process_single_iteration(
        original_filepath="unused.pptx",
        prompt_text="Translate every slide.",
        api_key="not-used",
        allow_generated_code=False,
    )
    assert "disabled by default" in result["error"]


def test_force_flags_are_mutually_exclusive(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "pptx_to_json", lambda _: {"slides": []})
    result = orchestrator._process_single_iteration(
        original_filepath="unused.pptx",
        prompt_text="Fix typos.",
        api_key="not-used",
        force_python_pptx=True,
        force_xml=True,
        allow_generated_code=True,
    )
    assert result == {"error": "force_python_pptx and force_xml are mutually exclusive."}


def test_environment_file_respects_process_precedence(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPSEEK_API_KEY=file-key\n"
        "VOICE_PPT_EDITOR_MODEL=file-editor\n"
        "UNSUPPORTED_SETTING=ignored\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "process-key")
    monkeypatch.delenv("VOICE_PPT_EDITOR_MODEL", raising=False)

    loaded = load_runtime_environment(env_file)

    assert loaded["DEEPSEEK_API_KEY"] == "file-key"
    assert loaded["VOICE_PPT_EDITOR_MODEL"] == "file-editor"
    assert "UNSUPPORTED_SETTING" not in loaded
    assert os.environ["DEEPSEEK_API_KEY"] == "process-key"
    assert os.environ["VOICE_PPT_EDITOR_MODEL"] == "file-editor"


def test_llm_key_loader_respects_process_precedence(
    tmp_path: Path, monkeypatch
) -> None:
    from voice_ppt_agent.llm import utils

    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPSEEK_API_KEY=file-key\n"
        "DEEPSEEK_BASE_URL=https://file.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(utils, "CREDENTIALS_FILE", env_file)
    monkeypatch.setattr(utils, "API_KEYS", {})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "process-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://process.invalid/")

    keys = utils.load_api_keys()
    assert keys["deepseek"] == "process-key"
    assert keys["deepseek_base_url"] == "https://process.invalid"


def test_validate_results_cli() -> None:
    root = Path(__file__).resolve().parents[1]
    assert main(["validate-results", "--workspace", str(root)]) == 0


def test_missing_transcript_file_is_reported(tmp_path: Path, capsys) -> None:
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"the file is not opened before transcript validation")
    exit_code = main(
        [
            "edit",
            "--pptx",
            str(deck),
            "--transcript-file",
            str(tmp_path / "missing.txt"),
        ]
    )
    assert exit_code == 2
    assert "Could not read transcript file" in capsys.readouterr().err


def test_generated_code_process_does_not_inherit_api_keys(
    tmp_path: Path, monkeypatch
) -> None:
    original = tmp_path / "input.pptx"
    output = tmp_path / "output.pptx"
    original.write_bytes(b"fixture")
    captured: dict = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        captured["command"] = args[0]
        return SimpleNamespace(returncode=1, stderr="controlled failure")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-leak")
    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)
    result = orchestrator._execute_generated_code(
        str(original),
        "raise RuntimeError('not executed')",
        {},
        output_filepath=output,
    )

    assert result is None
    assert captured["command"][1] == "-I"
    assert "DEEPSEEK_API_KEY" not in captured["env"]
    assert not output.exists()


def test_faster_whisper_load_error_becomes_result(monkeypatch) -> None:
    from voice_ppt_agent.asr.engines.faster_whisper import FasterWhisperEngine

    engine = FasterWhisperEngine()

    def fail_load() -> None:
        raise RuntimeError("controlled model-load failure")

    monkeypatch.setattr(engine, "_load_model", fail_load)
    result = engine.transcribe("unused.wav")
    assert result.transcript == ""
    assert result.error == "controlled model-load failure"


def test_qwen_load_error_becomes_result(monkeypatch) -> None:
    from voice_ppt_agent.asr.engines.qwen_asr import QwenASREngine

    engine = QwenASREngine()

    def fail_load() -> None:
        raise RuntimeError("controlled model-load failure")

    monkeypatch.setattr(engine, "_load_model", fail_load)
    result = engine.transcribe("unused.wav")
    assert result.transcript == ""
    assert result.error == "controlled model-load failure"
