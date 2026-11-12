"""Validate existing write contracts before either transport mutates state."""
import math

from apps.catalog import KNOWN_APP_IDS


def object_value(value):
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def choice(value, options, field):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f"Invalid {field}")


def number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {field}")


def settings(data):
    object_value(data)
    if "color_theme" in data:
        choice(data["color_theme"], ("amber", "green", "white"), "color_theme")
    if "animations_enabled" in data and not isinstance(data["animations_enabled"], bool):
        raise ValueError("Invalid animations_enabled")
    if "orientation" in data:
        choice(data["orientation"], ("portrait", "landscape"), "orientation")
    if "brightness" in data:
        number(data["brightness"], "brightness")
        if not 0.1 <= data["brightness"] <= 1:
            raise ValueError("Invalid brightness")


def layout(data, providers, app_id="uk_station"):
    choice(app_id, KNOWN_APP_IDS, "app_id")
    choice(data.get("layout", "single"), ("single", "dual", "carousel"), "layout")
    slots = data.get("slots", ["mock"])
    if not isinstance(slots, list) or not (0 if app_id == "system_status" else 1) <= len(slots) <= 3:
        raise ValueError("Invalid slots")
    for sid in slots:
        choice(sid, providers, "slot")


def source_config(data, provider):
    object_value(data)
    schema = provider.get_config_schema()
    for key, value in data.items():
        if key not in schema:
            raise ValueError("Unknown source field")
        spec = schema[key]
        kind = spec.get("type")
        if kind == "string" and not isinstance(value, str):
            raise ValueError(f"Invalid {key}")
        if kind in ("select", "multi_select"):
            options = [v.get("value") if isinstance(v, dict) else v for v in spec["options"]]
        if kind == "select":
            choice(value, options, key)
        if kind == "multi_select":
            if not isinstance(value, list):
                raise ValueError(f"Invalid {key}")
            for item in value:
                choice(item, options, key)
        if kind == "number":
            number(value, key)
            if key == "lookahead_days" and (int(value) != value or not 0 <= value <= 366):
                raise ValueError("Invalid lookahead_days")
            if key == "refresh_interval_sec" and value < 1:
                raise ValueError("Invalid refresh_interval_sec")
        if kind == "rows":
            if not isinstance(value, list):
                raise ValueError("Invalid rows")
            for row in value:
                if isinstance(row, str):
                    continue
                if isinstance(row, list) and len(row) >= 2 and all(isinstance(v, str) for v in row):
                    continue
                object_value(row)
                for field in ("left", "right"):
                    if field in row and not isinstance(row[field], str):
                        raise ValueError("Invalid row text")
                for field in ("left_color", "right_color"):
                    if field in row:
                        choice(row[field], ("amber", "green", "white", "orange", "red", "dim"), field)
                if "highlight" in row and not isinstance(row["highlight"], bool):
                    raise ValueError("Invalid highlight")
        if key in ("latitude", "longitude") and value != "":
            try:
                coordinate = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {key}") from None
            limit = 90 if key == "latitude" else 180
            if not math.isfinite(coordinate) or not -limit <= coordinate <= limit:
                raise ValueError(f"Invalid {key}")


def http_write(endpoint, data, args, providers):
    object_value(data)
    if endpoint in ("api_layout", "api_app_layout"):
        layout(data, providers, args.get("app_id", "uk_station"))
    elif endpoint in ("api_source_config", "api_provider_config"):
        sid = args.get("source_id", args.get("pid"))
        if sid in providers:
            source_config(data, providers[sid])
    elif endpoint == "api_current_app":
        choice(data.get("app_id"), KNOWN_APP_IDS, "app_id")
    elif endpoint in ("api_settings", "api_device_settings", "api_app_settings", "api_orientation"):
        settings(data)


def ws_write(data, providers):
    object_value(data)
    action = data.get("action")
    if action in ("set_layout", "set_app_layout"):
        if "layout" not in data or "slots" not in data:
            raise ValueError("layout and slots required")
        layout(data, providers, data.get("app_id", "uk_station") if action == "set_app_layout" else "uk_station")
    elif action in ("update_source_config", "update_config"):
        sid = data.get("source_id" if action == "update_source_config" else "provider_id")
        choice(sid, providers, "source_id")
        source_config(data.get("config"), providers[sid])
    elif action in ("update_settings", "update_device_settings", "update_app_settings"):
        field = {"update_settings": "settings", "update_device_settings": "device_settings",
                 "update_app_settings": "app_settings"}[action]
        if action == "update_app_settings":
            choice(data.get("app_id", "uk_station"), KNOWN_APP_IDS, "app_id")
        settings(data.get(field, {}))
    elif action == "switch_app":
        choice(data.get("app_id"), KNOWN_APP_IDS, "app_id")
    elif action == "refresh":
        choice(data.get("provider_id", ""), providers, "provider_id")
