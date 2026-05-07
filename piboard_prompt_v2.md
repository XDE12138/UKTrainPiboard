# PiBoard — 树莓派 Zero 2W 个人显示系统 v2

## 项目背景

在树莓派 Zero 2W（ARMv8, 512MB RAM）+ 7寸屏幕上，搭建一套**轻量、可扩展的个人信息显示系统**。

整体视觉风格：**完全统一为英国火车站 LED 点阵报站大屏风格**。
内容完全可插拔：列车时刻、天气、日程、自定义文字……任何内容都能以相同的点阵风格呈现。

核心渲染方案：**Python + pygame（SDL2 kmsdrm 后端，无桌面环境）**  
远程控制方案：**Flask + WebSocket（局域网访问）**

---

## 一、核心设计理念

**渲染与内容完全解耦。**

```
┌─────────────────────────────────────────────────┐
│            点阵渲染引擎（固定，不变）              │
│         dot_matrix renderer / board.py           │
└─────────────────┬───────────────────────────────┘
                  │ 只认识 BoardContent 结构
┌─────────────────┴───────────────────────────────┐
│           ContentProvider 抽象接口               │
└──────┬──────────┬──────────┬────────────────────┘
       │          │          │          │
  列车时刻      天气预报    个人日程    自定义文本
TrainProvider WeatherProvider CalendarProvider CustomProvider
  (调API)      (调API)       (读ics/手填)    (Web端直接编辑)
```

渲染层永远不知道内容从哪来，内容层永远不知道自己怎么被画出来。
**新增一种内容 = 新建一个 Provider 文件，零改动渲染代码。**

---

## 二、目录结构

```
piboard/
├── main.py                        # 入口：启动 pygame 主循环 + Flask 子线程
├── config.py                      # 全局配置（分辨率、帧率、Provider 注册表等）
├── state.py                       # 线程安全全局共享状态（单例）
├── renderer.py                    # pygame 主渲染循环
│
├── board/
│   ├── content.py                 # ★ BoardContent / BoardRow 数据结构定义
│   ├── dot_font.py                # ★ 点阵字体渲染引擎
│   ├── board_renderer.py          # ★ 把 BoardContent 画到 pygame Surface
│   └── animations.py              # 滚动、翻页、逐行出现等动画
│
├── providers/                     # ★ 内容提供者（可随意增删）
│   ├── base.py                    # BaseProvider 抽象基类
│   ├── train.py                   # 列车时刻 Provider
│   ├── weather.py                 # 天气 Provider
│   ├── calendar_provider.py       # 日程 Provider
│   ├── custom.py                  # 自定义文本 Provider（Web 端直接编辑内容）
│   └── mock.py                    # Mock Provider（开发调试用，不调任何 API）
│
├── layouts/
│   ├── base.py                    # Layout 基类
│   ├── single.py                  # 单板全屏布局
│   ├── dual.py                    # 左右双板布局
│   └── carousel.py                # 多板轮播布局
│
├── web/
│   ├── server.py                  # Flask + flask-sock
│   ├── templates/
│   │   └── index.html             # 控制台（单文件，响应式，暗色）
│   └── static/
│       └── app.js
│
├── data/
│   └── fetcher.py                 # 通用后台数据拉取调度器
│
├── assets/
│   └── fonts/                     # 备用 TTF 字体
│
├── requirements.txt
├── install.sh
├── piboard.service                # systemd 服务文件
└── README.md
```

---

## 三、BoardContent 协议（content.py）★ 最核心

这是渲染层和内容层之间**唯一的契约**，所有 Provider 都输出这个结构：

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class BoardRow:
    """中间内容区的一行"""
    left: str                        # 左侧文字（站名、事件标题、天气描述）
    right: str                       # 右侧文字（时间、温度、状态）
    left_color: str = "amber"        # amber / green / red / orange / white / dim
    right_color: str = "amber"
    highlight: bool = False          # 是否高亮整行（如「下一班」）
    indent: int = 0                  # 左缩进（点数），用于层级展示

