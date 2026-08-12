#!/usr/bin/env python3
"""Check this public repository: what it publishes, and that its gates can speak.

Three rules live here, because this repository has one verifier, and they are
numbered below in the order they are stated.

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
did not object" then reads as true about a check that never started. Every step
in a pull-request workflow that could be silenced this way therefore has to say
when it runs, and `check_gate_conditions` below refuses one that does not.

Which steps those are is one sentence, and it is the same sentence in all five
repositories: **a step runs a gate when it runs a script — when it has a `run:`
key** — and a `uses:` step joins it when another step names it as a dependency,
unless it is the job's first step. See steps_that_must_say_when_they_run().

Which *jobs* those steps have to be in is job_can_run_on_a_pull_request(). A job
a pull request can never start cannot silence a gate on one, so it is outside
the rule; a job condition this code cannot decide is inside it, because an
exemption nobody can evaluate would be an opt-out anyone could write in one
line. This repository has no exempt job today — its single workflow has a single
job with no `if:` of its own — and the function is here because it is in the
shared block, where it is load-bearing for the siblings that do.

The third rule is about this file. Everything the second rule rests on — the
YAML subset and the definition above — is a shared block copied byte for byte
between the five repositories, and a construct it cannot read is an error rather
than an empty result. The reason is written at the head of that block.

Only the standard library, so it runs anywhere python3 does.
"""

from __future__ import annotations

import re
import subprocess
import sys

# Named in one `except` clause inside the shared block, on the path where the
# gate registry will not load. This repository has no registry (see below), so
# that path is unreachable here — but the block is copied verbatim, and a name
# it can reach must resolve, or the one thing that would run there is a
# NameError. Standard library since 3.11, so this costs nothing.
import tomllib
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
# The gate registry, which this repository does not have.
#
# The shared block below consults `load_gates()` for exactly one purpose: to
# *name* the gate a step runs, so that an error reads "runs gate
# contract-current" and sends someone to the right place. The four sibling
# repositories keep that registry in tools/quality/gates.toml. This one has no
# build and no toolchain — it publishes text and checks it — so there is nothing
# for a registry to enumerate here, and writing one anyway would create a second
# hand-kept list of this repository's gates, free to drift away from
# governance.yml with nothing to notice.
#
# So the registry is empty. Empty is not a degraded mode: it is a branch the
# shared block already takes and already has a test for. Since C2 the perimeter
# does not depend on the registry at all — that is the point of the change — so
# an empty one costs a gate's name in one clause of one error message and
# nothing else. The step, the file and the reason are still there.
# ---------------------------------------------------------------------------


def load_gates() -> list[dict[str, object]]:
    """No gates are declared in this repository; see the note above."""
    return []


# The shared block that follows is byte-identical to the copies in
# agentic-development-template, mylabella-console, RicettediMarilena and
# platform-mylabella-vps. Its own header gives the command that proves it, and
# names verify_repository.py, because that is what the file is called in those
# four. Here it is:
#
#     sed -n '/^# === Shared block/,/^# === end of the shared block/p' \
#       tools/quality/verify_public_content.py | sha256sum
#
# and it must print
#
#     96e628812dbe745b7d66a8b5fe069a631a64743d47275d7113bf37553cebc4d5
#
# The file name is the only thing that differs, and it is written out here,
# outside the block, precisely so that the block itself stays byte-identical: a
# real divergence then shows up as a difference in that one hash instead of
# hiding behind a difference that was always expected.


