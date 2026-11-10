# promisekept

Check that the promises in your rebuttal actually made it into the revised paper.

During author response you write things like "we will add a threat model paragraph" or "Table 3 will report latency overhead". Weeks later, under a camera-ready deadline, some of those promises quietly get lost. Reviewers and meta-reviewers do check. `promisekept` reads the rebuttal, pulls out every commitment, and looks for evidence of each one in the text you **added** to the LaTeX source.

## What's novel

Existing tools diff LaTeX (latexdiff) or lint it (chktex). None of them connect the response-to-reviewers document to the revision. `promisekept`:

- extracts commitments from free-form rebuttal prose ("we will", "will be added", "in the revised version", "we have now added", ...) and attributes them to Reviewer 1/R2/meta-review headings;
- turns each promise into stemmed key terms, quoted phrases (weighted 3x), and structural refs (Table 3, Section 4);
- **diff-aware**: with `--old`, it only credits text that is new or changed since the submitted version, so it can tell a promise that was really kept from one that was already in the paper (`preexisting`, often a sign the rebuttal promised nothing new, or that the "addition" was never written);
- points at the best evidence line (`file:line`) for each promise, works on a single `.tex` or a whole project directory, and gives a CI gate with `--fail-on`.

Statuses: `kept`, `preexisting`, `partial`, `missing`.

Pure Python standard library, fully offline. Nothing leaves your machine.

## Install

```bash
pip install git+https://github.com/rashedhasan090/promisekept
# or run from a clone
python -m promisekept --help
```

## Usage

```bash
promisekept rebuttal.md paper/ --old submitted/            # diff-aware
promisekept rebuttal.txt main.tex                          # no baseline, whole paper counts
promisekept rebuttal.md paper/ --old submitted/ --format md > promises.md
promisekept rebuttal.md paper/ --old submitted/ --fail-on missing   # exit 1 in CI
```

Options: `--format text|json|md`, `--only-problems`, `--kept 0.6`, `--partial 0.3` (coverage thresholds), `--fail-on missing|partial|preexisting|never`.

## Demo

```bash
python -m promisekept examples/rebuttal.md examples/revised.tex --old examples/submitted.tex
```

```
[MISS] P3 (R2, rebuttal line 6) coverage 0%
       promise: The comparison with "ToolSentry" will be included in the related work.
       not found: comparison, relat, "ToolSentry"
[MISS] P4 (R2, rebuttal line 7) coverage 0%
       promise: We will discuss false positives caused by benign redirects in the limitations section.
       not found: false, positiv, caus, benign, redirect, limit
[OLD ] P5 (R3, rebuttal line 10) coverage 100%
       promise: We will clarify that the evaluation uses 412 real MCP servers collected from public registries.
       best evidence revised.tex:6: Our evaluation uses 412 real MCP servers collected from public registries.
[OK  ] P1 (R1, rebuttal line 2) coverage 75%
       promise: We will add a threat model paragraph describing the attacker capabilities and trust boundaries.
       best evidence revised.tex:4: The attacker controls tool descriptions; we state attacker capabilities and the trust boundaries between host and server.
[OK  ] P2 (R1, rebuttal line 3) coverage 100%
       promise: In the revised version, Table 3 will report latency overhead for each benchmark.
       best evidence revised.tex:7: Table reports latency overhead per benchmark.
5 promises: 2 kept, 1 preexisting, 0 partial, 2 missing
```

## Limits

It is lexical, not semantic: a promise fulfilled with entirely different wording can show as `partial` or `missing`, and a coincidental word match can over-credit. Treat it as a checklist that points you at the right lines, not a verdict.

## Tests

```bash
python -m unittest discover -s tests -v
```

## License

MIT
