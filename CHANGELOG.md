# Changelog

## v0.1.1 - 2026-05-12

### Fixed

- Added a Pi-readable runtime version marker through `BUILD_INFO` and `/api/version`.
- Marked mock/demo train, weather fallback, and calendar fallback states so they are not presented as live data.
- Clarified Web console copy for Overview, Train, Weather, Calendar, and Custom data truthfulness.

### Verified

- Local Python compile check passes for `piboard`.
- Minimal v0.1.1 smoke checks cover mock cycle order, state example JSON, Train mock bridge, Weather no-key Open-Meteo path selection, and API/state shape.
- Open-Meteo live weather path was verified locally with no API key.
- Current HEAD was deployed to Pi, `/api/version` returned `v0.1.1`, `piboard.service` was active/enabled, and Overview/Train/Weather/Calendar/Custom page switching passed in a safe acceptance state.

### Documentation

- Updated README scope for `v0.1.1`.
- Added `docs/v0.1.1.md` acceptance record structure.
- Updated `piboard/README.md` to separate verified behavior from mock/demo and pending live checks.

### Known Issues

- Huxley2 live requests returned HTTP 500 during local release validation, so Train live is not claimed as verified in `v0.1.1`.
- Calendar live is not claimed as verified without a safe public iCal test feed.

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