# === Shared block: the YAML subset, and the rule about when a step runs ======
#
# From this banner to the end of check_gate_conditions() the code is
# byte-identical in agentic-development-template, mylabella-console,
# RicettediMarilena, platform-mylabella-vps and .github. That is not tidiness.
# These five copies drifted once already: the folded-scalar fix — `run: >-`
# joined with newlines instead of spaces, so a gate command written over two
# lines matched nothing and its step became exempt — landed in two repositories
# and was missing from the other three, and nothing could show it because there
# was nothing to diff. Copy this block whole. If one repository ever needs to
# differ, write the difference *here*, with its reason, so the next divergence
# is still one hunk of one diff. Two copies are the same when this agrees:
#
#     sed -n '/^# === Shared block/,/^# === end of the shared block/p' \
#       tools/quality/verify_repository.py | sha256sum
#
# The rule below has to read every step of a workflow separately. Reading the
# file as one string and looking for `cancelled()` anywhere in it would pass on
# exactly the state this check exists to refuse: one conditioned step and eight
# unconditioned ones below it.
#
# PyYAML would do the parsing and is not available. This verifier is invoked as
# a bare `python3 tools/quality/verify_repository.py` — governance.yml installs
# nothing before calling it, and neither does the CI of a generated project — so
# importing PyYAML makes the check either a dependency this repository does not
# have or, with a try/except around the import, a check that skips on the
# machine where it matters. A check that skips is the failure this whole rule is
# about.
#
# The subset is what a workflow file is: block mappings, block sequences, block
# scalars (`|` kept line by line, `>` folded onto one line with spaces, which is
# what YAML does and what the first version of this parser got wrong), plain and
# quoted scalars including the ones that run past the end of their line,
# one-line flow sequences, comments, and a leading `---`.
#
# Everything else is refused by name, with a file and a line. That refusal is
# the reason this block was rewritten. The first version treated what it could
# not read as absence, which in this check is indistinguishable from approval:
#
#   - a file beginning with `---` — legal YAML, and what yamllint's
#     document-start rule requires — parsed as `{}`. No `on:`, therefore not a
#     pull-request workflow, therefore no gate steps, therefore green;
#   - a long `if:` wrapped onto a second line without `>-` ended the mapping, so
#     the step lost its `run:` and every step below it disappeared. An
#     unconditioned gate became invisible rather than reported;
#   - a `run: >-` command written over two lines was joined with a newline, so
#     it no longer matched the registry verbatim and its step left the perimeter.
#
# Each of those is the original defect — an absence that reads as a consent —
# moved one level up, into the check written to remove it. So: a construct this
# parser does not know is an error, not a shrug, and a workflow that parses into
# something unrecognisable (no `on:`, no `jobs:`, a job with no steps) is an
# error too. The fourth unknown construct will arrive. When it does it will stop
# a pull request by name instead of quietly emptying a check.
#
# tests/test_verify_repository.py asks PyYAML for a second opinion on these
# files wherever PyYAML happens to be installed, and enumerates the files from
# the filesystem rather than from this parser — so a file the parser refuses to
# read fails a test instead of leaving the loop empty. That test skips where
# PyYAML is not installed, which is why it is a second opinion and not the
# guard.
# ---------------------------------------------------------------------------

BLOCK_SCALAR = re.compile(r"^[|>][+-]?\d*$")

# A sequence item that opens a mapping: `- name: x`, but not `- main` and not
# `- 5432:5432`, where the colon is not a key separator.
SEQUENCE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*\s*:(\s|$)")

# `---` and `...`. The first opens a document and is supported; a second one
# means a multi-document file, which is not.
DOCUMENT_MARKER = re.compile(r"^(---|\.\.\.)(\s|$)")

# `&anchor` or `*alias` where a value begins. Deliberately narrow: `rm *` and
# `*.py` are not aliases, and a check that thought they were would refuse files
# it can read perfectly well.
ANCHOR_OR_ALIAS = re.compile(r"^[&*][A-Za-z0-9_][A-Za-z0-9_-]*(\s|$)")

# `steps.<id>.` inside a condition — the way one step declares that it depends
# on another. Used to find the steps something behind them depends on.
DEPENDENCY = re.compile(r"steps\.([A-Za-z_][A-Za-z0-9_-]*)\.")

# `github.event_name == 'push'` and `github.event_name != 'pull_request'`: the
# only two shapes of a job condition job_can_run_on_a_pull_request() claims to
# understand. Anchored at both ends on purpose — a trailing bracket, a second
# comparison or anything else around it means something is going on that this
# regular expression is not reading, and then the job keeps its obligations.
EVENT_NAME_TEST = re.compile(
    r"^github\.event_name\s*(==|!=)\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\2$"
)


class UnsupportedWorkflow(Exception):
    """A workflow construct this parser does not read, refused instead of guessed.

    Carries a line number and a remedy, because "cannot parse" without either is
    a message whose only available response is to delete the check.
    """

    def __init__(self, line: int, problem: str, remedy: str) -> None:
        super().__init__(f"line {line}: {problem} — {remedy}")
        self.line = line
        self.problem = problem
        self.remedy = remedy


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


