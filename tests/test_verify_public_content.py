"""Tests for the public content check and for the workflow rule beside it.

This script is the only executable code in the repository and the only thing
standing between a careless paste and a public leak of how the private
infrastructure is put together. An unverified gate is a gate nobody should
trust, so each pattern is tested for what it must catch and for what it must
leave alone. The second half matters more: a check that cries wolf gets
disabled, and a disabled check protects nothing.

The rest of this file is about the second rule: that every step in a
pull-request workflow which an earlier failure could silence says when it runs.
Three things are being asserted, and they are not the same thing:

  - the rule catches a step with no condition — `GateStepConditions`, whose
    central case is `test_every_step_is_read_separately`, because the way to get
    this rule wrong is to scan the file as one string, find a `cancelled()`
    belonging to some other step, and pass on exactly the state it refuses;

  - the parser fails closed — `FailingClosed` and `WorkflowStructure`. A
    construct it cannot read is an error naming the construct, never an empty
    document. The first version returned `{}` for any file beginning with `---`,
    and an empty document is a file with no steps, and a file with no steps is a
    file with nothing to complain about;

  - and the two above are asserted about **every workflow file on disk** —
    `TheRealWorkflows`. The previous version of that class iterated over
    whatever the parser returned, so a file the parser could not read produced
    no subtests and every assertion passed by having nothing to say. That is the
    original defect — an absence that reads as consent — reproduced inside the
    tests written to forbid it.

`TheSharedBlock` closes the last of it: the parser and the rule are copied byte
for byte between five repositories, and this checks that the copy here is the
one the file says it is.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import inspect
import re
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
    """Point the workflow rules at workflows a test wrote.

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


@contextlib.contextmanager
def registry(gates: list[dict[str, object]] | None) -> Iterator[None]:
    """Lend the shared block a gate registry, which this repository has none of.

    `load_gates()` here returns `[]` on purpose — the reason is written above it
    in the verifier. That leaves one branch of the shared block unexercised: the
    clause that turns a step's command into a gate's *name* in the error message.
    A branch no test reaches is a branch that can rot, and rot in a block copied
    byte for byte between five repositories is exactly what this round of work is
    about. So the tests that are about naming lend it a registry, and the tests
    that are about the perimeter do not — the perimeter must not depend on it.
    """
    if gates is None:
        yield
        return
    original = verify.load_gates
    verify.load_gates = lambda: gates  # type: ignore[assignment]
    try:
        yield
    finally:
        verify.load_gates = original  # type: ignore[assignment]


def condition_errors(
    files: dict[str, str], gates: list[dict[str, object]] | None = None
) -> list[str]:
    """Run check_gate_conditions against workflows a test wrote."""
    with registry(gates), temporary_workflows(files):
        errors: list[str] = []
        verify.check_gate_conditions(errors)
        return errors


def workflow_problems(files: dict[str, str]) -> list[str]:
    """Run check_workflows against workflows a test wrote."""
    with temporary_workflows(files):
        errors: list[str] = []
        verify.check_workflows(errors)
        return errors


def refusal(text: str) -> verify.UnsupportedWorkflow:
    """The exception parse_workflow raises for `text`, or a test failure."""
    try:
        document = verify.parse_workflow(text)
    except verify.UnsupportedWorkflow as exc:
        return exc
    raise AssertionError(f"parsed instead of refusing, into {document!r}")


def script(step: dict[str, object]) -> list[str]:
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


