# Security Policy

## Supported Versions

PenG is an early-stage open-source project and does not currently maintain
versioned security releases. Please report vulnerabilities against the latest
repository state.

## Reporting a Vulnerability

Do not disclose suspected vulnerabilities in a public GitHub issue. Use the
repository's private GitHub security advisory workflow if it is enabled. If it
is not available, contact the maintainers through the private contact channel
listed in the repository profile and include `[SECURITY]` in the subject.

Please include:

- A concise description and impact.
- Reproduction steps or a minimal proof of concept.
- Affected commit, endpoint, configuration, or dependency.
- Any proposed mitigation.

Do not include real API keys, ngrok tokens, private documents, personal data,
or other secrets in a report. Redact logs and use synthetic files.

## Security Scope and Limitations

- PenG is a local/Colab MVP, not a production multi-tenant service.
- The API has no authentication or authorization layer.
- Uploaded files and generated SQLite/LightRAG data are local runtime data;
  operators must protect the host and any public tunnel.
- Model output is untrusted input. The mindmap path sanitizes Markdown before
  rendering, but deployments should still review browser and reverse-proxy
  policies.
- Do not expose a Colab/ngrok server to sensitive data without adding access
  control, transport, storage, and resource protections.

We will acknowledge valid reports when possible and coordinate disclosure with
the reporter.
