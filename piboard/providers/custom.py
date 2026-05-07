"""
自定义文本 Provider。
内容完全由 Web 控制台直接编辑，fetch() 直接把 config 映射成 BoardContent。
无任何网络请求。
"""
from providers.base import BaseProvider
from board.content import BoardContent, BoardRow


class CustomProvider(BaseProvider):

    provider_id = "custom"
    display_name = "Custom Text"
    default_refresh_interval = 86400  # 基本不需要刷新

    def get_config_schema(self):
        return {
            "header_left":  {"type": "string", "label": "左上角", "default": ""},
            "header_right": {"type": "string", "label": "右上角", "default": ""},
            "title":        {"type": "string", "label": "主标题", "default": "PiBoard"},
            "title_color":  {"type": "select", "label": "标题颜色",
                             "options": ["amber", "green", "white", "orange", "red"],
                             "default": "amber"},
            "subtitle":     {"type": "string", "label": "副标题", "default": ""},
            "rows":         {"type": "rows",   "label": "内容行（左文字 + 右文字）",
                             "default": []},
            "footer":       {"type": "string", "label": "底部来源", "default": ""},
            "status_text":  {"type": "string", "label": "状态文字", "default": ""},
            "status_color": {"type": "select", "label": "状态颜色",
                             "options": ["green", "amber", "orange", "red", "white"],
                             "default": "green"},
            "ticker":       {"type": "string", "label": "跑马灯文字（留空不显示）",
                             "default": ""},
        }

    def fetch(self) -> BoardContent:
        c = self.config
        rows = []
        for row_data in c.get("rows", []):
            if isinstance(row_data, dict):
                rows.append(BoardRow(
                    left=str(row_data.get("left", "")),
                    right=str(row_data.get("right", "")),
                    left_color=row_data.get("left_color", "amber"),
                    right_color=row_data.get("right_color", "amber"),
                    highlight=bool(row_data.get("highlight", False)),
                ))
            elif isinstance(row_data, (list, tuple)) and len(row_data) >= 2:
                rows.append(BoardRow(str(row_data[0]), str(row_data[1])))
            elif isinstance(row_data, str):
                rows.append(BoardRow(row_data))

        ticker = c.get("ticker", "").strip() or None

        content = BoardContent(
            header_left=c.get("header_left", ""),
            header_right=c.get("header_right", ""),
            title=c.get("title", "PiBoard"),
            title_color=c.get("title_color", "amber"),
            subtitle=c.get("subtitle", ""),
            rows=rows,
            footer=c.get("footer", ""),
            status_text=c.get("status_text", ""),
            status_color=c.get("status_color", "green"),
            ticker=ticker,
            provider_id=self.provider_id,
        )
        self._cached_content = content
        return content


if __name__ == "__main__":
    p = CustomProvider(config={
        "title": "Hello World",
        "subtitle": "Custom content",
        "rows": [
            {"left": "Item 1", "right": "Value 1"},
            {"left": "Item 2", "right": "Value 2"},
        ],
        "status_text": "OK",
        "ticker": "This is a custom ticker message.",
    })
    c = p.fetch()
    print(f"title={c.title!r}, rows={len(c.rows)}, ticker={c.ticker!r}")