def parse_block_scalar(
    lines: list[str], index: int, indent: int, *, folded: bool = False
) -> tuple[str, int]:
    """Everything indented past `indent`, joined.

    Relative indentation inside the scalar is dropped: this exists so that a
    `run: |` script is one string to search, and so that a line inside it can
    never be mistaken for structure. A `# comment` in a shell script is script.

    `folded` is the `>` form, and it is not cosmetic. YAML folds those lines onto
    one line separated by single spaces, and a blank line is where a fold
    becomes a newline. Joining them with newlines instead — which this function
    did until a gate command written as

        run: >-
          python3 tools/quality/check_contracts.py
          --strict

    stopped matching the registry verbatim — silently removes that step from the
    perimeter of check_gate_conditions. The step keeps running the gate; the
    check stops seeing that it does.
    """
    collected: list[str] = []
    while index < len(lines):
        line = lines[index]
        if line.strip() and indent_of(line) <= indent:
            break
        collected.append(line.strip())
        index += 1
    if not folded:
        return "\n".join(collected), index
    paragraphs: list[list[str]] = [[]]
    for piece in collected:
        if piece:
            paragraphs[-1].append(piece)
        elif paragraphs[-1]:
            paragraphs.append([])
    return "\n".join(" ".join(paragraph) for paragraph in paragraphs if paragraph), index


def parse_plain_scalar(
    lines: list[str], index: int, indent: int, first: str
) -> tuple[str, int]:
    """A value written after the colon, plus the deeper lines that continue it.

    A scalar that runs past the end of its line is ordinary YAML and needs no
    marker: everything indented deeper than its key belongs to it, folded onto
    one line with single spaces. It is what happens to anyone who wraps a long
    condition:

        if: ${{ !cancelled() &&
          steps.checkout.outcome == 'success' }}

    Before this function existed the second line matched nothing the parser
    expected, so the mapping ended there — the step lost its `run:` and every
    step after it vanished from the document. A gate step with no condition
    below that point could not be reported, because it could not be seen. That
    is the likelier of the two silent parses this parser was rewritten for: the
    other one needs a `---` at the top of the file, this one needs only somebody
    wrapping a long line.
    """
    pieces = [first]
    while True:
        index = next_significant(lines, index)
        if index >= len(lines):
            break
        line = strip_comment(lines[index])
        if indent_of(line) <= indent:
            break
        pieces.append(line.strip())
        index += 1
    return scalar(" ".join(pieces)), index


def parse_mapping(lines: list[str], index: int, indent: int) -> tuple[dict[str, object], int]:
    mapping: dict[str, object] = {}
    while True:
        index = next_significant(lines, index)
        if index >= len(lines):
            break
        line = strip_comment(lines[index])
        column = indent_of(line)
        stripped = line.strip()
        if column < indent or (column == indent and stripped.startswith("-")):
            # A dedent ends the mapping, and so does a sequence item at the
            # mapping's own column. Both are how block YAML says "this mapping
            # is over"; neither is a surprise.
            break
        if column > indent:
            # Deeper than the key column, and not a continuation — parse_value,
            # parse_block_scalar and parse_plain_scalar have already consumed
            # every legitimate deeper line by the time control returns here.
            # Whatever this is, the parser does not know where it belongs, and
            # guessing means dropping the rest of the file.
            raise UnsupportedWorkflow(
                index + 1,
                f"a line indented {column} spaces where a key at column {indent} "
                f"was expected",
                "check the indentation; if the file is right, this parser is "
                "missing a construct and needs it added with a test",
            )
        key, separator, rest = stripped.partition(":")
        if not separator:
            raise UnsupportedWorkflow(
                index + 1,
                "a line that is neither `key: value` nor a `- ` sequence item",
                "this parser reads block mappings and block sequences; write "
                "the value out in that form, or teach parse_mapping() the "
                "construct and prove the new case in tests/",
            )
        index += 1
        rest = rest.strip()
        value: object
        if not rest:
            value, index = parse_value(lines, index, indent)
        elif BLOCK_SCALAR.match(rest):
            value, index = parse_block_scalar(lines, index, indent, folded=rest[0] == ">")
        elif rest.startswith("["):
            value = flow_sequence(rest)
        else:
            value, index = parse_plain_scalar(lines, index, indent, rest)
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


