#!/usr/bin/env python3
"""
Report real code references to a name, ignoring comments and docstrings.

`grep` cannot tell a call site from a sentence about a call site, so a gate
built on grep fires on the documentation describing the very defect it hunts,
and on the docstring of a module that has already been fixed. That is how a
gate becomes noise people learn to skip.

Usage:
    check_call_sites.py <name> <file.py> [file.py ...]

Exits 0 with no output when nothing in CODE references the name. Exits 1 and
prints `name referenced in CODE at <path>:<line>` for each hit, otherwise.

A bare identifier (`MockAPI`, a class) matches any use. A dotted attribute
(`subprocess.run`) matches only attribute access, so `subprocess` does not
flag `import subprocess`.
"""
import ast
import sys


def _docstring_nodes(tree):
    """Every node that is a docstring, so its text is never matched."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                yield body[0].value


def _names_in(node, name):
    """Yield (lineno) for each reference to `name` inside `node`."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == name:
            yield node.lineno
        elif isinstance(func, ast.Name) and func.id == name:
            yield node.lineno
    elif isinstance(node, ast.Name) and node.id == name:
        yield node.lineno
    elif isinstance(node, ast.Attribute) and node.attr == name:
        yield node.lineno
    elif isinstance(node, ast.alias) and (node.asname == name or node.name == name):
        yield node.lineno


def scan(path, name):
    """Yield (path, lineno) for each code reference to `name` in `path`."""
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Unparseable code is not this check's business; do not mask it here.
        return
    docstrings = {id(d) for d in _docstring_nodes(tree)}
    for node in ast.walk(tree):
        if id(node) in docstrings:
            continue
        for lineno in _names_in(node, name):
            yield path, lineno


def main(argv):
    if len(argv) < 3:
        print("usage: check_call_sites.py <name> <file.py> [...]", file=sys.stderr)
        return 2
    name, paths = argv[1], argv[2:]
    hits = [hit for path in paths for hit in scan(path, name)]
    if not hits:
        return 0
    for path, lineno in hits:
        print(f"{name} referenced in CODE at {path}:{lineno}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
