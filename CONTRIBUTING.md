# Contributing to Mylabella projects

Thank you for helping improve a Mylabella project. Useful contributions include
code, documentation, tests, examples, design feedback, and clear bug reports.

This file is the organization-wide default. A repository may publish its own
`CONTRIBUTING.md` when its tooling or maintenance model requires different
rules. The repository-local file takes precedence.

Participation is subject to the
[Code of Conduct](https://github.com/Mylabella/.github/blob/main/CODE_OF_CONDUCT.md).
Use the channels described in
[SUPPORT.md](https://github.com/Mylabella/.github/blob/main/SUPPORT.md), and
never disclose suspected vulnerabilities publicly.

## Before contributing

1. Read the target repository's README, status, license, and local contribution
   guide.
2. Search existing issues and pull requests to avoid duplicates.
3. For a substantial feature or architectural change, open a proposal before
   investing in implementation.
4. Keep secrets, personal data, proprietary material, and production details
   out of issues, logs, examples, and commits.

## Branching

Two branches are permanent. **`main` is what has been released** and must stay
releasable at all times. **`develop` is where finished work waits for the next
release.** Neither is ever pushed to directly, including while working alone;
organization rules refuse it and a repository that deploys also refuses to act
on a commit no reviewed pull request produced.

- Everyday work starts from `develop`, on a short-lived
  `feature/<description>`, `fix/<description>` or `chore/<description>` branch,
  and its pull request goes back into `develop`.
- Promotion happens on a `release/<component>-vX.Y.Z` branch, and repair of
  something already released on a `hotfix/<component>-vX.Y.Z` branch. Both carry
  a component **and** a version: `release/console` says nothing about which
  release, and `release/v1.2.3` is a tag's name rather than a branch's.
- Those five prefixes are the entire list. A tool's default branch name is not
  an exception to it, and neither is an agent's.
- Open a pull request for every change, including changes made while working
  alone. Update the branch before merge when repository rules require it.
- **Squash merge into `develop`.** The pull-request title becomes the durable
  commit message, so write it as one.
- **Merge commit into `main`, never squash.** A squashed promotion writes a
  commit `main` does not share with `develop`, so the two stop being related and
  the next merge between them conflicts with work that is already in both. The
  merge commit is also what lets a deploy prove its own provenance: it is the
  commit a pull request based on `main` produced, and that is the question the
  release guards ask.
- **After a hotfix reaches `main`, merge `main` back into `develop` in the same
  sitting.** Whoever merged the hotfix owns this. Nothing checks it, and it is
  the one step whose omission is silent: `develop` simply stops containing a fix
  that is live, and the next release quietly removes it.
- Delete merged branches.

## Do not stack pull requests

Never open a pull request whose base is another open pull request's branch.
Either make the two changes independent of each other, or finish and merge the
first before opening the second.

Stacking looks efficient and behaves badly under the workflow this document
already requires. Squash merge replaces the branch's commits with one new
commit on `main`, so when the base pull request merges, the stacked one is left
pointing at a branch that no longer leads anywhere: **its changes silently do
not reach `main`, and nothing reports this.** It has happened here, and it cost
a recovery pull request to notice and undo.

Renaming a branch that has an open pull request is the same class of mistake and
can close the pull request outright. Rename before opening it, or open a new one.

If a change genuinely depends on another, say so in the description and wait.
Sequential is slower than stacked by exactly the review time, and faster than
stacked by however long it takes to discover that half the work never landed.

## Who merges

An author may merge their own pull request when every blocking gate is green and
the change is under 1000 hand-written lines. Above that line, or on any of these
triggers, stop and ask the maintainer instead of deciding:

- a change to a published contract, or a response field removed or narrowed;
- a migration that removes or narrows anything a running previous version reads;
- a new secret, or a new environment variable read at runtime;
- a change to a workflow's `permissions:` or `secrets:` block;
- a new externally reachable route, or any change on an authentication or
  authorization path;
- a new direct dependency;
- a test deleted, skipped, or marked expected-to-fail.

The boundary is the measurement, not the identity. A rule that says the
maintainer merges is satisfied by every merge the maintainer performs, including
the ones nobody read; a size limit and a trigger list can each be checked.

For the same reason this project does not ask a contributor to attest that they
reviewed their own work. An attestation written by the same party that wrote the
change records nothing, and a file full of them is worse than an empty one,
because it reads as evidence.

## Dead code

Remove what is no longer used, in the change that stops using it. Do not leave a
commented-out block, an unreferenced function, a module nothing imports, a table
nothing reads, a placeholder never filled, or a document whose claims have become
false.

A deterministic check enforces the part a tool can prove — unused imports, unused
locals, unused arguments, commented-out code, unused TypeScript locals and
parameters — and it blocks.

What a tool can only guess — a module with no importer outside its own test, an
endpoint with no caller, a table with no reader — belongs in the repository's
dead-code inventory, and every entry carries a date. The date is the point: an
entry without a deadline is abandonment with better manners. The repository fails
when a date passes.

Test coverage does not answer this question. A module with its own passing test
suite and no production caller is fully covered and entirely dead.

## Backend and frontend change together

A change to one side carries the other side in the same pull request. Adding an
endpoint means adding its caller; removing a response field means removing its
reader; adding a value to a vocabulary means adding the label that renders it.

Where a generated client exists, the generation is the enforcement, and the
generated file is never edited by hand.

Landing one side alone is permitted only when the maintainer says so explicitly,
in that pull request. It is then recorded as an open issue labelled
`parity-debt` stating what is missing, on which side, and the date by which it
closes. A workflow reads those issues, reports them on every pull request, and
fails once one is past its date. The circle is closed by closing the issue, never
by merging the pull request that opened it.

## Pull requests

Keep pull requests focused and reviewable. A pull request over 4000 hand-written
lines is refused; lockfiles, generated clients, and fixtures do not count towards
that number.

Raised from 400 to 1000 on 2026-08-08 and from 1000 to 4000 on 2026-08-21, both
times deliberately. It is no longer the same number as the one under *Who
merges*: that one is about how much a person may land without asking, this one is
about how much anybody can be expected to read, and they were only ever equal by
coincidence of history.

That is a gate and not a hope: `tools/quality/check_diff_size.py` counts the
lines a change adds against its base and fails the pull request over the limit.
What does not count is read back out of the base branch's `.gitattributes`
rather than from a list kept here, and out of the base's copy on purpose — a
change that could declare its own payload generated would be writing the rule it
is measured by. Deleted lines do not count either: dead code is removed in the
change that stops using it, and a gate that refuses a large deletion argues with
that rule and loses.

Every pull request must explain:

- the user or operational outcome;
- why the change is necessary;
- important design choices and rejected alternatives;
- how the change was verified;
- documentation, dependency, security, migration, and rollback impact.

Draft pull requests are welcome for early feedback, but they must not be used to
bypass proposal or security discussions.

## AI-assisted contributions

AI tools may assist with research, code, tests, or documentation. The human
author remains accountable for the entire contribution and must:

- understand and review every submitted change;
- verify behavior with appropriate tests or direct observation;
- check licenses, attribution, privacy, and security implications;
- never submit secrets, confidential data, or material they are not permitted
  to share to an external model or service.

Do not attribute authorship to a tool. No co-author trailer, no generated-with
footer, and no standing disclosure section in the pull-request body: under squash
merge that body becomes the commit message, so a line that is true of every
change would be recorded forever on every change while informing nobody. The
accountability is the point, and the checklist carries it.

Generated output is evidence to inspect, not proof that a change is correct.

## Dependencies

Before adding a direct dependency:

1. check the language standard library and existing dependencies;
2. compare maintenance, security history, license, size, and transitive
   dependencies;
3. document why owning a small implementation would be worse;
4. pin or lock the selected version using the stack's standard mechanism;
5. add automated update and vulnerability monitoring where the repository
   supports it.

Remove dependencies that are unused, duplicated, abandoned, or no longer worth
their operational cost.

## Releases

When a repository contains independently deployable components, version them as
`<component>-vX.Y.Z`, for example `backend-v1.4.0` or `frontend-v2.0.1`.
Deploy only a component whose version changed.

Publishing a GitHub Release is the production approval event. A release
promotes an already-built immutable artifact; it must not rebuild different
bytes.

That applies to anything with a build to choose between. A repository that
describes infrastructure rather than producing an artifact has nothing to
version, and converges from `main` instead: there, merging is the approval
event, and the repository records that in its own ADRs. Applications are
released because a release is a decision about a build; shared services are
converged because there is no build to decide about.

Each production repository documents its delivery and rollback process under
`docs/`.

## Licensing

The target repository's license governs contributions to that repository.
Unless explicitly agreed otherwise, submitting a contribution means agreeing
to license it under the same terms. Do not contribute material that is
incompatible with those terms.

