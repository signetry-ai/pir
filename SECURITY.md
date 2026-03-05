# Security Policy

## Reporting a Vulnerability

If you discover a security issue in the PIR schema, validation logic, or data integrity of certified records, please report it privately.

**Email:** security@signetry.ai

**Do not** open a public GitHub issue for security vulnerabilities.

## Scope

- Schema validation bypass (allowing invalid or malicious data through CI)
- Brand certification spoofing (setting `brand_certified: true` without owning the domain)
- Data integrity attacks on certified records
- Injection via record fields that could affect downstream consumers

## Out of Scope

- Factual inaccuracies in uncertified (`brand_certified: false`) records — open a regular issue
- Records with incorrect GTINs — open a regular issue or PR
- The Signetry API serving this data — report to security@signetry.ai separately

## Response

We aim to acknowledge reports within 48 hours and resolve confirmed vulnerabilities within 14 days.
