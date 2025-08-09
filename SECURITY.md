# Security Policy

## Reporting a Vulnerability
- Please open a private issue or email the maintainer (add contact) with details.
- Do not disclose publicly until we confirm a fix or mitigation.

## Secrets
- Never commit secrets. Use environment variables (`.env` is git-ignored).
- Tokens required: Telegram/Slack tokens, and the Claude/Anthropic credentials used by `claude-code-sdk` (e.g., `ANTHROPIC_API_KEY`).
