# Mylabella organization defaults

This public repository is the shared community and engineering baseline for the
`Mylabella` organization. GitHub uses supported files here as fallbacks for
organization repositories that do not provide a local version.

## Repository map

| Path | Purpose |
| --- | --- |
| [`profile/README.md`](profile/README.md) | Public organization profile |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contribution and engineering workflow |
| [`AGENTS.md`](AGENTS.md) | Operating contract for coding agents |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community participation standards |
| [`SECURITY.md`](SECURITY.md) | Private vulnerability reporting |
| [`SUPPORT.md`](SUPPORT.md) | Routing for bugs, questions, and proposals |
| [`GOVERNANCE.md`](GOVERNANCE.md) | Maintainer-led decisions and project lifecycle |
| [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) | Default bug and feature forms |
| [`.github/pull_request_template.md`](.github/pull_request_template.md) | Default pull-request body |
| [`docs/benchmark.md`](docs/benchmark.md) | Organizations and practices used as benchmarks |
| [`tools/quality/`](tools/quality/) | The check that keeps the content rule honest |

This repository publishes no `LICENSE`. The one proposed alongside these files
had the Apache-2.0 appendix missing and one clause reworded, and altered licence
text is not the licence it claims to be.

## How organization defaults work

- A file inside an individual repository takes precedence over the default
  published here. Add a local file only when a repository genuinely needs a
  different policy.
- GitHub inherits only supported community health files and templates. The
  profile and governance documents remain specific to this repository.
- Changes here can affect every repository that relies on the default. Review
  them as organization-wide production changes.
- This repository is public. It must contain only general engineering policy.
  Never add hostnames, addresses, file system paths, secret names, credentials,
  infrastructure topology, personal data, or anything specific to a deployment
  environment. The list is deliberately enumerable, because a rule a check can
  be written against outlives a rule that only sounds careful.
- GitHub does not support an inherited default `LICENSE`. Every repository must
  select and publish its own license.

## License

This repository does not currently publish a license, so default copyright
applies and its contents are not licensed for reuse. `CODE_OF_CONDUCT.md` is the
exception: it is the Contributor Covenant and carries its own CC BY 4.0 terms.

