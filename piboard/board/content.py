from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BoardRow:
    """中间内容区的一行"""
    left: str                           # 左侧文字（站名、事件标题、天气描述）
    right: str = ""                     # 右侧文字（时间、温度、状态）
    left_color: str = "amber"           # amber / green / red / orange / white / dim
    right_color: str = "amber"
    highlight: bool = False             # 是否高亮整行（如「下一班」）
    indent: int = 0                     # 左缩进（点数），用于层级展示


@dataclass
class BoardContent:
    """
    一块报站板的完整内容描述。
    渲染引擎只认识这个结构，不关心内容从哪来。
    """
    # 顶部栏
    header_left: str = ""              # 左上角（如 "11:35"、"14°C"、"MON"）
    header_right: str = ""             # 右上角（如 "Platform 9"、"London"、"Week 15"）
    header_left_clock_format: Optional[str] = None
    header_right_clock_format: Optional[str] = None

    # 主标题区
    title: str = ""                    # 大字主标题（目的地 / 今日天气 / 日程标题）
    title_clock_format: Optional[str] = None
    title_color: str = "amber"
    subtitle: str = ""                 # 副标题（"Calling at:" / "Feels like 11°C" / "3 events today"）
    subtitle_color: str = "dim"

    # 内容行（中间主体）
    rows: List[BoardRow] = field(default_factory=list)

    # 底部
    footer: str = ""                   # 来源/品牌（"Great Northern" / "OpenWeather" / "Google Calendar"）
    footer_color: str = "dim"
    status_text: str = ""              # 状态标签（"On time" / "Sunny" / "2 upcoming"）
    status_color: str = "green"        # green / orange / red / white

    # 跑马灯（可选）
    ticker: Optional[str] = None       # 底部滚动文字，None 表示不显示

    # 车厢 / 翻页提示（可选，train 专用最小扩展）
    carriage_hint: Optional[str] = None  # "N"（车厢数），如 "8"
    page_label: Optional[str] = None     # 右对齐页码，如 "Page 1 of 1"

    # 模板与字号策略
    template: str = "auto"             # "auto" | "train" | "info"
                                       # auto: 有 carriage_hint 走 train，否则走 info
    title_size: str = "AUTO"           # "AUTO" | "LARGE" | "XLARGE"
                                       # AUTO: 优先 XLARGE，超宽自动降级 LARGE

    # 元信息（不渲染，供调度器使用）
    provider_id: str = ""              # 哪个 Provider 生成的
    expires_at: Optional[float] = None # Unix 时间戳，过期后调度器主动刷新
