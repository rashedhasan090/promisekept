import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from promisekept.core import extract_promises, check, strip_latex, stem  # noqa: E402

EX = os.path.join(ROOT, "examples")


def read(p):
    with open(p) as f:
        return f.read()


class TestExtract(unittest.TestCase):
    def test_finds_commitments_and_reviewers(self):
        ps = extract_promises(read(os.path.join(EX, "rebuttal.md")))
        self.assertEqual(len(ps), 5)
        self.assertEqual([p.reviewer for p in ps], ["R1", "R1", "R2", "R2", "R3"])

    def test_quoted_phrase_and_refs(self):
        ps = extract_promises(read(os.path.join(EX, "rebuttal.md")))
        self.assertIn("ToolSentry", ps[2].phrases)
        self.assertIn("table 3", ps[1].refs)

    def test_ignores_non_commitments(self):
        self.assertEqual(extract_promises("We thank the reviewer for the kind words."), [])

    def test_stem(self):
        self.assertEqual(stem("boundaries"), stem("boundary"))
        self.assertEqual(stem("benchmarks"), "benchmark")


class TestCheck(unittest.TestCase):
    def setUp(self):
        self.f = check(read(os.path.join(EX, "rebuttal.md")),
                       os.path.join(EX, "revised.tex"), os.path.join(EX, "submitted.tex"))
        self.by = {f.promise.id: f.status for f in self.f}

    def test_statuses(self):
        self.assertEqual(self.by["P1"], "kept")       # threat model added
        self.assertEqual(self.by["P2"], "kept")       # latency table added
        self.assertEqual(self.by["P3"], "missing")    # ToolSentry never cited
        self.assertEqual(self.by["P4"], "missing")    # limitations never written
        self.assertEqual(self.by["P5"], "preexisting")  # already said in submission

    def test_without_old(self):
        f = check(read(os.path.join(EX, "rebuttal.md")), os.path.join(EX, "revised.tex"))
        st = {x.promise.id: x.status for x in f}
        self.assertEqual(st["P5"], "kept")
        self.assertNotIn("preexisting", st.values())

    def test_evidence_location(self):
        p1 = [f for f in self.f if f.promise.id == "P1"][0]
        self.assertTrue(p1.location.startswith("revised.tex:"))

    def test_strip_latex(self):
        self.assertNotIn("\\", strip_latex(r"\textbf{Hi} \cite{x} % comment"))
        self.assertNotIn("comment", strip_latex(r"text % comment"))

    def test_directory_input(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sec"))
            with open(os.path.join(d, "sec", "a.tex"), "w") as fh:
                fh.write("We compare against ToolSentry in related work.\n")
            f = check('Comparison with "ToolSentry" will be included in related work.', d)
            self.assertEqual(f[0].status, "kept")
            self.assertTrue(f[0].location.startswith(os.path.join("sec", "a.tex")))


class TestCLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "promisekept", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_json_and_fail_on(self):
        r = self.run_cli(os.path.join(EX, "rebuttal.md"), os.path.join(EX, "revised.tex"),
                         "--old", os.path.join(EX, "submitted.tex"), "--format", "json", "--fail-on", "missing")
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(len(data), 5)

    def test_md_and_pass(self):
        r = self.run_cli(os.path.join(EX, "rebuttal.md"), os.path.join(EX, "revised.tex"), "--format", "md")
        self.assertEqual(r.returncode, 0)
        self.assertIn("| id |", r.stdout)


if __name__ == "__main__":
    unittest.main()
