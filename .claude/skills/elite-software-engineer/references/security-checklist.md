# Security Checklist

Use whenever code touches inputs, auth, files, URLs, secrets, database queries, serialization, templates, HTML, commands, dependencies, or external services.

## Check

- Authentication is required where needed.
- Authorization checks are enforced server-side.
- Input validation is explicit.
- SQL/NoSQL injection is prevented.
- XSS is prevented by escaping/sanitization.
- CSRF is considered for browser state-changing actions.
- SSRF is prevented for user-controlled URLs.
- Path traversal is prevented.
- Shell injection is prevented.
- Secrets are not logged or committed.
- Sensitive data is redacted.
- Dependencies are justified and maintained.
- Error messages do not leak sensitive internals.
- Rate limiting/abuse protection considered when relevant.

## Output

```markdown
## Security Review

Critical:
High:
Medium:
Low:
No findings:
Residual risks:
```
