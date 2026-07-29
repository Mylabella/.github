# Security policy

Security reports are handled privately. Do not disclose a suspected
vulnerability in a public issue, discussion, pull request, commit, or chat.

## Reporting a vulnerability

Use the affected repository's **Security** tab and GitHub private vulnerability
reporting when it is enabled. If it is unavailable, contact a repository owner
privately using a verified contact method associated with their GitHub profile.

Include only the information needed to investigate:

- affected repository, component, and version or commit;
- prerequisites and minimal reproduction steps;
- observed behavior and likely impact;
- any known workaround or suggested mitigation;
- whether the issue has been disclosed elsewhere.

Do not include active credentials, production personal data, customer
information, or unnecessary exploit material. If sensitive evidence is
essential, first agree on a safe transfer method with the maintainer.

## What to expect

Maintainers will assess scope, severity, affected versions, and a remediation
path. Response and release timing depend on project maturity and maintainer
availability; this policy does not promise a service-level agreement.

Please allow a reasonable period for investigation and coordinated remediation
before public disclosure. Maintainers will credit reporters who request credit
when doing so is safe and appropriate.

## Supported versions

Each repository defines its own supported versions and deployment assumptions.
Experimental or archived projects may not receive security fixes. When no
support table is published, only the latest revision of the default branch
should be assumed to be in scope.

Implementation-specific security requirements belong in the affected
repository under `docs/` or in its local `SECURITY.md`.

