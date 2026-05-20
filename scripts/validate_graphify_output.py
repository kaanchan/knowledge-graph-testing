"""
validate_graphify_output.py — Validate graphify JSON output against the success gate.

Success gate (from spec §Step 1):
  - All node IDs match regex ^[a-z0-9_]+$
  - confidence field on every edge is one of: EXTRACTED | INFERRED | AMBIGUOUS
  - edge count > 0 across the full output
  - Flag nodes with empty label

GH issue: #3 (ref #8)

USAGE:
    python scripts/validate_graphify_output.py --input <path-to-graphify-output.json>

    Example:
        python scripts/validate_graphify_output.py --input graphify-output.json
"""

import json
import re
import argparse
import sys
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

NODE_ID_REGEX      = re.compile(r"^[a-z0-9_]+$")
VALID_CONFIDENCE   = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
VALID_FILE_TYPES   = {"code", "document", "paper", "image", "rationale", "concept"}
VALID_RELATIONS    = {
    "calls", "implements", "references", "cites",
    "conceptually_related_to", "shares_data_with", "semantically_similar_to"
}


# ── Validators ────────────────────────────────────────────────────────────────

def validate(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Validate a graphify output dict.

    Returns:
        (passed: bool, errors: list[str], warnings: list[str])
    """
    errors:   list[str] = []
    warnings: list[str] = []

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # ── Node checks ───────────────────────────────────────────────────────────
    node_ids: set[str] = set()

    for i, node in enumerate(nodes):
        nid = node.get("id", "")

        # ID format
        if not nid:
            errors.append(f"Node[{i}]: missing 'id' field")
        elif not NODE_ID_REGEX.match(nid):
            errors.append(
                f"Node[{i}] id='{nid}': FAILS regex ^[a-z0-9_]+$ — "
                "must be lowercase, no hyphens or dots"
            )
        else:
            if nid in node_ids:
                warnings.append(f"Node[{i}] id='{nid}': duplicate node ID")
            node_ids.add(nid)

        # Empty label warning
        label = node.get("label", "")
        if not label or not label.strip():
            warnings.append(f"Node[{i}] id='{nid}': empty 'label' field — flag for review")

        # file_type check (informational)
        ft = node.get("file_type", "")
        if ft and ft not in VALID_FILE_TYPES:
            warnings.append(f"Node[{i}] id='{nid}': unexpected file_type='{ft}'")

    # ── Edge checks ───────────────────────────────────────────────────────────
    if len(edges) == 0:
        errors.append("CRITICAL: edge count = 0 — SUCCESS GATE FAILED. No relationships extracted.")

    for i, edge in enumerate(edges):
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        conf = edge.get("confidence", "")

        # Confidence enum
        if not conf:
            errors.append(f"Edge[{i}] {src}->{tgt}: missing 'confidence' field")
        elif conf not in VALID_CONFIDENCE:
            errors.append(
                f"Edge[{i}] {src}->{tgt}: confidence='{conf}' is not one of "
                f"{sorted(VALID_CONFIDENCE)}"
            )

        # Source/target must exist as node IDs
        if src and src not in node_ids:
            warnings.append(f"Edge[{i}]: source='{src}' not found in node IDs")
        if tgt and tgt not in node_ids:
            warnings.append(f"Edge[{i}]: target='{tgt}' not found in node IDs")

        # Relation type check (informational)
        rel = edge.get("relation", "")
        if rel and rel not in VALID_RELATIONS:
            warnings.append(f"Edge[{i}] {src}->{tgt}: unexpected relation='{rel}'")

    passed = len(errors) == 0
    return passed, errors, warnings


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Validate graphify output JSON against the Step 1 success gate (GH #3 ref #8)"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to graphify output JSON file"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"ERROR: File not found: {input_path}")

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: Invalid JSON in {input_path}: {e}")

    # The graphify output may be a list of per-file records or a single dict
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = [data]
    else:
        sys.exit(f"ERROR: Unexpected JSON structure — expected dict or list, got {type(data)}")

    print(f"Validating: {input_path}")
    print(f"Records to validate: {len(records)}")
    print()

    all_errors:   list[str] = []
    all_warnings: list[str] = []
    all_passed = True

    for i, record in enumerate(records):
        src = record.get("source_file", f"record[{i}]")
        passed, errors, warnings = validate(record)

        status = "PASS" if passed else "FAIL"
        color  = "\033[32m" if passed else "\033[31m"
        reset  = "\033[0m"

        n_nodes = len(record.get("nodes", []))
        n_edges = len(record.get("edges", []))
        print(f"{color}[{status}]{reset} {src}  ({n_nodes} nodes, {n_edges} edges)")

        for err in errors:
            print(f"       ERROR:   {err}")
            all_errors.append(f"[{src}] {err}")

        for warn in warnings:
            print(f"       WARNING: {warn}")
            all_warnings.append(f"[{src}] {warn}")

        if not passed:
            all_passed = False

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    if all_passed:
        print("\033[32mOVERALL: PASS — Success gate met.\033[0m")
    else:
        print("\033[31mOVERALL: FAIL — Success gate NOT met.\033[0m")
        print("  -> Proceed to Step 2 (GBNF grammar fallback)")

    print(f"  Total records: {len(records)}")
    print(f"  Errors:        {len(all_errors)}")
    print(f"  Warnings:      {len(all_warnings)}")
    print("=" * 60)

    if all_errors:
        print()
        print("All errors:")
        for e in all_errors:
            print(f"  {e}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
