#!/usr/bin/env python3
"""Which branches may enter `main`, and which questions this declines to answer.

The check is driven entirely by the event's environment, so every case here is
an environment handed to the real script as a subprocess. The inherited one is
stripped first, and that is not hygiene: this suite runs inside a `pull_request`
job whose GITHUB_BASE_REF and GITHUB_HEAD_REF describe the pull request adding
these tests. A case that sets neither would judge that pull request instead of
its own fixture — green or red for a reason nothing in the test can see. The
same trap cost an afternoon in tests/test_main_not_ahead.py, where three cases
passed on the desk and failed on the runner.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

GATE = (
    Path(__file__).resolve().parents[1] / "tools" / "quality" / "check_release_path.py"
)


def judge(**event: str) -> tuple[int, str]:
    """Run the real script under exactly the event `event` describes."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GITHUB_") and name != "BRANCH"
    }
    environment.update(event)
    done = subprocess.run(
        [sys.executable, str(GATE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    return done.returncode, done.stdout + done.stderr


def into_main(head: str) -> tuple[int, str]:
    return judge(
        GITHUB_EVENT_NAME="pull_request", GITHUB_BASE_REF="main", GITHUB_HEAD_REF=head
    )


class OnlyAReleaseAHotfixOrDevelopEntersMain(unittest.TestCase):
    def test_a_release_branch_is_entitled(self) -> None:
        code, output = into_main("release/console-v1.2.3")
        self.assertEqual(0, code, output)

    def test_a_hotfix_branch_is_entitled(self) -> None:
        code, output = into_main("hotfix/console-v1.2.4")
        self.assertEqual(0, code, output)

    def test_a_feature_branch_is_refused(self) -> None:
        code, output = into_main("feature/qualcosa")
        self.assertEqual(1, code)
        self.assertIn("may not merge into main", output)

    def test_develop_itself_is_allowed(self) -> None:
        """The deliberate deviation, and the reason it is in a test.

        Promoting `develop` straight into `main` skips the release branch and
        the thing it buys — a name to tag, a place to stabilise, a unit to
        revert. On a small project shipped directly to a client that ceremony
        buys nothing, and the maintainer takes the short road on purpose. This
        gate exists for the *other* case, a feature that never went through
        `develop` at all, so the short road is asserted here rather than left to
        be rediscovered the first time somebody ships.
        """
        code, output = into_main("develop")
        self.assertEqual(0, code, output)

    def test_the_refusal_says_where_the_work_should_go(self) -> None:
        _, output = into_main("fix/una-riparazione")
        self.assertIn("Work goes to develop", output)
        self.assertIn("release/<component>-vX.Y.Z", output)

    def test_the_refusal_says_retargeting_does_not_close_the_pull_request(self) -> None:
        # The remedy is one dropdown, and an author who does not know that
        # closes and reopens instead, losing the review.
        _, output = into_main("feature/qualcosa")
        self.assertIn("without closing it", output)


class WhatItLeavesAlone(unittest.TestCase):
    def test_a_pull_request_into_develop_is_not_its_business(self) -> None:
        code, output = judge(
            GITHUB_EVENT_NAME="pull_request",
            GITHUB_BASE_REF="develop",
            GITHUB_HEAD_REF="feature/qualcosa",
        )
        self.assertEqual(0, code, output)

    def test_the_back_merge_into_develop_passes(self) -> None:
        # chore/riporta-main-dentro-develop targets develop, so the repair for
        # a main that ran ahead is never caught by the rule about entering main.
        code, output = judge(
            GITHUB_EVENT_NAME="pull_request",
            GITHUB_BASE_REF="develop",
            GITHUB_HEAD_REF="chore/riporta-main-dentro-develop",
        )
        self.assertEqual(0, code, output)

    def test_outside_a_pull_request_there_is_nothing_to_judge(self) -> None:
        code, output = judge(GITHUB_EVENT_NAME="push")
        self.assertEqual(0, code, output)
        self.assertIn("not a pull request", output)


class ItWillNotApproveWhatItCannotSee(unittest.TestCase):
    def test_a_pull_request_into_main_with_no_head_ref_exits_2(self) -> None:
        """Exit 0 here would approve exactly the merge this exists to refuse."""
        code, output = judge(GITHUB_EVENT_NAME="pull_request", GITHUB_BASE_REF="main")
        self.assertEqual(2, code, output)
        self.assertIn("could not be read", output)


if __name__ == "__main__":
    unittest.main()
