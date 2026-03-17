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
    """
    Loads the uploaded JSON file containing official CPT/HCPCS descriptions.
    """
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
    """
    Ask Gemini whether each generated description reasonably matches the
    official description from cpt_code_dict.json.
    """

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
You are validating medical billing outputs.

For each item below, determine whether the generated description is reasonably aligned
with the official CPT/HCPCS description.

Rules:
- Return match = true if the generated description is semantically consistent with the official description,
  even if it is shorter, broader, or missing minor qualifiers.
- Return match = false only if the generated description refers to a different procedure/service,
  contradicts the official meaning, or is too unrelated to trust.
- Do not require the generated description to include every modifier, size threshold, or technical qualifier
  from the official description, as long as the core procedure meaning matches.
- Be strict about wrong procedure families, but lenient about abbreviated wording.

Return JSON only in this exact format:
{{
  "results": [
    {{
      "cpt_code": "97597",
      "match": true,
      "reason": "short explanation"
    }}
  ]
}}

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

Each item in "items" must contain:
- "cpt_code"
- "description"
- "rationale"

Rules:
- Only include services explicitly documented in the note.
- Do not infer undocumented services.
- Keep descriptions concise.
- If no billable services are clearly documented, return {{"items": []}}.

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

    # First filter: code must exist in cpt dictionary.
    # Secondary check: try the pricing database as a supplemental signal.
    candidates = []
    for item in codes:
        if not isinstance(item, dict):
            continue

        cpt_code = str(item.get("cpt_code", "")).strip()
        is_in_cpt_dict = cpt_code in valid_codes_dict
        is_in_pricer = (cpt_code in priced_codes) if has_pricer_codes else True
        # if cpt_code in valid_codes_dict:
        if is_in_cpt_dict:
            candidates.append(item)
            if has_pricer_codes and not is_in_pricer:
                _stage(
                    "parse_note.pricer_miss_non_blocking",
                    {"cpt_code": cpt_code, "note": "Accepted by CPT dictionary; not found in pricing database."},
                )
        else:
            _stage(
                "parse_note.filtered_out_invalid_code",
                {
                    "item": item,
                    "is_in_cpt_dict": is_in_cpt_dict,
                    "is_in_pricer": is_in_pricer,
                },
            )

    if not candidates:
        _stage("parse_note.no_candidates", "No extracted items had valid CPT codes.")
        return []
    _stage("parse_note.candidates", candidates)

    # Second filter: generated description must align with official file meaning
    match_map = validate_descriptions_batch(client, candidates, valid_codes_dict)

    filtered = []
    for item in candidates:
        cpt_code = str(item.get("cpt_code", "")).strip()

        if match_map.get(cpt_code, False):
            item["official_description"] = valid_codes_dict[cpt_code]
            filtered.append(item)
        else:
            _stage("parse_note.filtered_out_description_mismatch", item)

    _stage("parse_note.final_filtered", filtered)
    return filtered

# Uses cpt_code_dict.json as the source of truth for valid codes
def process_single_note(
    note_text: str,
    valid_codes_dict: dict[str, str] | None = None,
    gemini_client=None,
) -> list[dict]:
    """
    Process one note through the same Gemini extraction and validation flow
    used by the sample runner.
    """
    codes_dict = valid_codes_dict if valid_codes_dict is not None else load_cpt_code_dict(CPT_JSON_FILE)
    active_client = gemini_client if gemini_client is not None else client
    return parse_note(note_text, codes_dict, active_client)


def iter_sample_files(samples_dir: Path):
    for path in sorted(samples_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.parts and "answers" in path.parts:
            continue
        if path.name.startswith("."):
            continue
        yield path


def output_path_for_sample(sample_path: Path) -> Path:
    relative = sample_path.relative_to(SAMPLES_DIR)
    stem = sample_path.stem if sample_path.suffix else sample_path.name
    out_name = f"{stem}.json"
    return ANSWERS_DIR / relative.parent / out_name


def run_all_samples(valid_codes_dict: dict[str, str], client) -> None:
    _stage("run_all_samples.start", {"samples_dir": str(SAMPLES_DIR), "answers_dir": str(ANSWERS_DIR)})
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)

    sample_files = list(iter_sample_files(SAMPLES_DIR))
    _stage("run_all_samples.discovered_files", {"count": len(sample_files)})

    for sample_file in sample_files:
        _stage("run_all_samples.sample_start", str(sample_file))
        try:
            note_text = sample_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            _stage("run_all_samples.sample_read_error", {"file": str(sample_file), "error": str(exc)})
            continue

        result = process_single_note(
            note_text,
            valid_codes_dict=valid_codes_dict,
            gemini_client=client,
        )
        out_path = output_path_for_sample(sample_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        _stage("run_all_samples.sample_written", {"input": str(sample_file), "output": str(out_path)})

    _stage("run_all_samples.done", "Finished processing all samples.")


if __name__ == "__main__":
    _stage("main.start", {"model": MODEL_NAME, "cpt_json_file": CPT_JSON_FILE})
    valid_codes_dict = load_cpt_code_dict(CPT_JSON_FILE)
    run_all_samples(valid_codes_dict, client)
