"""Tests for the pull-request size gate.

Two kinds. The first runs the real script in a throwaway repository, because the
exit codes are the whole interface: 0, 1 and 2 mean three different things to a
workflow, and a threshold nobody has pinned at the boundary is one nobody knows
the direction of. The second checks the exclusions against *this* repository and
asks each path's owner where it lives rather than repeating it — which is the
omission a transcribed list cannot catch about itself, and the defect this gate
exists to avoid repeating.

The first version of this file tested only what the gate was meant to do. Four
of the six defects an adversarial review then found — a change exempting itself
in one line, an exclusion wider than anything protects, a directory name that
excused source code, a move counted twice — were invisible to it, because a test
suite that only asks "does it pass what should pass" never asks what else it
passes. Every one of them has a test below that fails against the version that
shipped them.

Adapted from the copy in the four repositories that have a build. The script
beside it is byte for byte theirs; this file cannot be, and every difference is
a fact about this repository rather than a decision about the gate:

  - there is no generated contract and no generated client here, so the class
    that asks those checks where their artefacts live has nothing to ask. What
    this repository does declare in `.gitattributes` is the `binary` macro on
    image and archive types, and that is asserted instead — the same shape of
    claim, read out of the same file, about the exclusion this tree actually
    has;
  - no lockfile is tracked here, because nothing here is built or installed. The
    scan that finds them stays, asserting that the set found and the set
    excluded are the same set. Today both are empty, and the day a lockfile
    arrives it is this test that has to agree with the gate;
  - the paths are this repository's paths.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / "tools" / "quality"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, QUALITY / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


size = _load("check_diff_size")

ATTRIBUTES = (ROOT / ".gitattributes").read_text(encoding="utf-8")


def here(*arguments: str, stdin: str | None = None) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, input=stdin, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def declared_attributes() -> str:
    """A tree holding this repository's `.gitattributes` as it stands right now.

    `exclusions()` resolves against a commit, on purpose. But the question the
    class below asks is what this working tree declares, and reading `HEAD`
    would answer for the previous commit instead — so the assertions would go
    green on a rule not yet written and stay green on one just deleted. The file
    is hashed and put in a one-entry tree, which is what the base will hold the
    moment this change lands.
    """
    blob = here("hash-object", "-w", "--", ".gitattributes")
    # `-z`, because a subprocess text-mode pipe on Windows rewrites "\n" as
    # "\r\n" and git would then build a tree holding a file whose name ends in a
    # carriage return — which resolves no attributes at all, and quietly.
    return here("mktree", "-z", stdin=f"100644 blob {blob}\t.gitattributes\0")


def body(count: int, first: int = 0) -> str:
    return "".join(f"line {n}\n" for n in range(first, first + count))


def measure(
    added: dict[str, str] | None = None,
    *,
    before: dict[str, str] | None = None,
    removed: tuple[str, ...] = (),
    moved: tuple[tuple[str, str], ...] = (),
    attributes: str = ATTRIBUTES,
    head_attributes: str | None = None,
    base: str | None = None,
) -> tuple[int, str]:
    """Build a two-commit throwaway repository, then run the real script on it.

    `before` is the base commit's content, `added`/`removed`/`moved` the change.
    `head_attributes` writes a *different* `.gitattributes` in the second commit,
    which is the only way to state the self-exemption case: the question is which
    of the two copies the gate reads.
    """
    with tempfile.TemporaryDirectory() as raw:
        work = Path(raw)

        def write(path: str, text: str) -> None:
            target = work / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")

        def run(*arguments: str) -> str:
            return subprocess.run(
                ["git", *arguments], cwd=work, check=True, capture_output=True, text=True
            ).stdout

        script = work / "tools" / "quality" / "check_diff_size.py"
        script.parent.mkdir(parents=True)
        script.write_bytes((QUALITY / "check_diff_size.py").read_bytes())
        # The attributes travel with it: they are half of what it reads.
        write(".gitattributes", attributes)
        for path, text in (before or {}).items():
            write(path, text)

        run("init", "-q", "-b", "main", ".")
        run("config", "user.email", "proof@example.invalid")
        run("config", "user.name", "proof")
        run("add", "-A")  # the script and the attributes, as the base commit
        run("commit", "-qm", "base")
        recorded = run("rev-parse", "HEAD").strip()

        if head_attributes is not None:
            write(".gitattributes", head_attributes)
        for path, text in (added or {}).items():
            write(path, text)
        for path in removed:
            (work / path).unlink()
        for old, new in moved:
            (work / new).parent.mkdir(parents=True, exist_ok=True)
            run("mv", old, new)
        run("add", "-A")
        run("commit", "-qm", "change")

        done = subprocess.run(
            [sys.executable, str(script)], cwd=work, capture_output=True, text=True,
            env=dict(os.environ, BASE_SHA=recorded if base is None else base),
        )
    return done.returncode, done.stdout + done.stderr


class Boundary(unittest.TestCase):
    def test_the_threshold_falls_between_1000_and_1001(self) -> None:
        """The rule refuses a pull request *over* 1000, so 1000 is the last size
        that passes. Which side of a threshold the boundary falls on is the
        detail everyone assumes and nobody states."""
        for count, expected in ((999, 0), (1000, 0), (1001, 1)):
            with self.subTest(count=count):
                self.assertEqual(expected, measure({"docs/big.md": body(count)})[0])

    def test_a_refusal_names_the_count_the_threshold_and_the_file(self) -> None:
        code, output = measure({"docs/big.md": body(1100)})
        self.assertEqual(1, code)
        for expected in ("1100 hand-written lines added", "1000", "docs/big.md"):
            self.assertIn(expected, output)

    def test_a_lockfile_of_any_size_is_not_a_review_burden(self) -> None:
        """The proof that matters: a gate that counts lockfiles is a gate that
        gets switched off the first time Dependabot opens a pull request."""
        code, output = measure({"tools/pnpm-lock.yaml": body(1100)})
        self.assertEqual(0, code)
        self.assertIn("tools/pnpm-lock.yaml", output)

    def test_a_lockfile_does_not_buy_room_for_hand_written_lines(self) -> None:
        """The excluded half is excluded; the counted half is still counted."""
        code, output = measure(
            {"docs/big.md": body(1001), "tools/pnpm-lock.yaml": body(500)}
        )
        self.assertEqual(1, code)
        self.assertIn("1001 hand-written lines added", output)

    def test_an_undeterminable_base_exits_2_rather_than_passing(self) -> None:
        """Exit 0 here would report success for a measurement never made."""
        code, output = measure({"docs/big.md": body(1100)}, base="deadbeef" * 5)
        self.assertEqual(2, code)
        self.assertIn("cannot determine the base", output)


class TheChangeCannotWriteTheRuleItIsMeasuredBy(unittest.TestCase):
    """A pull request that appends one line to `.gitattributes` exempted 1100
    hand-written lines at a declared cost of 1. `git check-attr` reads the
    checkout, and in CI the checkout is the head, so the change was resolving
    its own exclusions. The attributes are now resolved against the base."""

    SELF_EXEMPTION = "docs/benchmark.md linguist-generated=true\n"

    def test_a_change_cannot_declare_its_own_payload_generated(self) -> None:
        code, output = measure(
            {"docs/benchmark.md": body(1100)},
            head_attributes=ATTRIBUTES + self.SELF_EXEMPTION,
        )
        self.assertEqual(1, code, output)
        # 1101: the 1100 lines, plus the line that tried to excuse them.
        self.assertIn("1101 hand-written lines added", output)
        self.assertIn("1100  docs/benchmark.md", output)
        self.assertNotIn("benchmark.md: the base's .gitattributes", output)

    def test_an_exclusion_the_base_already_declared_still_holds(self) -> None:
        """The other direction, or the fix is "ignore .gitattributes", which
        would count every lockfile and get the gate switched off."""
        code, output = measure(
            {"docs/benchmark.md": body(1100)},
            attributes=ATTRIBUTES + self.SELF_EXEMPTION,
        )
        self.assertEqual(0, code, output)
        self.assertIn("declares it generated", output)


class DeletedLinesAreNotAReviewBurden(unittest.TestCase):
    """Added lines only. The org rule is that dead code is removed in the change
    that stops using it; a gate refusing an 1100-line deletion fights that rule,
    and the author who meets it once leaves the dead code where it is."""

    def test_a_large_deletion_passes(self) -> None:
        code, output = measure(
            before={"docs/gone.md": body(1100), "docs/keep.md": "x\n"},
            removed=("docs/gone.md",),
        )
        self.assertEqual(0, code, output)
        self.assertIn("0 hand-written line(s) added", output)

    def test_a_large_addition_is_still_refused(self) -> None:
        self.assertEqual(1, measure({"docs/big.md": body(1100)})[0])

    def test_a_rewrite_is_counted_by_what_it_adds(self) -> None:
        """300 added over 800 deleted is 300, which is the number of lines
        somebody has to read."""
        code, output = measure(
            {"docs/churn.md": body(300, first=10_000)},
            before={"docs/churn.md": body(800)},
        )
        self.assertEqual(0, code, output)
        self.assertIn("300 hand-written line(s) added", output)


class AMoveIsNotSomethingToRead(unittest.TestCase):
    def test_a_pure_rename_counts_nothing(self) -> None:
        """`--no-renames` turned a 500-line move into 1000 changed lines and
        refused it, where git itself reports zero. A gate that punishes moving a
        file teaches people not to move files."""
        code, output = measure(
            before={"docs/moved.md": body(500)},
            moved=(("docs/moved.md", "docs/elsewhere.md"),),
        )
        self.assertEqual(0, code, output)
        self.assertIn("0 hand-written line(s) added", output)

    def test_a_move_that_also_rewrites_counts_what_it_adds(self) -> None:
        """Rename detection is not an exemption: the move is free, the 1001 new
        lines inside it are not."""
        code, output = measure(
            {"docs/elsewhere.md": body(2000) + body(1001, first=10_000)},
            before={"docs/moved.md": body(2000)},
            removed=("docs/moved.md",),
        )
        self.assertEqual(1, code, output)
        self.assertIn("1001 hand-written lines added", output)


class ExclusionsAreDerived(unittest.TestCase):
    """Against this repository, with every path asked of its owner."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.attributes = declared_attributes()

    def reason(self, path: Path) -> str | None:
        relative = path.relative_to(ROOT).as_posix()
        return size.exclusions([relative], self.attributes).get(relative)

    def test_what_the_attributes_call_binary_does_not_count(self) -> None:
        """The one exclusion this repository's `.gitattributes` really declares.

        `binary` expands to `-diff`, and content git never shows is content
        nobody reviews. Read out of the attributes rather than transcribed here,
        so removing the line from `.gitattributes` fails this instead of quietly
        widening what counts. The suffixes come from the file itself for the
        same reason.
        """
        declared = [
            line.split()[0].lstrip("*")
            for line in ATTRIBUTES.splitlines()
            if line.strip().endswith(" binary")
        ]
        self.assertTrue(declared, "this repository declares binary types; finding none is a broken scan")
        for suffix in declared:
            with self.subTest(suffix=suffix):
                self.assertIsNotNone(self.reason(ROOT / f"profile/banner{suffix}"))

    def test_ordinary_published_source_counts(self) -> None:
        """Or every assertion here is satisfied by a check that excludes the
        whole tree."""
        for path in ("README.md", "CONTRIBUTING.md", "docs/benchmark.md"):
            with self.subTest(path=path):
                self.assertIsNone(self.reason(ROOT / path))

    def test_every_lockfile_actually_tracked_is_excluded(self) -> None:
        """Found by scanning, so a lockfile added tomorrow in a directory nobody
        predicted fails here rather than inflating somebody's line count.

        This repository has no build and installs nothing, so the set is empty
        today. The scan is here for the day it is not: the assertion is that the
        set git reports and the set the gate excuses are the same set, which is
        a claim a transcribed list cannot make about itself.
        """
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.split()
        self.assertTrue(tracked, "this repository has tracked files; finding none is a broken scan")
        lockfiles = [
            name
            for name in tracked
            if size.LOCKFILE_SHAPE.search(Path(name).name)
            or Path(name).name in size.LOCKFILE_NAMES
        ]
        self.assertEqual(
            sorted(lockfiles), sorted(size.exclusions(lockfiles, self.attributes))
        )

    def test_the_lockfile_shape_is_the_shape_and_not_a_path(self) -> None:
        """The scan above is vacuous while this repository tracks no lockfile,
        so the rule itself is stated once: a name shape, at any depth, so one
        landing in a directory nobody predicted is covered the day it arrives."""
        for name in ("uv.lock", "pnpm-lock.yaml", "package-lock.json", "go.sum"):
            with self.subTest(name=name):
                self.assertIsNotNone(self.reason(ROOT / "somewhere" / name))

    def test_a_fixtures_directory_does_not_make_source_into_data(self) -> None:
        """Any `fixtures` component at any depth used to exclude any file type,
        so `tests/fixtures/factory.py` was 1100 unreviewed lines behind a
        directory name. The suffix is now part of the rule."""
        self.assertIsNone(self.reason(ROOT / "tests/fixtures/factory.py"))
        self.assertIsNone(self.reason(ROOT / "docs/fixtures/build.ts"))
        self.assertIsNotNone(self.reason(ROOT / "tests/fixtures/rows.sql"))
        self.assertIsNotNone(self.reason(ROOT / "docs/fixtures/projects.json"))


if __name__ == "__main__":
    unittest.main()
