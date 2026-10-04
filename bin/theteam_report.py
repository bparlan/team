#!/usr/bin/env python3
"""
theteam_report.py — assembles a discussion report from independent member
notes plus one synthesis pass. This script owns FORMATTING ONLY: it never
invents agreement, disagreement, or a recommendation. Those come from the
orchestrating agent's synthesis pass (synthesis.json) after every enabled
member has already filed independent notes. Keeping judgment out of this
script is deliberate — the mechanical part (structure, ordering, "did every
enabled member actually report in") should never silently drift from what
was really said.

Member note file (one JSON file per member, any filename, in --notes-dir):
    {
      "id": "architect",
      "role": "Systems Architect",
      "verdict": "one-line stance, e.g. 'Approve with changes'",
      "note": "full markdown body of this member's independent note"
    }

Synthesis file (--synthesis, one JSON file, written by the orchestrator
after reading all member notes):
    {
      "summary": "1-3 sentence framing of the topic and outcome",
      "agreements": ["point every/most members converged on", ...],
      "disagreements": ["point where members genuinely differed", ...],
      "open_questions": ["unresolved item needing a human decision", ...],
      "recommendation": "the team's single recommended next step, or
                          'No consensus — see disagreements' if there
                          genuinely isn't one. Never fabricate consensus."
    }

Usage:
    theteam_report.py build --topic "<topic>" --notes-dir <dir> \
        --synthesis <synthesis.json> --out <out.md> [--project "<name>"] \
        [--expected-ids id1,id2,id3]

Exit codes:
    0  success
    1  usage error
    2  input file missing / unreadable / not valid JSON
    3  integrity check failed (e.g. an expected member never filed notes)
"""
import sys
import os
import json
import glob
import html as _html
import re
from datetime import datetime, timezone

#: Inline markdown the HTML renderer restores after escaping. Applied in this
#: order: code first, so bold/italic/link never match inside a code span.
_re_code = re.compile(r"`([^`\n]+)`")
_re_bold = re.compile(r"\*\*([^*]+)\*\*")
_re_italic = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_re_link = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")


def _fatal(code, message):
    sys.stderr.write(f"FATAL: {message}\n")
    sys.exit(code)


def load_notes(notes_dir):
    if not os.path.isdir(notes_dir):
        _fatal(2, f"notes directory not found: {notes_dir}")
    paths = sorted(glob.glob(os.path.join(notes_dir, "*.json")))
    if not paths:
        _fatal(2, f"no *.json note files found in: {notes_dir}")
    notes = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                _fatal(2, f"note file is not valid JSON: {p}\n{e}")
        for key in ("id", "role", "verdict", "note"):
            if key not in data:
                _fatal(2, f"note file {p} is missing key: {key}")
        notes.append(data)
    notes.sort(key=lambda n: n["id"])
    return notes


