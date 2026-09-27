"""
The dashboard package.

Reflex launches from `web_dashboard/`, where the repo root is not on
`sys.path`, so `theteam.*` absolute imports need it. Walking up to the
containing `theteam/` package finds it at any nesting depth; a fixed number of
parent hops only works at the depth it was written for.
"""

import sys
from pathlib import Path


def _ensure_repo_root_on_path() -> None:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "theteam" / "__init__.py").exists():
            root = str(candidate)
            if root not in sys.path:
                sys.path.insert(0, root)
            return


_ensure_repo_root_on_path()