@dataclass
class BoardContent:
    """
    一块报站板的完整内容描述。
    渲染引擎只认识这个结构，不关心内容从哪来。
    """
    # 顶部栏
    header_left: str = ""            # 左上角（如 "11:35"、"14°C"、"MON"）
    header_right: str = ""           # 右上角（如 "Platform 9"、"London"、"Week 15"）

    # 主标题区
    title: str = ""                  # 大字主标题（目的地 / 今日天气 / 日程标题）
    title_color: str = "amber"
    subtitle: str = ""               # 副标题（"Calling at:" / "Feels like 11°C" / "3 events today"）
    subtitle_color: str = "dim"

    # 内容行（中间主体）
    rows: List[BoardRow] = field(default_factory=list)

    # 底部
    footer: str = ""                 # 来源/品牌（"Great Northern" / "OpenWeather" / "Google Calendar"）
    footer_color: str = "dim"
    status_text: str = ""            # 状态标签（"On time" / "Sunny" / "2 upcoming"）
    status_color: str = "green"      # green / orange / red / white

    # 跑马灯（可选）
    ticker: Optional[str] = None     # 底部滚动文字，None 表示不显示

    # 元信息（不渲染，供调度器使用）
    provider_id: str = ""            # 哪个 Provider 生成的
    expires_at: Optional[float] = None  # Unix 时间戳，过期后调度器主动刷新
```

### 颜色常量映射（在 config.py 中定义，可整体调整）

```python
COLORS = {
    "amber":   (255, 149,   0),   # 主色，琥珀色
    "green":   ( 80, 220,  80),   # 状态正常
    "red":     (220,  50,  50),   # 告警/延误
    "orange":  (255, 160,  30),   # 次要信息
    "white":   (220, 220, 220),   # 高亮白
    "dim":     ( 80,  55,  10),   # 暗色辅助文字
}
```

---

## 四、BaseProvider 抽象基类（providers/base.py）

```python
from abc import ABC, abstractmethod
from board.content import BoardContent
from typing import Optional, Dict, Any

class BaseProvider(ABC):
    
    provider_id: str = "base"           # 唯一标识，用于注册和 Web 端引用
    display_name: str = "Base Provider" # Web 控制台显示名称
    default_refresh_interval: int = 60  # 默认刷新间隔（秒）
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._cached_content: Optional[BoardContent] = None
    
    @abstractmethod
    def fetch(self) -> BoardContent:
        """
        拉取/生成内容，返回 BoardContent。
        此方法在后台线程中调用，可以做网络请求、读文件等。
        不要在此方法中调用任何 pygame API。
        """
        ...
    
    def get_content(self) -> BoardContent:
        """返回缓存内容，供渲染层调用（主线程安全）"""
        return self._cached_content or self._empty_content()
    
    def get_config_schema(self) -> Dict:
        """
        返回此 Provider 的配置项描述，Web 控制台据此自动生成表单。
        格式示例：
        {
            "city": {"type": "string", "label": "城市", "default": "London"},
            "units": {"type": "select", "label": "单位", "options": ["metric", "imperial"]},
            "api_key": {"type": "string", "label": "API Key", "secret": True}
        }
        """
        return {}
    
    def _empty_content(self) -> BoardContent:
        return BoardContent(
            title=self.display_name,
            subtitle="Loading...",
            status_text="--",
            status_color="dim",
            provider_id=self.provider_id
        )
