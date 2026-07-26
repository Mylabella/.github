# Governance

Mylabella uses maintainer-led governance suited to a small, independent
engineering organization. The aim is to make responsibility and decisions
visible without introducing process that the current project scale cannot
support.

## Roles

### Organization owners

Organization owners are responsible for:

- repository visibility, access, and organization-wide settings;
- shared community health and security policy;
- appointing or removing repository maintainers;
- resolving cross-repository or conduct escalations;
- archiving projects that no longer have a credible maintenance path.

### Repository maintainers

Maintainers are responsible for:

- the repository roadmap, architecture, review, releases, and support status;
- protecting user data and production systems;
- documenting project-specific decisions and ex…247 tokens truncated…resolved conflict of
  interest makes impartial review unreasonable.

There is currently no voting body or guaranteed appeal panel. When consensus is
not possible, the responsible maintainer must document the decision and its
rationale.

## Project lifecycle

Each public repository should state one of these stages in its README:

| Stage | Meaning |
| --- | --- |
| Experimental | Exploration; interfaces and availability may change without notice |
| Active | Maintained and accepting appropriately scoped contributions |
| Maintenance | Supported selectively; major new features are unlikely |
| Archived | Read-only historical reference; no support or security fixes promised |

A project may move between stages when its maintainer capacity, purpose, or risk
changes. Archiving is preferable to presenting an unmaintained project as
active.

## Organization-wide policy

Changes to this `.github` repository require a pull request and should be
reviewed as changes to every repository that inherits its defaults. A local
repository policy may override an organization default when the exception is
documented and no weaker security boundary is introduced without explicit
approval.

## Amendments

This governance document evolves through pull requests. Material changes should
explain the problem, affected repositories, rejected alternatives, and
transition impact.

