"""Core logic: extract promises from a rebuttal, find evidence in a LaTeX revision."""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass, field, asdict

COMMIT_RE = re.compile(
    r"\b(we\s+will|we'll|we\s+shall|we\s+plan\s+to|we\s+intend\s+to|we\s+are\s+going\s+to|"
    r"will\s+be\s+(added|included|clarified|expanded|revised|discussed|moved|fixed|corrected|updated|released|extended|reported|cited|shortened|removed)|"
    r"in\s+the\s+(revised|final|camera[- ]ready|next)\s+(version|draft|manuscript|paper)|"
    r"we\s+have\s+(now\s+)?(added|included|clarified|expanded|revised|fixed|corrected|updated|moved|removed)|"
    r"we\s+(now\s+)?(add|include|clarify|expand)\b)",
    re.I,
)
REVIEWER_RE = re.compile(r"^\s*(?:#+\s*|\*\*)?\s*(reviewer\s*#?\s*([A-Za-z0-9]+)|R([0-9]+)\b|meta[- ]?review(?:er)?)", re.I)
QUOTE_RE = re.compile(r"[\"\u201c]([^\"\u201d]{3,80})[\"\u201d]")
REF_RE = re.compile(r"\b(section|sec\.|table|figure|fig\.|appendix|algorithm|eq\.|equation|theorem|lemma)\s*~?\s*([A-Z]?\d+(?:\.\d+)*|[A-Z])\b", re.I)

STOP = set("""
a an the and or but if then than that this these those to of in on for with by from as at into onto
is are was were be been being it its we our us you your they their them he she his her i me my
will shall would should could can may might must also more most very much many such both each
not no nor so too just only own same other some any all few further once here there when where why
how what which who whom whose do does did doing have has had having about above below after before
between during through under over again against up down out off now new add added adding include
included including clarify clarified expand expanded revise revised version final paper manuscript
camera ready draft next plan intend going section table figure appendix thank thanks reviewer
point comment comments concern concerns suggestion suggest suggested agree indeed address addressed
make made discuss discussed discussion explicitly detail details detailed better further clearly
moreover however furthermore additionally regarding following note please work text
""".split())


def stem(w: str) -> str:
    w = w.lower()
    for suf in ("ization", "ations", "ation", "ments", "ment", "ness", "ings", "ing", "ies", "ied", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
    return w


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9]|[A-Za-z]", text)


@dataclass
class Promise:
    id: str
    reviewer: str
    line: int
    text: str
    keywords: list[str]
    phrases: list[str]
    refs: list[str]


@dataclass
class Finding:
    promise: Promise
    status: str  # kept | partial | preexisting | missing
    coverage: float
    matched: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    evidence: str = ""
    location: str = ""

    def to_dict(self):
        d = asdict(self)
        d["coverage"] = round(self.coverage, 2)
        return d


def split_sentences(text: str):
    """Yield (line_no, sentence) for prose text, keeping reviewer headings separate."""
    out = []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"\u201c(])", line):
            if s.strip():
                out.append((i, s.strip()))
    return out


def extract_promises(rebuttal: str) -> list[Promise]:
    promises: list[Promise] = []
    reviewer = "-"
    for line_no, sent in split_sentences(rebuttal):
        m = REVIEWER_RE.match(sent)
        if m:
            tag = m.group(2) or m.group(3)
            reviewer = f"R{tag}" if tag else "Meta"
        if not COMMIT_RE.search(sent):
            continue
        phrases = [p.strip() for p in QUOTE_RE.findall(sent)]
        refs = [f"{a.rstrip('.').lower()} {b}" for a, b in REF_RE.findall(sent)]
        body = QUOTE_RE.sub(" ", sent)
        body = REF_RE.sub(" ", body)
        kws: list[str] = []
        for w in words(body):
            lw = w.lower()
            if lw in STOP or len(lw) < 3 or lw.isdigit():
                continue
            if lw.startswith("reviewer") or re.fullmatch(r"r\d+", lw):
                continue
            s = stem(lw)
            if s not in kws and lw not in STOP:
                kws.append(s)
        if not kws and not phrases:
            continue
        promises.append(Promise(f"P{len(promises)+1}", reviewer, line_no, sent, kws, phrases, refs))
    return promises


# ---------- LaTeX handling ----------

