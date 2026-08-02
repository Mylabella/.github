#!/usr/bin/env python3
"""Check that this public repository contains only general engineering policy.

The README states the rule this enforces: never add hostnames, addresses, file
system paths, secret names, credentials, infrastructure topology, or anything
specific to a deployment environment. It is the strictest rule in the
organization and it had no check, which made it the rule with the worst failure
mode and the least protection: this repository is public, and the private ones
it sets policy for are not.

The patterns look for the realistic mistake rather than for every conceivable
leak. The realistic mistake is a paragraph pasted out of a runbook.

Only the standard library, so it runs anywhere python3 does.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

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


def main() -> int:
    try:
        files = tracked_files()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"ERROR: could not list tracked files: {error}", file=sys.stderr)
        return 2

    errors: list[str] = []
    for path in files:
        try:
            text = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for number, matched, reason in scan(text):
            errors.append(f"{relative}:{number}: {reason}: {matched}")

    if errors:
        for error in sorted(set(errors)):
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            "\nThis repository is public and sets policy for private ones. "
            "Describe the rule, not the machine.",
            file=sys.stderr,
        )
        return 1

    print(f"Public content check passed for {len(files)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
