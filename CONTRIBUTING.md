# Contributing

This is the organization-wide default. A repository that needs different rules
publishes its own `CONTRIBUTING.md` and states why.

## Branching

- `main` is protected and must remain releasable.
- Create a short-lived `feature/<description>`, `fix/<description>`, or `chore/<description>` branch.
- Open a pull request for every change, including changes made while working alone.
- Rebase or update the branch before merge when required by repository rules.
- Prefer squash merge. The pull-request title becomes the durable commit message.
- Delete merged branches.

Release branches are not part of the default workflow. Create one only when a supported version must be stabilized or maintained independently.

## Pull requests

Keep pull requests focused and reviewable. Prefer fewer than 400 changed production lines; exceeding that is a review signal, not an automatic failure.

Every pull request must explain:

- the user or operational outcome;
- the reason for the change;
- the important design choices;
- how the change was verified;
- documentation, dependency, security, migration, and rollback impact.

## Dependencies

Before adding a direct dependency:

1. check the language standard library and existing dependencies;
2. compare maintenance, security history, license, size, and transitive dependencies;
3. document why owning a small implementation would be worse;
4. pin or lock the selected version using the stack's standard mechanism;
5. add automated update and vulnerability monitoring.

Remove dependencies that are unused, duplicated, abandoned, or no longer worth their operational cost.

## Releases

Components are versioned and released independently as `<component>-vX.Y.Z`, for
example `backend-v1.4.0` or `frontend-v2.0.1`. Deploy only a component whose
version changed.

Publishing a GitHub Release is the production approval event. A release promotes an already-built immutable artifact; it must not rebuild different bytes.

Each repository documents its own delivery and rollback process under `docs/`.