def gate(**overrides: object) -> dict[str, object]:
    """A registry entry shaped as the four sibling repositories declare them."""
    entry: dict[str, object] = {
        "id": "public-content",
        "command": "python3 tools/quality/verify_public_content.py",
        "stages": ["pr"],
        "blocking": True,
    }
    entry.update(overrides)
    return entry


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

    def test_a_leading_document_marker_is_read_and_not_a_wall(self) -> None:
        """F1. `---` is legal YAML, required by yamllint's document-start rule,
        and already the convention in the platform's ansible tree. The first
        version of this parser returned `{}` for any file beginning with it —
        no triggers, so not a pull-request workflow, so not checked, so green.
        """
        text = (
            "---\n"
            "on:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: one\n"
            "        run: a\n"
        )
        document = verify.parse_workflow(text)
        self.assertEqual({"pull_request"}, verify.triggers(document))
        self.assertEqual(
            ["one"],
            [s["name"] for s in verify.steps_of(verify.jobs_of(document)["governance"])],
        )

    def test_a_plain_scalar_may_run_past_its_line(self) -> None:
        """F2, and the likelier of the two: it needs only a long condition.

        The wrapped line used to end the mapping, so the step lost its `run:`
        and every step below it left the document entirely.
        """
        document = verify.parse_workflow(
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: one\n"
            "        if: ${{ !cancelled() &&\n"
            "          steps.checkout.outcome == 'success' }}\n"
            "        run: a\n"
            "      - name: two\n"
            "        run: b\n"
        )
        steps = verify.steps_of(verify.jobs_of(document)["governance"])
        self.assertEqual(["one", "two"], [step["name"] for step in steps])
        self.assertEqual(
            "${{ !cancelled() && steps.checkout.outcome == 'success' }}", steps[0]["if"]
        )
        self.assertEqual("a", steps[0]["run"])

    def test_a_folded_block_scalar_joins_with_spaces(self) -> None:
        """F3. Joined with newlines, a folded gate command stops matching the
        registry verbatim, and its step leaves the perimeter of the rule."""
        document = verify.parse_workflow(
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: one\n"
            "        run: >-\n"
            "          python3\n"
            "          tools/quality/verify_public_content.py\n"
        )
        step = verify.steps_of(verify.jobs_of(document)["governance"])[0]
        self.assertEqual("python3 tools/quality/verify_public_content.py", step["run"])

    def test_a_literal_block_scalar_keeps_its_lines(self) -> None:
        """The other half of the same fix: `|` must not start folding."""
        document = verify.parse_workflow("run: |\n  one\n  two\n")
        self.assertEqual("one\ntwo", document["run"])

    def test_a_folded_scalar_keeps_a_blank_line_as_a_break(self) -> None:
        document = verify.parse_workflow("text: >\n  one\n  two\n\n  three\n")
        self.assertEqual("one two\nthree", document["text"])


class FailingClosed(unittest.TestCase):
    """A construct this parser cannot read is an error, never an absence.

    Adding the three constructs above was necessary and is not sufficient: the
    fourth unknown construct will arrive, and under the old parser it would
    again produce a document with no steps, which this check reads as a file
    with nothing to complain about. Every refusal below names the construct and
    the line.
    """

    def test_an_anchor_is_refused_by_name(self) -> None:
        exception = refusal("permissions: &readonly\n  contents: read\n")
        self.assertEqual(1, exception.line)
        self.assertIn("anchor or alias", exception.problem)
        self.assertIn("&readonly", exception.problem)

    def test_an_alias_is_refused(self) -> None:
        self.assertIn("anchor or alias", refusal("permissions: *readonly\n").problem)

    def test_a_shell_glob_is_not_an_alias(self) -> None:
        """The refusal has to be narrow, or it refuses files it reads fine."""
        self.assertEqual({"run": "rm -rf *"}, verify.parse_workflow("run: rm -rf *\n"))
        self.assertEqual({"paths": ["*.py"]}, verify.parse_workflow("paths: ['*.py']\n"))

    def test_a_flow_mapping_is_refused(self) -> None:
        exception = refusal("jobs:\n  governance:\n    with: {a: 1}\n")
        self.assertEqual(3, exception.line)
        self.assertIn("flow mapping", exception.problem)

    def test_an_actions_expression_is_not_a_flow_mapping(self) -> None:
        document = verify.parse_workflow("if: ${{ github.ref == 'refs/heads/main' }}\n")
        self.assertEqual("${{ github.ref == 'refs/heads/main' }}", document["if"])

    def test_a_tab_in_the_indentation_is_refused(self) -> None:
        exception = refusal("on:\n\tpull_request:\n")
        self.assertEqual(2, exception.line)
        self.assertIn("tab", exception.problem)

    def test_a_second_document_is_refused(self) -> None:
        exception = refusal("on: pull_request\n---\non: push\n")
        self.assertEqual(2, exception.line)
        self.assertIn("second YAML document", exception.problem)

    def test_a_multi_line_flow_sequence_is_refused(self) -> None:
        self.assertIn("flow sequence", refusal("on: [push,\n  pull_request]\n").problem)

    def test_a_line_that_is_not_a_key_is_refused(self) -> None:
        exception = refusal("on:\n  pull_request:\nnot a key\n")
        self.assertIn("neither `key: value`", exception.problem)

    def test_a_construct_inside_a_script_is_script(self) -> None:
        """The refusals must not reach into a `run:` body, which may hold
        anything a shell accepts — braces, asterisks, tabs and `---`."""
        document = verify.parse_workflow(
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: one\n"
            "        run: |\n"
            "          echo '---'\n"
            "          jq '{a: 1}' < x\n"
            "          printf 'a\\tb'\n"
            "          rm -rf *\n"
        )
        step = verify.steps_of(verify.jobs_of(document)["governance"])[0]
        self.assertIn("jq '{a: 1}'", str(step["run"]))

    def test_every_refusal_says_what_to_do(self) -> None:
        """A message whose only available response is to delete the check is
        how a check gets deleted."""
        for text in (
            "a: &x\n  b: 1\n",
            "with: {a: 1}\n",
            "on:\n\tpush:\n",
            "on: push\n---\non: pull_request\n",
        ):
            with self.subTest(text=text):
                self.assertTrue(refusal(text).remedy.strip())