```

---

## 五、内置 Provider 实现要求

### 5.1 列车时刻（providers/train.py）

配置项：
```python
{
    "station_crs": {"type": "string", "label": "出发站 CRS 代码", "default": "KGX"},
    "destination_crs": {"type": "string", "label": "目的地 CRS（可选）", "default": ""},
    "api_key": {"type": "string", "label": "Transport API Key", "secret": True},
    "data_source": {"type": "select", "label": "数据源", 
                    "options": ["mock", "transportapi", "huxley2"], "default": "mock"}
}
```

输出的 BoardContent 示例：
```
header_left  = "11:35"
header_right = "Platform 9"
title        = "Edinburgh"
subtitle     = "Calling at:  Page 1 of 1"
rows = [
    BoardRow("Newcastle",         "12:35"),
    BoardRow("Morpeth",           "12:59"),
    BoardRow("Alnmouth (Alnwick)","13:07"),
    BoardRow("& Edinburgh",       "14:15"),
]
footer       = "LNER Azuma"
status_text  = "On time"
status_color = "green"
ticker       = "LNER Azuma train service. Reserve seats up to coach A."
```

### 5.2 天气（providers/weather.py）

配置项：
```python
{
    "city": {"type": "string", "label": "城市", "default": "London"},
    "api_key": {"type": "string", "label": "OpenWeatherMap API Key", "secret": True},
    "units": {"type": "select", "label": "温度单位", "options": ["metric", "imperial"], "default": "metric"}
}
```

输出的 BoardContent 示例（模仿火车板风格）：
```
header_left  = "14°C"
header_right = "London"
title        = "Partly Cloudy"
subtitle     = "Feels like  11°C"
rows = [
    BoardRow("Humidity",    "72%"),
    BoardRow("Wind",        "SW 18km/h"),
    BoardRow("Visibility",  "10km"),
    BoardRow("UV Index",    "Low"),
    BoardRow(""),                          # 空行分隔
    BoardRow("Tomorrow",    "12°C / 8°C"),
    BoardRow("Wed",         "15°C / 9°C"),
    BoardRow("Thu",         "11°C / 7°C"),
]
footer       = "OpenWeather"
status_text  = "Partly Cloudy"
status_color = "white"
ticker       = "Today: Cloudy morning, clearing in the afternoon. Low chance of rain."
```

### 5.3 日程（providers/calendar_provider.py）

配置项：
```python
{
    "ical_url": {"type": "string", "label": "iCal URL（Google/Apple日历）", "default": ""},
    "lookahead_days": {"type": "number", "label": "显示未来几天", "default": 3}
}
```

输出的 BoardContent 示例：
```
header_left  = "MON"
header_right = "08 Apr"
title        = "Today's Schedule"
subtitle     = "3 events"
rows = [
    BoardRow("09:00  Team standup",    "30min",  highlight=True),
    BoardRow("14:00  Dentist",         "1hr"),
    BoardRow("19:30  Dinner - Marks",  "2hr"),
    BoardRow(""),
    BoardRow("Tomorrow",               "2 events", left_color="dim", right_color="dim"),
    BoardRow("10:00  Code review",     "1hr",    left_color="dim", right_color="dim"),
    BoardRow("16:00  Weekly sync",     "45min",  left_color="dim", right_color="dim"),
]
footer       = "Google Calendar"
status_text  = "Next: 09:00"
status_color = "green"
```

### 5.4 自定义文本（providers/custom.py）

**无需 API，内容完全由 Web 控制台直接编辑。**

配置项就是内容本身：
```python
{
    "header_left":  {"type": "string", "label": "左上角"},
    "header_right": {"type": "string", "label": "右上角"},
    "title":        {"type": "string", "label": "主标题"},
    "subtitle":     {"type": "string", "label": "副标题"},
    "rows":         {"type": "rows",   "label": "内容行（每行填左文字和右文字）"},
    "footer":       {"type": "string", "label": "底部来源"},
    "status_text":  {"type": "string", "label": "状态文字"},
    "status_color": {"type": "select", "label": "状态颜色",
                     "options": ["green", "amber", "orange", "red", "white"]},
    "ticker":       {"type": "string", "label": "跑马灯文字（留空不显示）"},
}
```

此 Provider 的 `fetch()` 直接把 config 映射成 BoardContent，无任何网络请求。

### 5.5 Mock（providers/mock.py）

开发用，内置多个预设的 BoardContent（火车/天气/日程各一个），
按时间轮换，无需任何 API Key 即可看到完整效果。

---

## 六、点阵渲染引擎（board/dot_font.py + board_renderer.py）

### 6.1 点阵字体（dot_font.py）

参照英国火车站 LED 点阵屏视觉特征：

- 每个字符为 **5×7** 点阵（小字）或 **7×9** 点阵（大字/标题）
- 每个「像素」渲染为**小圆点**（`pygame.draw.circle`），非方块
- **亮点**：琥珀色 `#FF9500`，可选轻微径向渐变（中心略亮）
- **暗点**：`#1C1000`（极暗，模拟 LED 未点亮物理状态，必须渲染）
- 圆点直径 = 点间距 × 0.72（留间隙）
- 支持字号枚举：`SMALL / MEDIUM / LARGE / XLARGE`

字符渲染结果缓存到 `Dict[str, pygame.Surface]`，同字符不重复绘制。

### 6.2 板面渲染（board_renderer.py）

接收 `BoardContent`，输出到指定 `pygame.Surface`：

布局（从上到下）：
```
┌─────────────────────────────────────┐  ← 顶部栏（MEDIUM字号）
│  header_left          header_right  │    高度约 15% 屏高
├─────────────────────────────────────┤
│  title                              │  ← 主标题（LARGE/XLARGE）
│  subtitle                           │    高度约 15% 屏高
├─────────────────────────────────────┤
│  row[0].left          row[0].right  │
│  row[1].left          row[1].right  │  ← 内容行（SMALL字号）
│  ...                                │    高度约 50% 屏高，自动计算行高
├─────────────────────────────────────┤
│  footer                             │  ← 底部品牌（SMALL，dim色）
│  [status_text]                      │    高度约 10% 屏高
├─────────────────────────────────────┤
│  ←← ticker 滚动文字 ←←             │  ← 跑马灯（SMALL）
└─────────────────────────────────────┘    高度约 10% 屏高
```

