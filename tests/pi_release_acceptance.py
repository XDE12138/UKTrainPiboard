"""Opt-in Pi release check. Never prints private source config or event text.

Run from the deployed project: python3 tests/pi_release_acceptance.py --switch-pages
Reports are written under the project; screenshots are a separate safe-fixture step.
"""
import argparse
import copy
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "piboard"))


def api(path, data=None):
    request = urllib.request.Request("http://127.0.0.1:8080" + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def canonical(value):
    value = copy.deepcopy(value)
    value.pop("dirty", None)
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True, timeout=10).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switch-pages", action="store_true", required=True)
    parser.add_argument("--out-dir", default=".visual-review/v0.1.2")
    parser.add_argument("--expected-commit")
    parser.add_argument("--expected-version")
    args = parser.parse_args()
    if "Raspberry Pi" not in Path("/sys/firmware/devicetree/base/model").read_text():
        raise SystemExit("This check is for the deployed Raspberry Pi only")
    out = (ROOT / args.out_dir).resolve()
    if ROOT not in out.parents:
        raise SystemExit("Output must be inside the project")
    out.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.CRITICAL)
    before = api("/api/state")
    report = {"version": api("/api/version"), "api_schema_version": before["schema_version"],
              "source_ids": sorted(before["source_configs"]), "pages": {}, "data": {}}
    if args.expected_commit:
        assert report["version"]["commit"] == args.expected_commit
    if args.expected_version:
        assert report["version"]["version"] == args.expected_version
    manifest_path = ROOT / ".visual-review/v0.1.2/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert all((ROOT / p).is_file() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
               for p, h in manifest.items()), "Deployed source checksum mismatch"
    report["source_checksums"] = {"files": len(manifest), "mismatches": 0,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    report["api_state_summary"] = {"current_app": before["current_app"],
        "apps": before["apps"], "device_settings": before["device_settings"]}
    for path, payload in (("/api/layout", {"slots": [{}]}),
                          ("/api/source/custom/config", {"title": []})):
        try:
            api(path, payload)
        except urllib.error.HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("Invalid live API write was accepted")
    assert canonical(api("/api/state")) == canonical(before)
    report["invalid_write_rejected_without_mutation"] = True
    pid = int(command("systemctl", "show", "piboard.service", "-p", "MainPID", "--value"))
    report["service"] = {
        "active": command("systemctl", "is-active", "piboard.service"),
        "enabled": command("systemctl", "is-enabled", "piboard.service"),
        "exec_start": command("systemctl", "show", "piboard.service", "-p", "ExecStart", "--value").replace(str(ROOT), "<project-root>"),
        "environment": command("systemctl", "show", "piboard.service", "-p", "Environment", "--value"),
    }
    with open(f"/proc/{pid}/environ", "rb") as file:
        report["service"]["runtime_sdl_backend"] = next(v.decode().split("=", 1)[1]
            for v in file.read().split(b"\0") if v.startswith(b"SDL_VIDEODRIVER="))
    from simple_websocket import Client
    ws = Client.connect("ws://127.0.0.1:8080/ws")
    try:
        assert json.loads(ws.receive(timeout=8))["type"] == "state"
        api("/api/state")
        ws.send(json.dumps({"action": "get_state"}))
        assert json.loads(ws.receive(timeout=8))["type"] == "state"
        report["http_with_websocket"] = "pass"
    finally:
        ws.close()
    original = before["apps"]["uk_station"]
    preset = before["source_configs"]["mock"].get("preset")
    if preset is None:
        raise SystemExit("Explicit original preset required for exact API restoration")
    try:
        api("/api/current-app", {"app_id": "uk_station"})
        api("/api/source/mock/config", {"preset": "overview"})
        for page, slot in (("overview", "mock"), ("train", "train"), ("weather", "weather"),
                           ("calendar", "calendar"), ("custom", "custom")):
            api("/api/app/uk_station/layout", {"layout": "single", "slots": [slot]})
            time.sleep(3)
            state = api("/api/state")
            assert state["apps"]["uk_station"]["slots"] == [slot]
            assert command("systemctl", "show", "piboard.service", "-p", "MainPID", "--value") == str(pid)
            report["pages"][page] = "API selected; same render process alive"
    finally:
        api("/api/source/mock/config", {"preset": preset})
        api("/api/app/uk_station/layout", {"layout": original["layout"], "slots": original["slots"]})
        api("/api/current-app", {"app_id": before["current_app"]})
    assert canonical(api("/api/state")) == canonical(before), "Runtime state was not restored"
    disk = json.loads((ROOT / "piboard/data/state.json").read_text())
    backup = json.loads((ROOT / ".visual-review/v0.1.2/state.before.json").read_text())
    report["private_state_preserved"] = disk == backup
    assert disk == backup, "Private persisted state differs from pre-release backup"
    # Fetch with the exact saved configuration, in a separate process/state instance.
    from state import app_state
    from main import build_providers
    app_state._state = copy.deepcopy(before)
    providers = build_providers()
    for sid in ("train", "weather", "calendar", "custom", "mock"):
        provider = providers[sid]
        try:
            content = provider.fetch()
            provider._cached_content = content
            raw = getattr(getattr(provider, "_source", None), "_cached_data", None)
            summary = {"fetch": "pass", "rows": len(content.rows),
                       "configured_source_used": provider.config == before["source_configs"][sid]}
            if sid == "train":
                summary.update(mode=provider.config.get("data_source", "mock"),
                    station_crs=provider.config.get("station_crs"), departures=len(raw.departures) if raw else None,
                    upstream_error=bool(raw.error) if raw else None,
                    live_response_verified=bool(raw and not raw.error and raw.mode == "departures"))
                if raw and raw.error:
                    summary["fetch"] = "handled_upstream_error"
                    summary["reason"] = raw.error
            elif sid == "weather":
                summary.update(mode=provider.config.get("location_mode"), source=content.footer,
                               live=content.footer == "Open-Meteo",
                               location_config_matches_saved=provider.config == before["source_configs"][sid])
            elif sid == "calendar":
                summary.update(subscription_configured=bool(provider.config.get("ical_url")),
                    source=raw.source_label if raw else None, events=len(raw.events) if raw else None)
            elif sid == "mock":
                import datetime
                now = datetime.datetime.now()
                summary["overview_states"] = {
                    "train": provider._overview_rail()["state"],
                    "calendar": provider._overview_calendar_from_content(providers["calendar"].get_content(), now)["state"],
                    "weather": provider._overview_weather_from_content(providers["weather"].get_content(), now)["state"],
                }
            report["data"][sid] = summary
        except Exception as error:
            report["data"][sid] = {"fetch": "fail", "error_type": type(error).__name__}
    def ticks():
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[11]) + int(fields[12])
    start, started = ticks(), time.monotonic()
    time.sleep(5)
    cpu = (ticks() - start) / os.sysconf("SC_CLK_TCK") / (time.monotonic() - started) * 100
    memory = {line.split(":", 1)[0]: line.split(":", 1)[1].strip()
              for line in Path(f"/proc/{pid}/status").read_text().splitlines() if line.startswith(("VmRSS:", "VmHWM:"))}
    device = api("/api/device-status")
    report["device"] = {"hostname": "<redacted-host>", "temp_c": device["temp_c"],
        "throttled": device["throttled"], "cpu_percent_one_core_5s": round(cpu, 2), **memory}
    report["state_sha256"] = digest(disk)
    report["timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if all(v["fetch"] in ("pass", "handled_upstream_error")
                    for v in report["data"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
