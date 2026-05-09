# Raspberry Pi Deployment Record - 2026-04-29

## Connection

- Target: `<pi-user>@<pi-host>`, fallback `<pi-user>@<pi-ip>`
- Hostname: `<pi-host>`
- Deployment path: `/home/<pi-user>/CC-UK-TR`
- App path: `/home/<pi-user>/CC-UK-TR/piboard`

## Pi Self Check

- OS: Raspbian GNU/Linux 13 (trixie)
- Kernel: `Linux <pi-host> 6.12.47+rpt-rpi-v7 #1 SMP Raspbian 1:6.12.47-1+rpt1 (2025-09-16) armv7l GNU/Linux`
- Python: `Python 3.13.5`
- pip: `pip 25.1.1`
- Disk: `/dev/mmcblk0p2` 29G total, 4.8G used, 23G available
- Memory before deploy: 425Mi total, about 124Mi available
- Display session: `rpd-labwc`, Wayland, active seat session
- Display output: `HDMI-A-1`, current mode `1024x600`, transform `90`
- DRI devices: `/dev/dri/card0`, `/dev/dri/renderD128`
- User groups include `video` and `render`

## Existing UK Transport Demo

- Existing demo directory: `/home/<pi-user>/UK-transport-LED`
- Existing system service: `uk-transport-led.service`
- Service state: `enabled`, but inactive during this deployment
- Active old demo processes found:
  - `/usr/bin/labwc -m`
  - Chromium kiosk opening `http://127.0.0.1:8080/index.html?kiosk=display-v3`
  - `python3 -m http.server 8080` with cwd `/home/<pi-user>/UK-transport-LED`
- Startup source: `~/.config/labwc/autostart`
- Temporary stop performed:
  - Sent TERM only to the old Chromium kiosk process and its old `http.server 8080`
  - Left `labwc` running
  - Did not delete, overwrite, disable, or edit old demo files or service

## Sync And Dependencies

- Sync method: `rsync -az`
- Safe sync helper: `deployment/sync-to-pi.sh` stops `piboard.service`
  before syncing, preventing the old process from saving stale state during
  shutdown.
- Excluded: `__pycache__`, `.DS_Store`, `review_artifacts`, `*.pyc`
- Requirements file confirmed: `/home/<pi-user>/CC-UK-TR/piboard/requirements.txt`
- Core files confirmed:
  - `/home/<pi-user>/CC-UK-TR/piboard/main.py`
  - `/home/<pi-user>/CC-UK-TR/piboard/config.py`
  - `/home/<pi-user>/CC-UK-TR/piboard/piboard.service`
- Python validation:
  - `python3 -m compileall -q piboard` passed
  - `pygame 2.6.1 (SDL 2.32.4, Python 3.13.5)`
  - `flask`, `flask_sock`, `requests`, `icalendar` import passed
- Packages installed:
  - `flask-sock 0.7.0`
  - `icalendar 7.0.3`
  - `simple-websocket 1.1.0`
  - `tzdata 2026.2`
  - `wsproto 1.3.2`
  - `h11 0.16.0`

## Manual Run

The successful manual run used the existing Wayland/labwc display session:

```bash
env XDG_RUNTIME_DIR=/run/user/1000 \
    WAYLAND_DISPLAY=wayland-0 \
    SDL_VIDEODRIVER=wayland \
    SDL_AUDIODRIVER=dummy \
    PYTHONUNBUFFERED=1 \
    setsid -f python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait \
    > /tmp/piboard-run.log 2>&1 < /dev/null
```

Runtime log confirmed:

- `Screen: 600x1024 (portrait)`
- Web server on `http://<pi-ip>:8080`
- Current state: `uk_station`, `single`, slot `mock`
- Mock preset restored to `overview`

## Visual Verification

Screenshots captured via `grim` from the Pi Wayland session and copied back locally:

- Overview: `<repo>/piboard-deploy-overview.png`
- Final Overview after detached restart: `<repo>/piboard-deploy-final-overview.png`
- Rail: `<repo>/piboard-deploy-rail.png`
- Weather: `<repo>/piboard-deploy-weather.png`
- Schedule: `<repo>/piboard-deploy-schedule.png`

Observed:

- Overview, Rail, Weather, and Schedule all render at `600x1024`
- Portrait orientation is correct
- No visible window border in screenshots
- No visible mouse cursor in screenshots
- No obvious edge cropping
- Text is readable on the 600px width capture
- Ticker/status band is visible

## Autostart

Autostart was not changed in this pass.