### 6.3 动画（animations.py）

- **跑马灯**：ticker 文字从右向左匀速滚动，循环播放
- **翻页**：内容行超出显示区时，每 N 秒自动翻页（上滑动画）
- **数字更新**：header_left 时间数字变化时，有轻微的纵向翻转效果（可配置关闭）
- **内容切换**：板面切换 Provider 时，旧内容向上淡出，新内容从下淡入

所有动画基于 `pygame.time.get_ticks()` 实现，**不使用 time.sleep()**。

---

## 七、布局系统（layouts/）

布局控制「在屏幕上放几块板、怎么放」，与内容完全无关。

### 7.1 单板全屏（single.py）

一个 Provider 的内容撑满整个屏幕。

### 7.2 左右双板（dual.py）

屏幕左右各一块，分别绑定不同 Provider。  
参照图片2、4的效果，中间有 1px 分隔线。

### 7.3 轮播（carousel.py）

全屏，多个 Provider 按设定间隔（默认10秒）自动轮换，切换时有翻页动画。

---

## 八、调度器（data/fetcher.py）

负责在后台线程定期调用各 Provider 的 `fetch()`，更新缓存：

```python
class DataFetcher:
    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        self._executor = ThreadPoolExecutor(max_workers=2)  # Zero 2W 限制并发数
    
    def register(self, provider: BaseProvider): ...
    def start(self): ...   # 启动调度循环
    def force_refresh(self, provider_id: str): ...  # Web 端触发立即刷新
```

- 每个 Provider 按自己的 `default_refresh_interval` 独立调度
- 失败时保留上次缓存，不崩溃，记录日志
- `ThreadPoolExecutor(max_workers=2)` 限制并发，避免 Zero 2W 过载

---

## 九、Web 控制台（web/）

### 9.1 功能

手机/电脑访问 `http://<Pi的IP>:5000`：

- **布局控制**：选择当前布局（单板/双板/轮播），选择每个槽位绑定哪个 Provider
- **Provider 配置**：根据 `get_config_schema()` 自动渲染配置表单，修改后即时生效
- **自定义 Provider**：直接在 Web 端编辑 header/title/rows/ticker 等字段，实时预览
- **强制刷新**：手动触发某个 Provider 立即重新拉取数据
- **全局设置**：亮度、点阵颜色主题（琥珀/绿/白）、动画开关
- **实时预览**：所有修改通过 WebSocket 即时推送到 Pi 屏幕

### 9.2 API

```
GET  /                              # 控制台页面
GET  /api/state                     # 完整状态 JSON
GET  /api/providers                 # 已注册 Provider 列表及其 schema
POST /api/layout                    # { "layout": "dual", "slots": ["train", "weather"] }
POST /api/provider/<id>/config      # 更新 Provider 配置
POST /api/provider/<id>/refresh     # 强制刷新数据
POST /api/settings                  # { "brightness": 0.8, "color_theme": "amber" }
WS   /ws                            # 双向实时通信
```

### 9.3 界面设计

- 纯 HTML + CSS + Vanilla JS，**不依赖任何前端框架**
- 暗色主题，风格与点阵屏呼应（深色背景 + 琥珀色文字/边框）
- 响应式，手机竖屏优先
- WebSocket 断线自动重连

---

## 十、state.py — 共享状态

```python
# 需包含的字段：
{
    "current_layout": "single",          # 当前布局
    "layout_slots": ["train"],           # 各槽位绑定的 provider_id
    "providers_config": {                # 每个 Provider 的配置
        "train":    { "station_crs": "KGX", ... },
        "weather":  { "city": "London", ... },
        "custom":   { "title": "Hello", "rows": [...], ... },
    },
    "settings": {
        "brightness": 1.0,
        "color_theme": "amber",          # amber / green / white
        "animations_enabled": True,
    },
    "dirty": True,                       # 是否需要重绘
}
```

---

## 十一、性能约束（必须严格遵守）

Zero 2W：4核 1GHz ARM，512MB RAM

| 指标 | 目标 |
|------|------|
| 静止画面 CPU | < 3% |
| 动画运行 CPU | < 25% |
| 总内存占用 | < 80MB |
| 启动时间 | < 5秒 |
| 后台并发请求 | 最多 2 个 |

