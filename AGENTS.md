# Agent operating contract

These rules apply to every human-guided or autonomous coding agent working in
this repository.

Read `CONTRIBUTING.md` first. It is the engineering workflow in full, this file
is what an agent needs before its first edit, and where they overlap
`CONTRIBUTING.md` is the longer explanation rather than a second opinion.

## The organization contract is not replicated here

Every repository in this organization carries a block of shared rules, identical
byte for byte, delimited by `<!-- BEGIN organization contract -->`.
`agentic-development-template` holds the canonical text and
`check_agents_contract.py` propagates it with `--write`.

**That block is deliberately absent from this repository**, and the absence is
the rule rather than an oversight to correct. `check_agents_contract.py` requires
a repository to adopt the contract and the machinery together, or neither: the
contract names the check that verifies each rule, and a rule whose detector is
missing is a promise nothing keeps. Of the twelve files it requires, this
repository has two — `tools/quality/check_release_path.py` and
`.claude/settings.json`. The other ten are absent, and three of them
(`check_migrations.py`, `check_contracts.py`, `check_adr_required.py`) have no
subject here at all: this repository has no database, no committed contract and
no decision log.

Copying the block in without them would be the failure the check exists to catch.
Editing the block to remove the sentences that point at missing files is the same
failure by the other road, and it has happened before in this organization: a
repository reworded the shared text to fix a broken promise, which is exactly how
one rule became four versions.

So the contract is honoured here by reference. **Read it in
`agentic-development-template/AGENTS.md` before working in any repository of this
organization, including this one.** What follows is only what is specific to this
one, and it does not repeat what the contract already says.

## What this repository is

The organization's default community health files. GitHub serves the supported
ones as fallbacks to any repository that does not carry its own, so a change here
can take effect in repositories nobody touched. Review a change as an
organization-wide production change.

What is inherited is a closed list: `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`,
discussion category forms, `FUNDING.yml`, issue and pull request templates with
their `config.yml`, `SECURITY.md`, `SUPPORT.md`.

**Workflows are not on it.** `.github/workflows/` is not inherited by anything; it
runs for this repository alone. A gate that should apply everywhere has to be
added to every repository, or required by an organization ruleset — the ruleset
rule that imposes a workflow without a per-repository file needs an Enterprise
plan this organization does not have.

This repository sets policy for private repositories and is itself public. That
asymmetry is the reason for the strictest rule below.

## What this repository may contain

Only general engineering policy. Never a hostname, an address, a filesystem path,
the name of a secret, a credential, infrastructure topology, personal data, or
anything specific to a deployment environment.

`verify_public_content.py` enforces this over **every tracked file outside
`tools/` and `tests/`** — this file included, and workflow comments and commit-
adjacent prose with it. It refuses a link to a host outside a short allowlist, so
naming a service beats linking it, and an API endpoint under `api.github.com`
fails even inside a code fence. It also refuses truncation and merge-conflict
markers, because text that was never finished is something a reader assumes they
misread.

Run it before proposing any change to a published file.

## How a branch is named

The grammar is the organization's and lives in the contract. What is specific
here: this repository has no `.claude/hooks/branch_guard.py`, so a cloud session's
assigned `claude/...` branch **is not renamed for you**. Rename it by hand, before
any work exists on it:

```sh
git branch -m chore/<description>
git branch --unset-upstream
```

The rename is local; it touches no remote ref and cannot close a pull request. A
remote branch the harness already created is left where it is — deleting a remote
ref is destructive and is not needed to get the name right.

The step named "Check the branch name" in `.github/workflows/governance.yml`
speaks at the merge. It carries the grammar inline rather than in a script,
because this repository does not have `check_branch_name.py` either.

## Nobody but the author is credited

The rule is the organization's; read it in the contract. Two things are specific
to this repository.

`.claude/settings.json` carries `"attribution": {"commit": "", "pr": ""}` and
**nothing else** — no hooks. `authorship_guard.py` and `branch_guard.py` import
their patterns from `check_authorship.py`, which is not here, and declaring hooks
that do not exist would print an error on every shell call: noise that stops
nothing. So the tool's own footers are suppressed, and everything else is manual.

That setting governs what the tool appends. It does not reach the identity: a
cloud session sets an agent's name and address in the *global* git config, so its
commits are authored by a tool however clean the message is. Set `user.name` and
`user.email` for this repository before the first commit. Nothing here checks it —
`check_authorship.py` is one of the ten absent files — so it is on you.

## Where a change goes, and how large

Open the pull request against `develop`; `check_release_path.py` refuses anything
reaching `main` that did not come from `release/`, `hotfix/` or `develop` itself.
Merge into `develop` with a merge commit — organization rules refuse a squash
there.

A pull request is refused above 6000 hand-written added lines by
`check_diff_size.py`. Lockfiles, generated files and deletions do not count. A
pull request into `main` is measured against `develop`, because a promotion
carries nothing that was not already read on the way in.

`check_main_not_ahead.py` is referenced by `check_diff_size.py` and is **not in
this repository**. The invariant it enforces elsewhere — that `main` never holds
work `develop` never received — is currently enforced here by nothing.

## Before it is finished

Run what the pull request will run:

```sh
python3 tools/quality/check_diff_size.py
python3 tools/quality/verify_public_content.py
python3 -m unittest discover -s tests
python3 tools/quality/check_release_path.py
```

The pull-request body follows `.github/pull_request_template.md`. This repository
has no `check_pr_brief.py`, so the `## Brief` and `## Rischi residui` sections
that other repositories require are not used here.

Never weaken, skip or delete a gate to make a change pass, and never report
success without having run the checks.
