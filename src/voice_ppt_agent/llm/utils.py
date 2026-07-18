import json
import os
import re
from pathlib import Path
from typing import Optional

CREDENTIALS_FILE = Path(os.environ.get("VOICE_PPT_ENV_FILE", ".env")).expanduser()
API_KEYS = {}


def normalize_pptx_xml_path(path: str) -> str:
    """Return the PPTX-internal XML path when an extracted temp path is provided."""
    normalized = str(path or "").strip().strip('"').strip("'").replace("\\", "/")
    if normalized.startswith("file://"):
        normalized = normalized[len("file://"):]

    for marker in ("ppt/", "docProps/", "_rels/"):
        idx = normalized.find(marker)
        if idx != -1:
            return normalized[idx:]

    content_types = "[Content_Types].xml"
    idx = normalized.find(content_types)
    if idx != -1:
        return content_types

    return normalized

def _log(message, request_id=None):
    """Helper function for logging with an optional request ID."""
    if request_id:
        print(f"[{request_id}] {message}")
    else:
        print(message)

def load_api_keys():
    """Load API settings from the configured .env file or process environment."""
    global API_KEYS
    if not API_KEYS:  # Load only once
        API_KEYS = {}
        file_loaded = False

        # Process variables have higher precedence than the local file. The CLI
        # has already loaded supported file values into the environment without
        # overwriting any variables supplied by the caller.
        env_deepseek = os.environ.get("DEEPSEEK_API_KEY")
        env_deepseek_base_url = os.environ.get("DEEPSEEK_BASE_URL")
        if env_deepseek:
            API_KEYS["deepseek"] = env_deepseek
        if env_deepseek_base_url:
            API_KEYS["deepseek_base_url"] = env_deepseek_base_url.rstrip("/")

        try:
            if CREDENTIALS_FILE.exists():
                with CREDENTIALS_FILE.open('r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            value = value.strip().strip('"').strip("'")
                            normalized_key = key.strip().upper()
                            if (
                                normalized_key == "DEEPSEEK_API_KEY"
                                and value
                                and "deepseek" not in API_KEYS
                            ):
                                API_KEYS["deepseek"] = value
                            elif (
                                normalized_key == "DEEPSEEK_BASE_URL"
                                and value
                                and "deepseek_base_url" not in API_KEYS
                            ):
                                API_KEYS["deepseek_base_url"] = value.rstrip("/")
                file_loaded = True
        except Exception as e:
            _log(f"Error loading {CREDENTIALS_FILE}: {e}")
            API_KEYS = {}

        # Only warn if nothing was found anywhere
        if not API_KEYS and not file_loaded:
            _log(f"Warning: {CREDENTIALS_FILE} not found and no API keys present in environment.", None)
    return API_KEYS

def _create_deepseek_client(api_key: Optional[str] = None):
    keys = load_api_keys()
    resolved_key = api_key or keys.get("deepseek") or keys.get("deepseek_api_key")
    if not resolved_key:
        return None
    return {
        "api_key": resolved_key,
        "base_url": keys.get("deepseek_base_url") or "https://api.deepseek.com",
    }

def _extract_text_from_deepseek_response(resp: dict) -> str:
    try:
        return resp["choices"][0]["message"]["content"] or ""
    except Exception:
        return json.dumps(resp, ensure_ascii=False)

def extract_json_from_llm_response(response_text: str) -> dict:
    """
    Robustly extracts JSON from LLM responses that may contain extra text,
    markdown formatting, or multiple JSON objects.
    """
    if not response_text or not response_text.strip():
        raise ValueError("Empty response text")

    try:
        # First, try to parse the response directly as JSON
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    # Try to extract from markdown code blocks
    json_patterns = [
        r'```json\s*\n(.*?)\n\s*```',  # Standard json code block
        r'```\s*\n(.*?)\n\s*```',      # Generic code block
        r'`(.*?)`',                    # Inline code
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Try to find JSON objects by searching for balanced braces
    text = response_text.strip()

    # Find the first opening brace
    start_idx = text.find('{')
    if start_idx == -1:
        raise ValueError("No JSON object found in response")

    # Find the matching closing brace by counting nested braces
    brace_count = 0
    end_idx = start_idx

    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break

    if brace_count != 0:
        raise ValueError("Unbalanced braces in JSON response")

    # Extract and parse the JSON
    json_str = text[start_idx:end_idx + 1]
    return json.loads(json_str)

def parse_llm_response_for_xml_changes(llm_text_response):
    """
    Extract modified XML blocks from LLM output in multiple tolerant formats:
    1) MODIFIED_XML_FILE: <path>```xml ... ```
    2) MODIFIED_XML_FILE: <path>``` ... ``` (no language tag)
    3) MODIFIED_XML_FILE: <path> followed by raw XML until the next tag or end
    4) JSON-shaped output containing { "modified_files": { path: xml, ... } }
    """
    modified_files = {}
    text = llm_text_response or ""

    # First try JSON
    try:
        parsed = extract_json_from_llm_response(text)
        if isinstance(parsed, dict):
            mf = parsed.get("modified_files") or parsed.get("files") or parsed.get("xml_files")
            if isinstance(mf, dict):
                # Accept only .xml keys
                for k, v in mf.items():
                    if isinstance(k, str) and k.endswith('.xml') and isinstance(v, str) and v.strip():
                        modified_files[normalize_pptx_xml_path(k)] = v.strip()
                if modified_files:
                    return modified_files
    except Exception:
        pass

    # Regex approach with multiple patterns
    fence_patterns = [
        re.compile(r"MODIFIED_XML_FILE:\s*(?P<filename>[a-zA-Z0-9./\-_]+?\.xml)\s*```xml\n(?P<xml_content>.+?)\n```", re.DOTALL),
        re.compile(r"MODIFIED_XML_FILE:\s*(?P<filename>[a-zA-Z0-9./\-_]+?\.xml)\s*```\n(?P<xml_content>.+?)\n```", re.DOTALL),
    ]
    for pat in fence_patterns:
        for m in pat.finditer(text):
            filename = normalize_pptx_xml_path(m.group('filename').strip())
            xml_content = m.group('xml_content').strip()
            modified_files[filename] = xml_content
    if modified_files:
        return modified_files

    # Fallback: scan segments between tags
    tag_pat = re.compile(r"MODIFIED_XML_FILE:\s*([a-zA-Z0-9./\-_]+?\.xml)")
    starts = list(tag_pat.finditer(text))
    for i, m in enumerate(starts):
        filename = normalize_pptx_xml_path(m.group(1).strip())
        seg_start = m.end()
        seg_end = starts[i + 1].start() if (i + 1) < len(starts) else len(text)
        segment = text[seg_start:seg_end].strip()
        if not segment:
            continue
        # If contains a code fence, grab inside; else take segment as XML
        cf = re.search(r"```(?:xml)?\n([\s\S]+?)\n```", segment)
        if cf:
            content = cf.group(1).strip()
        else:
            content = segment.strip()
        # Basic sanity: should look like XML
        if '<' in content and '>' in content:
            modified_files[filename] = content

    return modified_files