措施：
1. `dirty` 标志位：静止时降至 1fps
2. 点阵字符 Surface 缓存（`lru_cache` 或手动 dict）
3. Provider 数据拉取在线程池中，主线程只做渲染
4. Flask 单线程模式
5. 动画只在 `animations_enabled=True` 时运行

---

## 十二、启动参数

```bash
python3 main.py                  # 正常启动（kmsdrm，全屏）
python3 main.py --window         # 窗口模式（开发机调试，不需要 Pi）
python3 main.py --mock           # 强制所有 Provider 使用 mock 数据
python3 main.py --provider train # 直接指定启动后显示的 Provider
python3 main.py --layout dual    # 指定启动布局
```

---

## 十三、安装部署

### install.sh

```bash
sudo apt update
sudo apt install -y python3-pygame python3-pip libsdl2-dev
pip3 install flask flask-sock requests icalendar --break-system-packages

# /boot/firmware/config.txt 追加：
# dtoverlay=vc4-kms-v3d
# gpu_mem=64

sudo cp piboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable piboard
sudo systemctl start piboard
```

### piboard.service

```ini
[Unit]
Description=PiBoard Display System
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/piboard/main.py
WorkingDirectory=/home/pi/piboard
Restart=always
RestartSec=5
User=pi
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=dummy

[Install]
WantedBy=multi-user.target
```

---

## 十四、开发建议顺序

1. `board/content.py` — 定义 BoardContent / BoardRow 数据结构
2. `providers/base.py` + `providers/mock.py` — Provider 接口 + Mock 数据
3. `board/dot_font.py` — 点阵字体，用 `--window` 模式单独跑预览脚本验证视觉
4. `board/board_renderer.py` — 渲染单块板，输入 mock BoardContent，看效果
5. `board/animations.py` — 加入跑马灯和翻页
6. `layouts/single.py` — 最简布局
7. `state.py` + `data/fetcher.py` — 状态管理 + 后台调度
8. `renderer.py` + `main.py` — 整合主循环
9. `providers/train.py` + `providers/weather.py` + `providers/calendar_provider.py` — 真实 Provider
10. `web/server.py` + `index.html` — Web 控制台
11. `layouts/dual.py` + `layouts/carousel.py` — 更多布局
12. `install.sh` + `piboard.service` — 部署
13. 性能优化（Surface 缓存、dirty 帧控制）

---

## 十五、如何新增一个 Provider（开发者文档）

新增一种内容只需三步，**完全不修改任何现有代码**：

**第一步**：在 `providers/` 新建文件，继承 `BaseProvider`：

```python
# providers/my_provider.py
from providers.base import BaseProvider
from board.content import BoardContent, BoardRow

class MyProvider(BaseProvider):
    provider_id = "my_provider"
    display_name = "我的自定义内容"
    default_refresh_interval = 300

    def get_config_schema(self):
        return {
            "my_param": {"type": "string", "label": "参数", "default": "hello"}
        }

    def fetch(self) -> BoardContent:
        param = self.config.get("my_param", "hello")
        return BoardContent(
            header_left="12:00",
            header_right="My Board",
            title=param,
            rows=[
                BoardRow("Item 1", "Value 1"),
                BoardRow("Item 2", "Value 2"),
            ],
            footer="My Provider",
            status_text="OK",
            status_color="green",
        )
```

**第二步**：在 `config.py` 注册：

```python
from providers.my_provider import MyProvider

REGISTERED_PROVIDERS = [
    TrainProvider,
    WeatherProvider,
    CalendarProvider,
    CustomProvider,
    MyProvider,   # ← 加这一行
]
```

**第三步**：重启 PiBoard，Web 控制台自动出现新 Provider 选项。

---

## 附：点阵视觉还原要点

真实 LED 点阵屏特征，务必在 dot_font.py 中复现：

- 每个字符约 5×7 点阵，间距 1 点
- 圆点直径 = 间距 × 0.72
- 亮点：`#FF9500`，可选轻微发光（在圆心额外画一个更小更亮的圆 `#FFD080`）
- 暗点：`#1C1000`（**必须存在**，非纯黑，这是 LED 点阵感的关键）
- 整体背景：`#080808`（极深黑，OLED 直接熄灭像素）
- 字符之间间距 1~2 点，行间距 2~3 点
- 大标题（title）用 7×9 点阵，其余用 5×7
