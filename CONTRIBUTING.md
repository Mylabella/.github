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

- `main` must remain releasable at all times. Protect it wherever the plan
  allows; where branch protection is unavailable, a repository that deploys from
  `main` is expected to refuse a commit that no reviewed pull request produced.
- Create a short-lived `feature/<description>`, `fix/<description>`, or
  `chore/<description>` branch. Those three are the entire list. A tool's
  default branch name is not an exception to it, and neither is an agent's.
- Never push to `main`, including while working alone.
- Open a pull request for every change, including changes made while working
  alone.
- Update the branch before merge when required by repository rules.
- Use squash merge. The pull-request title becomes the durable commit message,
  so write it as one.
- Delete merged branches.

Release branches are not part of the default workflow. Create one only when a
supported version must be stabilized or maintained independently.

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

## Every gate speaks on every run

A workflow step with no `if:` carries an implicit `success()`, so it is skipped
as soon as an earlier step has failed. For a build that is correct. For a series
of quality gates it is not: gates are independent objections, and a run that
stops at the first one reports one objection per push. The summary is the worse
half of that — a skipped step and a passing step look alike there, so a check
that never started reads as a check that agreed.

In every workflow triggered by `pull_request`, a step that could be silenced this
way therefore carries `if: ${{ !cancelled() }}`. Not `always()`: these workflows
cancel a run that a newer push has superseded, and under `always()` the replaced
job keeps working.

Which steps those are is one sentence, and it is the same sentence in every
repository: **a step runs a gate when it runs a script — when it has a `run:`
key** — and a `uses:` step joins it when another step names it as a dependency,
unless it is the job's first step.

That is wider than it first sounds, on purpose. The earlier wording asked only
for the steps that run a named gate, which left every step those gates stand on
uncovered: the toolchain install, the dependency sync, the step that runs the
advisory list. A setup step that stops at the first red takes the gates behind it
down with it — they are conditioned on its outcome, and a skipped dependency
skips them just as silently as no condition at all. An action nothing depends on
is left out because it silences nothing, and the job's first step is left out
because nothing precedes it; that second exemption is about position, so it
expires by itself the moment a step is put above it.

Real dependencies are not erased by any of this. They are declared by name rather
than inherited: give the producing step an `id:`, and condition the steps that
need it with `&& steps.<id>.outcome == 'success'`. Bind each step to the least it
truly needs. The checkout is a real dependency of every gate that reads the tree —
without it a failed checkout produces one red gate per missing file and nothing
that names the cause, which is the same deception in a mirror. A lockfile check is
the instructive exception: tie it to the package manager's setup and not to the
install, because a stale lockfile fails the install as well, and that is precisely
the run where the lockfile gate is the only one that can say why.

Release and deploy workflows are out of scope. There the sequence is the point,
and stopping at the first failure is correct.

Each repository enforces this in its own verifier, and the verifier reads every
step separately. A check that reads the workflow as one string finds a
`cancelled()` belonging to some other step and passes on exactly the state the
rule exists to refuse.

The verifier also refuses a workflow it cannot read. A parser that shrugs at an
unfamiliar construct returns an empty document, an empty document has no steps,
and a file with no steps is a file with nothing to complain about — the same
absence-read-as-consent, one level up. So an unknown construct stops the check by
name, with the line and what to do about it, rather than quietly covering one
file fewer than it did yesterday.

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

Keep pull requests focused and reviewable. A pull request over 1000 hand-written
lines is refused; lockfiles, generated clients, and fixtures do not count towards
that number.

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

