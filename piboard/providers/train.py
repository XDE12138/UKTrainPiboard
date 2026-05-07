"""
列车时刻 Provider。
支持三种数据源：
  mock        — 内置假数据，无需 API Key
  huxley2     — 调用 Huxley2 API（免费，基于 Darwin 数据）
  transportapi — 调用 Transport API（需 Key）
"""
import time
import logging
import requests
from providers.base import BaseProvider
from board.content import BoardContent, BoardRow

log = logging.getLogger(__name__)

HUXLEY2_BASE = "https://huxley2.azurewebsites.net"


class TrainProvider(BaseProvider):

    provider_id = "train"
    display_name = "Train Departures"
    default_refresh_interval = 60

    def get_config_schema(self):
        return {
            "station_crs":     {"type": "string",  "label": "出发站 CRS 代码",
                                 "default": "KGX"},
            "destination_crs": {"type": "string",  "label": "目的地 CRS（可选）",
                                 "default": ""},
            "api_key":         {"type": "string",  "label": "Transport API Key",
                                 "secret": True, "default": ""},
            "data_source":     {"type": "select",  "label": "数据源",
                                 "options": ["mock", "huxley2", "transportapi"],
                                 "default": "mock"},
        }

    def fetch(self) -> BoardContent:
        source = self.config.get("data_source", "mock")
        if source == "huxley2":
            return self._fetch_huxley2()
        elif source == "transportapi":
            return self._fetch_transportapi()
        else:
            return self._mock_content()

    # ------------------------------------------------------------------
    # Huxley2
    # ------------------------------------------------------------------

    def _fetch_huxley2(self) -> BoardContent:
        crs = self.config.get("station_crs", "KGX").upper()
        dest = self.config.get("destination_crs", "").upper()
        url = f"{HUXLEY2_BASE}/departures/{crs}/5"
        if dest:
            url = f"{HUXLEY2_BASE}/departures/{crs}/to/{dest}/5"

        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        services = data.get("trainServices") or []
        rows = []
        for svc in services[:6]:
            dest_name = svc.get("destination", [{}])[0].get("locationName", "?")
            std = svc.get("std", "")
            etd = svc.get("etd", "On time")
            time_str = etd if etd != "On time" else std
            highlight = (len(rows) == 0)
            rows.append(BoardRow(dest_name, time_str, highlight=highlight))

        platform = ""
        status = "On time"
        status_color = "green"
        if services:
            platform = services[0].get("platform") or ""
            etd = services[0].get("etd", "On time")
            if etd not in ("On time", ""):
                status = f"Exp {etd}"
                status_color = "orange"

        return BoardContent(
            header_left="RAIL",
            header_right="",
            header_right_clock_format="%H:%M",
            title=services[0]["destination"][0]["locationName"]
                  if services else "No services",
            subtitle="Calling at:",
            page_label=f"PLATFORM {platform}" if platform else crs,
            rows=rows,
            footer="National Rail",
            status_text=status,
            status_color=status_color,
            ticker=f"Live departures from {crs}. Data via Huxley2/Darwin.",
            provider_id=self.provider_id,
        )

    # ------------------------------------------------------------------
    # Transport API
    # ------------------------------------------------------------------

    def _fetch_transportapi(self) -> BoardContent:
        crs = self.config.get("station_crs", "KGX").upper()
        api_key = self.config.get("api_key", "")
        url = (f"https://transportapi.com/v3/uk/train/station/{crs}/live.json"
               f"?app_id=piboard&app_key={api_key}&train_status=passenger")

        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        departures = data.get("departures", {}).get("all", [])[:6]
        rows = []
        for i, dep in enumerate(departures):
            dest = dep.get("destination_name", "?")
            aimed = dep.get("aimed_departure_time", "")
            expected = dep.get("expected_departure_time", "On time")
            t = expected if expected and expected != aimed else aimed
            rows.append(BoardRow(dest, t, highlight=(i == 0)))

        return BoardContent(
            header_left="RAIL",
            header_right="",
            header_right_clock_format="%H:%M",
            title=departures[0]["destination_name"] if departures else "No services",
            subtitle="Departures",
            page_label=crs,
            rows=rows,
            footer="Transport API",
            status_text="Live",
            status_color="green",
            ticker=f"Live departures from {crs}.",
            provider_id=self.provider_id,
        )

    # ------------------------------------------------------------------
    # Mock
    # ------------------------------------------------------------------

    def _mock_content(self) -> BoardContent:
        crs = self.config.get("station_crs", "KGX").upper()
        now = time.strftime("%H:%M")
        return BoardContent(
            header_left="RAIL",
            header_right="",
            header_right_clock_format="%H:%M",
            title="Edinburgh",
            subtitle="Calling at:",
            page_label="PLATFORM 9",
            rows=[
                BoardRow("Newcastle",          "12:35", highlight=True),
                BoardRow("Morpeth",            "12:59"),
                BoardRow("Alnmouth (Alnwick)", "13:07"),
                BoardRow("& Edinburgh",        "14:15"),
            ],
            footer="LNER Azuma",
            status_text="On time",
            status_color="green",
            ticker="LNER Azuma train service. Reserve seats up to coach A.",
            provider_id=self.provider_id,
            expires_at=time.time() + 60,
        )


if __name__ == "__main__":
    p = TrainProvider(config={"data_source": "mock", "station_crs": "KGX"})
    c = p.fetch()
    print(f"title={c.title!r}, rows={len(c.rows)}, status={c.status_text!r}")
