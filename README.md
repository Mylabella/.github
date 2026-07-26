# Organization defaults

This repository holds the default community health files for the `Mylabella`
organization. GitHub applies them automatically to every repository that does
not provide its own file of the same name.

| File | Applies to |
| --- | --- |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branching, pull requests, dependencies, releases |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |
| [.github/pull_request_template.md](.github/pull_request_template.md) | Default pull request body |

## Rules

- A file inside a repository always wins over the default published here.
  Remove the local copy to inherit the organization default.
- This repository is public. It must contain only general engineering policy.
  Never add hostnames, addresses, file system paths, secret names, credentials,
  infrastructure topology, or anything specific to a deployment environment.
- Changes here take effect immediately in every repository that relies on the
  default. Review them as production changes.
- Default license files are not supported by GitHub. Every repository keeps its
  own `LICENSE`.
