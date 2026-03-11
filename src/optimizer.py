import json
from itertools import combinations
from typing import Any

from constraints import check_pair
from pricer import code_price


# Converts a raw price value into a float with safe defaults for missing/bad inputs.
def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text.lower() in {"none", "nan"}:
        return 0.0

    try:
        return float(text)
    except ValueError:
        return 0.0


# Looks up one CPT/HCPCS code's facility fee amount for a given locality/carrier.
def _facility_price_for_code(cpt_code: str, locality: str, carrier: str) -> float:
    result = code_price(cpt_code, locality, carrier)
    if result is None or result.empty:
        return 0.0

    value = result.iloc[0]["Facility Fee Schedule Amount"]
    return _to_float(value)


# Checks all code pairs in a subset and flags whether any codes require a modifier.
def _pairwise_status(subset_codes: tuple[str, ...]) -> tuple[bool, set[str]]:
    modifier_required_codes: set[str] = set()
    for code1, code2 in combinations(subset_codes, 2):
        pair_result = check_pair(code1, code2)
        if not pair_result.get("allowed", False):
            return False, set()
        if pair_result.get("modifier") not in (None, "", "0"):
            modifier_required_codes.add(code1)
            modifier_required_codes.add(code2)
    return True, modifier_required_codes


# Builds the structured JSON payload for one valid subset and its per-code status.
def _build_subset_payload(
    subset_codes: tuple[str, ...],
    modifier_required_codes: set[str],
    price_cache: dict[str, float],
) -> dict[str, Any]:
    total = sum(price_cache[code] for code in subset_codes)
    code_statuses = []
    for code in subset_codes:
        status = "valid_with_modifier" if code in modifier_required_codes else "valid"
        code_statuses.append({"cpt_code": code, "status": status})

    return {
        "codes": list(subset_codes),
        "total_reimbursement": round(total, 6),
        "requires_modifier": bool(modifier_required_codes),
        "code_statuses": code_statuses,
    }


# Applies selection ordering rules based on reimbursement and modifier requirements.
def _select_subsets_by_modifier_rule(valid_subsets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not valid_subsets:
        return []

    # Higher reimbursement first; tie-breaker prefers no-modifier subsets.
    ranked = sorted(
        valid_subsets,
        key=lambda row: (-float(row["total_reimbursement"]), bool(row["requires_modifier"])),
    )

    if not ranked[0]["requires_modifier"]:
        return [ranked[0]]

    selected = []
    for subset in ranked:
        selected.append(subset)
        if not subset["requires_modifier"]:
            break
    return selected


# Finds and returns highest-reimbursing valid subsets from parsed note code output.
def optimize_code_subsets(
    parsed_note_items: list[dict[str, Any]],
    locality: str = "00",
    carrier: str = "15202",
) -> dict[str, Any]:
    codes = []
    for item in parsed_note_items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("cpt_code", "")).strip()
        if code:
            codes.append(code)
    if not codes:
        return {"input_codes": [], "subsets": []}

    price_cache = {code: _facility_price_for_code(code, locality, carrier) for code in codes}

    valid_subsets: list[dict[str, Any]] = []
    for subset_size in range(1, len(codes) + 1):
        for subset_codes in combinations(codes, subset_size):
            allowed, modifier_required_codes = _pairwise_status(subset_codes)
            if not allowed:
                continue
            valid_subsets.append(
                _build_subset_payload(subset_codes, modifier_required_codes, price_cache)
            )

    return {
        "input_codes": codes,
        "subsets": _select_subsets_by_modifier_rule(valid_subsets),
    }


if __name__ == "__main__":
    # Optional local runner: pass parse_note output JSON (list of objects) on stdin.
    import sys

    try:
        parsed_items = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"error": "Expected JSON list from stdin."}, indent=2))
        raise SystemExit(1)

    if not isinstance(parsed_items, list):
        print(json.dumps({"error": "Expected a JSON list of parse_note items."}, indent=2))
        raise SystemExit(1)

    output = optimize_code_subsets(parsed_items)
    print(json.dumps(output, indent=2))
