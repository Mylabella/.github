#!/usr/bin/env python3
"""Check this public repository: what it publishes, and that its gates can speak.

Two rules live here, because this repository has one verifier.

The first is the one the README states: never add hostnames, addresses, file
system paths, secret names, credentials, infrastructure topology, or anything
specific to a deployment environment. It is the strictest rule in the
organization and it had no check, which made it the rule with the worst failure
mode and the least protection: this repository is public, and the private ones
it sets policy for are not.

The patterns look for the realistic mistake rather than for every conceivable
leak. The realistic mistake is a paragraph pasted out of a runbook.

The second rule is about the workflow that runs the first. A step with no `if:`
carries an implicit `success()`, so a single earlier failure skips it — and in
the run summary a skipped step and a passing step look alike. "The content check
did not object" then reads as true about a check that never started. Every gate
step in a pull-request workflow therefore has to say when it runs, and
`check_gate_conditions` below refuses one that does not.

Only the standard library, so it runs anywhere python3 does.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

# The checker and its tests contain the patterns themselves, and a rule file is
# not policy content. Everything else published here is in scope.
EXCLUDED_PREFIXES = ("tools/", "tests/")

# Hosts that may legitimately appear in a link. Anything else is either a
# deployment detail or a reference that should be named rather than linked.
ALLOWED_HOSTS = frozenset(
    {
        "github.com",
        "docs.github.com",
        "www.contributor-covenant.org",
        "contributor-covenant.org",
        "creativecommons.org",
        "www.apache.org",
        "opensource.org",
    }
)

URL = re.compile(r"https?://([A-Za-z0-9._-]+)")

CHECKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
        "looks like an IP address",
    ),
    (
        re.compile(r"(?<![\w.])/(?:srv|etc|var|opt|root|home|mnt|usr/local)/"),
        "looks like an absolute path on a real machine",
    ),
    (
        re.compile(r"\b[A-Za-z]:\\"),
        "looks like a Windows filesystem path",
    ),
    (
        re.compile(r"\.ts\.net\b|\btailnet\b|\btailscale\b", re.IGNORECASE),
        "names the private network",
    ),
    (
        # The character class has to include the underscore, or a name with more
        # than one segment slips through: POSTGRES_SUPERUSER_PASSWORD has no word
        # boundary before SUPERUSER, so an underscore-free class can never reach
        # the suffix. The test for this pattern is the reason that is known.
        re.compile(r"\b[A-Z][A-Z0-9_]{2,}_(?:TOKEN|PASSWORD|SECRET|KEY|CREDENTIALS?)\b"),
        "looks like the name of a secret",
    ),
    (
        re.compile(r"\b[A-Za-z0-9-]+\.(?:internal|local|lan|home|intranet)\b"),
        "looks like a private hostname",
    ),
    (
        re.compile(r"\b[a-z_][a-z0-9_-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "looks like an account on a specific host",
    ),
    (
        # GOVERNANCE.md carried "…247 tokens truncated…" in the middle of a
        # sentence, in the public repository, for as long as this file has
        # existed — and every check here was green on it, because they all look
        # for things that should not be published rather than for evidence that
        # the text was never finished.
        #
        # Two sentences fused into one is not something a reader reports; it is
        # something a reader assumes they misread. So the machine says it.
        re.compile(
            r"…\s*\d+\s+tokens?\s+truncated\s*…"
            r"|\[\s*(?:\.\.\.|…)?\s*\d+\s+(?:lines?|tokens?|chars?|characters?)\s+truncated"
            r"|\.\.\.\s*\[\s*truncated"
            r"|\[truncated\]"
            r"|<<<<<<<\s|>>>>>>>\s|^=======$",
            re.IGNORECASE | re.MULTILINE,
        ),
        "carries a truncation or merge-conflict marker: the text was never finished",
    ),
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    names = [n for n in result.stdout.decode("utf-8").split("\0") if n]
    return [ROOT / n for n in names if not n.startswith(EXCLUDED_PREFIXES)]


def scan(text: str) -> list[tuple[int, str, str]]:
    """Return (line number, matched text, reason) for every finding."""
    findings: list[tuple[int, str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, reason in CHECKS:
            for match in pattern.finditer(line):
                findings.append((number, match.group(0), reason))
        for match in URL.finditer(line):
            host = match.group(1).lower()
            if host not in ALLOWED_HOSTS:
                findings.append((number, host, "links to an unexpected host"))
    return findings


def check_public_content(files: list[Path], errors: list[str]) -> None:
    for path in files:
        try:
            text = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for number, matched, reason in scan(text):
            errors.append(f"{relative}:{number}: {reason}: {matched}")


# ---------------------------------------------------------------------------
# A YAML subset, parsed here rather than with PyYAML.
#
# The rule below has to read every step of a workflow separately. Reading the
# file as one string and looking for `cancelled()` anywhere in it would pass on
# exactly the state this check exists to refuse: one conditioned step and three
# unconditioned ones below it.
#
# PyYAML would do the parsing and is not available. This verifier is invoked as
# a bare `python3 tools/quality/verify_public_content.py`, and governance.yml
# installs nothing before calling it — so importing PyYAML makes the check
# either a dependency this repository does not have or, behind a try/except, a
# check that skips on the one machine where it matters. A check that skips is
# the failure this whole rule is about.
#
# The subset is what a workflow file is: block mappings, block sequences, block
# scalars (`|`, `>`), one-line flow sequences, quoted and plain scalars, and
# comments. Anchors, aliases, flow mappings and multi-document files are not
# supported; none of them appears in a GitHub workflow, and any of them would
# produce a parse this check reports as "no steps" — visible rather than silent,
# because a workflow with no steps also has no gate step to skip.
#
# tests/test_verify_public_content.py asks PyYAML for a second opinion on these
# files wherever PyYAML happens to be installed. That test skips where it is
# not, which is why it is a second opinion and not the guard.
# ---------------------------------------------------------------------------

BLOCK_SCALAR = re.compile(r"^[|>][+-]?\d*$")

# A sequence item that opens a mapping: `- name: x`, but not `- main` and not
# `- 5432:5432`, where the colon is not a key separator.
SEQUENCE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*\s*:(\s|$)")


def strip_comment(line: str) -> str:
    """Drop a trailing `# ...` that is not inside a quoted scalar."""
    quote: str | None = None
    index = 0
    while index < len(line):
        character = line[index]
        if quote is None:
            if character in "'\"":
                quote = character
            elif character == "#" and (index == 0 or line[index - 1] in " \t"):
                return line[:index].rstrip()
        elif character == quote:
            quote = None
        elif quote == '"' and character == "\\":
            index += 1
        index += 1
    return line.rstrip()


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def next_significant(lines: list[str], index: int) -> int:
    """The next line that is neither blank nor only a comment."""
    while index < len(lines) and not strip_comment(lines[index]).strip():
        index += 1
    return index


def scalar(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        body = text[1:-1]
        return body.replace("''", "'") if text[0] == "'" else body
    return text


def flow_sequence(text: str) -> list[str]:
    """`[push, pull_request]`. Commas inside quotes do not occur in a workflow."""
    return [scalar(item) for item in text.strip()[1:-1].split(",") if item.strip()]


def parse_block_scalar(lines: list[str], index: int, indent: int) -> tuple[str, int]:
    """Everything indented past `indent`, joined.

    Relative indentation inside the scalar is dropped: this exists so that a
    `run:` script is one string to search, and so that a line inside it can never
    be mistaken for structure. A `# comment` in a shell script is script, and
    `echo '- name: two'` is not a second step.
    """
    collected: list[str] = []
    while index < len(lines):
        line = lines[index]
        if line.strip() and indent_of(line) <= indent:
            break
        collected.append(line.strip())
        index += 1
    return "\n".join(collected), index


def parse_mapping(lines: list[str], index: int, indent: int) -> tuple[dict[str, object], int]:
    mapping: dict[str, object] = {}
    while True:
        index = next_significant(lines, index)
        if index >= len(lines):
            break
        line = strip_comment(lines[index])
        if indent_of(line) != indent or line.strip().startswith("-"):
            break
        key, separator, rest = line.strip().partition(":")
        if not separator:
            break
        index += 1
        rest = rest.strip()
        value: object
        if not rest:
            value, index = parse_value(lines, index, indent)
        elif BLOCK_SCALAR.match(rest):
            value, index = parse_block_scalar(lines, index, indent)
        elif rest.startswith("["):
            value = flow_sequence(rest)
        else:
            value = scalar(rest)
        mapping[scalar(key)] = value
    return mapping, index


def parse_sequence(lines: list[str], index: int, indent: int) -> tuple[list[object], int]:
    items: list[object] = []
    while True:
        index = next_significant(lines, index)
        if index >= len(lines):
            break
        line = strip_comment(lines[index])
        stripped = line.strip()
        if indent_of(line) != indent or not (stripped == "-" or stripped.startswith("- ")):
            break
        content = stripped[1:].strip()
        if not content:
            value, index = parse_value(lines, index + 1, indent)
            items.append(value)
            continue
        if SEQUENCE_KEY.match(content):
            # Line the first key up with the keys under it, so the item is an
            # ordinary mapping from here on. `lines` is this parse's own copy.
            column = indent + 1 + (len(line[indent + 1 :]) - len(line[indent + 1 :].lstrip(" ")))
            lines[index] = " " * column + content
            value, index = parse_mapping(lines, index, column)
            items.append(value)
            continue
        items.append(scalar(content))
        index += 1
    return items, index


def parse_value(lines: list[str], index: int, indent: int) -> tuple[object, int]:
    """The value of a key written at `indent` whose line ended after the colon.

    A block sequence may sit at the key's own column or deeper; a nested mapping
    must be deeper. Anything shallower means the key had no value.
    """
    index = next_significant(lines, index)
    if index >= len(lines):
        return None, index
    line = strip_comment(lines[index])
    column = indent_of(line)
    stripped = line.strip()
    if column >= indent and (stripped == "-" or stripped.startswith("- ")):
        return parse_sequence(lines, index, column)
    if column > indent:
        return parse_mapping(lines, index, column)
    return None, index


def parse_workflow(text: str) -> dict[str, object]:
    lines = [line.rstrip("\r") for line in text.splitlines()]
    index = next_significant(lines, 0)
    if index >= len(lines):
        return {}
    document, _ = parse_mapping(lines, index, indent_of(strip_comment(lines[index])))
    return document


def workflow_files() -> list[Path]:
    if not WORKFLOWS.is_dir():
        return []
    return sorted(
        path
        for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in (".yml", ".yaml")
    )


def triggers(document: dict[str, object]) -> set[str]:
    """The event names under `on:`, however it is written."""
    raw = document.get("on")
    if isinstance(raw, dict):
        return {str(key) for key in raw}
    if isinstance(raw, list):
        return {str(item) for item in raw}
    if isinstance(raw, str) and raw:
        return {raw}
    return set()


def jobs_of(document: dict[str, object]) -> dict[str, dict[str, object]]:
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return {}
    return {name: job for name, job in jobs.items() if isinstance(job, dict)}


def steps_of(job: dict[str, object]) -> list[dict[str, object]]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def pull_request_workflows() -> dict[Path, dict[str, object]]:
    """The workflows a pull request runs, including the ones it calls.

    Release and deploy workflows are out of scope on purpose: there the sequence
    is the point and stopping at the first failure is correct. A `workflow_call`
    file is in scope by transitivity — its steps run on the pull request that
    called it, so its gates can be silenced the same way — and it is found by
    following the call rather than by assuming no such file exists. This
    repository has no reusable workflow today; the code resolves that rather
    than the reader having to remember it.
    """
    documents = {}
    for path in workflow_files():
        try:
            documents[path] = parse_workflow(path.read_text(encoding="utf-8"))
        except OSError:
            continue

    by_name = {path.name: path for path in documents}
    selected = {
        path for path, document in documents.items() if "pull_request" in triggers(document)
    }

    pending = list(selected)
    while pending:
        for job in jobs_of(documents[pending.pop()]).values():
            uses = job.get("uses")
            if not isinstance(uses, str) or not uses.startswith("./"):
                continue
            # A reusable workflow in the same repository lives in this directory
            # by GitHub's rule, so the file name identifies it.
            called = by_name.get(Path(uses.split("@")[0]).name)
            if called is not None and called not in selected:
                selected.add(called)
                pending.append(called)

    return {path: documents[path] for path in sorted(selected)}


def gate_in_step(step: dict[str, object]) -> str | None:
    """The name of the gate this step runs, or None because it runs no gate.

    This is the definition, written out rather than left to judgement.

    **A step runs a gate when it has a `run:` script.** Sibling repositories
    consult `tools/quality/gates.toml` and match a blocking gate's command
    verbatim; this repository has no registry, because it has no build and no
    toolchain — it publishes text and checks it. Every `run:` in its workflow is
    a check that can fail the pull request, and the only step that is not one is
    the checkout, which is a `uses:` action and a dependency of the checks rather
    than a check itself.

    The classification errs towards including a step, and that is the safe
    direction. A step that turned out to be a producer rather than a gate carries
    `!cancelled()` harmlessly: it runs anyway, and whatever needs it names it by
    id. Excluding a step, by contrast, is the silence this rule exists to refuse.

    The gate is named by the step's `id:` where it has one, and otherwise by the
    first command in its script — enough for the error message to say which check
    would have been skipped, not merely which step.
    """
    script = step.get("run")
    if not isinstance(script, str):
        return None
    identifier = str(step.get("id", "")).strip()
    if identifier:
        return identifier
    for line in script.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


def check_gate_conditions(errors: list[str]) -> None:
    """Refuse a gate step that an earlier failure would silence.

    A step with no `if:` carries an implicit `success()`, so it runs only while
    nothing before it has failed. For a build that is right. For a series of
    gates it is not: gates are independent objections, and a run that stops at
    the first one tells the author about one objection per push. Worse, in the
    run summary a skipped step and a passing step look alike, so "the branch-name
    check did not object" reads as true about a check that never started.

    So every gate step names `cancelled()`, and the mention is the rule rather
    than a fixed formula — `!cancelled() && steps.checkout.outcome == 'success'`
    is a gate declaring a real dependency, which is the encouraged form.
    `always()` is not the same thing and does not satisfy this: this workflow
    sets `cancel-in-progress`, and under `always()` a job already replaced by a
    newer push keeps working.
    """
    for path, document in pull_request_workflows().items():
        relative = path.relative_to(ROOT).as_posix()
        for job_name, job in jobs_of(document).items():
            for position, step in enumerate(steps_of(job), start=1):
                gate = gate_in_step(step)
                if gate is None:
                    continue
                if "cancelled()" in str(step.get("if", "")):
                    continue
                label = str(step.get("name") or f"{job_name} step {position}")
                errors.append(
                    f"{relative}: step {label!r} runs gate {gate} without a "
                    f"condition naming cancelled() — the implicit default is "
                    f"success(), so one earlier failure skips this gate and the "
                    f"summary reads as though it agreed. Give it "
                    f"if: ${{{{ !cancelled() }}}}, and name any real dependency "
                    f"with && steps.<id>.outcome == 'success'"
                )


def main() -> int:
    try:
        files = tracked_files()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"ERROR: could not list tracked files: {error}", file=sys.stderr)
        return 2

    content: list[str] = []
    workflows: list[str] = []
    check_public_content(files, content)
    check_gate_conditions(workflows)

    if content:
        for error in sorted(set(content)):
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            "\nThis repository is public and sets policy for private ones. "
            "Describe the rule, not the machine.",
            file=sys.stderr,
        )
    if workflows:
        for error in sorted(set(workflows)):
            print(f"ERROR: {error}", file=sys.stderr)
    if content or workflows:
        return 1

    scoped = len(pull_request_workflows())
    print(
        f"Public content check passed for {len(files)} files, and every gate "
        f"step in {scoped} pull-request workflow(s) says when it runs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
