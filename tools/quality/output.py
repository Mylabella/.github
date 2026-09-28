#!/usr/bin/env python3
"""Say what a check found in UTF-8, whatever the platform's codepage is.

`changed.git` names the encoding it *reads* git with, and the comment there
explains why. The same asymmetry exists on the way out. A check holds a correct
string — a commit subject with an accent, a branch named in Italian, an emoji a
tool appended — and then writes it to a pipe in the locale codepage, so whatever
reads that output receives bytes no UTF-8 reader accepts. On the Linux runner
the locale is UTF-8 and nothing goes wrong; on the machine these checks are
written on, it does. Green in CI and broken on the desk is the worse of the two
orders, because the desk is where the next check gets written.

It lives here rather than inside one check because two checks now need it, and a
rule with two implementations is a rule that has begun to disagree with itself —
which is the failure `docs/quality/README.md` calls "one rule, one detector".
Both times this was found the same way: a test could not decode the refusal it
had just provoked.
"""

from __future__ import annotations

import sys


def speak_utf8() -> None:
    """Reconfigure this process's stdout and stderr to write UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
