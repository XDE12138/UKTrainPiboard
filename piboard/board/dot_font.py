"""
点阵字体渲染引擎
参照英国火车站 LED 点阵屏视觉特征：
  - 5×7 点阵（SMALL/MEDIUM）  或  7×9 点阵（LARGE/XLARGE）
  - 每个"像素"渲染为小圆点（pygame.draw.circle），非方块
  - 圆点半径 = (间距-1)//2，确保相邻圆点之间有 1px 间隙，还原独立 LED 外观
  - 亮点：使用传入主题色
  - 暗点：#1C1000（模拟未点亮 LED）
  - 背景：#080808
"""

import os
import pygame
from typing import Dict, Tuple, Optional

# ---------------------------------------------------------------------------
# 颜色常量
# ---------------------------------------------------------------------------
DOT_OFF   = (28, 16,  0)   # #1C1000 — 未点亮 LED
BG_COLOR  = (8,   8,   8)  # #080808

# ---------------------------------------------------------------------------
# 字号定义
# ---------------------------------------------------------------------------
class FontSize:
    SMALL  = "SMALL"    # 5×7  点阵，间距 3px，半径 1px
    MEDIUM = "MEDIUM"   # 5×7  点阵，间距 4px，半径 1px
    LARGE  = "LARGE"    # 7×9  点阵，间距 5px，半径 2px
    XLARGE = "XLARGE"   # 7×9  点阵，间距 7px，半径 3px

_SIZE_CONFIG = {
    # (点阵列数, 点阵行数, 间距px)
    # 半径由 max(1, (spacing-1)//2) 自动计算，确保圆点独立不重叠
    FontSize.SMALL:  (5, 7, 3),
    FontSize.MEDIUM: (5, 7, 4),
    FontSize.LARGE:  (7, 9, 5),
    FontSize.XLARGE: (7, 9, 7),
}

