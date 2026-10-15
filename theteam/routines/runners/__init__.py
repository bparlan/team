"""Phase runners. Layer 3 (§5.1): how one phase actually executes.

`llm` is the second kind beside the default script runner. It is imported by
name at the call site in `routines/executor.py`, not re-exported here, so this
package stays a namespace rather than a place where import order decides
whether an `llm` phase is available.
"""
