"""Command line interface for promisekept."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core import check

ORDER = {"kept": 0, "preexisting": 1, "partial": 2, "missing": 3}
ICON = {"kept": "OK  ", "preexisting": "OLD ", "partial": "PART", "missing": "MISS"}


def render_text(findings, show_kept=True):
    lines = []
    for f in findings:
        if not show_kept and f.status == "kept":
            continue
        p = f.promise
        lines.append(f"[{ICON[f.status]}] {p.id} ({p.reviewer}, rebuttal line {p.line}) coverage {f.coverage:.0%}")
        lines.append(f"       promise: {p.text}")
        if f.location:
            lines.append(f"       best evidence {f.location}: {f.evidence}")
        if f.unmatched and f.status != "kept":
            lines.append(f"       not found: {', '.join(f.unmatched)}")
    lines.append(summary(findings))
    return "\n".join(lines)


def summary(findings):
    c = {k: 0 for k in ORDER}
    for f in findings:
        c[f.status] += 1
    return (f"{len(findings)} promises: {c['kept']} kept, {c['preexisting']} preexisting, "
            f"{c['partial']} partial, {c['missing']} missing")


def render_md(findings):
    out = ["| id | reviewer | status | coverage | promise | evidence |", "|---|---|---|---|---|---|"]
    for f in findings:
        p = f.promise
        esc = lambda s: s.replace("|", "\\|")
        out.append(f"| {p.id} | {p.reviewer} | {f.status} | {f.coverage:.0%} | {esc(p.text)} | {esc(f.location)} |")
    out.append("")
    out.append(summary(findings))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="promisekept",
        description="Check that what your rebuttal promised actually landed in the revised LaTeX.")
    ap.add_argument("rebuttal", help="rebuttal / response-to-reviewers text or markdown file")
    ap.add_argument("new", help="revised LaTeX file or directory")
    ap.add_argument("--old", help="submitted (pre-rebuttal) LaTeX file or directory; enables diff-aware checks")
    ap.add_argument("--format", choices=["text", "json", "md"], default="text")
    ap.add_argument("--only-problems", action="store_true", help="hide kept promises in text output")
    ap.add_argument("--kept", type=float, default=0.6, help="coverage threshold for kept (default 0.6)")
    ap.add_argument("--partial", type=float, default=0.3, help="coverage threshold for partial (default 0.3)")
    ap.add_argument("--fail-on", choices=["missing", "partial", "preexisting", "never"], default="never",
                    help="exit 1 if any promise is at or worse than this status")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    with open(a.rebuttal, encoding="utf-8", errors="replace") as fh:
        reb = fh.read()
    findings = check(reb, a.new, a.old, a.kept, a.partial)
    findings.sort(key=lambda f: (-ORDER[f.status], f.promise.id))
    if a.format == "json":
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    elif a.format == "md":
        print(render_md(findings))
    else:
        print(render_text(findings, not a.only_problems))
    if a.fail_on != "never":
        limit = {"preexisting": 1, "partial": 2, "missing": 3}[a.fail_on]
        if any(ORDER[f.status] >= limit for f in findings):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