Reason: the old UK demo still has an enabled system service and a labwc autostart entry. Switching boot behavior safely requires explicit approval to replace or disable the old startup path.

## Open Issues

1. PiBoard runs correctly under Wayland/labwc, but CPU is high: `top` showed the Python process around `90-110%` CPU and about `114MiB` RSS.
2. Temporarily setting `animations_enabled=false` did not lower CPU during this test, so the issue is not solved by runtime app settings alone.
3. Production startup mode needs a decision:
   - Keep labwc and run PiBoard through SDL Wayland fullscreen, then optimize CPU.
   - Or switch to the project-intended direct SDL `kmsdrm` mode, which likely requires replacing the old labwc/chromium kiosk startup path.
4. Boot autostart is still old-demo-first until the startup path is explicitly switched.

## KMSDRM Cutover - 2026-04-29 02:32-02:44 CST

Follow-up action after the initial deployment: switched the Pi from the old labwc/Chromium kiosk route to PiBoard direct SDL `kmsdrm`.

### Backups

Created before changing startup services:

- `/home/<pi-user>/piboard-deploy-backups/20260429-0232-kmsdrm-test/labwc-autostart`
- `/home/<pi-user>/piboard-deploy-backups/20260429-0232-kmsdrm-test/labwc-environment`
- `/home/<pi-user>/piboard-deploy-backups/20260429-0232-kmsdrm-test/labwc-rc.xml`
- `/home/<pi-user>/piboard-deploy-backups/20260429-0232-kmsdrm-test/uk-transport-led.service`
- `/home/<pi-user>/piboard-deploy-backups/20260429-0232-kmsdrm-test/display-manager.status`
- `/home/<pi-user>/piboard-deploy-backups/20260429-0232-kmsdrm-test/uk-transport-led.status`

### Temporary KMSDRM Test

Stopped the display manager temporarily:

```bash
sudo systemctl stop display-manager
```

Manual direct-render test:

```bash
cd /home/<pi-user>/CC-UK-TR/piboard
SDL_VIDEODRIVER=kmsdrm SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1 \
  python3 main.py --portrait
```

Result:

- PiBoard started successfully.
- Log confirmed `Screen: 600x1024 (portrait)`.
- Web API worked at `http://<pi-ip>:8080`.
- Rail, Weather, Schedule, and Overview mock presets switched successfully through the API.

### CPU Fix

KMSDRM itself started correctly, but CPU initially remained near `100%` because `UKStationApp.is_animating()` still treated ticker state as active even when `animations_enabled=false`.

Applied a narrow code fix in:

- `/home/<pi-user>/CC-UK-TR/piboard/apps/uk_station/app.py`
- local source: `<repo>/piboard/apps/uk_station/app.py`

Change: `_check_anim_controller()` now returns `False` immediately when its animation controller is disabled.

With `animations_enabled=false`, PiBoard entered the low-frame idle path:

- PiBoard process CPU sample: `0.0%`
- Temperature after test: about `51.5-53.7'C`
- `vcgencmd get_throttled`: `0x0`

Tradeoff: ticker/page animations are disabled for the low-heat boot profile. Static pages and API-driven page changes still render.

### Installed Service

Service template added locally:

- `<repo>/piboard/deployment/piboard-kmsdrm.service`

Installed on Pi as:

- `/etc/systemd/system/piboard.service`

Service summary:

```ini
User=<pi-user>
WorkingDirectory=/home/<pi-user>/CC-UK-TR/piboard
ExecStart=/usr/bin/python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=dummy
```

Startup switch:

```bash
sudo systemctl disable lightdm.service
sudo systemctl disable uk-transport-led.service
sudo systemctl enable piboard.service
sudo systemctl start piboard.service
```

Old demo files were not deleted and old labwc config files were not edited.

### Reboot Verification

After `sudo reboot`:

- `piboard.service`: enabled and active
- `lightdm.service`: disabled and inactive
- `uk-transport-led.service`: disabled and inactive
- Active display process: `/usr/bin/python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait`
- No `labwc`, `chromium`, old `http.server 8080`, or `UK-transport-LED` process was running
- API state: `uk_station`, layout `single`, slot `mock`, mock preset `overview`, orientation `portrait`, `animations_enabled=false`
- CPU sample after reboot: `0.0%`
- Temperature after reboot: about `53.2'C`
- Throttling: `0x0`

### Physical Portrait Rotation Fix

