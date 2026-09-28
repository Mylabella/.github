#!/usr/bin/env python3
"""Refuse a pull request that is too large to review.

The organization's CONTRIBUTING: *a pull request over 6000 hand-written lines is
refused; lockfiles, generated clients and fixtures do not count.* Added lines
only — the org rule that dead code is removed in the change that stops using it
is one a gate refusing a 5900-line deletion would fight.

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

*Which* base is the question this got wrong for longer, and the answer is in
`resolve_base` below: a pull request into `main` is measured against `develop`,
because a promotion is not a second review of the same lines.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]

# Over this many is refused; exactly this many passes. The rule says "over 6000".
# Raised from 400 to 1000 on 2026-08-08, from 1000 to 4000 on 2026-08-21, and
# from 4000 to 6000 on 2026-08-25 — every time by the maintainer, every time
# deliberately, and every time against the standing preference not to widen a
# rule to match practice. That preference is why each raise is written down here
# as a decision with a date rather than a number quietly edged up the first time
# something did not fit: a threshold nobody remembers agreeing to is one nobody
# can disagree with either.
#
# The third raise is the one with the cleanest conscience and it is worth saying
# why, because the next reader will otherwise count three and conclude the limit
# is decorative. The first two were made under the pressure this file no longer
# creates: a promotion measured against `main` carried the sum of every feature
# since the last release, so the limit was raised to let a release through and
# the number was doing work the base should have been doing. That pressure was
# removed in the same change that carried this raise — see `resolve_base` — so
# 6000 was chosen against a gate that had stopped lying about what it measured,
# which is the only honest moment to choose one.
#
# Why 6000 and not some other number: it was agreed with Andrea on 2026-08-25,
# and it is provisional — whether this limit survives at all is under discussion
# between them. Both halves of that are written down on purpose. A number with
# no reason beside it is one nobody can argue with afterwards, and "provisional"
# is the adjective that most reliably becomes permanent in silence. If the limit
# goes, this comment is the record of what it was for; if it stays, whoever
# proposes a fourth raise argues against this instead of against nothing.
#
# The number lives here and in CONTRIBUTING, and tests/test_diff_size.py pins
# the boundary so the two cannot drift apart in silence.
THRESHOLD = 6000

# The two permanent branches, named because `resolve_base` decides on them.
# check_release_path.py and check_main_not_ahead.py know the same two names; the
# grammar of a release branch is not re-stated here, because none of the three
# needs it and a rule written twice is a rule that will disagree with itself.
MAIN = "main"
DEVELOP = "develop"

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
    # The encoding is named rather than left to the locale. `text=True` alone
    # decodes with the platform's preferred encoding — UTF-8 on the Linux
    # runner, the ANSI codepage on the Windows machine this repository is
    # developed on — and git writes UTF-8 either way, so a branch or path with
    # an accent in it reads correctly in CI and arrives as mojibake locally.
    # Green in CI and wrong on the desk is the worse of the two orders.
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT, input=stdin, check=check, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    ).stdout


def rev(name: str) -> str:
    """The commit `name` points at, or "" when there is no such commit.

    `--verify --quiet` exits 1 and prints nothing for a name that is simply
    absent, so `check=False` here distinguishes "no such branch" — an ordinary
    answer this has to handle — from git failing, which does not go quiet.
    """
    return git(
        ["rev-parse", "--verify", "--quiet", f"{name}^{{commit}}"], check=False
    ).strip()


def branch(name: str) -> tuple[str, str]:
    """A branch as (the ref that answered, its commit), or ("", "") for neither.

    `origin/<name>` first because on a pull request the checkout is detached and
    the local branch may not exist at all; the bare name is the fallback for a
    working copy on somebody's desk. Same order and same reason as
    `check_main_not_ahead.py`, which asks git the same question.

    The ref comes back with the commit so the output can name the one that
    answered. Printing `origin/develop` when the local `develop` is what was
    read would be a small lie in the only line anyone reads when the number
    surprises them.
    """
    for candidate in (f"origin/{name}", name):
        found = rev(candidate)
        if found:
            return candidate, found
    return "", ""


def resolve_base() -> tuple[str, str]:
    """The commit to measure against, and where that answer came from.

    ## A promotion is not a second review

    A pull request into `main` is measured against `develop`, not against
    `main`. Every line already on `develop` was counted when it entered
    `develop` — `protezione-develop` requires a pull request there too, so there
    is no way in that this gate did not see — and charging a promotion for them
    again measures the sum of every feature since the last release. That sum
    grows without bound and has nothing to do with how much anybody is being
    asked to read, which is what the limit is about.

    It is not a hypothesis. On the day this was written the promotion pull
    request was arithmetically impossible in three repositories of this
    organization at the 4000 then in force — 29285, 18207 and 4270 hand-written
    lines — and a fourth had shipped its promotion as `Promozione 1 di 2` and
    `Promozione 2 di 2`, two halves that left `main` in a state that was never a
    release and made nothing more readable, because every line in both had
    already been reviewed once. The threshold was raised to 6000 the same day
    and that is recorded above with its date, but it is not what made a
    promotion measurable and it could not have been: 29285 is not a number any
    threshold anybody would propose ever reaches. Only the base could fix it.

    What arrives at `main` without passing `develop` is still counted, and that
    is the case the rule is for: a hotfix, cut from `main`, is measured by
    exactly what it adds — `check_main_not_ahead.py` is what keeps that true, by
    refusing a `main` that holds work `develop` does not. When that invariant is
    briefly false, between a hotfix landing and its back-merge, the next hotfix
    is charged for the previous one as well. That is a false alarm with a
    harmless remedy: the back-merge that clears it is correct anyway. It is the
    same false alarm `check_main_not_ahead.py` documents, and it is stated here
    rather than discovered.

    ## The base branch is read live, not as GitHub froze it

    `pull_request.base.sha` is the tip of the base branch **when the pull
    request was opened**, and GitHub does not update it when the base moves —
    only a push to the head branch does. So a pull request open while three
    others land on `develop` is charged for all three, which is precisely the
    defect the merge-base fallback was written to prevent and never did, because
    BASE_SHA was preferred over it. It cost a real pull request: `#25` in
    app-smartsoil kept measuring 4270 lines against the `main` of before `#26`
    even after `#26` had merged, and had to be closed and reopened as `#27` to
    be measured against the `main` that actually existed.

    So the base branch is resolved by name and the merge base computed now.
    BASE_SHA remains the fallback for the case the name cannot answer, and the
    local `origin/main` merge base the fallback after that.

    Every fallback below counts *more* than the answer it replaces, never less.
    That direction is the property to preserve when editing this: a base that is
    further back inflates the number and fails safe, and one that is further
    forward hides lines nobody read.
    """
    target = os.environ.get("GITHUB_BASE_REF", "").strip()

    if target == MAIN:
        ref, reviewed = branch(DEVELOP)
        if reviewed:
            return (
                f"{ref}: this pull request promotes into {MAIN}, and what "
                f"{DEVELOP} already holds was counted on the way in",
                reviewed,
            )
        # No `develop` means no repository that has adopted GitFlow, so nothing
        # has been counted anywhere and there is no promotion to recognise. Fall
        # through to the answer below, which counts everything.

    if target:
        ref, tip = branch(target)
        # An empty merge base is unrelated histories — the two-root-commits trap
        # a template repository created with "include all branches" falls into.
        # It is not this check's business to diagnose, and the fallbacks below
        # count more rather than less, so it declines rather than guessing.
        common = git(["merge-base", tip, "HEAD"], check=False).strip() if tip else ""
        if common:
            return f"git merge-base {ref} HEAD", common

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
    verified = rev(recorded)
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
