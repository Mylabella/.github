"""Tests for the public content check and for the workflow rule beside it.

This script is the only executable code in the repository and the only thing
standing between a careless paste and a public leak of how the private
infrastructure is put together. An unverified gate is a gate nobody should
trust, so each pattern is tested for what it must catch and for what it must
leave alone. The second half matters more: a check that cries wolf gets
disabled, and a disabled check protects nothing.

The second half of this file is about the second rule: that every gate step in
a pull-request workflow says when it runs. Its central test is
`test_every_step_is_read_separately`, because the way to get that rule wrong is
to scan the file as one string, find a `cancelled()` belonging to some other
step, and pass on exactly the state the rule refuses.
"""

from __future__ import annotations

import contextlib
import importlib.util
import inspect
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "quality" / "verify_public_content.py"
SPEC = importlib.util.spec_from_file_location("verify_public_content", MODULE_PATH)
assert SPEC and SPEC.loader
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


def reasons(text: str) -> list[str]:
    return [reason for _, _, reason in verify.scan(text)]


@contextlib.contextmanager
def temporary_workflows(files: dict[str, str]) -> Iterator[Path]:
    """Point the workflow rule at workflows a test wrote.

    ROOT moves with WORKFLOWS, because the error messages name the workflow
    relative to the repository root and a temporary directory is not under it.
    """
    original_root = verify.ROOT
    original_workflows = verify.WORKFLOWS
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        for name, text in files.items():
            (workflows / name).write_text(text, encoding="utf-8")
        verify.ROOT = root
        verify.WORKFLOWS = workflows
        try:
            yield workflows
        finally:
            verify.ROOT = original_root
            verify.WORKFLOWS = original_workflows


def condition_errors(files: dict[str, str]) -> list[str]:
    """Run check_gate_conditions against workflows a test wrote."""
    with temporary_workflows(files):
        errors: list[str] = []
        verify.check_gate_conditions(errors)
        return errors


def script_lines(step: dict[str, object]) -> list[str]:
    """A step's `run:` as stripped, non-empty lines.

    The subset parser drops the relative indentation inside a block scalar on
    purpose, so a comparison against another parser has to compare the lines.
    """
    return [line.strip() for line in str(step.get("run", "")).split("\n") if line.strip()]


def without_condition(text: str, step_name: str) -> str:
    """The workflow with one named step's `if:` deleted, and nothing else.

    The break the rule is proved against, applied to one step at a time — which
    is the part that matters. A file with every condition removed would be caught
    even by a check that reads the file as one string, and that check is the one
    this rule exists to replace.
    """
    lines = text.splitlines()
    column: int | None = None
    for index, line in enumerate(lines):
        if column is None:
            if line.strip() == f"- name: {step_name}":
                column = verify.indent_of(line) + 2
            continue
        if line.strip() and verify.indent_of(line) < column:
            break
        if verify.indent_of(line) == column and line.strip().startswith("if:"):
            del lines[index]
            return "\n".join(lines) + "\n"
    raise AssertionError(f"no if: to remove from step {step_name!r}")


class Rejects(unittest.TestCase):
    """Every one of these is a sentence that could plausibly be pasted here."""

    CASES = {
        "The host answers at 203.0.113.17 over the tunnel.": "looks like an IP address",
        "Secrets live under /srv/mylabella/secrets/platform.": "looks like an absolute path on a real machine",
        "Clone it into C:\\Users\\someone\\projects.": "looks like a Windows filesystem path",
        "Reach it at box.example.ts.net once joined.": "names the private network",
        "Set POSTGRES_SUPERUSER_PASSWORD before converging.": "looks like the name of a secret",
        "The database is at postgres.internal on the private net.": "looks like a private hostname",
        "Connect with deploy@vps.example.com to check.": "looks like an account on a specific host",
        "See https://grafana.example.com for the graphs.": "links to an unexpected host",
    }

    def test_each_case_is_reported(self) -> None:
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertIn(expected, reasons(text))


class Accepts(unittest.TestCase):
    """Ordinary policy prose must pass, or the check will be turned off."""

    CASES = (
        "Open a pull request for every change, including changes made alone.",
        "Prefer squash merge. The pull-request title becomes the commit message.",
        "See [the covenant](https://www.contributor-covenant.org) for the text.",
        "Benchmarked against [farmOS](https://github.com/farmOS/.github).",
        "Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).",
        "Components are versioned as `<component>-vX.Y.Z`, e.g. backend-v1.4.0.",
        "Fewer than 400 changed production lines is a useful target.",
        "Report vulnerabilities privately through the repository Security tab.",
        "Read the README, then see docs/benchmark.md for the comparison.",
        "Use a short-lived feature/, fix/, or chore/ branch.",
    )

    def test_no_false_positives(self) -> None:
        for text in self.CASES:
            with self.subTest(text=text):
                self.assertEqual([], reasons(text))


