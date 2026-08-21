#!/usr/bin/env python3
"""Refuse work that reaches `main` without passing through `develop`.

Work lands on `develop`. `main` receives a stable release from a `release/`
branch, an urgent repair from a `hotfix/` branch, or `develop` itself. A feature
merged straight into `main` is none of those: it is a commit `develop` does not
have, so the next release silently reverts it, and every branch cut from
`develop` meanwhile is built on a tree that is missing it.

`develop` is on the list deliberately, and it is the one place this is looser
than the textbook. Promoting `develop` straight into `main` skips the release
branch, which costs the thing a release branch buys — a name to tag, a place to
stabilise, something to revert as a unit. On a small project shipped directly to
a client that ceremony buys nothing, and the maintainer uses the short road on
purpose. What this gate is for is the *other* case: a feature that never went
through `develop` at all.

Nothing prevented this. GitHub offers no ruleset rule for "which branches may
open a pull request into this one": a ruleset can require a check, require a
review, forbid a force-push, and say nothing about where a merge comes from. So
the rule lives here, where it can fail, and the organization's ruleset makes it
binding by requiring `governance` on `main`.

It was not hypothetical either. Across this organization, six of the last six
merged pull requests in one repository went `feature/... -> main`, and two more
did in another. Two of those were the migration to GitFlow itself, which is the
honest exception a rule like this cannot encode and a human has to grant.

## What it does not judge

A pull request into `develop`, or into anything else, is none of its business —
that is the ordinary road and the check says so and stops.

Nor does it check the *shape* of the release name; `check_branch_name.py` already
owns the grammar and refuses `release/console` and `release/v1.2.3` for reasons
written out there. Two checks reading one rule is how an organization ends up
with two rules, so this one asks a single question: does this pull request enter
`main` from a branch entitled to?

## When it declines to answer

Outside a pull request there is no target and nothing to judge. Inside one with
no head ref, it exits 2 rather than passing: a check that cannot see what it is
judging must not report that it found nothing wrong.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from output import speak_utf8  # noqa: E402 - the import path is set immediately above

MAIN = "main"
DEVELOP = "develop"

#: The prefixes entitled to enter `main`. Not a grammar — the grammar is
#: `check_branch_name.py`'s — just the entrance list.
ENTITLED_PREFIXES = ("release/", "hotfix/")

#: And the one whole branch name entitled to, which is a different shape: there
#: is exactly one `develop` and it has no suffix to match.
ENTITLED_BRANCHES = (DEVELOP,)


def event() -> str:
    return os.environ.get("GITHUB_EVENT_NAME", "").strip()


def target() -> str:
    return os.environ.get("GITHUB_BASE_REF", "").strip()


def source() -> str:
    for variable in ("GITHUB_HEAD_REF", "BRANCH"):
        value = os.environ.get(variable, "").strip()
        if value:
            return value
    return ""


def main() -> int:
    speak_utf8()

    if event() != "pull_request":
        print("not a pull request; there is no target branch to judge")
        return 0

    base = target()
    if base != MAIN:
        print(f"this pull request targets {base or 'another branch'}, not {MAIN}")
        return 0

    head = source()
    if not head:
        print(
            f"error: this pull request targets {MAIN} and the branch it comes "
            f"from could not be read",
            file=sys.stderr,
        )
        print(
            "GITHUB_HEAD_REF is empty. Passing here would approve exactly the "
            "merge this refuses, so it does not.",
            file=sys.stderr,
        )
        return 2

    if head in ENTITLED_BRANCHES or head.startswith(ENTITLED_PREFIXES):
        print(f"{head} is entitled to enter {MAIN}")
        return 0

    print(f"error: '{head}' may not merge into {MAIN}", file=sys.stderr)
    print(
        f"Work goes to {DEVELOP}. {MAIN} receives a stable release from "
        f"release/<component>-vX.Y.Z, an urgent repair from "
        f"hotfix/<component>-vX.Y.Z, or {DEVELOP} itself, and nothing else.",
        file=sys.stderr,
    )
    print(
        f"Retarget this pull request at {DEVELOP} — the base can be changed on "
        f"an open pull request without closing it, unlike a rename. If this "
        f"really is a release, promote {DEVELOP} itself, or cut a release/ "
        f"branch from it when the version needs a name to tag.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
