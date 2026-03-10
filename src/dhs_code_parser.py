import re
import json
import csv
import os


CODE_LINE_RE = re.compile(r'^\s*([A-Z0-9]{4,5}[A-Z]?|[A-Z]\d{4})\s+(.+?)\s*$')

def normalize_cpt_code(raw_code: str) -> str:
    code = str(raw_code).strip().upper()
    if not code:
        return ""
    if code.isdigit():
        return code.zfill(5)
    return code


def parse_cpt_txt_to_dict(txt_path: str) -> dict[str, str]:
    code_dict = {}

    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = " ".join(raw_line.strip().split())
            if not line:
                continue

            match = CODE_LINE_RE.match(line)
            if not match:
                continue

            code, description = match.groups()
            code = normalize_cpt_code(code)

            if description.lower().startswith("any future"):
                continue

            code_dict[code.strip()] = description.strip()

    return code_dict


def parse_cpt_csv_to_dict(csv_path: str) -> dict[str, str]:
    code_dict = {}

    with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_code = row.get("CPT Code", "")
            raw_description = row.get("Description", "")
            code = normalize_cpt_code(raw_code)
            description = str(raw_description).strip()

            if not code or not description:
                continue

            code_dict[code] = description

    return code_dict


def save_code_dict_as_json(txt_path: str, csv_path: str, json_path: str) -> dict[str, str]:
    txt_dict = parse_cpt_txt_to_dict(txt_path)
    code_dict = dict(txt_dict)
    csv_dict = parse_cpt_csv_to_dict(csv_path)
    merged_count = 0

    for code, description in csv_dict.items():
        if code not in code_dict:
            merged_count += 1
        code_dict[code] = description

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(code_dict, f, indent=2, ensure_ascii=False)

    print(f"Loaded {len(txt_dict)} codes from DHS txt.")
    print(f"Loaded {len(csv_dict)} codes from deduped csv.")
    print(f"Added/updated {merged_count} codes from deduped csv.")
    return code_dict


if __name__ == "__main__":
    txt_file = "data/2026_DHS_Code_List_Addendum_12_01_2025 (2).txt"
    csv_file = "data/cpt_codes_deduped - cpt_codes_deduped.csv"
    if not os.path.exists(csv_file):
        csv_file = "data/cpt_codes.csv"
    out_file = "data/cpt_code_dict.json"

    code_dict = save_code_dict_as_json(txt_file, csv_file, out_file)
    print(f"Saved {len(code_dict)} codes to {out_file}")
