import json
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load env vars from both project root and src folder.
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(CURRENT_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not API_KEY:
    raise ValueError("Please set the GEMINI_API_KEY environment variable.")

client = genai.Client(api_key=API_KEY)

CPT_JSON_FILE = str(PROJECT_ROOT / "data" / "cpt_code_dict.json")
SAMPLES_DIR = PROJECT_ROOT / "samples"
ANSWERS_DIR = SAMPLES_DIR / "answers"
PRICES_DB_FILE = PROJECT_ROOT / "data" / "prices.db"


def _stage(name: str, value=None) -> None:
    print(f"\n=== STAGE: {name} ===")
    if value is not None:
        if isinstance(value, (dict, list)):
            print(json.dumps(value, indent=2))
        else:
            print(value)


def load_all_priced_codes() -> set[str]:
    if not PRICES_DB_FILE.is_file():
        raise FileNotFoundError(f"Pricing database not found at {PRICES_DB_FILE}")

    conn = sqlite3.connect(PRICES_DB_FILE)
    try:
        rows = conn.execute("SELECT DISTINCT [HCPCS Code] FROM Prices").fetchall()
    finally:
        conn.close()

    return {str(code).strip() for (code,) in rows if str(code).strip()}


def load_priced_code_set() -> set[str]:
    try:
        priced_codes = load_all_priced_codes()
    except Exception as exc:
        _stage("load_priced_code_set.error", f"load_all_priced_codes() failed: {exc}")
        return set()

    _stage("load_priced_code_set.done", {"total_priced_codes": len(priced_codes)})
    return priced_codes


def load_cpt_code_dict(json_path: str) -> dict[str, str]:
    _stage("load_cpt_code_dict.start", {"json_path": json_path})
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cleaned = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            cleaned[k.strip()] = v.strip()
    _stage("load_cpt_code_dict.done", {"total_codes": len(cleaned)})
    return cleaned


def _extract_json_text(text: str) -> str:
    if not text:
        return ""

    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _gemini_json(client, prompt: str) -> dict:
    _stage("gemini.request.prompt", prompt)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    content = response.text or ""
    _stage("gemini.response.raw_text", content)
    parsed = json.loads(_extract_json_text(content))
    if not isinstance(parsed, dict):
        raise ValueError("Expected top-level JSON object.")
    _stage("gemini.response.parsed_json", parsed)
    return parsed


def validate_descriptions_batch(client, extracted_items: list[dict], valid_codes_dict: dict[str, str]) -> dict[str, bool]:
    payload = []

    for item in extracted_items:
        cpt_code = str(item.get("cpt_code", "")).strip()
        generated_description = str(item.get("description", "")).strip()

        if cpt_code in valid_codes_dict:
            payload.append({
                "cpt_code": cpt_code,
                "generated_description": generated_description,
                "official_description": valid_codes_dict[cpt_code]
            })

    if not payload:
        _stage("validate_descriptions_batch.skip", "No payload items to validate.")
        return {}

    _stage("validate_descriptions_batch.payload", payload)

    prompt = f"""
Validate CPT descriptions.

Return JSON:
{{ "results": [{{ "cpt_code": "...", "match": true }}] }}

Items:
{json.dumps(payload, indent=2)}
"""

    try:
        response_data = _gemini_json(client, prompt)
        results = response_data.get("results", [])
        if not isinstance(results, list):
            return {}

        match_map = {}
        for r in results:
            code = str(r.get("cpt_code", "")).strip()
            match_map[code] = bool(r.get("match", False))

        _stage("validate_descriptions_batch.match_map", match_map)
        return match_map

    except Exception as e:
        print(f"Batch validation error: {e}")
        return {}


def parse_note(note_text: str, valid_codes_dict: dict[str, str], client) -> list[dict]:
    _stage("parse_note.start", {"note_preview": note_text.strip()[:300]})

    priced_codes = load_priced_code_set()
    has_pricer_codes = bool(priced_codes)

    extraction_prompt = f"""
You are a medical coding assistant.

Read the clinical note and identify billable services explicitly documented in the note.

Return JSON only in this exact format:
{{
  "items": [
    {{
      "cpt_code": "97597",
      "description": "brief description",
      "rationale": "why it is billable"
    }}
  ]
}}

Rules:
- Only include services explicitly documented
- Do not infer undocumented services

Clinical note:
{note_text}
"""

    try:
        response_data = _gemini_json(client, extraction_prompt)
        codes = response_data.get("items", [])
        _stage("parse_note.extracted_items", codes)
    except Exception as e:
        print(f"Error parsing note: {e}")
        return []

    if not isinstance(codes, list):
        return []

    # 🔥 UPDATED: use pricing DB as source of truth
    candidates = []
    for item in codes:
        if not isinstance(item, dict):
            continue

        cpt_code = str(item.get("cpt_code", "")).strip()
        is_in_pricer = (cpt_code in priced_codes) if has_pricer_codes else True

        if is_in_pricer:
            candidates.append(item)
        else:
            _stage(
                "parse_note.filtered_out_unpriced_code",
                {"item": item, "reason": "Not in pricing DB"}
            )

    if not candidates:
        _stage("parse_note.no_candidates", "No valid priced CPT codes.")
        return []

    _stage("parse_note.candidates", candidates)

    match_map = validate_descriptions_batch(client, candidates, valid_codes_dict)

    filtered = []
    for item in candidates:
        cpt_code = str(item.get("cpt_code", "")).strip()

        # 🔥 FIX: allow fallback if Gemini fails
        if not match_map or match_map.get(cpt_code, False):
            item["official_description"] = valid_codes_dict.get(cpt_code, "")
            filtered.append(item)
        else:
            _stage("parse_note.filtered_out_description_mismatch", item)

    _stage("parse_note.final_filtered", filtered)
    return filtered


def process_single_note(
    note_text: str,
    valid_codes_dict=None,
    gemini_client=None,
):
    codes_dict = valid_codes_dict if valid_codes_dict is not None else load_cpt_code_dict(CPT_JSON_FILE)
    active_client = gemini_client if gemini_client is not None else client
    return parse_note(note_text, codes_dict, active_client)


def iter_sample_files(samples_dir: Path):
    for path in sorted(samples_dir.rglob("*")):
        if path.is_file() and "answers" not in path.parts:
            yield path


def output_path_for_sample(sample_path: Path) -> Path:
    relative = sample_path.relative_to(SAMPLES_DIR)
    return ANSWERS_DIR / relative.parent / f"{sample_path.stem}.json"


def run_all_samples(valid_codes_dict, client):
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)

    for sample_file in iter_sample_files(SAMPLES_DIR):
        note_text = sample_file.read_text(errors="ignore")
        result = process_single_note(note_text, valid_codes_dict, client)

        out_path = output_path_for_sample(sample_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    valid_codes_dict = load_cpt_code_dict(CPT_JSON_FILE)
    run_all_samples(valid_codes_dict, client)