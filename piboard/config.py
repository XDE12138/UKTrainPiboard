"""全局配置：分辨率、帧率、颜色、Provider 注册表等"""

# 显示设置 — 横屏（Landscape）
SCREEN_WIDTH  = 1024
SCREEN_HEIGHT = 600

# 显示设置 — 竖屏（Portrait）
PORTRAIT_WIDTH  = 600
PORTRAIT_HEIGHT = 1024

FPS_ACTIVE = 30     # 有动画/内容变化时的帧率
FPS_IDLE = 1        # 静止时降至 1fps，节省 CPU
LOW_POWER_TICKER_PAGE_INTERVAL_MS = 5000


def is_portrait(w: int, h: int) -> bool:
    """根据屏幕尺寸判断是否为竖屏模式。"""
    return h > w

# 背景色
BG_COLOR = (8, 8, 8)   # #080808，极深黑

# 颜色常量映射
COLORS = {
    "amber":  (255, 149,   0),   # 主色，琥珀色
    "green":  ( 80, 220,  80),   # 状态正常
    "red":    (220,  50,  50),   # 告警/延误
    "orange": (255, 160,  30),   # 次要信息
    "white":  (220, 220, 220),   # 高亮白
    "dim":    (160, 100,   5),   # 暗色辅助文字（约 62% amber，匹配参考图可读 dim）
}

# 颜色主题变体（color_theme 设置生效时，主色 amber 映射到以下颜色）
COLOR_THEMES = {
    "amber": COLORS,
    "green": {**COLORS, "amber": ( 80, 220,  80)},
    "white": {**COLORS, "amber": (220, 220, 220)},
}

# 点阵字体点间距（像素），各尺寸
DOT_SPACING = {
    "SMALL":  3,    # 5×7 点阵，间距3px → 字符宽15px，高21px
    "MEDIUM": 4,    # 5×7 点阵，间距4px → 字符宽20px，高28px
    "LARGE":  5,    # 7×9 点阵，间距5px → 字符宽35px，高45px
    "XLARGE": 7,    # 7×9 点阵，间距7px → 字符宽49px，高63px
}

# ---------------------------------------------------------------------------
# Typography Spec v1
# ---------------------------------------------------------------------------
# 【当前实现约束 / Current Implementation Constraints】
#
#   字号层级（4档固定，不允许页面自行发明新尺寸）：
#     SMALL:  15×21px  — 列表行、跑马灯、metadata
#     MEDIUM: 20×28px  — header、平台号、状态标签
#     LARGE:  35×45px  — 标题、车站名
#     XLARGE: 49×63px  — 主时间、hero 信息
#
#   大小写约束：
#     LARGE / XLARGE 当前只有 7×9 大写字母 + 数字原生字模；
#     小写字母会触发 5×7→7×9 拉伸 fallback，导致字形失真。
#     规则：LARGE 和 XLARGE 必须使用全大写文本，直到 _FONT_7X9 补充小写定义。
#
#   Descender（下伸部字母）：
#     当前 g / y / p / q / j 被压缩在 5×7 网格内，底边与大写字母齐平。
#     这是网格尺寸约束，不是设计意图。
#     后续若需真实 descender，应将小写字模扩展至 5×9（增加 2 行 descender zone）。
#
#   Baseline：
#     当前无 baseline 概念，所有字符以顶边对齐渲染。
#     字符底边 = cap height 底边 = 当前事实 baseline。
#
# 【目标规则 / Target Typography Rules】
#
#   - 引入 baseline_row 概念：5×7 中 row 5 为 baseline，row 6 = descender zone
#   - LARGE/XLARGE 补充 a-z 7×9 字模，消除 fallback 拉伸
#   - line-height 使用下方 LINE_HEIGHTS 常量，不允许各 renderer 自行硬编码
#   - 数字必须等宽（当前已满足）
#   - 常用符号（: / - . %）在同档字号内宽度统一（当前已满足）
# ---------------------------------------------------------------------------

# 行高常量：字符高度 + leading，各页面 renderer 应引用此常量而非硬编码
# char_h + leading = LINE_HEIGHTS[size]
LINE_HEIGHTS = {
    "SMALL":  27,   # 21px + 6px leading
    "MEDIUM": 36,   # 28px + 8px leading
    "LARGE":  55,   # 45px + 10px leading
    "XLARGE": 77,   # 63px + 14px leading
}

# 动画设置
TICKER_SPEED = 60       # 跑马灯速度，像素/秒
PAGE_FLIP_INTERVAL = 8  # 内容行翻页间隔，秒
TRANSITION_DURATION = 500  # 板面切换动画时长，毫秒

# Web 服务设置
WEB_HOST = "0.0.0.0"
WEB_PORT = 8080

# Provider 注册表（在 main.py 中填充，这里只留空列表作为默认）
# 使用字符串延迟导入，避免循环依赖
REGISTERED_PROVIDER_CLASSES = []

# 数据目录
import os
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
