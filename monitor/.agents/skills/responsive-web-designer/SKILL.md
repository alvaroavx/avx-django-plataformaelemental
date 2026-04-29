---
name: responsive-web-designer
description: Use when designing or implementing monitor templates, dashboard states, site detail pages, responsive behavior, accessibility, and AVX Mission Control visual direction.
---

# Responsive Web Designer - monitor

## Scope
Design and template work inside `monitor/`.

## Visual direction
Use `monitor/docs/13-design-direction.md` as the source for AVX Mission Control:
- control cabin
- radar
- system matrix
- threat console
- telemetry stream

## Principles
- Operational clarity beats decoration.
- Color communicates status.
- Mobile must solve the same task, not merely shrink desktop.
- Avoid wide tables for primary mobile workflows.
- Empty states need a clear next action.

## Workflow
1. Read `monitor/AGENTS.md`.
2. Read `monitor/docs/13-design-direction.md`.
3. Identify desktop and mobile layouts before editing.
4. Implement templates and CSS within `monitor/`.
5. Check text wrapping, focus states and empty states.

## Expected UI
- Dashboard summary cards.
- Compact status lists.
- Severity indicators with text labels or icons.
- Site detail panels.
- Clear primary action for adding a site.

## Accessibility
- Do not rely on color alone.
- Use semantic buttons and links.
- Keep focus visible.
- Keep contrast readable.
