"""
天气 Provider。
支持 mock（内置假数据）和 openweathermap（需 API Key）。
"""
import time
import logging
import requests
from providers.base import BaseProvider
from board.content import BoardContent, BoardRow

log = logging.getLogger(__name__)

OWM_URL = "https://api.openweathermap.org/data/2.5"


class WeatherProvider(BaseProvider):

    provider_id = "weather"
    display_name = "Weather"
    default_refresh_interval = 600  # 10分钟

    def get_config_schema(self):
        return {
            "location_mode": {"type": "select", "label": "位置模式",
                              "options": ["auto", "manual"], "default": "auto"},
            "city":    {"type": "string", "label": "手动城市", "default": ""},
            "latitude": {"type": "string", "label": "当前位置纬度", "default": ""},
            "longitude": {"type": "string", "label": "当前位置经度", "default": ""},
            "api_key": {"type": "string", "label": "OpenWeatherMap API Key",
                        "secret": True, "default": ""},
            "units":   {"type": "select", "label": "温度单位",
                        "options": ["metric", "imperial"], "default": "metric"},
        }

    def fetch(self) -> BoardContent:
        api_key = self.config.get("api_key", "")
        if not api_key:
            return self._mock_content()
        return self._fetch_owm(api_key)

    # ------------------------------------------------------------------
    # OpenWeatherMap
    # ------------------------------------------------------------------

    def _fetch_owm(self, api_key: str) -> BoardContent:
        city  = self._location_label()
        units = self.config.get("units", "metric")
        unit_sym = "°C" if units == "metric" else "°F"
        speed_unit = "km/h" if units == "metric" else "mph"
        location_params = self._location_params()

        # 当前天气
        curr = requests.get(
            f"{OWM_URL}/weather",
            params={**location_params, "appid": api_key, "units": units},
            timeout=10,
        ).json()

        # 预报
        fcst = requests.get(
            f"{OWM_URL}/forecast",
            params={**location_params, "appid": api_key, "units": units, "cnt": 24},
            timeout=10,
        ).json()

        temp       = round(curr["main"]["temp"])
        feels_like = round(curr["main"]["feels_like"])
        humidity   = curr["main"]["humidity"]
        desc       = curr["weather"][0]["description"].title()
        wind_speed = round(curr["wind"]["speed"] * 3.6
                           if units == "metric" else curr["wind"]["speed"])
        wind_dir   = self._wind_dir(curr["wind"].get("deg", 0))
        visibility = curr.get("visibility", 0) // 1000

        rows = [
            BoardRow("Humidity",   f"{humidity}%"),
            BoardRow("Wind",       f"{wind_dir} {wind_speed}{speed_unit}"),
            BoardRow("Visibility", f"{visibility}km"),
            BoardRow(""),
        ]

        # 简易日预报（每天取正午条目）
        days_seen = set()
        for item in fcst.get("list", []):
            dt_txt = item["dt_txt"]
            date   = dt_txt[:10]
            hour   = int(dt_txt[11:13])
            if hour == 12 and date not in days_seen:
                days_seen.add(date)
                hi = round(item["main"]["temp_max"])
                lo = round(item["main"]["temp_min"])
                import datetime
                day_name = datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%a")
                rows.append(
                    BoardRow(day_name, f"{hi}{unit_sym} / {lo}{unit_sym}",
                             left_color="dim", right_color="dim")
                )
                if len(days_seen) >= 3:
                    break

        return BoardContent(
            header_left="WEATHER",
            header_right="",
            header_right_clock_format="%H:%M",
            title=desc,
            subtitle=f"Feels like  {feels_like}{unit_sym}",
            page_label=city.upper(),
            rows=rows,
            footer="OpenWeather",
            status_text=desc,
            status_color="white",
            ticker=f"{city}: {desc}. Humidity {humidity}%. Wind {wind_dir} {wind_speed}{speed_unit}.",
            provider_id=self.provider_id,
            expires_at=time.time() + 600,
        )

    @staticmethod
    def _wind_dir(deg: float) -> str:
        dirs = ["N","NE","E","SE","S","SW","W","NW"]
        idx = round(deg / 45) % 8
        return dirs[idx]

    # ------------------------------------------------------------------
    # Mock
    # ------------------------------------------------------------------

    def _mock_content(self) -> BoardContent:
        city = self._location_label()
        return BoardContent(
            header_left="WEATHER",
            header_right="",
            header_right_clock_format="%H:%M",
            title="Partly Cloudy",
            subtitle="Feels like  11\u00b0C",
            page_label=city.upper(),
            rows=[
                BoardRow("Humidity",   "72%"),
                BoardRow("Wind",       "SW 18km/h"),
                BoardRow("Visibility", "10km"),
                BoardRow("UV Index",   "Low"),
                BoardRow(""),
                BoardRow("Tomorrow",   "12\u00b0C / 8\u00b0C",
                         left_color="dim", right_color="dim"),
                BoardRow("Wed",        "15\u00b0C / 9\u00b0C",
                         left_color="dim", right_color="dim"),
                BoardRow("Thu",        "11\u00b0C / 7\u00b0C",
                         left_color="dim", right_color="dim"),
            ],
            footer="OpenWeather (mock)",
            status_text="Partly Cloudy",
            status_color="white",
            ticker="Today: Cloudy morning, clearing in the afternoon. "
                   "Low chance of rain.",
            provider_id=self.provider_id,
        )

    def _location_params(self) -> dict:
        if self.config.get("location_mode", "auto") == "auto":
            lat = str(self.config.get("latitude", "")).strip()
            lon = str(self.config.get("longitude", "")).strip()
            if lat and lon:
                return {"lat": lat, "lon": lon}
        city = str(self.config.get("city", "")).strip()
        return {"q": city or "Beijing"}

    def _location_label(self) -> str:
        city = str(self.config.get("city", "")).strip()
        if self.config.get("location_mode", "auto") == "auto":
            return city or "当前位置"
        return city or "Beijing"


if __name__ == "__main__":
    p = WeatherProvider(config={"city": "London"})
    c = p.fetch()
    print(f"title={c.title!r}, rows={len(c.rows)}, header={c.header_left!r}")
