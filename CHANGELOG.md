# Changelog

## v0.1.2 - 2026-11-12

### Fixed

- Integrated the runtime, board typography and console fixes from `v0.1.2-rc.1` without adding pages, layouts or data-source types.
- Rejected malformed/non-object JSON, invalid layouts/slots, source field types/options and invalid settings before mutation in canonical and compatibility REST/WebSocket writes. Invalid WebSocket messages receive an error without closing an otherwise usable connection.

### Verified

- Local and Pi: compile checks, 41 unittest cases and 10 release/visual smoke checks pass. Local console browser checks pass at five desktop/mobile widths.
- Pi: existing service active/enabled on SDL kmsdrm; five-page API switching keeps the render process alive; private configuration restores exactly. HTTP remains responsive alongside WebSocket connections.
- Pi: saved-location Open-Meteo fetch and the existing private iCal subscription fetch pass (0 calendar events in the checked window). Train upstream failure is handled visibly as WAIT, not verified live departures.
- Deployed source files are checksum-verified against the clean commit. Final tag/commit/marker evidence is attached to the GitHub Release; public PNGs are safe offscreen Pi renders, not physical panel photos.

### Documentation

- Added `docs/v0.1.2.md`, a reproducible opt-in Pi acceptance helper and safe hardware-rendered specimens.
- Updated both README languages and technical-guide status; retained historical candidate/audit records with their original scope.

### Known Issues

- Both Huxley2-compatible endpoints returned HTTP 500 for BHM during acceptance; live train availability is not claimed. No new endpoint/data-source type was added to hide the outage.
- Complete iCal recurrence/multi-day semantics, OpenWeatherMap overview compatibility and concurrent multi-controller settings conflicts remain out of scope.
- Console remains unauthenticated, trusted-LAN only. CPU/RSS targets are not fully met; physical panel optics and long-duration soak testing are not certified by offscreen renders.

## v0.1.2-rc.1 - 2026-11-12

Integration candidate, not a final Pi-accepted release. The `v0.1.1` tag remains unchanged.

### Fixed

- Kept HTTP requests responsive alongside WebSocket connections and removed the application-level idle disconnect.
- Bounded duplicate background refreshes and stopped scheduling before executor shutdown.
- Made state recovery atomic, restored missing app defaults, preserved legacy manual weather cities, and supported saving to a filename without a directory.
- Corrected rotated System Status layout, idle carousel/page-flip wakeups, and pagination after row-count changes.
- Corrected train demo/live/stale labels and calendar cache expiry in Overview.
- Fixed installer user/port hints and custom service-name installation; removed the unused provider-class registry placeholder.
- Refined board geometry, mixed-script alignment, measured truncation, static pagination and transition clearing without changing the page/data-source set.
- Corrected S/0/N/V/W bitmap patterns and minimum inter-character separation; retained native dot dimensions and added a portable before/after review page.
- Unified console colors, local licensed icons, mobile controls, keyboard focus, navigation scroll retention and loading/error feedback.
- Included earlier post-v0.1.1 endpoint and console hotfixes already present on main:
- Switched the default Huxley2-compatible Train live endpoint to `https://national-rail-api.davwheat.dev` after the original Azure endpoint returned HTTP 500.
- Added `huxley2_base_url` to Train configuration and kept the original Azure endpoint as a fallback.

### Verified

- Historical endpoint hotfix: BHM live departures returned locally and on Pi; this is not a fresh live-service check for this candidate.
- Local release/visual smoke checks and runtime/display/font regression checks are reproducible using the commands in `docs/v0.1.2-rc.1.md`.
- Presentation overlay and the exact human-approved font checksum were verified on Pi separately; 7 font and 9 display tests passed there. Full integration of the runtime fixes remains pending.

### Documentation

- Added runtime audit, visual review, font acceptance and candidate release records with safe evidence.
- Updated version/readmes to distinguish source candidate, historical release and deployed overlays; excluded private handover notes and runtime state.

### Known Issues

- Full candidate Pi deployment/acceptance has not been performed; no final `v0.1.2` tag is created.
- Write API input validation, concurrent settings updates, complete iCal recurrence handling and OpenWeatherMap overview compatibility remain open; the console is trusted-LAN only.
- External live-service availability and hardware performance targets are not established by offline fixtures.

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
