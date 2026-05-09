# Changelog

## v0.1-demo-public - 2026-05-09

Public GitHub release closure for the v0.1 demo.

Included scope:

- Sanitized public documentation to replace local paths, LAN addresses, and private Pi identifiers with placeholders.
- Sanitized deployment defaults so the public helper script no longer embeds a real Pi target.
- Added MIT license metadata and safe demo screenshots to the root README.
- Updated the repository version marker to `v0.1-demo-public`.

Release notes:

- No feature work or core business logic changes are included in this release closure.
- `piboard/data/state.json` remains ignored and must not be committed.
- Private iCal URLs, API tokens, and real keys are intentionally excluded.

## v0.1-demo - 2026-05-08

Initial Git version record for PiBoard.

Included scope:

- UK railway-style LED dot-matrix display renderer.
- Single, dual, and carousel display layouts.
- Weather, calendar, train, custom, and mock content providers.
- Source/Binding bridge layer for productized data-to-display mapping.
- Chinese-first local Web console for page, source, device, and display settings.
- Raspberry Pi KMSDRM deployment assets and deployment record.
- Visual QA screenshots and review artifacts.

Known gaps at this version:

- No automated test suite yet.
- Current local runtime state is intentionally excluded from Git.
- Pi-side verification should be repeated after the latest local UI/content changes.

Follow-up records:

- `350c022` added the Pi acceptance record in `docs/v0.1-demo.md`.
- `475ecea` added safe Pi acceptance screenshots under `piboard/review_artifacts/pi-acceptance-v0.1-demo/`.
- `piboard/data/state.json` remains ignored; `piboard/data/state.example.json` is the public example config.
- README/TODO now describe the current `v0.1-demo` MVP: port `8080`, brightness overlay, Open-Meteo default weather, Pi deployment, and acceptance evidence.