class WorkflowStructure(unittest.TestCase):
    """A workflow that parses into nothing recognisable is an error too.

    The parser can be defeated without raising: it reads what it can and stops.
    So the shape of the result is checked as well — a GitHub workflow has
    triggers, jobs and steps, and something that came back without them was not
    read, whatever the reason.
    """

    WHOLE = (
        "on:\n"
        "  pull_request:\n"
        "jobs:\n"
        "  governance:\n"
        "    steps:\n"
        "      - name: one\n"
        "        run: a\n"
    )

    def test_a_whole_workflow_reports_nothing(self) -> None:
        self.assertEqual([], workflow_problems({"governance.yml": self.WHOLE}))

    def test_a_workflow_with_no_triggers_is_an_error(self) -> None:
        text = self.WHOLE.replace("on:\n  pull_request:\n", "")
        problems = workflow_problems({"governance.yml": text})
        self.assertTrue(any("no `on:` triggers" in p for p in problems), problems)

    def test_a_workflow_with_no_jobs_is_an_error(self) -> None:
        problems = workflow_problems({"governance.yml": "on:\n  pull_request:\n"})
        self.assertTrue(any("no `jobs:`" in p for p in problems), problems)

    def test_a_job_with_no_steps_is_an_error(self) -> None:
        text = "on:\n  pull_request:\njobs:\n  governance:\n    runs-on: ubuntu-latest\n"
        problems = workflow_problems({"governance.yml": text})
        self.assertTrue(any("has no steps" in p for p in problems), problems)

    def test_a_job_that_calls_a_reusable_workflow_needs_no_steps(self) -> None:
        """It has none by GitHub's rule; its steps are checked where they live."""
        text = (
            "on:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  shared:\n"
            "    uses: ./.github/workflows/shared.yml\n"
        )
        self.assertEqual([], workflow_problems({"caller.yml": text}))

    def test_an_empty_file_is_an_error_and_not_an_empty_perimeter(self) -> None:
        problems = workflow_problems({"governance.yml": "\n# nothing here\n"})
        self.assertTrue(any("empty document" in p for p in problems), problems)

    def test_an_unreadable_workflow_is_reported_with_its_line(self) -> None:
        text = "on:\n  pull_request:\njobs: &jobs\n  governance:\n    steps:\n      - run: a\n"
        problems = workflow_problems({"governance.yml": text})
        self.assertEqual(1, len(problems), problems)
        self.assertIn("governance.yml:3", problems[0])
        self.assertIn("anchor", problems[0])

    def test_the_condition_rule_reports_it_too(self) -> None:
        """Both checks report an unread file, and main() de-duplicates.

        The overlap is the point: deleting either call leaves the other one
        talking, and a file leaving the perimeter unannounced is the defect
        being repaired.
        """
        text = "on:\n  pull_request:\njobs: &jobs\n  governance:\n    steps:\n      - run: a\n"
        errors = condition_errors({"governance.yml": text})
        self.assertTrue(any("anchor" in e for e in errors), errors)


