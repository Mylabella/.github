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

## Pull requests

Keep pull requests focused and reviewable. Fewer than 400 changed production
lines is a useful target, not an automatic limit.

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