def refuse_unsupported(lines: list[str]) -> None:
    """Raise on the first construct this parser does not read.

    A single pass over the structural lines — the bodies of block scalars are
    skipped, because a shell script is allowed to contain anything. Each refusal
    names the construct, so the message is actionable by someone who has never
    read this file: they either rewrite the two lines of YAML or add the
    construct here with a test, and both are better than a check that quietly
    covers one file fewer than it did yesterday.
    """
    index = 0
    content = False
    while index < len(lines):
        raw = lines[index]
        number = index + 1
        indentation = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in indentation:
            raise UnsupportedWorkflow(
                number,
                "a tab in the indentation",
                "YAML forbids tabs for indentation and this parser counts "
                "spaces; replace the tab with spaces",
            )
        line = strip_comment(raw)
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("%"):
            raise UnsupportedWorkflow(
                number,
                "a YAML directive (%YAML, %TAG)",
                "GitHub does not need one; remove the directive",
            )
        if DOCUMENT_MARKER.match(stripped):
            # One `---` before anything else opens the only document there is.
            # Anything after content has started means a second document.
            if content or stripped.startswith("..."):
                raise UnsupportedWorkflow(
                    number,
                    "a second YAML document in one workflow file",
                    "GitHub reads only the first document; put one workflow in "
                    "one file. This parser refuses rather than reading the "
                    "first and ignoring the rest, which is how a step ends up "
                    "unchecked and nobody is told",
                )
            index += 1
            continue
        content = True
        item = stripped
        if item.startswith("- "):
            item = item[2:].strip()
        elif item == "-":
            index += 1
            continue
        _, separator, rest = item.partition(":")
        value = rest.strip() if separator else item
        if ANCHOR_OR_ALIAS.match(value):
            raise UnsupportedWorkflow(
                number,
                f"a YAML anchor or alias ({value.split()[0]})",
                "this parser does not resolve them, and resolving them wrongly "
                "would change which steps exist; write the value out in full, "
                "or teach this parser anchors and prove the new case in tests/",
            )
        if value.startswith("{"):
            raise UnsupportedWorkflow(
                number,
                "a flow mapping ({...})",
                "write it as a block mapping on the following lines",
            )
        if value.startswith("[") and "]" not in value:
            raise UnsupportedWorkflow(
                number,
                "a flow sequence spanning more than one line",
                "keep a `[a, b]` sequence on one line, or write it as a block "
                "sequence with `- ` items",
            )
        if separator and BLOCK_SCALAR.match(value):
            # The body is content, not structure. Skip it wholesale: a `run:`
            # script may legally contain tabs, braces, asterisks and `---`.
            body_indent = indent_of(line)
            index += 1
            while index < len(lines) and (
                not lines[index].strip() or indent_of(lines[index]) > body_indent
            ):
                index += 1
            continue
        index += 1


def parse_workflow(text: str) -> dict[str, object]:
    """The document, or UnsupportedWorkflow naming what stopped it.

    Never `{}` for a file that has content: that return value was the shape of
    the bug. A caller cannot tell an empty workflow from an unread one, so this
    does not offer it the chance to guess.
    """
    lines = [line.rstrip("\r") for line in text.splitlines()]
    refuse_unsupported(lines)
    index = next_significant(lines, 0)
    if index < len(lines) and DOCUMENT_MARKER.match(strip_comment(lines[index]).strip()):
        # A leading `---` is legal, common, and required by yamllint's
        # document-start rule and by ansible-lint. The first version of this
        # parser stopped dead on it and returned `{}`, which every caller read
        # as "not a workflow".
        index = next_significant(lines, index + 1)
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