After user visual inspection, the direct `kmsdrm` output still appeared landscape on the portrait-mounted 7-inch HDMI panel. The previous labwc route used `wlr-randr --transform 90`; direct `kmsdrm` has no compositor transform, so PiBoard now supports an explicit physical output rotation.

Files changed:

- `<repo>/piboard/main.py`
- `<repo>/piboard/host/host.py`
- `<repo>/piboard/deployment/piboard-kmsdrm.service`

Current service command:

```ini
ExecStart=/usr/bin/python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait --display-rotate 90
```

Runtime log after restart:

```text
Screen: logical 600x1024 (portrait), physical 1024x600, rotate=90
```

CPU stayed low after the rotation path was enabled:

- PiBoard process CPU sample: `0.0%`

If the physical direction is reversed on the mounted panel, change only the service argument from `--display-rotate 90` to `--display-rotate 270`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl restart piboard.service
```

### Current Page Switching Behavior

Current state:

- Layout: `single`
- Slot: `mock`
- Mock preset: `overview`
- App animations: `false`

Therefore the board does not automatically switch pages right now. It stays on the Overview / comprehensive schedule page.

## Local Weather Live-Data Fix - 2026-04-29

Follow-up action after Web console testing: the Weather page no longer uses the old London default or mock weather when no OpenWeatherMap API key is configured.

Files changed:

- `<repo>/piboard/sources/weather.py`
- `<repo>/piboard/providers/weather.py`
- `<repo>/piboard/providers/weather_bridge.py`
- `<repo>/piboard/bindings/weather_to_uk.py`
- `<repo>/piboard/state.py`
- `<repo>/piboard/web/static/app.js`
- `<repo>/piboard/web/server.py`
- `<repo>/piboard/data/fetcher.py`

Behavior:

- No API key path now uses Open-Meteo live data.
- Manual city mode geocodes the city name through Open-Meteo geocoding, then fetches forecast/current weather by latitude/longitude.
- Auto location mode uses browser geolocation when the Web console is opened and permission is granted; it stores latitude/longitude in `data/state.json`.
- Legacy default `city=London` is migrated away when it matches the old no-key default shape.
- "保存并刷新" and "只刷新" now wait for the forced refresh to complete before showing success. Weather failures or timeouts return Chinese errors instead of reporting success too early.

Local Beijing validation:

- Config tested: `location_mode=manual`, `city=Beijing`, `api_key=""`, `units=metric`
- Open-Meteo geocoding result: Beijing / `39.9075, 116.39723`
- Open-Meteo current result at `2026-04-29T17:00` Beijing local time:
  - `temperature_2m`: `22.8`
  - `relative_humidity_2m`: `14`
  - `apparent_temperature`: `18.2`
  - `weather_code`: `0`
  - `wind_speed_10m`: `11.7`
  - `wind_direction_10m`: `221`
  - `visibility`: `16220.0`
- Rendered PiBoard fields matched:
  - Hero temperature: `23°C`
  - Humidity row: `14%`
  - Visibility row: `16KM`
  - Wind row: `SW 12KM/H`

Validation artifacts:

- `<repo>/piboard/weather-beijing-live-check.json`
- `<repo>/piboard/weather-beijing-live-check.png`

The existing carousel layout interval in code is `10_000 ms` (10 seconds), but it is not currently enabled in this low-heat boot profile.

### Screenshot Note

Wayland screenshots from the initial validation remain valid for UI rendering. After switching to direct `kmsdrm`, `grim` is unavailable because there is no Wayland compositor. `ffmpeg` `kmsgrab` failed because the DRM framebuffer handle was not exposed, and `/dev/fb0` captured the legacy framebuffer rather than the live PiBoard plane. Direct `kmsdrm` visual confirmation should be done by looking at the panel or taking a photo.

### Rollback

To return to the old desktop/kiosk path:

```bash
sudo systemctl stop piboard.service
sudo systemctl disable piboard.service
sudo systemctl enable lightdm.service
sudo systemctl enable uk-transport-led.service
sudo reboot
```

If labwc config needs restoration, copy files back from:

```bash
/home/<pi-user>/piboard-deploy-backups/20260429-0232-kmsdrm-test/
```

### Local Low-Power Dynamic Prep - 2026-04-29

Local-only changes prepared while the Pi hardware is unavailable. These changes
have not yet been synced to `/home/<pi-user>/CC-UK-TR/piboard`.

Goal: keep `animations_enabled=false` for the low-heat boot profile, while
allowing occasional content changes without restoring continuous 30fps ticker
animation.

Implemented locally:

- `DataFetcher` now marks `app_state` dirty after a successful provider fetch,
  so low-power mode can redraw when data changes.
- `BaseProvider.get_refresh_interval()` allows a provider to expose a
  config-driven refresh interval.
- `MockProvider` now defaults to a 60 second refresh cadence and supports
  `refresh_interval_sec` in its Web/source schema.
- `MockProvider` `preset=cycle` now rotates:
  `overview -> train -> weather -> calendar -> overview`.
- Mock cycle content now sets distinct content IDs such as `mock:overview` and
  `mock:train`, so layout animation state is reset cleanly when the mock page
  changes.
- `BaseApp` / `BaseLayout` now expose optional `next_render_ms()` for
  low-frequency scheduled rendering.
- `CarouselLayout` uses `60_000 ms` when animations are disabled, and switches
  statically at that cadence instead of running continuous animation frames.
- `BoardContent` now supports render-time header clocks via
  `header_left_clock_format` / `header_right_clock_format`.
- `UKStationApp` schedules a single low-power redraw at the next real minute
  boundary when the active content has a render-time header clock.
- Overview, train, and weather mock pages now update their top header clock on
  the minute without waiting for the next provider refresh.
- Local `data/state.json` is set to:
  - `layout=single`
  - `slot=mock`
  - `mock.preset=cycle`
  - `mock.refresh_interval_sec=60`
  - `animations_enabled=false`
  - `orientation=portrait`

Validation run locally:

```bash
PYTHONPYCACHEPREFIX=/tmp/piboard-pycache python3 -m compileall -q .
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 <carousel-low-power-smoke-test>
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 <minute-clock-smoke-test>
python3 <mock-cycle-smoke-test>
python3 -m json.tool data/state.json
```

Next Pi-side deployment plan:

1. Run `deployment/sync-to-pi.sh`.
2. Confirm the installed `piboard.service` command uses
   `--portrait --display-rotate 90`.
3. Confirm the state API shows `animations_enabled=false`,
   `mock.preset=cycle`, and `refresh_interval_sec=60`.
4. Observe CPU and temperature across at least two 60 second page changes.

### Local Web Console Rework - 2026-04-29

Local-only Web console changes prepared after the low-power dynamic work.
These changes have not yet been synced to the Pi.

Implemented locally:

- The Web console is now Chinese-first and opens on `页面内容`.
- Navigation is reorganized into:
  - `页面内容`
  - `数据源`
  - `设备状态`
  - `显示设置`
- `页面内容` provides cards for `概览`, `列车`, `天气`, `日程`, and `自定义`.
- Each page card has `设为当前页面` and `保存并刷新`.
- `自定义` keeps full manual editing for title, subtitle, rows, footer,
  status, and ticker.
- Live-data pages keep editing focused on their source configuration rather
  than adding a manual override layer.
- Mock low-power carousel now supports `cycle_presets`, with the default:
  `overview -> train -> weather -> calendar`.
- Web source schemas now support `multi_select`, used by the carousel page
  picker.
- Added `GET /api/device-status`.
  - Mac/local preview returns hostname and app/device state, with
    `temp_c=null` and `throttled=null`.
  - Pi reads `/sys/class/thermal/thermal_zone0/temp`.
  - Pi attempts `vcgencmd get_throttled`.
- Frontend requests now use one `apiRequest()` path with HTTP error handling.
- Save buttons enter a disabled/loading state until the request completes.
- Settings saves use a debounced `Promise.all()` for app/device settings.
- WebSocket updates no longer rebuild source/page forms while the user has
  unsaved edits.
- `DataFetcher.force_refresh()` now submits an immediate background fetch
  instead of waiting for the next scheduler tick.
- Weather configuration now defaults to `location_mode=auto` instead of
  hard-coded London.
- Weather pages expose `使用当前位置`, which fills browser geolocation
  latitude/longitude and keeps manual city override available.
- Without an OpenWeatherMap API key, weather remains mock data but the displayed
  location follows the selected auto/manual location. With an API key, auto mode
  uses latitude/longitude for the live OpenWeatherMap request.
- `ScreenHost` now logs whether a local preview exits because pygame sent a
  window close event or ESC key.

Additional Pi-side checks after sync:

1. Open `http://<pi-ip>:8080`.
2. Confirm the default page is `页面内容`.
3. Use `设为当前页面` for each page card and verify the HDMI display changes.
4. Change Mock carousel pages and interval, save, then confirm
   `/api/state` contains `cycle_presets`.
5. Open `设备状态` and confirm temperature plus throttling are visible.