class UnfinishedText(unittest.TestCase):
    """The one defect that was here, published, while every check was green."""

    def test_the_line_that_was_actually_committed(self) -> None:
        # GOVERNANCE.md carried this in the middle of a sentence about
        # maintainer responsibilities. Every pattern in this file looked for
        # something that should not be published; none looked for text that was
        # never finished.
        published = (
            "- documenting project-specific decisions and ex"
            "…247 tokens truncated…resolved conflict of"
        )
        self.assertTrue(any("never finished" in r for r in reasons(published)))

    def test_the_other_shapes_a_tool_leaves_behind(self) -> None:
        for artifact in (
            "... [12 lines truncated]",
            "[truncated]",
            "[... 40 tokens truncated",
            "<<<<<<< HEAD",
            ">>>>>>> origin/main",
        ):
            with self.subTest(artifact=artifact):
                self.assertTrue(any("never finished" in r for r in reasons(artifact)))

    def test_prose_about_truncation_is_left_alone(self) -> None:
        # A check that cries wolf gets disabled, and these documents are
        # allowed to discuss the subject.
        for innocent in (
            "Long outputs are truncated rather than dropped.",
            "The token budget is 4000 tokens per request.",
            "Use ======= as a section divider in a code sample when it is indented.",
        ):
            with self.subTest(innocent=innocent):
                self.assertEqual([], [r for r in reasons(innocent) if "never finished" in r])


class WorkflowParsing(unittest.TestCase):
    """The YAML subset, exercised on the shapes a workflow actually contains.

    Every one of these is a way a text-scanning check would get the wrong answer
    about which step is which.
    """

    def test_steps_are_separate_mappings(self) -> None:
        document = verify.parse_workflow(
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: one\n"
            "        if: ${{ !cancelled() }}\n"
            "        run: a\n"
            "      - name: two\n"
            "        run: b\n"
        )
        steps = verify.steps_of(verify.jobs_of(document)["governance"])
        self.assertEqual(["one", "two"], [step["name"] for step in steps])
        self.assertEqual("${{ !cancelled() }}", steps[0]["if"])
        self.assertIsNone(steps[1].get("if"))

    def test_a_sequence_may_sit_at_its_key_s_own_column(self) -> None:
        """Both indentations are legal YAML and both appear in real workflows."""
        document = verify.parse_workflow(
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "    - name: one\n"
            "      run: a\n"
        )
        steps = verify.steps_of(verify.jobs_of(document)["governance"])
        self.assertEqual(["one"], [step["name"] for step in steps])

    def test_a_block_scalar_is_content_and_not_structure(self) -> None:
        """A `run: |` script can contain anything, including `- name:` and `#`.

        The branch-name gate in this repository is exactly this shape: a case
        statement with comments and quoted text inside it.
        """
        document = verify.parse_workflow(
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: one\n"
            "        run: |\n"
            "          # a shell comment, not a YAML comment\n"
            "          echo '- name: two'\n"
            "          case \"$BRANCH\" in\n"
            "      - name: three\n"
            "        run: b\n"
        )
        steps = verify.steps_of(verify.jobs_of(document)["governance"])
        self.assertEqual(["one", "three"], [step["name"] for step in steps])
        self.assertIn("# a shell comment", str(steps[0]["run"]))
        self.assertIn('case "$BRANCH" in', str(steps[0]["run"]))

    def test_a_hash_inside_quotes_is_not_a_comment(self) -> None:
        self.assertEqual({"run": "echo 'a # b'"}, verify.parse_workflow("run: 'echo ''a # b'''"))

    def test_a_trailing_comment_is_dropped(self) -> None:
        document = verify.parse_workflow("uses: actions/checkout@abc # v7.0.1\n")
        self.assertEqual("actions/checkout@abc", document["uses"])

    def test_the_triggers_are_read_in_every_spelling(self) -> None:
        for text, expected in (
            (
                "on:\n  pull_request:\n  push:\n    branches:\n      - main\n",
                {"pull_request", "push"},
            ),
            ("on: [push, pull_request]\n", {"push", "pull_request"}),
            ("on: pull_request\n", {"pull_request"}),
            ("on:\n  push:\n    branches: [main]\n", {"push"}),
        ):
            with self.subTest(text=text):
                self.assertEqual(expected, verify.triggers(verify.parse_workflow(text)))

    def test_a_colon_inside_a_value_does_not_split_it(self) -> None:
        document = verify.parse_workflow("group: governance-${{ github.workflow }}\n")
        self.assertEqual("governance-${{ github.workflow }}", document["group"])

    def test_a_sequence_item_that_is_not_a_mapping_stays_a_scalar(self) -> None:
        document = verify.parse_workflow("branches:\n  - main\n")
        self.assertEqual(["main"], document["branches"])