def under_root(path: Path) -> str:
    """A workflow path as the repository names it.

    Falls back to the full path when the file is not under ROOT, which happens
    when a caller has pointed WORKFLOWS at one tree and ROOT at another. An
    honest absolute path is better than an exception from a formatting detail.
    """
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def structural_problems(relative: str, document: dict[str, object]) -> list[str]:
    """What a workflow must contain for this verifier to have read it at all.

    Not a style rule about workflows — a rule about this parser. A GitHub
    workflow has triggers, jobs and steps; if what came back has none of them,
    the file was not read, whatever the reason. Reporting that is the difference
    between a check with a blind spot and a check that says where its blind spot
    is.
    """
    problems: list[str] = []
    unread = (
        "if the file is correct, this parser is what is wrong: add the "
        "construct it is missing and prove it in tests/. Do not narrow the "
        "check to the files it happens to read"
    )
    if not document:
        return [f"{relative}: parsed as an empty document — {unread}"]
    if not triggers(document):
        problems.append(f"{relative}: no `on:` triggers were read from it — {unread}")
    raw_jobs = document.get("jobs")
    if not isinstance(raw_jobs, dict) or not raw_jobs:
        problems.append(f"{relative}: no `jobs:` were read from it — {unread}")
        return problems
    for name, job in raw_jobs.items():
        if not isinstance(job, dict):
            problems.append(f"{relative}: job {name} was not read as a mapping — {unread}")
            continue
        if isinstance(job.get("uses"), str):
            # A job that calls a reusable workflow has no steps of its own, by
            # GitHub's rule. Its steps are checked in the file it calls, which
            # pull_request_workflows() follows.
            continue
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append(f"{relative}: job {name} has no steps — {unread}")
            continue
        for position, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                problems.append(
                    f"{relative}: job {name} step {position} was not read as a "
                    f"mapping — {unread}"
                )
    return problems


def workflow_documents() -> tuple[dict[Path, dict[str, object]], list[str]]:
    """Every workflow file, parsed, and everything that went wrong doing it.

    The problems are returned rather than swallowed. A file this cannot read is
    reported as an error of the verifier — it is not quietly dropped from the
    set of files the rules apply to, which is what the previous version did to
    any workflow beginning with `---`.
    """
    documents: dict[Path, dict[str, object]] = {}
    problems: list[str] = []
    for path in workflow_files():
        relative = under_root(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"{relative}: cannot be read: {exc}")
            continue
        try:
            document = parse_workflow(text)
        except UnsupportedWorkflow as exc:
            problems.append(f"{relative}:{exc.line}: {exc.problem} — {exc.remedy}")
            continue
        problems.extend(structural_problems(relative, document))
        documents[path] = document
    return documents, problems


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


def pull_request_workflows() -> tuple[dict[Path, dict[str, object]], list[str]]:
    """The workflows a pull request runs, including the ones it calls.

    Release and deploy workflows are out of scope on purpose: there the sequence
    is the point and stopping at the first failure is correct. A `workflow_call`
    file is in scope by transitivity — its steps run on the pull request that
    called it, so its gates can be silenced the same way — and it is found by
    following the call rather than by assuming no such file exists.

    Returns the problems from workflow_documents() alongside the selection. A
    file that could not be parsed is not in the selection and must not therefore
    be out of scope: the caller reports it.
    """
    documents, problems = workflow_documents()

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

    return {path: documents[path] for path in sorted(selected)}, problems


def job_can_run_on_a_pull_request(job: dict[str, object]) -> bool:
    """Whether a `pull_request` event could reach this job's steps at all.

    The perimeter of check_gate_conditions is the jobs a pull request can
    actually run, and this is the second half of it: pull_request_workflows()
    picks the files, this picks the jobs inside them.

    **Why a job can be outside it.** A job GitHub will never start on a pull
    request cannot silence a gate on one, and asking it for `!cancelled()` is
    not merely noise — it is wrong on the merits. mylabella-console's `publish`
    job carries `if: github.event_name == 'push' && github.ref ==
    'refs/heads/main'`, and inside it the sequence build -> read the digest the
    image will report -> record that digest is precisely the case where the
    order *is* the point and stopping at the first failure is correct: reading a
    digest after a failed build reads a stale one, and recording it publishes a
    lie. That is the same exemption release and deploy already have one level
    up, in pull_request_workflows(); this grants it one level down, on the same
    grounds, to a job a pull request cannot reach.

    **Decidable, or in scope.** Exactly one form is read: a condition with no
    parentheses and no `||`, one of whose `&&` conjuncts is literally
    `github.event_name == '<event>'` for an event other than pull_request, or
    `github.event_name != 'pull_request'`. Such a condition is false on every
    pull request whatever else it says, because a false conjunct cannot be
    recovered by the conjuncts around it. That is the whole of what this
    function knows.

    **Everything it cannot judge stays in scope.** This is the half that keeps
    the rule from becoming its own escape hatch, and it is worth being explicit
    about: an exemption is a way to stop being checked, so an unreadable
    exemption must not work. `if: ${{ env.SOMETHING == 'x' }}` is a condition
    nothing here can evaluate, so the job wearing it keeps every obligation it
    had. `||` and parentheses end the reading rather than being approximated,
    because `github.event_name == 'push' || github.event_name ==
    'pull_request'` contains the exempting text verbatim and is true on a pull
    request — a reader that matched on containment would exempt exactly the job
    it must not. Failing closed here costs one `!cancelled()` on a job that did
    not need it; failing open costs a silenced gate nobody is told about.

    This decides whose *steps* are checked. It deliberately does not prune the
    reusable workflows pull_request_workflows() follows: a called file can have
    a second caller, and keeping it in scope errs towards checking more.
    """
    raw = job.get("if")
    if not isinstance(raw, str) or not raw.strip():
        # No condition is not an exemption: the job runs on every event the
        # workflow is triggered by, and one of them is pull_request.
        return True

    condition = raw.strip()
    if condition.startswith("${{") and condition.endswith("}}"):
        condition = condition[3:-2].strip()
    if "${{" in condition or "}}" in condition:
        # An expression spliced into surrounding text, or more than one of them.
        # Not something to take apart with str.split.
        return True
    if "||" in condition or "(" in condition or ")" in condition:
        return True

    for conjunct in condition.split("&&"):
        match = EVENT_NAME_TEST.match(conjunct.strip())
        if match is None:
            continue
        operator, _, event = match.groups()
        if operator == "==" and event != "pull_request":
            return False
        if operator == "!=" and event == "pull_request":
            return False
    return True


