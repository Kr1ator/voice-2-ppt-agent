import json
import os
import time
from pathlib import Path
from typing import Optional

import requests

from .llm.utils import (
    load_api_keys,
    _log,
    _create_deepseek_client,
    _extract_text_from_deepseek_response,
    extract_json_from_llm_response,
)
from .llm.prompt import (
    _construct_llm_input_prompt,
    get_relevant_xml_files_heuristic,
)


CREDENTIALS_FILE = ".env"
DEFAULT_DEEPSEEK_MODEL = os.environ.get("VOICE_PPT_EDITOR_MODEL", "deepseek-v4-pro")
DEEPSEEK_PLANNER_MODEL = os.environ.get("VOICE_PPT_PLANNER_MODEL", "deepseek-v4-flash")


def _resolve_deepseek_key(api_key: Optional[str] = None) -> Optional[str]:
    if api_key:
        return api_key
    keys = load_api_keys()
    return keys.get("deepseek") or keys.get("deepseek_api_key")


def _call_deepseek_messages(
    messages: list[dict],
    model_id: str,
    api_key: Optional[str] = None,
    request_id: Optional[str] = None,
    timeout: int = 600,
) -> tuple[str, float]:
    resolved_api_key = _resolve_deepseek_key(api_key)
    if not resolved_api_key:
        raise ValueError(f"DeepSeek API key not provided (set DEEPSEEK_API_KEY in UI, environment, or {CREDENTIALS_FILE}).")

    client = _create_deepseek_client(resolved_api_key)
    if client is None:
        raise ValueError("Failed to initialize DeepSeek client.")

    base_url = client["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {client['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id or DEFAULT_DEEPSEEK_MODEL,
        "messages": messages,
        "stream": False,
    }

    _log(f"Calling DeepSeek API ({payload['model']})", request_id)
    start_time = time.time()
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    elapsed = round(time.time() - start_time, 3)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        error_text = response.text[:1000]
        raise RuntimeError(f"DeepSeek API HTTP {response.status_code}: {error_text}") from exc

    data = response.json()
    text_response = _extract_text_from_deepseek_response(data)
    _log(f"DeepSeek API call successful (took {elapsed:.3f}s, output length {len(text_response or '')})", request_id)
    return text_response, elapsed


def _messages(system_prompt: str, user_prompt: str) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_prompt.strip()},
    ]


def call_deepseek_api(
    user_prompt,
    ppt_json_data,
    xml_file_paths,
    request_id=None,
    api_key=None,
    edit_history=None,
    edit_plan=None,
):
    response_data = {"text_response": "", "model_used": DEFAULT_DEEPSEEK_MODEL, "inference_time_seconds": None}
    if not _resolve_deepseek_key(api_key):
        error = f"DeepSeek API key not provided (set DEEPSEEK_API_KEY in UI, environment, or {CREDENTIALS_FILE})."
        response_data["text_response"] = f"Error: {error}"
        response_data["error"] = error
        return response_data

    try:
        text_prompt_content = _construct_llm_input_prompt(
            user_prompt,
            ppt_json_data,
            xml_file_paths,
            edit_history=edit_history,
            request_id=request_id,
            edit_plan=edit_plan,
        )

        text_response, elapsed = _call_deepseek_messages(
            [{"role": "user", "content": text_prompt_content}],
            DEFAULT_DEEPSEEK_MODEL,
            api_key=api_key,
            request_id=request_id,
        )
        response_data["text_response"] = text_response
        response_data["inference_time_seconds"] = elapsed
    except Exception as e:
        _log(f"DeepSeek API Error: {e}", request_id)
        response_data["text_response"] = f"DeepSeek API Error: {e}"
        response_data["error"] = str(e)
    return response_data


