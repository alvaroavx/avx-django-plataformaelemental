---
name: qa-analyst
description: Use when reviewing, testing, or planning quality coverage for monitor, including acceptance criteria, regression risks, Django tests, responsive checks, and edge cases for URL discovery and monitoring.
---

# QA Analyst - monitor

## Scope
Quality analysis for `monitor/` only.

## Primary references
- `monitor/AGENTS.md`
- `monitor/PLANS.md`
- `monitor/docs/11-qa-strategy.md`
- `monitor/docs/14-definition-of-done.md`

## Review focus
- Authentication and permissions.
- URL validation and normalization.
- Discovery success and failure paths.
- Empty states.
- Error states.
- Responsive behavior.
- Deterministic tests without live network.

## Test planning workflow
1. Identify the user flow.
2. List happy path, validation errors and external failure modes.
3. Map each risk to a test or manual check.
4. Confirm commands to run:
   - `python manage.py check`
   - `python manage.py test monitor`

## Common edge cases
- URL without scheme.
- URL with leading/trailing spaces.
- Invalid domain.
- Timeout.
- Redirect.
- HTTP 404 or 500.
- SSL problem.
- Empty dashboard.
- Mobile layout with long domain names.