# ---------------------------------------------------------------------------
# 5×7 ASCII 点阵 bitmap（行优先，每行一个 5-bit 整数，高位=左）
# 覆盖 ASCII 32-126（space 到 ~）
# ---------------------------------------------------------------------------
_FONT_5X7: Dict[str, list] = {
    " ": [0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    "!": [0x04,0x04,0x04,0x04,0x00,0x00,0x04],
    '"': [0x0A,0x0A,0x00,0x00,0x00,0x00,0x00],
    "#": [0x0A,0x0A,0x1F,0x0A,0x1F,0x0A,0x0A],
    "$": [0x04,0x0F,0x14,0x0E,0x05,0x1E,0x04],
    "%": [0x18,0x19,0x02,0x04,0x08,0x13,0x03],
    "&": [0x0C,0x12,0x14,0x08,0x15,0x12,0x0D],
    "'": [0x04,0x04,0x00,0x00,0x00,0x00,0x00],
    "(": [0x02,0x04,0x08,0x08,0x08,0x04,0x02],
    ")": [0x08,0x04,0x02,0x02,0x02,0x04,0x08],
    "*": [0x00,0x04,0x15,0x0E,0x15,0x04,0x00],
    "+": [0x00,0x04,0x04,0x1F,0x04,0x04,0x00],
    ",": [0x00,0x00,0x00,0x00,0x06,0x04,0x08],
    "-": [0x00,0x00,0x00,0x1F,0x00,0x00,0x00],
    ".": [0x00,0x00,0x00,0x00,0x00,0x06,0x06],
    "/": [0x00,0x01,0x02,0x04,0x08,0x10,0x00],
    "0": [0x0E,0x11,0x13,0x15,0x19,0x11,0x0E],
    "1": [0x04,0x0C,0x04,0x04,0x04,0x04,0x0E],
    "2": [0x0E,0x11,0x01,0x02,0x04,0x08,0x1F],
    "3": [0x1F,0x02,0x04,0x02,0x01,0x11,0x0E],
    "4": [0x02,0x06,0x0A,0x12,0x1F,0x02,0x02],
    "5": [0x1F,0x10,0x1E,0x01,0x01,0x11,0x0E],
    "6": [0x06,0x08,0x10,0x1E,0x11,0x11,0x0E],
    "7": [0x1F,0x01,0x02,0x04,0x04,0x04,0x04],
    "8": [0x0E,0x11,0x11,0x0E,0x11,0x11,0x0E],
    "9": [0x0E,0x11,0x11,0x0F,0x01,0x02,0x0C],
    ":": [0x00,0x06,0x06,0x00,0x06,0x06,0x00],
    ";": [0x00,0x06,0x06,0x00,0x06,0x04,0x08],
    "<": [0x02,0x04,0x08,0x10,0x08,0x04,0x02],
    "=": [0x00,0x00,0x1F,0x00,0x1F,0x00,0x00],
    ">": [0x08,0x04,0x02,0x01,0x02,0x04,0x08],
    "?": [0x0E,0x11,0x01,0x02,0x04,0x00,0x04],
    "@": [0x0E,0x11,0x01,0x0D,0x15,0x15,0x0E],
    "A": [0x0E,0x11,0x11,0x1F,0x11,0x11,0x11],
    "B": [0x1E,0x11,0x11,0x1E,0x11,0x11,0x1E],
    "C": [0x0E,0x11,0x10,0x10,0x10,0x11,0x0E],
    "D": [0x1C,0x12,0x11,0x11,0x11,0x12,0x1C],
    "E": [0x1F,0x10,0x10,0x1E,0x10,0x10,0x1F],
    "F": [0x1F,0x10,0x10,0x1E,0x10,0x10,0x10],
    "G": [0x0E,0x11,0x10,0x17,0x11,0x11,0x0F],
    "H": [0x11,0x11,0x11,0x1F,0x11,0x11,0x11],
    "I": [0x0E,0x04,0x04,0x04,0x04,0x04,0x0E],
    "J": [0x07,0x02,0x02,0x02,0x02,0x12,0x0C],
    "K": [0x11,0x12,0x14,0x18,0x14,0x12,0x11],
    "L": [0x10,0x10,0x10,0x10,0x10,0x10,0x1F],
    "M": [0x11,0x1B,0x15,0x15,0x11,0x11,0x11],
    "N": [0x11,0x19,0x15,0x13,0x11,0x11,0x11],
    "O": [0x0E,0x11,0x11,0x11,0x11,0x11,0x0E],
    "P": [0x1E,0x11,0x11,0x1E,0x10,0x10,0x10],
    "Q": [0x0E,0x11,0x11,0x11,0x15,0x12,0x0D],
    "R": [0x1E,0x11,0x11,0x1E,0x14,0x12,0x11],
    "S": [0x0F,0x10,0x10,0x0E,0x01,0x01,0x1E],
    "T": [0x1F,0x04,0x04,0x04,0x04,0x04,0x04],
    "U": [0x11,0x11,0x11,0x11,0x11,0x11,0x0E],
    "V": [0x11,0x11,0x11,0x11,0x11,0x0A,0x04],
    "W": [0x11,0x11,0x11,0x15,0x15,0x1B,0x11],
    "X": [0x11,0x11,0x0A,0x04,0x0A,0x11,0x11],
    "Y": [0x11,0x11,0x0A,0x04,0x04,0x04,0x04],
    "Z": [0x1F,0x01,0x02,0x04,0x08,0x10,0x1F],
    "[": [0x0E,0x08,0x08,0x08,0x08,0x08,0x0E],
    "\\": [0x00,0x10,0x08,0x04,0x02,0x01,0x00],
    "]": [0x0E,0x02,0x02,0x02,0x02,0x02,0x0E],
    "^": [0x04,0x0A,0x11,0x00,0x00,0x00,0x00],
    "_": [0x00,0x00,0x00,0x00,0x00,0x00,0x1F],
    "`": [0x08,0x04,0x00,0x00,0x00,0x00,0x00],
    "a": [0x00,0x00,0x0E,0x01,0x0F,0x11,0x0F],
    "b": [0x10,0x10,0x1E,0x11,0x11,0x11,0x1E],
    "c": [0x00,0x00,0x0E,0x10,0x10,0x11,0x0E],
    "d": [0x01,0x01,0x0F,0x11,0x11,0x11,0x0F],
    "e": [0x00,0x00,0x0E,0x11,0x1F,0x10,0x0E],
    "f": [0x06,0x09,0x08,0x1C,0x08,0x08,0x08],
    # descender 字母（g y p q j）：当前压缩在 5×7 网格内，底边与大写齐平。
    # 无真实 baseline 下沉。若需真实 descender，需扩展至 5×9 字模（增 2 行）。
    "g": [0x00,0x00,0x0F,0x11,0x0F,0x01,0x0E],
    "h": [0x10,0x10,0x1E,0x11,0x11,0x11,0x11],
    "i": [0x00,0x04,0x00,0x0C,0x04,0x04,0x0E],
    "j": [0x00,0x02,0x00,0x06,0x02,0x12,0x0C],
    "k": [0x10,0x10,0x12,0x14,0x18,0x14,0x12],
    "l": [0x0C,0x04,0x04,0x04,0x04,0x04,0x0E],
    "m": [0x00,0x00,0x1A,0x15,0x15,0x11,0x11],
    "n": [0x00,0x00,0x1E,0x11,0x11,0x11,0x11],
    "o": [0x00,0x00,0x0E,0x11,0x11,0x11,0x0E],
    "p": [0x00,0x00,0x1E,0x11,0x1E,0x10,0x10],
    "q": [0x00,0x00,0x0F,0x11,0x0F,0x01,0x01],
    "r": [0x00,0x00,0x16,0x19,0x10,0x10,0x10],
    "s": [0x00,0x00,0x0E,0x10,0x0E,0x01,0x1E],
    "t": [0x08,0x08,0x1C,0x08,0x08,0x09,0x06],
    "u": [0x00,0x00,0x11,0x11,0x11,0x13,0x0D],
    "v": [0x00,0x00,0x11,0x11,0x11,0x0A,0x04],
    "w": [0x00,0x00,0x11,0x15,0x15,0x15,0x0A],
    "x": [0x00,0x00,0x11,0x0A,0x04,0x0A,0x11],
    "y": [0x00,0x00,0x11,0x11,0x0F,0x01,0x0E],
    "z": [0x00,0x00,0x1F,0x02,0x04,0x08,0x1F],
    "{": [0x03,0x04,0x04,0x08,0x04,0x04,0x03],
    "|": [0x04,0x04,0x04,0x04,0x04,0x04,0x04],
    "}": [0x18,0x04,0x04,0x02,0x04,0x04,0x18],
    "~": [0x00,0x08,0x15,0x02,0x00,0x00,0x00],
    # 特殊字符（用于温度等）
    "°": [0x06,0x09,0x09,0x06,0x00,0x00,0x00],
}

# ---------------------------------------------------------------------------
# 7×9 ASCII 点阵 bitmap（行优先，每行一个 7-bit 整数，高位=左）
# 仅定义常用字符，其余回退到 5×7 放大渲染
# ---------------------------------------------------------------------------
_FONT_7X9: Dict[str, list] = {
    " ": [0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    "0": [0x1C,0x22,0x41,0x41,0x41,0x41,0x41,0x22,0x1C],
    "1": [0x08,0x18,0x28,0x08,0x08,0x08,0x08,0x08,0x3E],
    "2": [0x1C,0x22,0x41,0x01,0x02,0x04,0x08,0x10,0x7F],
    "3": [0x7F,0x02,0x04,0x02,0x1C,0x02,0x01,0x41,0x3E],
    "4": [0x04,0x0C,0x14,0x24,0x44,0x7F,0x04,0x04,0x04],
    "5": [0x7F,0x40,0x40,0x7E,0x01,0x01,0x01,0x41,0x3E],
    "6": [0x1C,0x20,0x40,0x7E,0x41,0x41,0x41,0x22,0x1C],
    "7": [0x7F,0x01,0x02,0x04,0x08,0x08,0x08,0x08,0x08],
    "8": [0x1C,0x22,0x41,0x22,0x1C,0x22,0x41,0x22,0x1C],
    "9": [0x1C,0x22,0x41,0x41,0x3F,0x01,0x02,0x04,0x18],
    ":": [0x00,0x18,0x18,0x00,0x00,0x18,0x18,0x00,0x00],
    "A": [0x08,0x14,0x22,0x41,0x41,0x7F,0x41,0x41,0x41],
    "B": [0x7E,0x41,0x41,0x41,0x7E,0x41,0x41,0x41,0x7E],
    "C": [0x1E,0x21,0x40,0x40,0x40,0x40,0x40,0x21,0x1E],
    "D": [0x7C,0x42,0x41,0x41,0x41,0x41,0x41,0x42,0x7C],
    "E": [0x7F,0x40,0x40,0x40,0x7E,0x40,0x40,0x40,0x7F],
    "F": [0x7F,0x40,0x40,0x40,0x7E,0x40,0x40,0x40,0x40],
    "G": [0x1E,0x21,0x40,0x40,0x47,0x41,0x41,0x21,0x1E],
    "H": [0x41,0x41,0x41,0x41,0x7F,0x41,0x41,0x41,0x41],
    "I": [0x1C,0x08,0x08,0x08,0x08,0x08,0x08,0x08,0x1C],
    "J": [0x07,0x02,0x02,0x02,0x02,0x02,0x02,0x42,0x3C],
    "K": [0x41,0x42,0x44,0x48,0x70,0x48,0x44,0x42,0x41],
    "L": [0x40,0x40,0x40,0x40,0x40,0x40,0x40,0x40,0x7F],
    "M": [0x41,0x63,0x55,0x49,0x41,0x41,0x41,0x41,0x41],
    "N": [0x41,0x61,0x51,0x49,0x45,0x43,0x41,0x41,0x41],
    "O": [0x1C,0x22,0x41,0x41,0x41,0x41,0x41,0x22,0x1C],
    "P": [0x7E,0x41,0x41,0x41,0x7E,0x40,0x40,0x40,0x40],
    "Q": [0x1C,0x22,0x41,0x41,0x41,0x45,0x42,0x21,0x1D],
    "R": [0x7E,0x41,0x41,0x41,0x7E,0x44,0x42,0x41,0x41],
    "S": [0x1E,0x21,0x40,0x40,0x1C,0x02,0x01,0x21,0x1E],
    "T": [0x7F,0x08,0x08,0x08,0x08,0x08,0x08,0x08,0x08],
    "U": [0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x22,0x1C],
    "V": [0x41,0x41,0x41,0x41,0x22,0x22,0x14,0x08,0x08],
    "W": [0x41,0x41,0x41,0x49,0x49,0x55,0x63,0x41,0x41],
    "X": [0x41,0x22,0x14,0x08,0x08,0x14,0x22,0x41,0x41],
    "Y": [0x41,0x22,0x14,0x08,0x08,0x08,0x08,0x08,0x08],
    "Z": [0x7F,0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x7F],
    "-": [0x00,0x00,0x00,0x00,0x7F,0x00,0x00,0x00,0x00],
    ".": [0x00,0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x00],
    "/": [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x00,0x00],
    "°": [0x0C,0x12,0x12,0x0C,0x00,0x00,0x00,0x00,0x00],
}


# ---------------------------------------------------------------------------
# 渲染缓存
# ---------------------------------------------------------------------------
_char_cache: Dict[Tuple, pygame.Surface] = {}
_font_cache: Dict[Tuple, object] = {}

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BUNDLED_DOTTED_SONGTI_CIRCLE = os.path.join(
    _PROJECT_ROOT,
    "third_party",
    "fonts",
    "dotted_songti",
    "DottedSongtiCircleRegular.otf",
)
_BUNDLED_DOTTED_SONGTI_SQUARE = os.path.join(
    _PROJECT_ROOT,
    "third_party",
    "fonts",
    "dotted_songti",
    "DottedSongtiSquareRegular.otf",
)

_CJK_FONT_PATHS = (
    # Project-bundled dotted pixel CJK fonts. GPL-2.0, see third_party/fonts/dotted_songti/LICENSE.
    _BUNDLED_DOTTED_SONGTI_CIRCLE,
    _BUNDLED_DOTTED_SONGTI_SQUARE,
    # Raspberry Pi OS / Debian
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    # macOS
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    # Windows / common cross-platform installs
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
)

_CJK_FONT_NAMES = (
    "Noto Sans CJK SC",
    "Noto Sans CJK",
    "WenQuanYi Micro Hei",
    "Droid Sans Fallback",
    "Source Han Sans CN",
    "Hiragino Sans GB",
    "PingFang SC",
    "Microsoft YaHei",
    "SimHei",
)


def _get_bitmap(char: str, size: str) -> Optional[list]:
    """返回字符的点阵 bitmap，大字号优先 7×9，其余用 5×7。

    已知限制（Typography Spec v1 记录）：
      - LARGE/XLARGE 小写字母未在 _FONT_7X9 中定义，触发此处 fallback。
        fallback 将 5×7 bitmap 按 7×9 网格拉伸，产生字形失真。
        规则：LARGE/XLARGE 场景必须使用全大写文本，避免触发此路径。
        后续修复：在 _FONT_7X9 中补充 a-z 定义，届时 fallback 仅用于罕见符号。

      - descender 支持（future）：
        若未来扩展小写字模至 5×9，此函数需增加 rows_override 参数，
        并在 _render_char 中按实际 bitmap 行数渲染（而非固定 rows）。
        设计草案：bitmap 长度 > grid_rows 时，超出行数渲染在 baseline 以下。
    """
    if size in (FontSize.LARGE, FontSize.XLARGE):
        if char in _FONT_7X9:
            return _FONT_7X9[char]
        # 回退：5×7 bitmap，后续渲染时会按 7×9 网格拉伸（字形有失真，见上方注释）
        return _FONT_5X7.get(char)
    else:
        return _FONT_5X7.get(char)


def _uses_font_fallback(char: str, size: str) -> bool:
    """Return True for Unicode chars that are not covered by built-in bitmaps."""
    return bool(char) and ord(char) > 127 and _get_bitmap(char, size) is None


def _font_fallback_side(size: str) -> int:
    """Fallback glyphs are rendered square and a touch fuller than Latin dots."""
    if size == FontSize.SMALL:
        return 24
    if size == FontSize.MEDIUM:
        return 32
    if size == FontSize.LARGE:
        return 48
    if size == FontSize.XLARGE:
        return 72
    _, rows, spacing = _SIZE_CONFIG[size]
    return rows * spacing


def _fallback_pixel_block(size: str) -> int:
    """Pixel-art fallback scale: rows stay fine, large titles scale as blocks."""
    if size == FontSize.XLARGE:
        return 3
    if size == FontSize.LARGE:
        return 2
    return 1


def _get_fallback_font_entry(px: int) -> Tuple[pygame.font.Font, str]:
    """Load a CJK-capable font and remember the source path."""
    if not pygame.font.get_init():
        pygame.font.init()

    env_path = os.environ.get("PIBOARD_CJK_FONT", "").strip()
    candidates = (env_path,) if env_path else ()
    candidates += _CJK_FONT_PATHS

    cache_key = ("fallback", px, env_path)
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        try:
            font = pygame.font.Font(path, px)
            entry = (font, path)
            _font_cache[cache_key] = entry
            return entry
        except Exception:
            continue

    for name in _CJK_FONT_NAMES:
        try:
            matched = pygame.font.match_font(name)
        except Exception:
            matched = None
        if not matched:
            continue
        try:
            font = pygame.font.Font(matched, px)
            entry = (font, matched)
            _font_cache[cache_key] = entry
            return entry
        except Exception:
            continue

    font = pygame.font.Font(None, px)
    entry = (font, "")
    _font_cache[cache_key] = entry
    return entry


def _get_fallback_font(px: int) -> pygame.font.Font:
    """Load a CJK-capable system font, with an env override for kiosk images."""
    return _get_fallback_font_entry(px)[0]


def _is_dotted_songti(path: str) -> bool:
    name = os.path.basename(path or "").lower()
    return name.startswith("dottedsongti")


def _render_dotted_font_char(char: str, size: str,
                             color: Tuple[int, int, int]) -> pygame.Surface:
    """Render Dotted Songti glyphs directly so their native dot pattern survives."""
    side = _font_fallback_side(size)
    font_px = max(10, int(side * 1.34))
    font, _path = _get_fallback_font_entry(font_px)
    glyph = font.render(char, True, color)
    bbox = glyph.get_bounding_rect()

    surf = pygame.Surface((side, side), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    if bbox.w <= 0 or bbox.h <= 0:
        return surf

    glyph = glyph.subsurface(bbox).copy()
    margin = 0 if size in (FontSize.SMALL, FontSize.MEDIUM) else 1
    max_w = max(1, side - 2 * margin)
    max_h = max(1, side - 2 * margin)
    scale = min(max_w / glyph.get_width(), max_h / glyph.get_height(), 1.0)
    target_w = max(1, int(glyph.get_width() * scale))
    target_h = max(1, int(glyph.get_height() * scale))
    if (target_w, target_h) != glyph.get_size():
        glyph = pygame.transform.smoothscale(glyph, (target_w, target_h))
    glyph = _solidify_alpha_glyph(glyph, color, threshold=36)

    surf.blit(glyph, (
        (side - target_w) // 2,
        (side - target_h) // 2,
    ))
    return surf


def _solidify_alpha_glyph(glyph: pygame.Surface,
                          color: Tuple[int, int, int],
                          threshold: int = 36) -> pygame.Surface:
    """Make dotted font samples read as lit LEDs instead of gray antialiasing."""
    out = pygame.Surface(glyph.get_size(), pygame.SRCALPHA)
    out.fill((0, 0, 0, 0))
    w, h = glyph.get_size()
    lit = (*color, 255)
    for y in range(h):
        for x in range(w):
            if glyph.get_at((x, y)).a >= threshold:
                out.set_at((x, y), lit)
    return out


def _render_font_fallback_char(char: str, size: str,
                               color: Tuple[int, int, int]) -> pygame.Surface:
    """Render a Unicode glyph as pixel-art CJK fallback.

    Bundled Dotted Songti is rendered directly so its own dot matrix remains
    visible. Non-dotted fallback fonts still use low-resolution sampling.
    """
    side = _font_fallback_side(size)
    block = _fallback_pixel_block(size)
    logical_side = max(8, side // block)

    surf = pygame.Surface((side, side), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))

    font_px = max(8, int(logical_side * 1.08))
    font, font_path = _get_fallback_font_entry(font_px)
    if _is_dotted_songti(font_path):
        return _render_dotted_font_char(char, size, color)

    glyph = font.render(char, False, (255, 255, 255))
    bbox = glyph.get_bounding_rect()

    logical = pygame.Surface((logical_side, logical_side), pygame.SRCALPHA)
    logical.fill((0, 0, 0, 0))

    if bbox.w > 0 and bbox.h > 0:
        glyph = glyph.subsurface(bbox).copy()
        margin = 0 if size in (FontSize.SMALL, FontSize.MEDIUM) else max(1, logical_side // 16)
        max_w = max(1, logical_side - 2 * margin)
        max_h = max(1, logical_side - 2 * margin)
        scale = min(max_w / glyph.get_width(), max_h / glyph.get_height())
        target_w = max(1, int(glyph.get_width() * scale))
        target_h = max(1, int(glyph.get_height() * scale))
        if (target_w, target_h) != glyph.get_size():
            glyph = pygame.transform.scale(glyph, (target_w, target_h))
        logical.blit(glyph, (
            (logical_side - target_w) // 2,
            (logical_side - target_h) // 2,
        ))

    glyph_mask = pygame.mask.from_surface(logical, 1)
    origin_x = (side - logical_side * block) // 2
    origin_y = (side - logical_side * block) // 2
    for py in range(logical_side):
        for px in range(logical_side):
            if glyph_mask.get_at((px, py)):
                dot_rect = pygame.Rect(
                    origin_x + px * block,
                    origin_y + py * block,
                    block,
                    block,
                )
                pygame.draw.circle(
                    surf,
                    color,
                    dot_rect.center,
                    max(1, block // 2),
                )
    return surf


def _render_char(char: str, size: str,
                 color: Tuple[int, int, int]) -> pygame.Surface:
    """
    渲染单个字符，返回 Surface。
    结果缓存在 _char_cache 中，相同参数不重复渲染。

    半径公式：radius = max(1, (spacing-1)//2)
      SMALL  (3px): radius=1 → 圆直径2px，相邻间距1px  ✓ 独立圆点
      MEDIUM (4px): radius=1 → 圆直径2px，相邻间距2px  ✓ 独立圆点
      LARGE  (5px): radius=2 → 圆直径4px，相邻间距1px  ✓ 独立圆点
      XLARGE (7px): radius=3 → 圆直径6px，相邻间距1px  ✓ 独立圆点
    """
    key = (char, size, color)
    if key in _char_cache:
        return _char_cache[key]

    cols, rows, spacing = _SIZE_CONFIG[size]
    bitmap = _get_bitmap(char, size)
    if bitmap is None and _uses_font_fallback(char, size):
        surf = _render_font_fallback_char(char, size, color)
        _char_cache[key] = surf
        return surf

    # 新半径公式：确保圆点之间至少有 1px 间隙，还原独立 LED 外观
    radius = max(1, (spacing - 1) // 2)

    # radius ≤ spacing//2，overflow 始终为 0，无需扩展 surface
    surf_w = cols * spacing
    surf_h = rows * spacing
    surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))  # 透明背景

    if bitmap is None:
        # 未知字符：渲染为全暗点
        bitmap = [0x00] * rows

    bm_rows = len(bitmap)
    bm_cols = cols  # 5 or 7

    for row_i in range(rows):
        bm_row = bitmap[row_i] if row_i < bm_rows else 0
        for col_i in range(cols):
            # bitmap 高位对应左侧
            bit = (bm_row >> (bm_cols - 1 - col_i)) & 1
            cx = col_i * spacing + spacing // 2
            cy = row_i * spacing + spacing // 2
            if bit:
                pygame.draw.circle(surf, color, (cx, cy), radius)
            else:
                pygame.draw.circle(surf, DOT_OFF, (cx, cy), radius)

    _char_cache[key] = surf
    return surf


def _measure_char(char: str, size: str) -> Tuple[int, int]:
    cols, rows, spacing = _SIZE_CONFIG[size]
    if _uses_font_fallback(char, size):
        side = _font_fallback_side(size)
        return side, side
    return cols * spacing, rows * spacing


def render_text(surface: pygame.Surface, text: str, x: int, y: int,
                size: str, color: Tuple[int, int, int],
                char_gap: int = 0) -> int:
    """
    在 surface 的 (x, y) 处渲染文字，返回渲染后的右边界 x 坐标。
    char_gap: 字符间额外间距（点），默认 0（紧凑，更接近真实 LED 屏）
    """
    _, _, spacing = _SIZE_CONFIG[size]
    gap_w = char_gap * spacing

    cx = x
    for ch in text:
        char_surf = _render_char(ch, size, color)
        surface.blit(char_surf, (cx, y))
        cx += char_surf.get_width() + gap_w

    return cx


def measure_text(text: str, size: str, char_gap: int = 0) -> Tuple[int, int]:
    """返回文字渲染宽高 (w, h)，不实际渲染。"""
    if not text:
        _, rows, spacing = _SIZE_CONFIG[size]
        return 0, rows * spacing

    _, _, spacing = _SIZE_CONFIG[size]
    gap_w = char_gap * spacing
    widths = []
    heights = []
    for ch in text:
        w, h = _measure_char(ch, size)
        widths.append(w + gap_w)
        heights.append(h)
    return sum(widths), max(heights)


def render_text_right_aligned(surface: pygame.Surface, text: str,
                               right_x: int, y: int,
                               size: str, color: Tuple[int, int, int]) -> None:
    """右对齐渲染文字。"""
    w, _ = measure_text(text, size)
    render_text(surface, text, right_x - w, y, size, color)


def clear_cache():
    """清空字符缓存（切换主题时调用）。"""
    _char_cache.clear()
    _font_cache.clear()
