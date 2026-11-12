# PiBoard Visual Review Implementation Plan

**Goal:** Improve everyday legibility and operation while preserving the existing British railway LED display language.

**Architecture:** Keep BoardContent, providers, APIs and saved configuration unchanged. Apply shared rendering fixes to all board pages and presentation-only HTML/CSS/JS fixes to the existing console.

**Tech Stack:** pygame bitmap renderer, Flask templates, plain JavaScript and CSS.

**Spec:** User's 2026-11-11 visual review request; `piboard/docs/design-language.md`.

## Constraints

- All files, captures, backups and temporary output stay inside this project.
- Preserve all pre-existing uncommitted work. Do not deploy unrelated audit changes.
- Keep the five board pages, system display and four console views; no new product pages or data sources.
- Preserve bitmap glyph proportions, amber-on-dark identity and semantic status colors.
- Verify with synthetic fixtures; do not copy private calendar URLs or events into evidence.
- User authorized autonomous implementation. No additional design approval is pending.

## Review Focus

- Mixed Chinese/English and punctuation: consistent baseline and no stretched glyphs.
- Long station names and narrow/half boards: title, subtitle and rows remain in bounds.
- Animated/static tickers and multi-page lists: no chopped Unicode or unreachable rows.
- Mobile and keyboard: visible focus, reachable buttons, stable loading states and scroll positions.
- Empty/loading/error/disconnected states: meaningful and honest, without duplicate noise.

## Tasks

- [x] Capture current console views and generate all board fixtures before editing.
- [x] Back up affected files, including their existing uncommitted state.
- [x] Correct shared typography, region sizing, fitting and ticker width handling.
- [x] Check Overview, Train, Weather, Calendar, Custom, System Status, single/dual/carousel and themes.
- [x] Refine console contrast, responsive spacing, form grouping, focus, click targets, notifications and selection states.
- [x] Exercise all four console views, editing, accordions, navigation, loading/error states and reduced motion in an isolated local preview.
- [x] Run focused rendering/interaction regression checks and existing smoke checks.
- [x] Compare fresh before/after images, record remaining limits and publish a concise review document.

Pi display overlay deployed and checked: 9/9 display regressions, all 20 responsive console views, unchanged private configuration checksum, active/enabled service. See the review record for the artifact checksum, backup paths and physical-screen verification limits.

## Evidence

Generated evidence and pre-edit backups: `.visual-review/2026-11-11/` (ignored).
Durable findings and reproducible checks: `docs/visual-review-2026-11-11.md`.
