#!/usr/bin/env python3
"""Refuse a pull request that is too large to review.

The organization's CONTRIBUTING: *a pull request over 4000 hand-written lines is
refused; lockfiles, generated clients and fixtures do not count.* Added lines
only — the org rule that dead code is removed in the change that stops using it
is one a gate refusing a 3900-line deletion would fight.

Every exclusion is read back out of a fact the repository already states rather
than transcribed: a hand-typed list is what made an earlier detector in this
organization blind, and no list notices its own omission.

Two properties this gets wrong if it is careless, both of which shipped here
once. The attributes are resolved against the **base** — `git check-attr` reads
the checkout, so appending one `linguist-generated=true` line exempted 900
hand-written lines at a declared cost of 1, and a change may not write the rule
it is measured by. And the base is asserted before anything is measured, exiting
2 rather than 0 when it cannot be: a check that measures nothing passes
anything.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]

# Over this many is refused; exactly this many passes. The rule says "over 4000".
# Raised from 400 to 1000 on 2026-08-08, and from 1000 to 4000 on 2026-08-21, both
# times by the maintainer and both times against the standing preference not to
# widen a rule to match practice. That preference is why each raise is written
# down here as a decision with a date rather than a number quietly edged up the
# first time something did not fit: a threshold nobody remembers agreeing to is
# one nobody can disagree with either. The number lives here and in CONTRIBUTING,
# and tests/test_diff_size.py pins the boundary so the two cannot drift apart in
# silence.
THRESHOLD = 4000

# `.lock` covers uv, poetry, Cargo, Gemfile, yarn, composer and flake;
# `-lock.json` and `-lock.yaml` cover npm and pnpm. The three that fit neither
# shape are named, and nothing else is.
LOCKFILE_SHAPE = re.compile(r"\.lock$|-lock\.(json|ya?ml)$")
LOCKFILE_NAMES = frozenset({"go.sum", "bun.lockb", "npm-shrinkwrap.json"})

# A `fixtures` directory holds invented *data*. It is not a place where source
# stops being source: backend/tests/fixtures/factory.py is 900 lines somebody
# reads, and a directory name is not an argument that they do not.
FIXTURE_DIRECTORY = "fixtures"
FIXTURE_DATA_SUFFIXES = frozenset(
    {".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".csv", ".tsv", ".sql", ".xml"}
)


class BaseUnknown(Exception):
    """The commit this change is measured against could not be established."""


def git(arguments: list[str], stdin: str | None = None, check: bool = True) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT, input=stdin, check=check, capture_output=True, text=True,
    ).stdout


def resolve_base() -> tuple[str, str]:
    """The commit to measure against, and where that answer came from.

    BASE_SHA is what GitHub recorded for the pull request, which is exact. The
    local fallback is the merge base rather than `origin/main` itself: a main
    that has moved would otherwise charge this change for what landed between.
    """
    recorded = os.environ.get("BASE_SHA", "").strip()
    source = "BASE_SHA, the base GitHub recorded for this pull request"
    if not recorded:
        source = "git merge-base origin/main HEAD"
        try:
            recorded = git(["merge-base", "origin/main", "HEAD"]).strip()
        except subprocess.CalledProcessError as error:
            raise BaseUnknown(f"{source}: {error.stderr.strip()}") from error
    if not recorded:
        raise BaseUnknown(f"{source} produced no commit")
    # --quiet exits 1 and prints nothing when the name is not a commit, so an
    # empty answer is the failure everything below depends on catching.
    verified = git(
        ["rev-parse", "--verify", "--quiet", f"{recorded}^{{commit}}"], check=False
    ).strip()
    if not verified:
        raise BaseUnknown(f"{recorded} is not a commit in this checkout")
    return source, verified


def changed_files(base: str) -> list[tuple[str, int | None]]:
    """Each path the diff touches, with the number of lines it *adds*.

    Rename detection is on, because git reports a pure move as nothing changed
    and it is right: nobody reads it twice. `--no-renames` called a 500-line
    move 1000 changed lines and refused it, which teaches the next author not to
    move files. With `-z` a renamed entry is `added TAB deleted TAB` and an
    empty path, followed by the old and the new path as two further records, so
    the stream is walked rather than split into lines. None is git's `-`: it
    treats that file as having no lines at all.
    """
    fields = git(["diff", "--numstat", "-z", "--find-renames", base, "HEAD"]).split("\0")
    entries: list[tuple[str, int | None]] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        if not path:  # a rename or copy: the two paths follow, the new one last
            path = fields[index + 1]
            index += 2
        entries.append((path, None if "-" in (added, deleted) else int(added)))
    return entries


def exclusions(paths: list[str], base: str) -> dict[str, str]:
    """Why each excluded path does not count. `base` is the tree that decides."""
    reasons: dict[str, str] = {}
    if not paths:
        return reasons
    payload = "".join(f"{path}\0" for path in paths)

    # Asking git rather than parsing .gitattributes: this is the resolution it
    # performs when it produces the diff, so nested attribute files and the
    # `binary` macro (which expands to `-diff`) are honoured for free. Content
    # git never shows is content nobody reviews, and `linguist-generated`
    # declares a file produced rather than written — GitHub collapses the same
    # diffs from it, and every path declared there is refused by another gate
    # the moment it drifts from its generator. `--source` wants git 2.40; an
    # older one raises below and exits 2, because falling back to the checkout
    # is precisely the exemption this argument exists to refuse.
    fields = git(
        ["check-attr", f"--source={base}", "--stdin", "-z", "diff", "linguist-generated"],
        stdin=payload,
    ).split("\0")
    for index in range(0, len(fields) - 2, 3):
        path, attribute, value = fields[index], fields[index + 1], fields[index + 2]
        if attribute == "linguist-generated" and value in {"set", "true"}:
            reasons.setdefault(path, "the base's .gitattributes declares it generated")
        elif attribute == "diff" and value == "unset":
            reasons.setdefault(path, "the base's .gitattributes marks it binary (-diff)")

    # The one rule no repository fact supplies — nothing here enumerates what a
    # lockfile is. A name shape and not a path, so one landing in a directory
    # nobody predicted is covered the day it arrives, and tests/test_diff_size.py
    # scans the tracked tree: the omission check a list cannot run on itself.
    for path in paths:
        parsed = PurePosixPath(path)
        if LOCKFILE_SHAPE.search(parsed.name) or parsed.name in LOCKFILE_NAMES:
            reasons.setdefault(path, "a lockfile")
        elif (
            FIXTURE_DIRECTORY in parsed.parent.parts
            and parsed.suffix.lower() in FIXTURE_DATA_SUFFIXES
        ):
            reasons.setdefault(path, "fixture data")
    return reasons


def main() -> int:
    try:
        source, base = resolve_base()
    except (BaseUnknown, FileNotFoundError) as error:
        print(
            f"error: cannot determine the base of this change: {error}\n"
            f"Nothing can be measured without one, and a size check that measures "
            f"nothing passes anything. In CI set BASE_SHA and check out enough "
            f"history (fetch-depth: 0); locally, fetch origin.",
            file=sys.stderr,
        )
        return 2

    try:
        entries = changed_files(base)
        reasons = exclusions([path for path, _ in entries], base)
    except subprocess.CalledProcessError as error:
        print(
            f"error: git could not answer for base {base[:12]}: "
            f"{error.stderr.strip()}\nExcluding nothing instead would be a guess and "
            f"resolving the attributes against this branch would be the hole the "
            f"--source argument closes, so this is a failure. `git check-attr "
            f"--source` wants git 2.40 or newer.",
            file=sys.stderr,
        )
        return 2

    counted: list[tuple[str, int]] = []
    excluded: list[tuple[str, str]] = []
    for path, added in entries:
        if added is None:
            excluded.append((path, "git treats it as binary; it has no lines"))
        elif path in reasons:
            excluded.append((path, reasons[path]))
        else:
            counted.append((path, added))
    total = sum(size for _, size in counted)

    print(f"base {base[:12]} ({source})")
    for path, reason in sorted(excluded):
        print(f"  excluded  {path}: {reason}")
    print(
        f"{total} hand-written line(s) added across {len(counted)} file(s); "
        f"{len(excluded)} path(s) excluded; deleted lines do not count"
    )

    if total > THRESHOLD:
        print(
            f"error: {total} hand-written lines added against {base[:12]}, over "
            f"the {THRESHOLD} this organization refuses.\n"
            f"The three largest contributors:",
            file=sys.stderr,
        )
        for path, size in sorted(counted, key=lambda item: (-item[1], item[0]))[:3]:
            print(f"  {size:>6}  {path}", file=sys.stderr)
        print(
            "If one of those is generated, a lockfile or fixture data it should not "
            "have been counted: declare it in .gitattributes on the base branch, "
            "which is the copy this reads. Otherwise the change is too large to "
            "review and wants splitting.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
