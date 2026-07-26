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

- `main` is protected and must remain releasable.
- Create a short-lived `feature/<description>`, `fix/<description>`, or
  `chore/<description>` branch.
- Open a pull request for every change, including changes made while working
  alone.
- Update the branch before merge when required by repository rules.
- Prefer squash merge. The pull-request title becomes the durable commit
  message.
- Delete merged branches.

Release branches are not part of the default workflow. Create one only when a
supported version must be stabilized or maintained independently.

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
- disclose significant AI assistance in the pull request when it affects review
  or provenance;
- never submit secrets, confidential data, or material they are not permitted
  to share to an external model or service.

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

Each production repository documents its delivery and rollback process under
`docs/`.

## Licensing

The target repository's license governs contributions to that repository.
Unless explicitly agreed otherwise, submitting a contribution means agreeing
to license it under the same terms. Do not contribute material that is
incompatible with those terms.