class GateStepConditions(unittest.TestCase):
    """The rule: a gate step says when it runs, or the verifier refuses it."""

    def workflow(self, first: str, second: str) -> str:
        return (
            "name: Governance\n"
            "\n"
            "on:\n"
            "  pull_request:\n"
            "\n"
            "jobs:\n"
            "  governance:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Check out repository\n"
            "        id: checkout\n"
            "        uses: actions/checkout@abc\n"
            "      - name: Check the published content\n"
            "        id: public-content\n"
            f"{first}"
            "        run: python3 tools/quality/verify_public_content.py\n"
            "      - name: Test the check itself\n"
            "        id: verifier-tests\n"
            f"{second}"
            "        run: python3 -m unittest discover -s tests\n"
        )

    CONDITION = "        if: ${{ !cancelled() && steps.checkout.outcome == 'success' }}\n"

    def test_every_step_is_read_separately(self) -> None:
        """The central requirement, and the one a text scan gets wrong.

        The file below *contains* `cancelled()` — on the first gate. A check that
        reads the workflow as one string finds it and passes, which is precisely
        the state this rule was written to refuse.
        """
        errors = condition_errors({"governance.yml": self.workflow(self.CONDITION, "")})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Test the check itself", errors[0])
        self.assertIn("verifier-tests", errors[0])
        self.assertIn("governance.yml", errors[0])

    def test_a_conditioned_pair_is_accepted(self) -> None:
        both = self.workflow(self.CONDITION, self.CONDITION)
        self.assertEqual([], condition_errors({"governance.yml": both}))

    def test_the_bare_form_is_accepted(self) -> None:
        """`!cancelled()` alone, for a gate that depends on nothing."""
        bare = "        if: ${{ !cancelled() }}\n"
        self.assertEqual([], condition_errors({"governance.yml": self.workflow(bare, bare)}))

    def test_always_is_not_the_same_thing(self) -> None:
        """It keeps a superseded job working, which cancel-in-progress forbids."""
        always = "        if: ${{ always() }}\n"
        errors = condition_errors({"governance.yml": self.workflow(always, always)})
        self.assertEqual(2, len(errors), errors)

    def test_an_unrelated_condition_is_not_enough(self) -> None:
        """The shape this repository actually had: the branch-name gate."""
        other = "        if: github.event_name == 'pull_request'\n"
        errors = condition_errors({"governance.yml": self.workflow(self.CONDITION, other)})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Test the check itself", errors[0])

    def test_a_uses_step_is_not_a_gate_step(self) -> None:
        """The checkout has no `run:`, so it is a dependency and not a gate.

        Asserted on the definition directly, because the workflow above would
        stay green if `uses:` steps were passed over for a different reason.
        """
        step: dict[str, object] = {"name": "Check out", "uses": "actions/checkout@abc"}
        self.assertIsNone(verify.gate_in_step(step))

    def test_a_gate_inside_a_multi_line_script_is_still_a_gate(self) -> None:
        text = (
            "on:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: Check the branch name\n"
            "        run: |\n"
            "          case \"$BRANCH\" in\n"
            "            *) exit 1 ;;\n"
            "          esac\n"
        )
        errors = condition_errors({"governance.yml": text})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Check the branch name", errors[0])

    def test_a_step_without_an_id_is_named_by_its_command(self) -> None:
        """The error still says which check would have been skipped."""
        step: dict[str, object] = {
            "name": "Check the published content",
            "run": "# a leading comment\npython3 tools/quality/verify_public_content.py\n",
        }
        self.assertEqual(
            "python3 tools/quality/verify_public_content.py", verify.gate_in_step(step)
        )

    def test_a_workflow_without_pull_request_is_out_of_scope(self) -> None:
        """Release and deploy stop at the first failure on purpose."""
        text = (
            "on:\n"
            "  push:\n"
            "    tags:\n"
            "      - 'v*'\n"
            "jobs:\n"
            "  release:\n"
            "    steps:\n"
            "      - name: Verify\n"
            "        run: python3 tools/quality/verify_public_content.py\n"
        )
        self.assertEqual([], condition_errors({"release.yml": text}))

    def test_a_called_workflow_is_in_scope_by_transitivity(self) -> None:
        """Its steps run on the pull request, so they can be silenced the same way."""
        caller = (
            "on:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  shared:\n"
            "    uses: ./.github/workflows/shared.yml\n"
        )
        called = (
            "on:\n"
            "  workflow_call:\n"
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: Verify\n"
            "        run: python3 tools/quality/verify_public_content.py\n"
        )
        errors = condition_errors({"caller.yml": caller, "shared.yml": called})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("shared.yml", errors[0])

    def test_a_called_workflow_nobody_calls_stays_out_of_scope(self) -> None:
        called = (
            "on:\n"
            "  workflow_call:\n"
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: Verify\n"
            "        run: python3 tools/quality/verify_public_content.py\n"
        )
        self.assertEqual([], condition_errors({"shared.yml": called}))

    def test_a_step_with_no_name_is_reported_by_its_position(self) -> None:
        text = (
            "on:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - run: python3 tools/quality/verify_public_content.py\n"
        )
        errors = condition_errors({"governance.yml": text})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("governance step 1", errors[0])