def blocking_commands() -> dict[str, str]:
    """command -> gate id, for the gates the registry declares blocking."""
    return {
        str(gate.get("command", "")).strip(): str(gate.get("id", "")).strip()
        for gate in load_gates()
        if gate.get("blocking") is True and str(gate.get("command", "")).strip()
    }


def gate_named_in(step: dict[str, object], commands: dict[str, str]) -> str | None:
    """Which registry gate this step's script names, or None.

    The registry's job here is to *name* the gate in the error message, which is
    worth a great deal — "step X runs gate contract-current" sends someone to
    the right place. It no longer decides which steps are checked. That was the
    old definition and it left the producers uncovered: see
    steps_that_must_say_when_they_run() below.
    """
    script = step.get("run")
    if not isinstance(script, str):
        return None
    for command, identifier in commands.items():
        if command in script:
            return identifier
    return None


def dependency_ids(job: dict[str, object]) -> set[str]:
    """The step ids that some step in this job names in its own condition."""
    named: set[str] = set()
    for step in steps_of(job):
        named.update(DEPENDENCY.findall(str(step.get("if", ""))))
    return named


def steps_that_must_say_when_they_run(
    job: dict[str, object],
) -> list[tuple[int, dict[str, object], str]]:
    """(position, step, why) for every step in this job that needs a condition.

    THE DEFINITION, in one sentence: **a step runs a gate when it runs a script
    — when it has a `run:` key** — and a `uses:` step joins it when another step
    names it as a dependency, unless it is the job's first step.

    This is the wider of the two definitions the five repositories were using,
    and it is wider on purpose. The old one — "its `run:` contains, verbatim, a
    blocking gate's command" — checked exactly the steps the registry knew
    about, and left every producer in front of them uncovered:

      - `uv sync --frozen --all-groups`, a plain `run:` step naming no gate,
        with eight to ten gates conditioned on `steps.sync.outcome`. Delete its
        `if:` and one earlier failure skips it, and skipping it skips all ten.
        Ten gates, silenced, and not one error;
      - the `Advisory gates` step, which runs run_gates.py — nobody's command,
        so nobody's gate, so unchecked. It is the to-do list, and it was allowed
        to shorten itself in silence;
      - `Install Node`, `Install the pinned Kamal`: `uses:` steps sitting after
        ten gates, with the frontend and deploy gates hanging off them.

    A setup step that stops at the first red takes the gates behind it down with
    it — they are conditioned on its outcome, and a skipped dependency skips
    them just as silently as no condition at all.

    Two decisions, written here so they are choices and not accidents:

    **A `run:` step is in scope unconditionally, wherever it sits.** No position
    exemption, even at position 1 where nothing can precede it. A script step is
    where a verdict comes from, and what is required of a verdict must not
    depend on the step order — least of all in the check whose whole subject is
    that step order is an unwritten dependency graph. The condition costs one
    line and stays true when a step is inserted above it tomorrow.

    **A `uses:` step is in scope only when another step's condition names it,
    and only when it is not the first step of the job.** Both halves matter. An
    action nothing depends on silences nothing: it produces no verdict of its
    own — the registry holds no actions — and no gate is waiting on it, so
    demanding a condition would be noise, and noise is how a rule stops being
    read. An action something *does* depend on is a gate's single point of
    failure and is treated as one. The exemption for the first step is the
    checkout: there is nothing before it that could fail, so `!cancelled()`
    there would be a condition about nothing. That exemption expires by itself —
    put any step above the checkout and the checkout is no longer first, so it
    comes into scope and the verifier asks for its condition.
    """
    steps = steps_of(job)
    depended_on = dependency_ids(job)
    needed: list[tuple[int, dict[str, object], str]] = []
    for position, step in enumerate(steps, start=1):
        if isinstance(step.get("run"), str):
            needed.append((position, step, "runs a script"))
            continue
        identifier = str(step.get("id", "")).strip()
        if position > 1 and identifier and identifier in depended_on:
            needed.append(
                (position, step, f"is what other steps depend on, as steps.{identifier}")
            )
    return needed