def load_synthesis(path):
    if not os.path.isfile(path):
        _fatal(2, f"synthesis file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            _fatal(2, f"synthesis file is not valid JSON: {path}\n{e}")
    for key in ("summary", "agreements", "disagreements", "open_questions", "recommendation"):
        if key not in data:
            _fatal(2, f"synthesis file is missing key: {key}")
    return data


def render(topic, project, notes, synthesis):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = []
    lines.append(f"# theteam — {topic}")
    lines.append("")
    lines.append(f"- **Project:** {project or '(unspecified)'}")
    lines.append(f"- **Generated:** {now}")
    lines.append(f"- **Members reporting:** {', '.join(n['id'] for n in notes)}")
    lines.append("")
    lines.append("## Individual notes")
    lines.append("")
    lines.append(
        "Each member's note below was written independently, before the "
        "synthesis pass — no member has seen another's note."
    )
    lines.append("")
    for n in notes:
        lines.append(f"### {n['role']} (`{n['id']}`)")
        lines.append("")
        lines.append(f"**Verdict:** {n['verdict']}")
        lines.append("")
        lines.append(n["note"].strip())
        lines.append("")
    lines.append("## Consolidated report")
    lines.append("")
    lines.append(synthesis["summary"].strip())
    lines.append("")
    lines.append("**Where the team agreed:**")
    lines.append("")
    if synthesis["agreements"]:
        for a in synthesis["agreements"]:
            lines.append(f"- {a}")
    else:
        lines.append("- (no explicit agreement recorded)")
    lines.append("")
    lines.append("**Where the team disagreed:**")
    lines.append("")
    if synthesis["disagreements"]:
        for d in synthesis["disagreements"]:
            lines.append(f"- {d}")
    else:
        lines.append("- (no disagreement recorded)")
    lines.append("")
    lines.append("**Open questions for you:**")
    lines.append("")
    if synthesis["open_questions"]:
        for q in synthesis["open_questions"]:
            lines.append(f"- {q}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("**Recommendation:**")
    lines.append("")
    lines.append(synthesis["recommendation"].strip())
    lines.append("")
    return "\n".join(lines)




_CSS = """
:root{color-scheme:light dark}
body{margin:0 auto;max-width:52rem;padding:2rem 1.25rem;
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  color:#1a1a1a;background:#fff}
@media (prefers-color-scheme:dark){body{color:#e6e6e6;background:#16181c}}
h1{font-size:1.7rem;margin:0 0 .5rem}
h2{font-size:1.25rem;margin:2.5rem 0 .5rem;padding-bottom:.3rem;
  border-bottom:1px solid #d8d8d8}
@media (prefers-color-scheme:dark){h2{border-color:#3a3d42}}
h3{font-size:1.05rem;margin:1.75rem 0 .35rem}
.meta{color:#666;font-size:.9rem;margin:0 0 1.5rem}
@media (prefers-color-scheme:dark){.meta{color:#9aa0a6}}
.note{background:#f6f7f9;border-left:3px solid #b9bec7;border-radius:0 4px 4px 0;
  padding:.1rem 1rem;margin:1rem 0}
@media (prefers-color-scheme:dark){.note{background:#1e2126;border-left-color:#4a4f57}}
.verdict{font-weight:600;margin:.5rem 0}
.body{white-space:pre-wrap}
ul{padding-left:1.4rem}li{margin:.3rem 0}
strong{font-weight:600}
code{font:.9em ui-monospace,SFMono-Regular,Menlo,monospace;
  background:#eef0f3;padding:.1em .35em;border-radius:3px}
@media (prefers-color-scheme:dark){code{background:#252930}}
"""


def _md_inline(text):
    """Escape, then restore the inline markdown the notes actually use.

    Deliberately not a markdown parser: the contract is a human-readable
    report, and a full parser is the overengineering this repo already
    declined once. Bold, italic, code and links cover what members write.
    """
    s = _html.escape(text)
    s = _re_code.sub(lambda m: f"<code>{m.group(1)}</code>", s)
    s = _re_bold.sub(lambda m: f"<strong>{m.group(1)}</strong>", s)
    s = _re_italic.sub(lambda m: f"<em>{m.group(1)}</em>", s)
    s = _re_link.sub(lambda m: (
        f'<a href="{m.group(2)}">{m.group(1)}</a>'
        if m.group(2).startswith(("http://", "https://"))
        else f"<code>{m.group(1)}</code>"), s)
    return s


def _md_block(text):
    """Inline markdown plus fenced code and bullet lists, block level."""
    out = []
    in_code = False
    in_list = False
    for raw in text.splitlines():
        if raw.strip().startswith("```"):
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(_html.escape(raw))
            continue
        item = re.match(r"^\s*[-*]\s+(.*)$", raw)
        if item:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_md_inline(item.group(1))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if raw.strip():
            out.append(f'<p class="body">{_md_inline(raw)}</p>')
        else:
            out.append("<p class=\"body\">&nbsp;</p>")
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def _items(values, empty):
    if not values:
        return f"<ul><li>{_html.escape(empty)}</li></ul>"
    return "<ul>\n" + "\n".join(f"<li>{_md_inline(v)}</li>" for v in values) + "\n</ul>"


def render_html(topic, project, notes, synthesis, now=None):
    """HTML sibling of render(). Consumes the same notes and synthesis dicts.

    Never parses render()'s markdown output: the markdown renderer and this
    one would then be two definitions of the report, free to disagree.
    Self-contained by contract -- inline CSS, no scripts, no webfonts.
    """
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    members = ", ".join(n["id"] for n in notes)
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>theteam — {_html.escape(topic)}</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>theteam — {_html.escape(topic)}</h1>",
        '<p class="meta">'
        f"Project: {_html.escape(project or '(unspecified)')}<br>"
        f"Generated: {now}<br>"
        f"Members reporting: {_html.escape(members)}</p>",

        "<h2>Individual notes</h2>",
        "<p>Each member's note below was written independently, before the "
        "synthesis pass — no member has seen another's note.</p>",
    ]
    for n in notes:
        parts.append("<h3>" + f"{_html.escape(n['role'])} "
                     f"(<code>{_html.escape(n['id'])}</code>)</h3>")
        parts.append(f'<div class="note">'
                     f'<p class="verdict">Verdict: {_md_inline(n["verdict"])}</p>'
                     f"{_md_block(n['note'].strip())}</div>")

    parts += [
        "<h2>Consolidated report</h2>",
        _md_block(synthesis["summary"].strip()),
        "<h3>Where the team agreed</h3>",
        _items(synthesis["agreements"], "(no explicit agreement recorded)"),
        "<h3>Where the team disagreed</h3>",
        _items(synthesis["disagreements"], "(no disagreement recorded)"),
        "<h3>Open questions for you</h3>",
        _items(synthesis["open_questions"], "(none)"),
        "<h3>Recommendation</h3>",
        _md_block(synthesis["recommendation"].strip()),
        "</body></html>",
    ]
    return "\n".join(parts)


def derive_out_path(out_path, fmt):
    """One place decides the extension, so the filename cannot disagree with
    the format it holds. A caller passing --format html and an --out ending
    in .md gets .html rather than markdown written to an html name, and the
    markdown default keeps the .md path callers already pass unchanged.
    """
    wanted = {"markdown": ".md", "html": ".html"}[fmt]
    root, ext = os.path.splitext(out_path)
    if ext.lower() == wanted:
        return out_path
    if ext.lower() in (".md", ".markdown", ".html"):
        return root + wanted
    return out_path + wanted


def cmd_build(args):
    topic = None
    notes_dir = None
    synthesis_path = None
    out_path = None
    project = None
    expected_ids = None
    fmt = "markdown"

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--topic":
            topic = args[i + 1]; i += 2
        elif a == "--notes-dir":
            notes_dir = args[i + 1]; i += 2
        elif a == "--synthesis":
            synthesis_path = args[i + 1]; i += 2
        elif a == "--out":
            out_path = args[i + 1]; i += 2
        elif a == "--project":
            project = args[i + 1]; i += 2
        elif a == "--expected-ids":
            expected_ids = args[i + 1].split(","); i += 2
        elif a == "--format":
            fmt = args[i + 1]; i += 2
        else:
            _fatal(1, f"unrecognized argument: {a}")

    missing_args = [
        name for name, val in [
            ("--topic", topic), ("--notes-dir", notes_dir),
            ("--synthesis", synthesis_path), ("--out", out_path),
        ] if val is None
    ]
    if missing_args:
        sys.stderr.write(
            "usage: theteam_report.py build --topic <t> --notes-dir <d> "
            "--synthesis <f> --out <o> [--project <p>] [--format markdown|html] "
            "[--expected-ids a,b,c]\n"
        )
        sys.exit(1)
    if fmt not in ("markdown", "html"):
        _fatal(1, f"unknown --format: {fmt} (expected markdown or html)")

    notes = load_notes(notes_dir)
    synthesis = load_synthesis(synthesis_path)

    # The expected-ids gate runs for BOTH formats. It is what catches a
    # dropped subagent; making it format-conditional would let a report
    # silently omit a member's view whenever html was requested.
    if expected_ids:
        got_ids = {n["id"] for n in notes}
        missing = [e for e in expected_ids if e not in got_ids]
        if missing:
            _fatal(
                3,
                "integrity check failed — expected member(s) never filed notes: "
                f"{missing}. Refusing to render a report that silently drops a "
                "team member's view. Fix the notes directory or re-run the "
                "missing member's subagent.",
            )

    out_path = derive_out_path(out_path, fmt)
    report = (render(topic, project, notes, synthesis) if fmt == "markdown"
              else render_html(topic, project, notes, synthesis))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    if os.path.exists(out_path):
        _fatal(2, f"refusing to overwrite existing report: {out_path}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"OK: wrote report to {out_path}")


COMMANDS = {"build": cmd_build}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.stderr.write(f"usage: theteam_report.py <{'|'.join(COMMANDS)}> ...\n")
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