class TheRealWorkflows(unittest.TestCase):
    """The rule against what is committed, and the proof that it can fail."""

    def in_scope(self) -> dict[str, str]:
        return {
            path.name: path.read_text(encoding="utf-8")
            for path in verify.pull_request_workflows()
        }

    def test_there_is_something_to_check(self) -> None:
        """Otherwise every assertion below is about an empty loop."""
        self.assertGreater(len(self.in_scope()), 0, "no workflow runs on pull_request")

    def test_every_gate_step_names_cancelled(self) -> None:
        errors: list[str] = []
        verify.check_gate_conditions(errors)
        self.assertEqual([], errors)

    def test_the_subset_parser_agrees_with_a_real_one(self) -> None:
        """A second opinion where one is available, never the check itself.

        The verifier reads YAML with a subset parser because it has to run on a
        bare `python3`. Where PyYAML happens to be installed — a laptop, a
        developer image — it is worth asking it whether the subset got these
        files right. It skips where PyYAML is absent, which is why it is an extra
        rather than the guard: the guard is the class above.
        """
        try:
            import yaml  # noqa: PLC0415
        except ImportError:  # pragma: no cover - depends on the machine
            self.skipTest("PyYAML is not installed")

        for path in verify.workflow_files():
            text = path.read_text(encoding="utf-8")
            mine = verify.parse_workflow(text)
            theirs = yaml.safe_load(text)
            for name, job in verify.jobs_of(mine).items():
                with self.subTest(workflow=path.name, job=name):
                    ours = verify.steps_of(job)
                    reference = theirs["jobs"][name].get("steps", [])
                    self.assertEqual(len(reference), len(ours))
                    for step, expected in zip(ours, reference):
                        for key in ("name", "id", "if", "uses"):
                            self.assertEqual(expected.get(key), step.get(key))
                        self.assertEqual(script_lines(expected), script_lines(step))

    def test_removing_any_one_condition_is_caught(self) -> None:
        """The proof kept as a test rather than as a paragraph in a report.

        One step at a time, every gate step in every in-scope workflow: drop its
        `if:`, and the check must produce exactly one error, naming that step,
        its gate and its file. The other steps keep their conditions, so the file
        still contains `cancelled()` — the state a text scan passes on.
        """
        files = self.in_scope()
        checked = 0
        for name, text in files.items():
            document = verify.parse_workflow(text)
            for job in verify.jobs_of(document).values():
                for step in verify.steps_of(job):
                    gate = verify.gate_in_step(step)
                    if gate is None:
                        continue
                    label = str(step["name"])
                    with self.subTest(workflow=name, step=label):
                        broken = dict(files)
                        broken[name] = without_condition(text, label)
                        self.assertIn("cancelled()", broken[name])
                        errors = condition_errors(broken)
                        self.assertEqual(1, len(errors), errors)
                        self.assertIn(label, errors[0])
                        self.assertIn(gate, errors[0])
                        self.assertIn(name, errors[0])
                    checked += 1
        self.assertGreater(checked, 0, "no gate step was found, so this asserted nothing")


class RealRepository(unittest.TestCase):
    def test_the_published_files_pass(self) -> None:
        """The rule is only credible if what is already here obeys it."""
        self.assertEqual(0, verify.main())

    def test_main_calls_every_check(self) -> None:
        """A check nothing calls is a check that cannot fail.

        Found while proving the workflow rule: deleting its call from main() left
        the whole suite green, because every other test calls the checks
        directly. That is the same hole as a check that matches nothing, one
        level up.
        """
        source = inspect.getsource(verify.main)
        for name in ("check_public_content", "check_gate_conditions"):
            with self.subTest(check=name):
                self.assertIn(f"{name}(", source)


if __name__ == "__main__":
    unittest.main()