def plan_xml_edits_with_router(
    user_prompt: str,
    ppt_json_data: dict,
    all_xml_file_paths: list,
    request_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict:
    """Use DeepSeek to produce a compact JSON plan for XML editing."""
    planner_model_id = DEEPSEEK_PLANNER_MODEL
    _log(f"Planning XML edits with DeepSeek router ({planner_model_id})...", request_id)

    resolved_api_key = _resolve_deepseek_key(api_key)
    if not resolved_api_key:
        return {"error": "DEEPSEEK_API_KEY missing (set it in .env or the process environment)."}

    files_manifest = {
        "slides": sorted([Path(p).as_posix() for p in all_xml_file_paths if "ppt/slides/slide" in Path(p).as_posix()]),
        "layouts": sorted([Path(p).as_posix() for p in all_xml_file_paths if "ppt/slideLayouts/" in Path(p).as_posix()]),
        "masters": sorted([Path(p).as_posix() for p in all_xml_file_paths if "ppt/slideMasters/" in Path(p).as_posix()]),
        "theme": sorted([Path(p).as_posix() for p in all_xml_file_paths if "ppt/theme/" in Path(p).as_posix()]),
        "other": sorted([Path(p).as_posix() for p in all_xml_file_paths if "ppt/" in Path(p).as_posix() and p.endswith(".xml")]),
    }

    system_prompt = (
        "You are an expert PowerPoint XML planner. Given a user instruction, a JSON summary of the presentation, "
        "and a manifest of available XML files, produce a concise JSON planning object indicating which XML files "
        "should be edited and what types of changes are needed. Do NOT output XML."
    )
    prompt = f"""
--- User Instruction ---
{user_prompt}

--- Presentation JSON Summary (truncated ok) ---
```json
{json.dumps(ppt_json_data, indent=2)[:120000]}
```

--- XML Files Manifest ---
```json
{json.dumps(files_manifest, indent=2)}
```

--- Output Requirements ---
Return a single JSON object with:
- targets: array of objects {{file: string, reason: string, operations: string[]}}
- global: array of file paths for global resources (themes/masters/layouts) if relevant
- notes: short rationale
"""

    try:
        plan_text, _ = _call_deepseek_messages(
            _messages(system_prompt, prompt),
            planner_model_id,
            api_key=resolved_api_key,
            request_id=request_id,
        )
        return extract_json_from_llm_response(plan_text.strip())
    except Exception as e:
        _log(f"Planning Error: {e}", request_id)
        return {"error": str(e)}


def get_llm_response(
    user_prompt,
    ppt_json_data,
    xml_file_paths,
    use_pre_analysis=True,
    request_id=None,
    api_key=None,
    edit_history=None,
):
    """Run optional target planning, then call DeepSeek with the selected XML files."""
    relevant_xml_paths = xml_file_paths
    edit_plan = None

    if use_pre_analysis:
        plan = plan_xml_edits_with_router(
            user_prompt=user_prompt,
            ppt_json_data=ppt_json_data,
            all_xml_file_paths=xml_file_paths,
            request_id=request_id,
            api_key=api_key,
        )
        if plan and not plan.get("error"):
            edit_plan = plan
            candidate_files = set()
            for t in plan.get("targets", []) or []:
                f = t.get("file")
                if isinstance(f, str):
                    candidate_files.add(f)
            for g in plan.get("global", []) or []:
                if isinstance(g, str):
                    candidate_files.add(g)
            provided = {Path(p).as_posix() for p in xml_file_paths}
            relevant_xml_paths = [p for p in candidate_files if p in provided]
            if relevant_xml_paths:
                _log(f"Planning selected {len(relevant_xml_paths)} XML files.", request_id)
            else:
                _log("Planning returned no matching files; falling back to heuristic.", request_id)
        else:
            _log("Planning failed; falling back to heuristic pre-analysis.", request_id)

        if not relevant_xml_paths:
            relevant_xml_paths = get_relevant_xml_files_heuristic(
                user_prompt,
                ppt_json_data,
                xml_file_paths,
            )
            if not relevant_xml_paths:
                return {
                    "text_response": "No changes needed (as determined by pre-analysis).",
                    "model_used": "preanalysis",
                    "inference_time_seconds": 0,
                    "relevant_files": [],
                }
            if len(relevant_xml_paths) == len(xml_file_paths):
                _log("First-pass check returned all files (or failed); proceeding with full context.", request_id)
            else:
                _log(f"Proceeding with {len(relevant_xml_paths)} files identified by heuristic.", request_id)
    else:
        _log("Skipping pre-analysis step as requested.", request_id)

    llm_response_data = call_deepseek_api(
        user_prompt,
        ppt_json_data,
        relevant_xml_paths,
        request_id=request_id,
        api_key=api_key,
        edit_history=edit_history,
        edit_plan=edit_plan,
    )

    llm_response_data["relevant_files"] = relevant_xml_paths
    if edit_plan:
        llm_response_data["planning_plan"] = edit_plan
        llm_response_data["planning_model"] = DEEPSEEK_PLANNER_MODEL
    return llm_response_data


def call_llm_router(
    user_prompt: str,
    ppt_json_data: dict,
    api_key: Optional[str] = None,
    request_id: Optional[str] = None,
) -> str:
    """Use DeepSeek to choose XML editing or python-pptx editing."""
    router_model_id = DEEPSEEK_PLANNER_MODEL

    system_prompt = """
You are a decision-making engine. Your task is to choose the best strategy for editing a PowerPoint presentation based on the user's request.
You have two choices:
1.  `XML_EDIT`: Best for complex, single-slide edits like creating SmartArt, charts, or intricate formatting changes that require direct XML manipulation.
2.  `PYTHON_PPTX_EDIT`: Best for simple, repetitive, multi-slide tasks like text replacement, translation, or applying a consistent style change across the entire deck.

Analyze the user's prompt and the presentation structure.
- If the user asks to "translate the whole deck", "translate all slides", or "rewrite all text", YOU MUST CHOOSE `PYTHON_PPTX_EDIT`.
- If the user asks for a specific visual design change on one slide, choose `XML_EDIT`.

Respond with ONLY the string `XML_EDIT` or `PYTHON_PPTX_EDIT`. Do not provide any explanation.
"""

    prompt = f"""
--- User Prompt ---
{user_prompt}

--- Presentation Summary (high-level) ---
{json.dumps({"slide_count": len(ppt_json_data.get("slides", [])), "slide_titles": [s.get("title", "Untitled") for s in ppt_json_data.get("slides", [])]}, indent=2)}

--- Your Decision ---
"""

    if not _resolve_deepseek_key(api_key):
        _log("Router Error: DeepSeek API key not found. Defaulting to XML_EDIT.", request_id)
        return "XML_EDIT"

    try:
        decision, _ = _call_deepseek_messages(
            _messages(system_prompt, prompt),
            router_model_id,
            api_key=api_key,
            request_id=request_id,
        )
        decision = decision.strip().upper()
    except Exception as e:
        _log(f"Router Error: {e}. Defaulting to XML_EDIT.", request_id)
        return "XML_EDIT"

    if "PYTHON_PPTX_EDIT" in decision:
        return "PYTHON_PPTX_EDIT"
    if "XML_EDIT" in decision:
        return "XML_EDIT"
    _log(f"Router Warning: Unexpected response '{decision}'. Defaulting to XML_EDIT.", request_id)
    return "XML_EDIT"


def generate_content_for_python_pptx(
    user_prompt: str,
    ppt_json_data: dict,
    api_key: Optional[str] = None,
    request_id: Optional[str] = None,
) -> dict:
    """Generate a structured JSON object used by the python-pptx script step."""
    system_prompt = """
You are a content generation specialist. Your task is to analyze a user's request to edit a PowerPoint presentation and extract or generate ONLY the data and content needed to perform the edit.

**CRITICAL RULE: You MUST NOT generate any code (Python, XML, etc.). Your ONLY output must be a single, valid JSON object.**

The JSON object should contain the necessary information for a separate coding step. For example:
- For a translation request, you will provide a mapping of original text to translated text.
- For a data update request, you will provide the new data points.
- For a summarization request, you will provide the summarized text for each slide.

Analyze the user's prompt and the provided JSON summary of the presentation, and generate the content required.
"""

    prompt = f"""
--- User Prompt ---
{user_prompt}

--- Full Presentation JSON Summary ---
{json.dumps(ppt_json_data, indent=2)}

--- Required Content (JSON Output Only) ---
"""

    try:
        response_text, _ = _call_deepseek_messages(
            _messages(system_prompt, prompt),
            DEFAULT_DEEPSEEK_MODEL,
            api_key=api_key,
            request_id=request_id,
        )
        return extract_json_from_llm_response(response_text.strip())
    except Exception as e:
        _log(f"Content Generation Error: {e}", request_id)
        return {"error": f"Failed to generate content: {str(e)}"}


def generate_python_pptx_code(
    user_prompt: str,
    ppt_json_data: dict,
    generated_content: dict,
    api_key: Optional[str] = None,
    request_id: Optional[str] = None,
) -> str:
    """Generate a python-pptx script to modify a presentation."""
    system_prompt = """
You are an expert Python programmer specializing in the `python-pptx` library. Your task is to write a complete, executable Python script that will modify a PowerPoint presentation.

**CRITICAL RULES:**
1.  **DO NOT** write anything other than the Python code. No explanations, no comments before or after the code block.
2.  The script MUST be self-contained and import all necessary libraries (`sys`, `json`, `pptx`).
3.  The script will be executed from the command line with two arguments: the path to the `.pptx` file and the path to a JSON file containing the content.
4.  You MUST include the boilerplate `if __name__ == "__main__":` to parse these arguments.
5.  The core logic should be in a function called `apply_edits(pptx_path, content_path)`.
6.  The `content` loaded from the JSON file will be the data you need to apply the edits. Use it as the source of truth for the changes.
7.  After modifying the presentation object, you MUST save it back to the **original `pptx_path`**.

**python-pptx COMMON MISTAKES — NEVER USE THESE:**
- `slide.slide_number` → use `enumerate(prs.slides, 1)` to get slide index
- `run.bold` → use `run.font.bold`
- `paragraph.bold` → use `paragraph.runs[0].font.bold` or iterate over `paragraph.runs`
- `shape.text_frame.paragraphs[0].bold = True` → set `run.font.bold = True` for each run
- `from pptx.enum.shapes import MSO_PLACEHOLDER` → does NOT exist, use `from pptx.enum.shapes import PP_PLACEHOLDER`
- Accessing `slide.placeholders` directly → use `slide.placeholders` (it does exist, but only on SlideLayout/SlideMaster, not always on Slide)

Below is the context you need to write the script.
"""

    prompt = f"""
--- User's Original Prompt ---
{user_prompt}

--- Presentation Structure (for context) ---
{json.dumps(ppt_json_data, indent=2)}

--- Pre-Generated Content (to be used by your script) ---
{json.dumps(generated_content, indent=2)}

--- Your Python Script (Code Only) ---
"""

    try:
        code, _ = _call_deepseek_messages(
            _messages(system_prompt, prompt),
            DEFAULT_DEEPSEEK_MODEL,
            api_key=api_key,
            request_id=request_id,
        )
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()
    except Exception as e:
        _log(f"Code Generation Error: {e}", request_id)
        return f"print('Error during code generation: {str(e)}')"
