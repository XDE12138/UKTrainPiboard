"""
WeatherSource：天气数据获取与归一化。

默认 live 路径使用 Open-Meteo，无需 API key。手动城市先通过
Open-Meteo geocoding 转成经纬度；当前位置模式使用 Web 控制台保存的
latitude / longitude。

职责边界：
- 从外部（mock / 未来 API）获取原始数据，归一化为 WeatherObservation
- 不构造 BoardContent，不做任何渲染相关判断
- 写入 self._cached_data，满足 BaseSource 约定

"""
import datetime as _dt
import time
from dataclasses import dataclass
from typing import List, Tuple
import requests
from sources.base import BaseSource


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class WeatherObservation:
    """天气归一化数据（WeatherSource 的输出格式）。"""
    temperature: int                        # 当前温度（整数）
    feels_like: int                         # 体感温度（整数）
    description: str                        # 天气描述，如 "Partly Cloudy"
    humidity: int                           # 湿度百分比，如 72
    wind_dir: str                           # 风向，如 "SW"
    wind_speed_str: str                     # 风速含单位，如 "18km/h"
    visibility_km: int                      # 能见度（公里），如 10
    uv_label: str                           # UV 指数文字标签，如 "Low"（mock 专用）
    forecast: List[Tuple[str, str, str]]    # [(day_name, hi_str, lo_str), ...]
    city: str                               # 城市名
    unit_sym: str                           # "°C" / "°F"
    fetched_at: float                       # Unix timestamp


