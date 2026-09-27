#!/usr/bin/env python3
"""
Ledger Compaction Script

Compacts the system-awareness-ledger.json by:
1. Keeping only the last N entries (default 50)
2. Aggregating older entries into a summary section
3. Trimming oversized current_analysis fields
4. Producing a compacted version suitable for agent context

Usage:
    python3 scripts/compact_ledger.py [--keep 50] [--output .mp/theteam/ledger-compacted.json]
"""
import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path


def trim_large_field(val, max_bytes: int = 5000):
    """Trim a list or dict to fit within max_bytes."""
    if isinstance(val, list):
        trimmed = []
        for item in val:
            trimmed.append(item)
            if len(json.dumps(trimmed)) > max_bytes:
                trimmed = trimmed[:-1]
                trimmed.append({"_trimmed": f"... {len(val) - len(trimmed) + 1} more items"})
                break
        return trimmed
    elif isinstance(val, dict):
        keys = list(val.keys())
        trimmed = {}
        for k in keys:
            trimmed[k] = val[k]
            if len(json.dumps(trimmed)) > max_bytes:
                del trimmed[k]
                trimmed["_trimmed"] = f"... {len(keys) - len(trimmed) + 1} more keys"
                break
        return trimmed
    return val


def compact_ledger(ledger_path: str, output_path: str, keep_last: int = 50) -> dict:
    """Compact a large ledger file (dict with analysis_history list)."""
    with open(ledger_path, "r") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return {"error": "Ledger is not a dict", "type": type(data).__name__}

    history = data.get("analysis_history", [])
    if not isinstance(history, list):
        return {"error": "analysis_history is not a list"}

    total = len(history)
    if total <= keep_last:
        return {"error": "Ledger already small enough", "entries": total}

    recent = history[-keep_last:]
    older = history[:-keep_last]

    # Aggregate older entries
    agg = dict(data)
    agg["compacted"] = True
    agg["original_history_entries"] = total
    agg["kept_history_entries"] = keep_last
    agg["compacted_at"] = datetime.now(timezone.utc).isoformat()
    agg["older_summary"] = {
        "count": len(older),
        "date_range": {
            "first": older[0].get("timestamp") if older else None,
            "last": older[-1].get("timestamp") if older else None,
        },
        "health_scores": [e.get("health_score") for e in older if "health_score" in e],
        "entries_with_score": sum(1 for e in older if "health_score" in e),
    }
    agg["analysis_history"] = recent

    # Trim current_analysis if too large
    current = agg.get("current_analysis", {})
    if isinstance(current, dict):
        for key in ("project_structure", "documentation"):
            val = current.get(key)
            if isinstance(val, (list, dict)):
                current[key] = trim_large_field(val)
        agg["current_analysis"] = current

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(agg, f, indent=2)

    original_size = Path(ledger_path).stat().st_size
    compacted_size = out.stat().st_size
    print(f"Compacted: {total} entries -> {keep_last} recent + summary")
    print(f"Size: {original_size} -> {compacted_size} bytes ({100 * compacted_size / original_size:.1f}%)")

    return agg


def main():
    parser = argparse.ArgumentParser(description="Compact system awareness ledger")
    parser.add_argument("--ledger", default=".mp/theteam/ledger.json")
    parser.add_argument("--output", default=".mp/theteam/ledger-compacted.json")
    parser.add_argument("--keep", type=int, default=50)
    parser.add_argument("--inplace", action="store_true",
                        help="Compact in place (backup original to .bak)")
    args = parser.parse_args()

    output = args.ledger if args.inplace else args.output
    result = compact_ledger(args.ledger, output, args.keep)
    if "error" in result:
        print(f"Note: {result['error']}")
        sys.exit(0)

    if args.inplace:
        backup = Path(args.ledger).with_suffix(args.ledger.suffix + ".bak")
        import shutil
        shutil.copy2(output, backup)
        print(f"Backup: {backup}")