class GateStepConditions(unittest.TestCase):
    """The rule: a step that could be silenced says when it runs, or it is refused."""

    GATES = [
        gate(id="public-content", command="python3 tools/quality/verify_public_content.py"),
        gate(id="verifier-tests", command="python3 -m unittest discover -s tests"),
    ]

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
        errors = condition_errors(
            {"governance.yml": self.workflow(self.CONDITION, "")}, self.GATES
        )
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Test the check itself", errors[0])
        self.assertIn("verifier-tests", errors[0])
        self.assertIn("governance.yml", errors[0])

    def test_a_conditioned_pair_is_accepted(self) -> None:
        both = self.workflow(self.CONDITION, self.CONDITION)
        self.assertEqual([], condition_errors({"governance.yml": both}, self.GATES))

    def test_the_bare_form_is_accepted(self) -> None:
        """`!cancelled()` alone, for a gate that depends on nothing."""
        bare = "        if: ${{ !cancelled() }}\n"
        self.assertEqual(
            [], condition_errors({"governance.yml": self.workflow(bare, bare)}, self.GATES)
        )

    def test_always_is_not_the_same_thing(self) -> None:
        """It keeps a superseded job working, which cancel-in-progress forbids."""
        always = "        if: ${{ always() }}\n"
        errors = condition_errors({"governance.yml": self.workflow(always, always)}, self.GATES)
        self.assertEqual(2, len(errors), errors)

    def test_an_unrelated_condition_is_not_enough(self) -> None:
        """The shape this repository actually had: the branch-name gate."""
        other = "        if: github.event_name == 'pull_request'\n"
        errors = condition_errors(
            {"governance.yml": self.workflow(self.CONDITION, other)}, self.GATES
        )
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Test the check itself", errors[0])

    def test_a_uses_step_nothing_depends_on_is_out_of_scope(self) -> None:
        """An action nobody waits on produces no verdict and silences nothing.

        Asserted on the definition directly, because the workflow above would
        stay green if `uses:` steps were reported for a different reason.
        """
        job: dict[str, object] = {
            "steps": [
                {"name": "Check out", "uses": "actions/checkout@abc"},
                {"name": "Upload the log", "uses": "actions/upload-artifact@abc"},
            ]
        }
        self.assertEqual([], verify.steps_that_must_say_when_they_run(job))

    def test_a_uses_step_that_other_steps_depend_on_is_in_scope(self) -> None:
        """F4, in its clearest form: the setup action with gates hanging off it.

        `Install Node` runs no script and names no gate, so the old definition
        never looked at it. Skip it — which one earlier red does, silently, when
        it has no condition — and every gate behind it is skipped too.
        """
        job: dict[str, object] = {
            "steps": [
                {"name": "Check out", "id": "checkout", "uses": "actions/checkout@abc"},
                {"name": "A gate", "if": "${{ !cancelled() }}", "run": "python3 x.py"},
                {"name": "Install Node", "id": "node", "uses": "actions/setup-node@abc"},
                {
                    "name": "Frontend gates",
                    "if": "${{ !cancelled() && steps.node.outcome == 'success' }}",
                    "run": "pnpm run verify",
                },
            ]
        }
        needed = verify.steps_that_must_say_when_they_run(job)
        self.assertEqual(
            ["A gate", "Install Node", "Frontend gates"],
            [str(step["name"]) for _, step, _ in needed],
        )
        self.assertIn("steps.node", [why for _, _, why in needed][1])

    def test_the_first_step_of_a_job_needs_no_condition(self) -> None:
        """Nothing precedes the checkout, so `!cancelled()` there says nothing."""
        job: dict[str, object] = {
            "steps": [
                {"name": "Check out", "id": "checkout", "uses": "actions/checkout@abc"},
                {
                    "name": "A gate",
                    "if": "${{ !cancelled() && steps.checkout.outcome == 'success' }}",
                    "run": "python3 x.py",
                },
            ]
        }
        self.assertEqual(
            ["A gate"],
            [str(step["name"]) for _, step, _ in verify.steps_that_must_say_when_they_run(job)],
        )

    def test_the_exemption_for_the_first_step_expires_by_itself(self) -> None:
        """Put anything above the checkout and the checkout is no longer root.

        Which is what makes the exemption safe to grant: it is about position,
        not about being a checkout, so it stops applying the moment something
        exists that could skip it.
        """
        job: dict[str, object] = {
            "steps": [
                {"name": "Warm the cache", "uses": "actions/cache@abc"},
                {"name": "Check out", "id": "checkout", "uses": "actions/checkout@abc"},
                {
                    "name": "A gate",
                    "if": "${{ !cancelled() && steps.checkout.outcome == 'success' }}",
                    "run": "python3 x.py",
                },
            ]
        }
        self.assertIn(
            "Check out",
            [str(step["name"]) for _, step, _ in verify.steps_that_must_say_when_they_run(job)],
        )

    def test_a_run_step_that_names_no_gate_is_still_in_scope(self) -> None:
        """C2, and the reason the definition was widened.

        A step that installs a toolchain names no gate and is nobody's gate, and
        every gate after it is conditioned on its outcome. Under the old
        definition the verifier never looked at it.
        """
        text = (
            "on:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - name: Check out\n"
            "        id: checkout\n"
            "        uses: actions/checkout@abc\n"
            "      - name: Install the locked environment\n"
            "        id: sync\n"
            "        run: uv sync --frozen --all-groups\n"
        )
        errors = condition_errors({"governance.yml": text}, self.GATES)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Install the locked environment", errors[0])
        self.assertIn("runs a script", errors[0])

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
        errors = condition_errors({"governance.yml": text}, self.GATES)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Check the branch name", errors[0])

    def test_a_step_without_an_id_is_named_by_its_command(self) -> None:
        """The error still says which check would have been skipped."""
        step: dict[str, object] = {
            "name": "Check the published content",
            "run": "# a leading comment\npython3 tools/quality/verify_public_content.py\n",
        }
        commands = {str(entry["command"]): str(entry["id"]) for entry in self.GATES}
        self.assertEqual("public-content", verify.gate_named_in(step, commands))

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
        self.assertEqual([], condition_errors({"release.yml": text}, self.GATES))

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
        errors = condition_errors({"caller.yml": caller, "shared.yml": called}, self.GATES)
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
        self.assertEqual([], condition_errors({"shared.yml": called}, self.GATES))

    def test_a_step_with_no_name_is_reported_by_its_position(self) -> None:
        text = (
            "on:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  governance:\n"
            "    steps:\n"
            "      - run: python3 tools/quality/verify_public_content.py\n"
        )
        errors = condition_errors({"governance.yml": text}, self.GATES)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("governance step 1", errors[0])

    def test_the_rule_runs_without_a_registry_at_all(self) -> None:
        """Which is this repository's permanent state, not a degraded one.

        `load_gates()` returns `[]` here by design, so no error message can name
        a gate. The perimeter must be unaffected: the step is still reported, and
        the sentence falls back to what the step does.
        """
        errors = condition_errors({"governance.yml": self.workflow(self.CONDITION, "")})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Test the check itself", errors[0])
        self.assertIn("runs a script", errors[0])

    def test_the_rule_survives_a_registry_that_will_not_load(self) -> None:
        """The clause the four siblings reach and this repository does not.

        It is exercised anyway, because the block is copied byte for byte and its
        `except` clause names `tomllib`. If that import were dropped here as
        unused, the one thing that would run on this path is a NameError — which
        is how a shared block quietly stops being shared.
        """
        original = verify.load_gates
        verify.load_gates = lambda: (_ for _ in ()).throw(FileNotFoundError())  # type: ignore[assignment]
        try:
            with temporary_workflows({"governance.yml": self.workflow(self.CONDITION, "")}):
                errors: list[str] = []
                verify.check_gate_conditions(errors)
        finally:
            verify.load_gates = original  # type: ignore[assignment]
        self.assertEqual(1, len(errors), errors)
        self.assertIn("Test the check itself", errors[0])


