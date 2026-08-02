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


class RealRepository(unittest.TestCase):
    def test_the_published_files_pass(self) -> None:
        """The rule is only credible if what is already here obeys it."""
        self.assertEqual(0, verify.main())


if __name__ == "__main__":
    unittest.main()
