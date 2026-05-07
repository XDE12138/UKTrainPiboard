"""
OverviewToUKBinding: map a compact cross-domain overview into BoardContent.

This binding deliberately stays inside the existing BoardContent + info template
contract. It does not introduce a block system or renderer-specific layout.
"""
import datetime as _dt
import time
from dataclasses import dataclass, field
from typing import List, Optional

from bindings.base import BaseBinding
from board.content import BoardContent, BoardRow


@dataclass
class OverviewAction:
    """One actionable item in the unified overview feed."""
    kind: str
    time_label: str
    text: str
    status: str = ""
    status_color: str = "amber"
    highlight: bool = False
    detail: str = ""
    detail_right: str = ""


@dataclass
class OverviewSummary:
    """One compact status line for the summary area."""
    label: str
    value: str
    right: str = ""
    value_color: str = "dim"
    right_color: str = "amber"


@dataclass
class OverviewBoardData:
    """Raw overview shape consumed by OverviewToUKBinding."""
    now: _dt.datetime
    location: str = "PIBOARD"
    hero_primary: str = "TODAY"
    hero_secondary: str = ""
    actions: List[OverviewAction] = field(default_factory=list)
    summaries: List[OverviewSummary] = field(default_factory=list)
    footer: str = "MOCK DATA"
    status_text: str = "ALL OK"
    status_color: str = "green"
    ticker: Optional[str] = None
    fetched_at: float = field(default_factory=time.time)


class OverviewToUKBinding(BaseBinding):
    """
    Convert OverviewBoardData into the UK Station info board language.

    The output uses one hero anchor (title/subtitle), a single unified feed,
    summary rows at the end of the same rows area, and a compact footer/status.
    """

    source_id = "overview"
    app_slot = "uk_station"
    _TITLE_LINE_CHAR_BUDGET = 38
    _TITLE_LINE_GAP_CHARS = 2
    _MAX_PAGE_LABEL_CHARS = 12
    _MAX_SUBTITLE_CHARS = 28
    _MIN_SUBTITLE_CHARS = 12

    def transform(self, raw: OverviewBoardData) -> BoardContent:
        rows = self._build_rows(raw)
        subtitle, page_label = self._fit_title_line(
            raw.hero_secondary, raw.location)

        return BoardContent(
            header_left="OVERVIEW",
            header_right="",
            header_right_clock_format="%H:%M",
            title=self._clean(raw.hero_primary, 12),
            title_color="amber",
            title_size="AUTO",
            subtitle=subtitle,
            subtitle_color="white" if subtitle else "dim",
            page_label=page_label,
            rows=rows,
            footer=self._format_footer(raw),
            footer_color="dim",
            status_text=self._clean(raw.status_text, 18),
            status_color=raw.status_color,
            ticker=self._clean(raw.ticker, 120) if raw.ticker else None,
            template="info",
            provider_id="overview",
            expires_at=raw.fetched_at + 60,
        )

    def _build_rows(self, raw: OverviewBoardData) -> List[BoardRow]:
        rows: List[BoardRow] = []
        actions = raw.actions[:6]

        if actions:
            rows.append(BoardRow(
                left="NEXT ACTIONS",
                right=f"{len(actions)} ITEMS",
                left_color="dim",
                right_color="dim",
            ))

        highlighted = False
        for index, action in enumerate(actions):
            left = self._format_action_left(action)
            should_highlight = not highlighted and (action.highlight or index == 0)
            highlighted = highlighted or should_highlight
            rows.append(BoardRow(
                left=left,
                right=self._clean(action.status, 10),
                left_color="amber",
                right_color=action.status_color,
                highlight=should_highlight,
            ))
            if action.detail or action.detail_right:
                rows.append(BoardRow(
                    left=self._clean(action.detail, 28),
                    right=self._clean(action.detail_right, 10),
                    left_color="dim",
                    right_color="dim",
                    indent=12,
                ))

        if raw.summaries:
            rows.append(BoardRow(
                left="BOARD SUMMARY",
                right=self._clean(raw.status_text, 10),
                left_color="dim",
                right_color=raw.status_color,
            ))

        for summary in raw.summaries[:4]:
            rows.append(BoardRow(
                left=self._format_summary_left(summary),
                right=self._clean(summary.right, 10),
                left_color=summary.value_color,
                right_color=summary.right_color,
            ))

        return rows

    def _fit_title_line(self, subtitle: str, page_label: str) -> tuple:
        """Keep subtitle and right-aligned page label from sharing pixels."""
        page = self._clean(page_label, self._MAX_PAGE_LABEL_CHARS)
        if not subtitle:
            return "", page

        available = self._TITLE_LINE_CHAR_BUDGET
        if page:
            available -= len(page) + self._TITLE_LINE_GAP_CHARS
        subtitle_budget = max(
            self._MIN_SUBTITLE_CHARS,
            min(self._MAX_SUBTITLE_CHARS, available),
        )
        return self._clean(subtitle, subtitle_budget), page

    def _format_action_left(self, action: OverviewAction) -> str:
        kind = self._clean(action.kind, 5).ljust(5)
        time_label = self._clean(action.time_label, 5).rjust(5)
        text = self._clean(action.text, 19)
        return f"{time_label} {kind} {text}"

    def _format_summary_left(self, summary: OverviewSummary) -> str:
        label = self._clean(summary.label, 7).ljust(7)
        value = self._clean(summary.value, 18)
        return f"{label} {value}"

    def _format_footer(self, raw: OverviewBoardData) -> str:
        source = self._clean(raw.footer, 80)
        if " UPDATED " in source:
            source = source.split(" UPDATED ", 1)[0]
        if " - " in source:
            source = source.split(" - ", 1)[0]
        if " · " in source:
            source = source.split(" · ", 1)[0]
        source = self._clean(source or "DATA", 12)
        updated = _dt.datetime.fromtimestamp(raw.fetched_at).strftime("%H:%M")
        return f"{source} - UPDATED {updated}"

    @staticmethod
    def _clean(value: Optional[str], max_len: int) -> str:
        if value is None:
            return ""
        text = " ".join(str(value).upper().split())
        if len(text) <= max_len:
            return text
        return text[:max(0, max_len - 1)].rstrip() + "."
