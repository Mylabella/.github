"""Tests for the public content check.

This script is the only executable code in the repository and the only thing
standing between a careless paste and a public leak of how the private
infrastructure is put together. An unverified gate is a gate nobody should
trust, so each pattern is tested for what it must catch and for what it must
leave alone. The second half matters more: a check that cries wolf gets
disabled, and a disabled check protects nothing.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "quality" / "verify_public_content.py"
SPEC = importlib.util.spec_from_file_location("verify_public_content", MODULE_PATH)
assert SPEC and SPEC.loader
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


def reasons(text: str) -> list[str]:
    return [reason for _, _, reason in verify.scan(text)]


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


class RealRepository(unittest.TestCase):
    def test_the_published_files_pass(self) -> None:
        """The rule is only credible if what is already here obeys it."""
        self.assertEqual(0, verify.main())


if __name__ == "__main__":
    unittest.main()