class WeatherSource(BaseSource):
    """
    天气数据 Source。

    构造时接收 config dict，与 WeatherProvider 保持相同配置键名。
    """

    def __init__(self, config: dict = None, force_mock: bool = False):
        super().__init__("weather", force_mock=force_mock)
        self.config = config or {}

    def fetch(self) -> WeatherObservation:
        """
        获取并归一化天气数据。默认使用 Open-Meteo live 数据；
        force_mock=True 时才返回内置 mock。
        """
        if self.force_mock:
            data = self._mock_data()
        else:
            data = self._live_data()
        self._cached_data = data
        return data

    # ------------------------------------------------------------------
    # Open-Meteo live 路径
    # ------------------------------------------------------------------

    def _live_data(self) -> WeatherObservation:
        loc = self._resolve_location()
        units = self.config.get("units", "metric")
        temp_unit = "fahrenheit" if units == "imperial" else "celsius"
        wind_unit = "mph" if units == "imperial" else "kmh"
        unit_sym = "°F" if units == "imperial" else "°C"
        wind_suffix = "mph" if units == "imperial" else "km/h"

        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "current": ",".join([
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "visibility",
                    "is_day",
                ]),
                "daily": ",".join([
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "uv_index_max",
                ]),
                "forecast_days": 4,
                "timezone": "auto",
                "temperature_unit": temp_unit,
                "wind_speed_unit": wind_unit,
            },
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()

        current = payload.get("current", {})
        daily = payload.get("daily", {})
        weather_code = int(current.get("weather_code", 0))
        desc = self._weather_description(weather_code, current.get("is_day", 1))

        forecast = []
        times = daily.get("time", [])
        max_vals = daily.get("temperature_2m_max", [])
        min_vals = daily.get("temperature_2m_min", [])
        for i, day in enumerate(times[:3]):
            label = self._day_label(day)
            hi = self._round_num(max_vals[i]) if i < len(max_vals) else "--"
            lo = self._round_num(min_vals[i]) if i < len(min_vals) else "--"
            forecast.append((label, f"{hi}{unit_sym}", f"{lo}{unit_sym}"))

        uv_values = daily.get("uv_index_max", [])
        uv_label = self._uv_label(uv_values[0]) if uv_values else "N/A"
        visibility_m = current.get("visibility")
        visibility_km = int(round(float(visibility_m) / 1000)) if visibility_m is not None else 0
        wind_speed = self._round_num(current.get("wind_speed_10m"))

        return WeatherObservation(
            temperature=self._round_num(current.get("temperature_2m")),
            feels_like=self._round_num(current.get("apparent_temperature")),
            description=desc,
            humidity=int(round(float(current.get("relative_humidity_2m", 0)))),
            wind_dir=self._wind_dir(float(current.get("wind_direction_10m", 0))),
            wind_speed_str=f"{wind_speed}{wind_suffix}",
            visibility_km=visibility_km,
            uv_label=uv_label,
            forecast=forecast,
            city=loc["label"],
            unit_sym=unit_sym,
            fetched_at=time.time(),
        )

    def _resolve_location(self) -> dict:
        mode = self.config.get("location_mode", "auto")
        city = str(self.config.get("city", "")).strip()
        lat = str(self.config.get("latitude", "")).strip()
        lon = str(self.config.get("longitude", "")).strip()

        if mode == "auto" and lat and lon:
            return {
                "latitude": float(lat),
                "longitude": float(lon),
                "label": city or "当前位置",
            }

        query = city or "Beijing"
        resp = requests.get(
            GEOCODING_URL,
            params={"name": query, "count": 1, "language": "zh", "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            raise RuntimeError(f"找不到天气城市：{query}")
        result = results[0]
        label = city or result.get("name") or query
        return {
            "latitude": float(result["latitude"]),
            "longitude": float(result["longitude"]),
            "label": label,
        }

    # ------------------------------------------------------------------
    # Mock 路径
    # ------------------------------------------------------------------

    def _mock_data(self) -> WeatherObservation:
        """
        返回与旧 WeatherProvider._mock_content() 语义等价的归一化数据。
        刻意保持摄氏度固定语义（°C），与旧 mock 行为一致。
        imperial 支持不在本轮范围内，此处不做扩展。
        """
        city = self._location_label()
        return WeatherObservation(
            temperature=14,
            feels_like=11,
            description="Partly Cloudy",
            humidity=72,
            wind_dir="SW",
            wind_speed_str="18km/h",
            visibility_km=10,
            uv_label="Low",
            forecast=[
                ("Tomorrow", "12°C", "8°C"),
                ("Wed",      "15°C", "9°C"),
                ("Thu",      "11°C", "7°C"),
            ],
            city=city,
            unit_sym="°C",
            fetched_at=time.time(),
        )

    @staticmethod
    def _round_num(value) -> int:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _day_label(day: str) -> str:
        try:
            date = _dt.datetime.strptime(day, "%Y-%m-%d")
            return date.strftime("%a")
        except ValueError:
            return day

    @staticmethod
    def _uv_label(value) -> str:
        try:
            uv = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if uv < 3:
            return "Low"
        if uv < 6:
            return "Moderate"
        if uv < 8:
            return "High"
        if uv < 11:
            return "Very High"
        return "Extreme"

    @staticmethod
    def _wind_dir(deg: float) -> str:
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[round(deg / 45) % 8]

    @staticmethod
    def _weather_description(code: int, is_day=1) -> str:
        _ = is_day
        codes = {
            0: "Clear Sky",
            1: "Mainly Clear",
            2: "Partly Cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Rime Fog",
            51: "Light Drizzle",
            53: "Drizzle",
            55: "Heavy Drizzle",
            56: "Freezing Drizzle",
            57: "Heavy Freezing Drizzle",
            61: "Light Rain",
            63: "Rain",
            65: "Heavy Rain",
            66: "Freezing Rain",
            67: "Heavy Freezing Rain",
            71: "Light Snow",
            73: "Snow",
            75: "Heavy Snow",
            77: "Snow Grains",
            80: "Rain Showers",
            81: "Heavy Showers",
            82: "Violent Showers",
            85: "Snow Showers",
            86: "Heavy Snow Showers",
            95: "Thunderstorm",
            96: "Thunderstorm Hail",
            99: "Heavy Thunderstorm Hail",
        }
        return codes.get(code, f"Weather Code {code}")

    def _location_label(self) -> str:
        city = str(self.config.get("city", "")).strip()
        if self.config.get("location_mode", "auto") == "auto":
            return city or "当前位置"
        return city or "Beijing"