def check_workflows(errors: list[str]) -> None:
    """Refuse a workflow this verifier could not read.

    Separate from check_gate_conditions so that "the parser failed" is its own
    sentence, and reported even for a workflow no pull request runs. Both checks
    report these problems; main() de-duplicates. That overlap is deliberate —
    deleting either call still leaves the other one talking, and an unread file
    silently leaving the perimeter is the exact failure being repaired here.
    """
    _, problems = workflow_documents()
    errors.extend(problems)


def check_gate_conditions(errors: list[str]) -> None:
    """Refuse a step that an earlier failure would silence.

    A step with no `if:` carries an implicit `success()`, so it runs only while
    nothing before it has failed. For a build that is right. For a series of
    gates it is not: gates are independent objections, and a run that stops at
    the first one tells the author about one objection per push. Worse, in the
    run summary a skipped step and a passing step look alike, so "the contract
    check did not object" reads as true about a check that never started.

    So every step in scope names `cancelled()`, and the mention is the rule
    rather than a fixed formula — `!cancelled() && steps.checkout.outcome ==
    'success'` is a gate declaring a real dependency, which is the encouraged
    form. `always()` is not the same thing and does not satisfy this: these
    workflows set `cancel-in-progress`, and under `always()` a job already
    replaced by a newer push keeps working.

    The perimeter is three decisions, each in its own function so that each can
    be read and argued with on its own: pull_request_workflows() picks the
    files, job_can_run_on_a_pull_request() drops the jobs a pull request cannot
    reach, and steps_that_must_say_when_they_run() picks the steps. The registry
    is consulted only to name the gate in the message, so a registry that will
    not load costs a good error message and nothing else — the perimeter no
    longer depends on it.
    """
    try:
        commands = blocking_commands()
    except (FileNotFoundError, tomllib.TOMLDecodeError, ValueError):
        # check_gates has already reported the registry. The rule still runs:
        # the gates it names are just anonymous in the message.
        commands = {}

    documents, problems = pull_request_workflows()
    errors.extend(problems)

    for path, document in documents.items():
        relative = under_root(path)
        for job_name, job in jobs_of(document).items():
            if not job_can_run_on_a_pull_request(job):
                continue
            for position, step, why in steps_that_must_say_when_they_run(job):
                if "cancelled()" in str(step.get("if", "")):
                    continue
                label = str(step.get("name") or f"{job_name} step {position}")
                identifier = gate_named_in(step, commands)
                does = f"runs gate {identifier}" if identifier else why
                errors.append(
                    f"{relative}: step {label!r} {does} without a "
                    f"condition naming cancelled() — the implicit default is "
                    f"success(), so one earlier failure skips this step and the "
                    f"summary reads as though it agreed. Give it "
                    f"if: ${{{{ !cancelled() }}}}, and name any real dependency "
                    f"with && steps.<id>.outcome == 'success'"
                )


# === end of the shared block ===============================================


def main() -> int:
    try:
        files = tracked_files()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"ERROR: could not list tracked files: {error}", file=sys.stderr)
        return 2

    content: list[str] = []
    workflows: list[str] = []
    check_public_content(files, content)
    check_workflows(workflows)
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

    scoped, _ = pull_request_workflows()
    print(
        f"Public content check passed for {len(files)} files, and every step "
        f"in {len(scoped)} pull-request workflow(s) says when it runs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
