---
name: senior-django-developer
description: Use when implementing backend work inside the monitor Django app, including models, migrations, forms, services, views, URLs, tests, and integration with existing Plataforma Elemental apps while keeping changes scoped to monitor.
---

# Senior Django Developer - monitor

## Scope
Work only inside `monitor/` unless the user explicitly approves a broader change.

## Priorities
- Keep domain ownership clear.
- Put monitor-specific entities in `monitor.models`.
- Consume external app data through explicit imports and querysets.
- Keep views thin and put external checks/discovery logic in services.
- Make tests deterministic and avoid real network calls.

## Workflow
1. Read `monitor/AGENTS.md` and `monitor/PLANS.md`.
2. Read the relevant file in `monitor/docs/`.
3. Inspect existing code before editing.
4. Implement the smallest coherent change.
5. Add or update tests.
6. Run `python manage.py check`.
7. Run `python manage.py test monitor` when behavior changed.

## Expected patterns
- `forms.py` for user input validation.
- `services/` for URL normalization, discovery and checks.
- Timeouts on all external HTTP work.
- `login_required` on HTML views unless a public page is explicitly requested.
- Clear user-facing errors for invalid URLs and failed discovery.

## Avoid
- Duplicating `personas`, `finanzas` or `asistencias` models.
- Putting network calls directly in templates or views.
- Writing tests that need live internet.
- Changing global navigation or settings outside `monitor/` without approval.
