#!/usr/bin/env python3
"""ARCHITECTURE.md §7.2 invariant 7: the import graph of the package entry point.

The other six checks in `check_invariants.sh` are greps and AST scans over
source text. None of them can see what a module *loads* when it is imported,
which is why a defect worth 62 modules shipped through all six: `theteam/
__init__.py` re-exported 41 stability symbols it never used, `core/__init__.py`
re-exported the PostgreSQL cluster layer, and `core/database.py` imported that
layer eagerly. Any one `import theteam` therefore pulled a database tier with
connection pooling, failover and read replicas - none of which §5.1 places in
this stack, and none of which any product command reaches.

This check measures the real thing: import the package in a clean interpreter,
count what arrived, and name the offenders. It is a measurement, not a grep,
so it cannot be satisfied by a comment or defeated by a docstring.

Budgets are set from the measured floor, not from taste. The package must be
importable by a user who has no PostgreSQL server, no OMP session, and no
optional extras installed; anything above these numbers means a module is being
loaded for a caller that does not exist.

Usage: check_import_graph.py [max_total] [max_core]
Exits 0 when within budget, 1 otherwise.
"""
import sys

# Modules that are legitimate on the entry point's path: state persistence the
# discussion path actually uses. `wal` and `transactions` are here because
# `UnifiedStateManager.__init__` constructs both, and that class is live.
ALLOWED_CORE = {
    "theteam.core.state_manager",
    "theteam.core.wal",
    "theteam.core.transactions",
    "theteam.core.checksum",
    "theteam.core.correlation",
    "theteam.core.database",
    "theteam.core.member",
    "theteam.core.event_bus",
}

# Anything matching these is a database/cluster tier. §5.1 has no such layer.
FORBIDDEN = ("postgres_cluster",)


def main() -> int:
    max_total = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    max_core = int(sys.argv[2]) if len(sys.argv) > 2 else 8

    sys.path.insert(0, ".")
    before = set(sys.modules)
    import theteam  # noqa: F401  - the import is the measurement
    loaded = set(sys.modules) - before

    total = len(loaded)
    core = sorted(m for m in loaded if m.startswith("theteam.core."))
    cluster = sorted(m for m in loaded
                     if any(tok in m for tok in FORBIDDEN))

    print(f"modules loaded by 'import theteam': {total} (budget {max_total})")
    print(f"theteam.core.* loaded: {len(core)} (budget {max_core})")
    for m in core:
        print(f"    {m}")

    if cluster:
        print(f"FAIL: database/cluster tier on the entry point: {cluster}")
        print("      §5.1 places no PostgreSQL layer in this stack. It must be")
        print("      imported at the point of use, not by a package __init__.")
        return 1

    unexpected = [m for m in core if m not in ALLOWED_CORE]
    if unexpected:
        print(f"FAIL: unexpected theteam.core.* on the entry point: {unexpected}")
        print("      Add to ALLOWED_CORE only if a live caller genuinely needs it,")
        print("      and say which caller in the comment above.")
        return 1

    if total > max_total or len(core) > max_core:
        print("FAIL: import graph over budget. Something re-exported for")
        print("      reachability is being loaded eagerly again.")
        return 1

    print("PASS: import graph within budget, no cluster tier loaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