class TheRealWorkflows(unittest.TestCase):
    """The rule against what is committed, and the proof that it can fail.

    Every method here enumerates the workflow files **from the filesystem**, and
    that is the correction this class needed. The previous version looped over
    whatever the parser returned: a file the parser could not read produced no
    subtests, so the loop was empty and the assertions passed by having nothing
    to say. `assertGreater(checked, 0)` did not save it, because a second file
    satisfied it. A file the parser cannot read now fails a test.
    """

    def files(self) -> list[Path]:
        found = sorted(
            path
            for pattern in ("*.yml", "*.yaml")
            for path in (ROOT / ".github" / "workflows").glob(pattern)
        )
        self.assertGreater(len(found), 0, "this repository has no workflow files")
        return found

    def test_the_verifier_looks_at_every_file_on_disk(self) -> None:
        """The perimeter is the directory listing, not the parser's opinion."""
        self.assertEqual(self.files(), verify.workflow_files())

    def test_every_workflow_file_parses_into_a_workflow(self) -> None:
        """Non-empty, with triggers and with steps — for every file, by name.

        `parse_workflow` raises on a construct it cannot read, so a file that is
        merely unreadable fails here too.
        """
        for path in self.files():
            with self.subTest(workflow=path.name):
                document = verify.parse_workflow(path.read_text(encoding="utf-8"))
                self.assertNotEqual({}, document)
                self.assertNotEqual(set(), verify.triggers(document))
                jobs = verify.jobs_of(document)
                self.assertGreater(len(jobs), 0)
                for name, job in jobs.items():
                    if isinstance(job.get("uses"), str):
                        continue
                    self.assertGreater(len(verify.steps_of(job)), 0, f"job {name}")

    def test_the_committed_workflows_have_no_structural_problems(self) -> None:
        errors: list[str] = []
        verify.check_workflows(errors)
        self.assertEqual([], errors)

    def test_there_is_something_to_check(self) -> None:
        """Otherwise every assertion below is about an empty loop."""
        in_scope, problems = verify.pull_request_workflows()
        self.assertEqual([], problems)
        self.assertGreater(len(in_scope), 0, "no workflow runs on pull_request")

    def test_every_step_in_scope_names_cancelled(self) -> None:
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

        PyYAML drives the loop, on files listed from disk. That is deliberate:
        the case worth catching is the file this parser does not read, and a
        comparison iterating over *this* parser's output would agree with the
        nothing it produced. Now the reference says how many jobs and steps
        there are, and the subset has to match that number.
        """
        try:
            import yaml  # noqa: PLC0415
        except ImportError:  # pragma: no cover - depends on the machine
            self.skipTest("PyYAML is not installed")

        for path in self.files():
            text = path.read_text(encoding="utf-8")
            theirs = yaml.safe_load(text)
            mine = verify.parse_workflow(text)
            with self.subTest(workflow=path.name):
                # `on:` is YAML 1.1's `True` to PyYAML and the string "on" here,
                # which is a disagreement about a spelling and not about what
                # the file says. The jobs are where a real disagreement lives.
                self.assertEqual(sorted(theirs["jobs"]), sorted(verify.jobs_of(mine)))
            for name, reference_job in theirs["jobs"].items():
                with self.subTest(workflow=path.name, job=name):
                    ours = verify.steps_of(verify.jobs_of(mine)[name])
                    reference = reference_job.get("steps", [])
                    self.assertEqual(len(reference), len(ours))
                    for step, expected in zip(ours, reference):
                        for key in ("name", "id", "if", "uses"):
                            self.assertEqual(expected.get(key), step.get(key))
                        self.assertEqual(script(expected), script(step))

    def test_removing_any_one_condition_is_caught(self) -> None:
        """The proof kept as a test rather than as a paragraph in a report.

        One step at a time, every step in scope in every in-scope workflow: drop
        its `if:`, and the check must produce exactly one error, naming it. The
        files come from disk, and every file that runs on a pull request has to
        contribute at least one step — a workflow that contributes none is a
        workflow this test says nothing about, which is the state being removed.
        """
        files = {path.name: path.read_text(encoding="utf-8") for path in self.files()}
        in_scope, problems = verify.pull_request_workflows()
        self.assertEqual([], problems)
        self.assertGreater(len(in_scope), 0)
        for path, document in in_scope.items():
            name = path.name
            here = [
                step
                for job in verify.jobs_of(document).values()
                for _, step, _ in verify.steps_that_must_say_when_they_run(job)
            ]
            self.assertGreater(
                len(here), 0, f"{name} runs on pull_request and has no step in scope"
            )
            for step in here:
                label = str(step.get("name") or "")
                self.assertTrue(label, f"{name}: a step in scope has no name")
                with self.subTest(workflow=name, step=label):
                    broken = dict(files)
                    broken[name] = without_condition(files[name], label)
                    if len(here) > 1:
                        # The trap this rule exists for: the file still contains
                        # `cancelled()`, on another step, so a check that read it
                        # as one string would find one and pass. Only assertable
                        # where the file has a second step in scope to keep it.
                        self.assertIn("cancelled()", broken[name])
                    errors = condition_errors(broken)
                    self.assertEqual(1, len(errors), errors)
                    self.assertIn(label, errors[0])
                    self.assertIn(name, errors[0])


class TheSharedBlock(unittest.TestCase):
    """The parser and the rule are one block, copied byte for byte between five
    repositories, and the verifier states its hash in a comment.

    That claim had nothing behind it, which is how the folded-scalar fix came to
    exist in two of the four copies and not the other two: a divergence nobody
    could see. Here it is a failing test.

    This asserts the hash the file itself states, not a constant duplicated in
    this file, so there is one place to update when the block legitimately
    changes — and updating it is a deliberate act in a diff, which is the whole
    point.
    """

    START = b"# === Shared block"
    END = b"# === end of the shared block"
    STATED = re.compile(rb"^#\s+([0-9a-f]{64})\s*$", re.MULTILINE)

    def source(self) -> list[bytes]:
        # .gitattributes pins `eol=lf`, so this is the byte sequence the sed and
        # sha256sum command in the verifier's own comment reads. The `\r` is
        # stripped anyway, so a checkout that ignored the attribute reports a
        # divergence in the block and not in its line endings.
        return [line.rstrip(b"\r") for line in MODULE_PATH.read_bytes().split(b"\n")]

    def bounds(self) -> tuple[int, int]:
        lines = self.source()
        starts = [i for i, line in enumerate(lines) if line.startswith(self.START)]
        ends = [i for i, line in enumerate(lines) if line.startswith(self.END)]
        self.assertEqual(1, len(starts), "the shared block must open exactly once")
        self.assertEqual(1, len(ends), "the shared block must close exactly once")
        self.assertLess(starts[0], ends[0])
        return starts[0], ends[0]

    def test_the_block_matches_the_hash_the_file_states(self) -> None:
        start, end = self.bounds()
        block = b"\n".join(self.source()[start : end + 1]) + b"\n"
        stated = self.STATED.findall(MODULE_PATH.read_bytes())
        self.assertEqual(1, len(stated), "exactly one hash is stated for the block")
        self.assertEqual(
            stated[0].decode(),
            hashlib.sha256(block).hexdigest(),
            "the shared block has diverged from the hash written beside it; if "
            "the change is intended, make it in all five repositories and "
            "update the hash in each",
        )

    def test_the_rule_and_the_parser_are_inside_the_block(self) -> None:
        """A function moved out of the block is a function free to drift."""
        start, end = self.bounds()
        inside = b"\n".join(self.source()[start : end + 1])
        for name in (
            b"parse_block_scalar",
            b"parse_plain_scalar",
            b"parse_mapping",
            b"refuse_unsupported",
            b"parse_workflow",
            b"structural_problems",
            b"workflow_documents",
            b"pull_request_workflows",
            b"gate_named_in",
            b"dependency_ids",
            b"steps_that_must_say_when_they_run",
            b"check_workflows",
            b"check_gate_conditions",
        ):
            with self.subTest(function=name.decode()):
                self.assertIn(b"def " + name + b"(", inside)


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
        for name in ("check_public_content", "check_workflows", "check_gate_conditions"):
            with self.subTest(check=name):
                self.assertIn(f"{name}(", source)

    def test_this_repository_declares_no_gates(self) -> None:
        """Stated as a test so that adding a registry has to come past it.

        The empty registry is a decision with a paragraph of reasons above
        `load_gates()`. If someone adds one, the naming branch of the shared
        block starts firing on the real workflows and the tests above that lend
        it a registry stop being the only coverage of it — which is a change
        worth noticing rather than absorbing.
        """
        self.assertEqual([], verify.load_gates())
        self.assertEqual({}, verify.blocking_commands())


if __name__ == "__main__":
    unittest.main()