def strip_latex(src: str) -> str:
    src = re.sub(r"(?<!\\)%.*", "", src)
    src = re.sub(r"\\(cite[tp]?|ref|eqref|label|autoref|cref|Cref|input|include|usepackage|documentclass)\*?(\[[^\]]*\])?\{[^}]*\}", " ", src)
    src = re.sub(r"\\begin\{[^}]*\}|\\end\{[^}]*\}", " ", src)
    src = re.sub(r"\\[A-Za-z]+\*?(\[[^\]]*\])?", " ", src)
    src = re.sub(r"[{}$~^_&\\]", " ", src)
    return re.sub(r"[ \t]+", " ", src)


def load_tex(path: str) -> list[tuple[str, int, str]]:
    """Return list of (file, line, text) units (paragraph lines) from a file or directory."""
    files = []
    if os.path.isdir(path):
        for root, _, names in os.walk(path):
            for n in sorted(names):
                if n.endswith(".tex"):
                    files.append(os.path.join(root, n))
    else:
        files.append(path)
    units = []
    base = path if os.path.isdir(path) else os.path.dirname(path)
    for f in sorted(files):
        with open(f, encoding="utf-8", errors="replace") as fh:
            rel = os.path.relpath(f, base) if base else f
            for i, line in enumerate(fh.read().splitlines(), 1):
                if line.strip():
                    units.append((rel, i, line))
    return units


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def added_units(old_units, new_units):
    """Lines of the new revision that are new or changed relative to the old one."""
    if old_units is None:
        return list(new_units)
    a = [norm(u[2]) for u in old_units]
    b = [norm(u[2]) for u in new_units]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            out.extend(new_units[j1:j2])
    return out


def _bag(text: str) -> set[str]:
    return {stem(w.lower()) for w in words(text)}


def _ref_hits(refs, raw_text):
    hits = []
    low = raw_text.lower()
    for r in refs:
        kind, num = r.split(" ", 1)
        if kind in ("appendix",) and re.search(r"\\appendix|appendix", low):
            hits.append(r)
        elif num.lower() in low and kind[:3] in low:
            hits.append(r)
    return hits


def score(promise: Promise, units) -> tuple[float, list[str], list[str], str, str]:
    """Coverage of promise terms across the given units, plus best evidence line."""
    if not units:
        return 0.0, [], promise.keywords + promise.phrases, "", ""
    plain = [(f, ln, strip_latex(t), t) for f, ln, t in units]
    bag = set()
    joined = []
    for _, _, p, _ in plain:
        bag |= _bag(p)
        joined.append(p.lower())
    corpus = " ".join(joined)
    matched, unmatched = [], []
    for k in promise.keywords:
        (matched if k in bag else unmatched).append(k)
    for ph in promise.phrases:
        (matched if norm(ph) in norm(corpus) else unmatched).append(f'"{ph}"')
    # phrases weigh 3x
    total = len(promise.keywords) + 3 * len(promise.phrases)
    got = sum(1 for m in matched if not m.startswith('"')) + 3 * sum(1 for m in matched if m.startswith('"'))
    cov = got / total if total else 0.0
    best, best_s = None, 0
    want = set(promise.keywords)
    for f, ln, p, raw in plain:
        s = len(want & _bag(p)) + 3 * sum(1 for ph in promise.phrases if norm(ph) in norm(p))
        if s > best_s:
            best, best_s = (f, ln, p.strip()), s
    ev, loc = ("", "")
    if best:
        ev = best[2][:160]
        loc = f"{best[0]}:{best[1]}"
    return cov, matched, unmatched, ev, loc


def check(rebuttal: str, new_path: str, old_path: str | None = None,
          kept: float = 0.6, partial: float = 0.3) -> list[Finding]:
    promises = extract_promises(rebuttal)
    new_units = load_tex(new_path)
    old_units = load_tex(old_path) if old_path else None
    delta = added_units(old_units, new_units)
    findings = []
    for p in promises:
        cov, m, um, ev, loc = score(p, delta)
        status = "kept" if cov >= kept else "partial" if cov >= partial else "missing"
        if status != "kept" and old_units is not None:
            cov_all, m2, um2, ev2, loc2 = score(p, new_units)
            if cov_all >= kept:
                status, cov, m, um, ev, loc = "preexisting", cov_all, m2, um2, ev2, loc2
        findings.append(Finding(p, status, cov, m, um, ev, loc))
    return findings
