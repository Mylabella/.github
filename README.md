# Mylabella organization defaults

This public repository is the shared community and engineering baseline for the
`Mylabella` organization. GitHub uses supported files here as fallbacks for
organization repositories that do not provide a local version.

## Repository map

| Path | Purpose |
| --- | --- |
| [`profile/README.md`](profile/README.md) | Public organization profile |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contribution and engineering workflow |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community participation standards |
| [`SECURITY.md`](SECURITY.md) | Private vulnerability reporting |
| [`SUPPORT.md`](SUPPORT.md) | Routing for bugs, questions, and proposals |
| [`GOVERNANCE.md`](GOVERNANCE.md) | Maintainer-led decisions and project lifecycle |
| [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) | Default bug and feature forms |
| [`.github/pull_request_template.md`](.github/pull_request_template.md) | Default pull-request body |
| [`docs/benchmark.md`](docs/benchmark.md) | Organizations and practices used as benchmarks |

## How organization defaults work

- A file inside an individual repository takes precedence over the default
  published here. Add a local file only when a repository genuinely needs a
  different policy.
- GitHub inherits only supported community health files and templates. The
  profile and governance documents remain specific to this repository.
- Changes here can affect every repository that relies on the default. Review
  them as organization-wide production changes.
- This repository is public. It must never contain credentials, private
  infrastructure details, personal data, internal paths, or unpublished product
  information.
- GitHub does not support an inherited default `LICENSE`. Every repository must
  select and publish its own license.

## License

Except where a file states otherwise, the contents of this repository are
licensed under the [Apache License 2.0](LICENSE). The license applies only to
this repository; it does not set the license of other Mylabella repositories.

