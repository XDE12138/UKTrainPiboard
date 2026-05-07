"""
WeatherToUKBinding：将 WeatherObservation 转换为 BoardContent。

职责边界：
- 只负责 raw WeatherObservation → BoardContent 的纯映射
- 不发网络请求，不读 config，不解析 live API 响应
- 输出语义采用 Detail Board 结构：当前状态为 hero，rows 分 NOW / NEXT / FORECAST
"""
import time
from bindings.base import BaseBinding
from sources.weather import WeatherObservation
from board.content import BoardContent, BoardRow


class WeatherToUKBinding(BaseBinding):
    """
    将 WeatherObservation 映射为 UK Station Board 风格的 BoardContent。

    source_id = "weather"，app_slot = "uk_station"。
    输出格式保持 BoardContent / BoardRow，不引入天气图标或复杂 block。
    """

    source_id = "weather"
    app_slot  = "uk_station"

    def transform(self, raw: WeatherObservation) -> BoardContent:
        """
        纯转换：WeatherObservation → BoardContent。
        相同输入始终产生相同输出（无副作用）。

        信息角色分配：
          title (hero/anchor) = 当前温度
          subtitle (context)  = 主天气状态
          rows                = NOW / NEXT / FORECAST 三段式数据行
          status_text         = 主天气状态
        """
        desc = raw.description.upper()
        forecast_count = max(0, len(raw.forecast) - 1)
        updated = time.strftime("%H:%M", time.localtime(raw.fetched_at))

        rows = [
            BoardRow("NOW", desc, right_color="white", highlight=True),
            BoardRow("FEELS", f"{raw.feels_like}{raw.unit_sym}"),
            BoardRow("WIND", f"{raw.wind_dir.upper()} {raw.wind_speed_str.upper()}"),
            BoardRow("HUMIDITY", f"{raw.humidity}%"),
            BoardRow("VISIBILITY", f"{raw.visibility_km}KM"),
            BoardRow("UV INDEX", raw.uv_label.upper()),
            BoardRow(""),
        ]

        if raw.forecast:
            day_name, hi, lo = raw.forecast[0]
            _ = day_name
            rows.append(BoardRow("TODAY", f"{hi}/{lo}"))
        else:
            rows.append(BoardRow(
                "TODAY",
                "NO FORECAST",
                left_color="dim",
                right_color="dim",
            ))

        rows.extend([
            BoardRow("FORECAST", f"{forecast_count} DAYS",
                     left_color="dim", right_color="dim"),
        ])

        for day_name, hi, lo in raw.forecast[1:]:
            rows.append(
                BoardRow(day_name.upper(), f"{hi} / {lo}",
                         left_color="dim", right_color="dim")
            )

        return BoardContent(
            header_left="WEATHER",
            header_right="",
            header_right_clock_format="%H:%M",
            title=f"{raw.temperature}{raw.unit_sym}",
            title_size="AUTO",
            subtitle=desc,
            page_label=f"{raw.city.upper()} UPD {updated}",
            rows=rows,
            footer="Open-Meteo",
            status_text=desc,
            status_color="white",
            ticker=self._ticker(raw),
            template="info",
            provider_id="weather",
            expires_at=raw.fetched_at + 600,
        )

    def _ticker(self, raw: WeatherObservation) -> str:
        parts = [
            f"{raw.city}: {raw.description}.",
            f"Now {raw.temperature}{raw.unit_sym}.",
            f"Feels like {raw.feels_like}{raw.unit_sym}.",
            f"Wind {raw.wind_dir.upper()} {raw.wind_speed_str.upper()}.",
        ]
        if raw.forecast:
            day_name, hi, lo = raw.forecast[0]
            _ = day_name
            parts.append(f"Today {hi}/{lo}.")
        updated = time.strftime("%H:%M", time.localtime(raw.fetched_at))
        parts.append(f"Updated {updated}.")
        return " ".join(parts)
