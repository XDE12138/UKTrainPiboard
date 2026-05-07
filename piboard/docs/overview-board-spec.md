# Overview Board Spec

> **站牌为骨，复古科技为皮，统一语法，易扩展**
>
> Overview Board 是 PiBoard 的默认常驻主页面：一台 7 寸竖屏桌面信息终端的第一眼，而不是 train / weather / schedule 三页拼贴。

## 文档定位

本文档定义 Overview Board 的页面职责、信息架构、区域规则和推荐版式，用于指导后续内容建模、布局设计和实现拆分。它承接 `design-language.md` 的项目级视觉方向，但更具体地约束「默认主页面」应该呈现什么、如何组织、什么绝对不要做。

本文档不要求修改 renderer、bindings 或 providers；它是方案文档，不是代码实现说明。

---

## 1. Overview Board 的页面职责

Overview Board 的核心职责是：**把用户最需要立刻知道的信息，翻译成同一套英国铁路电显语言，并在一屏内建立清晰优先级。**

它不是信息总量最大的页面，而是默认常驻时最有判断价值的页面。用户应该在 1 秒内知道「现在是什么状态」，在 3 秒内知道「接下来该注意什么」。

### 必须回答的问题

1. **现在是什么时候 / 今天是什么日子**
   - 当前时间、日期、星期是全局锚点。
   - 时间不应喧宾夺主到压过下一步行动，但必须稳定可见。

2. **当前最重要的事是什么**
   - 可能是下一班列车、下一个日程、天气警告、系统异常或用户自定义提醒。
   - 同一时刻只能有一个 Hero / Anchor。

3. **接下来有哪些可行动信息**
   - 今日剩余列车、日程、天气变化、待办提醒。
   - 用站牌列表表达，不做 dashboard 卡片堆叠。

4. **整体状态是否正常**
   - 列车是否延误、天气是否需要注意、今日是否有紧迫日程、数据是否新鲜。
   - 状态必须能被一眼识别，但不能把页面染成告警屏。

5. **数据从哪里来、何时更新**
   - Footer 和 ticker 负责元信息、补充上下文和低优先级提醒。

### 页面边界

Overview Board 只做跨域摘要和优先级判断；详细信息仍由 Rail、Weather、Schedule、Custom 等页面承担。

允许显示：
- 下一班列车与后续 1-2 条服务
- 下一个日程与今日剩余摘要
- 当前天气与最近天气风险
- 系统 / 数据状态
- 用户自定义短提醒

不允许显示：
- 完整列车时刻表
- 多日天气预报全表
- 全天日程完整展开
- 每个 Provider 各占一块独立小页面

---

## 2. 7 寸竖屏信息架构

默认目标尺寸按项目当前竖屏基准：**600×1024 portrait**。Overview Board 应使用单板全屏结构，信息从上到下按「锚点 → 主判断 → 可行动列表 → 汇总 → 元信息」递进。

### 推荐纵向分区

| 区域 | 高度倾向 | 视觉权重 | 作用 |
|------|----------|----------|------|
| Top Bar | 7-9% | 低 | 时间、日期、地点、页面身份 |
| Hero / Anchor | 20-26% | 最高 | 当前唯一最重要信息 |
| Main List | 36-44% | 高 | 接下来最有行动价值的条目 |
| Summary Modules | 13-18% | 中 | 跨域状态摘要 |
| Footer / Ticker | 7-10% | 低 | 来源、更新时间、补充滚动信息 |

### 信息密度原则

- 竖屏不是把更多内容塞进去，而是让层级更稳定。
- 上半屏决定「现在要看什么」，下半屏提供「后面还有什么」。
- 所有模块共享同一套站牌语法：左侧标签 / 主体文字，右侧时间 / 状态 / 数值。
- 不做 2×2 卡片网格；Overview 的分区是纵向信息流，不是 dashboard tiles。
- 内容超出时优先轮换 Main List 页，而不是压缩字号。

### 推荐阅读路径

```
TOP BAR       现在 / 哪里 / Overview
HERO          当前唯一锚点
MAIN LIST     接下来 4-6 条
SUMMARY       今日跨域摘要
FOOTER        来源 / 更新 / ticker
```

---

## 3. Top Bar 规则

Top Bar 是页面的稳定锚点，模拟站牌顶栏，但在 Overview 中不承担主信息表达。

### 内容结构

左侧建议：
- 当前时间：`08:42`
- 或时间 + 星期：`08:42 MON`

右侧建议：
- 地点 / 设备名：`LONDON DESK`
- 页面身份：`OVERVIEW`
- 简短状态：`LIVE`

推荐格式：

```
08:42 MON                         OVERVIEW
27 APR 2026                    LONDON DESK
```

在空间紧张时可降级为单行：

```
08:42 MON 27 APR                 OVERVIEW
```

### 规则

1. Top Bar 永远使用小号或中号点阵，不使用 Hero 级字号。
2. Top Bar 文本优先全大写。
3. Top Bar 只显示稳定锚点，不显示天气图标、列车图标或 Provider logo。
4. 右侧标题不应频繁变化；可用 `OVERVIEW` 保持主页面身份。
5. 数据异常时可在右侧短暂显示 `STALE` / `OFFLINE`，但详细原因放入 footer 或 ticker。
6. Top Bar 下方可使用单像素 dim 分割线，不能使用亮色边框或现代 UI header 背景块。

---

## 4. Hero / Anchor 规则

Hero / Anchor 是 Overview Board 的第一视觉落点。它回答「此刻最值得注意的是什么」。

### Anchor 选择优先级

默认推荐优先级：

1. **告警类**：列车取消 / 严重延误、天气警告、数据离线、日程即将开始且时间紧迫
2. **下一步行动**：下一班列车、下一个会议、即将出门窗口
3. **当前状态**：当前天气、今日摘要、通勤状态
4. **安静模式**：无紧迫事件时显示时间 + 今日轻摘要

同一时刻只能出现一个 Anchor。Overview 不是把 train、weather、schedule 同时抢主视觉，而是从这些来源中选出最重要的一个。

### 内容结构

Hero 建议由四层组成：

| 层级 | 示例 | 说明 |
|------|------|------|
| Label | `NEXT DEPARTURE` | 短标签，说明信息类型 |
| Primary | `CAMBRIDGE` | 最大字号，当前锚点 |
| Secondary | `PLATFORM 4 · 08:57` | 补充行动信息 |
| Status | `ON TIME` | 右侧或下方状态，使用语义色 |

### 示例

```
NEXT DEPARTURE
CAMBRIDGE
PLATFORM 4 · 08:57              ON TIME
```

```
NEXT EVENT
DESIGN REVIEW
STARTS 09:30 · ZOOM             42 MIN
```

```
WEATHER WATCH
LIGHT RAIN FROM 11:00
TAKE UMBRELLA                   LOW RISK
```

### 规则

1. Hero 主文字只允许一行；过长时使用可读缩写或移到 Secondary。
2. Hero 不使用图标，不使用 emoji，不使用天气插画。
3. Hero 状态颜色只表达语义：正常 green、注意 orange、异常 red、中性 white。
4. Hero 区域可以有更大的留白，因为它是主判断区，不是表格区。
5. Anchor 来源可以跨 Provider，但视觉语法必须统一。
6. 无紧迫信息时，Hero 不应空白；使用「当前时间 + 今日简报」作为安静锚点。

---

## 5. Main List 规则

Main List 是 Overview 的主要密度区，展示接下来最有行动价值的 4-6 条。它不是各 Provider 的完整列表，而是经过优先级排序后的统一站牌列表。

### 行结构

推荐统一行格式：

```
TYPE / TIME        PRIMARY TEXT                 STATUS
DETAIL             SECONDARY TEXT
```

在窄宽度中可简化为单行：

```
08:57 TRAIN        CAMBRIDGE                    ON TIME
09:30 CAL          DESIGN REVIEW                42 MIN
11:00 WEATHER      LIGHT RAIN                   UMBRELLA
18:10 TRAIN        KING'S CROSS                 CHECK
```

### 类型标签

推荐使用短英文标签，保持点阵屏可读：

| 类型 | 标签 |
|------|------|
| 列车 | `TRAIN` |
| 日程 | `CAL` |
| 天气 | `WX` 或 `WEATHER` |
| 待办 | `TODO` |
| 系统 | `SYS` |
| 自定义提醒 | `NOTE` |

### 排序规则

1. 时间敏感信息优先：未来 0-3 小时内的信息排在前面。
2. 告警信息可越级上移，但不应让整个列表被告警淹没。
3. 已过去条目默认不进入 Overview Main List；确有必要时使用 dim 色并自动退场。
4. 同类型信息连续过多时压缩为摘要，例如 `3 MORE TRAINS BEFORE NOON`。
5. Main List 内只允许一个当前高亮行，通常是 Hero 对应的后续行或下一条行动。

### 内容长度

- Primary Text 建议不超过 18-22 个英文字符。
- Status 建议不超过 8-10 个英文字符。
- Detail 可进入下一行或 ticker，不强行塞入主行。
- 过长地点名优先使用铁路常见缩写，如 `KING'S CROSS`、`ST PANCRAS`、`LIVERPOOL ST`。

---

## 6. Summary Modules 规则

Summary Modules 用于给出跨域状态摘要，帮助用户在不进入详情页的情况下理解「今天整体怎么样」。

它们不是 dashboard cards，而是站牌底部的状态小窗。视觉上应像仪器状态条或站牌附加行，而不是圆角卡片。

### 推荐模块

| 模块 | 示例 | 说明 |
|------|------|------|
| Travel | `TRAVEL  2 DUE · 0 DELAY` | 列车/通勤概况 |
| Weather | `WX  12C · RAIN 11:00` | 当前天气与短期风险 |
| Calendar | `CAL  3 LEFT · NEXT 09:30` | 今日日程摘要 |
| System | `DATA  LIVE · 2 MIN AGO` | 数据新鲜度 |

### 布局规则

推荐使用两行两列的文字状态区，但不要做卡片：

```
TRAVEL  2 DUE      WX   12C RAIN 11
CAL     3 LEFT     DATA LIVE 2M
```

或单列压缩：

```
TRAVEL 2 DUE · WX 12C · CAL 3 LEFT · DATA LIVE
```

### 规则

1. Summary Modules 使用 dim / amber 为主，只有异常数值使用 green / orange / red。
2. 模块数量建议 3-4 个，不超过 4 个。
3. 每个模块只表达一个判断，不展开详情。
4. 模块命名必须稳定，避免每次刷新改变布局。
5. Summary Modules 与 Main List 之间可以用 dim 单像素线分隔。
6. 如果某类数据不可用，显示 `WX OFFLINE` / `CAL EMPTY`，不要隐藏导致布局跳动。

---

## 7. Footer / Ticker 规则

Footer / Ticker 是最低优先级区域，但对桌面常驻设备很重要：它告诉用户数据是否可信，并承接不适合占用主区的补充信息。

### Footer 内容

左侧建议：
- 数据来源：`NATIONAL RAIL · OPENWEATHER · ICAL`
- 更新时间：`UPDATED 08:40`
- 模式：`MOCK DATA` / `LIVE DATA`

右侧建议：
- 全局状态：`ALL OK`
- 注意状态：`CHECK`
- 异常状态：`STALE`

示例：

```
LIVE DATA · UPDATED 08:40          ALL OK
```

### Ticker 内容

Ticker 只放次要补充，不放必须立即看到的信息。

适合：
- `ENGINEERING WORK BETWEEN FINSBURY PARK AND STEVENAGE AFTER 23:00`
- `MEETING ROOM CHANGED TO 4F-12`
- `RAIN EXPECTED 11:00-13:00 · WIND 18 KM/H`
- `CALENDAR SYNCED FROM WORK ICAL · NEXT REFRESH 08:45`

不适合：
- 下一班列车时间
- 即将开始的会议
- 严重延误
- 数据离线主告警

### 规则

1. Footer 固定可见，Ticker 可选。
2. Ticker 从右向左匀速滚动，不做炫技动画。
3. Ticker 文字使用 dim 或 amber；除非是告警摘要，否则不使用 red。
4. 空 ticker 时不保留大面积空白，可将 footer 区域自然压缩。
5. Footer 是可信度信息，不是装饰标语。

---

## 8. 推荐版式 Wireframe

推荐版式：**Anchor + Unified Feed + Compact Summary**。

它保持铁路站牌的纵向阅读节奏：顶部锚定身份，中部给出唯一主判断，随后用统一列表承接跨域信息，底部显示摘要和来源。

```
┌────────────────────────────────────────┐
│ 08:42 MON 27 APR            OVERVIEW   │
│ LONDON DESK                    LIVE    │
├────────────────────────────────────────┤
│ NEXT DEPARTURE                         │
│ CAMBRIDGE                              │
│ PLATFORM 4 · 08:57            ON TIME  │
├────────────────────────────────────────┤
│ 08:57 TRAIN  CAMBRIDGE        ON TIME  │
│ 09:30 CAL    DESIGN REVIEW    42 MIN   │
│ 11:00 WX     LIGHT RAIN       UMBRELLA │
│ 12:15 CAL    LUNCH WITH MAYA  TODAY    │
│ 18:10 TRAIN  KING'S CROSS     CHECK    │
├────────────────────────────────────────┤
│ TRAVEL 2 DUE      WX   12C RAIN 11     │
│ CAL    3 LEFT     DATA LIVE 2M         │
├────────────────────────────────────────┤
│ LIVE DATA · UPDATED 08:40      ALL OK  │
│ >>> RAIN EXPECTED 11:00-13:00 · WIND   │
└────────────────────────────────────────┘
```

### 推荐理由

- 它不是三页拼贴，而是把不同来源统一进同一个站牌时序。
- Hero 保证默认主页面有明确主判断。
- Main List 让 train / weather / schedule 以同一语法共存。
- Summary Modules 提供全局健康状态，适合常驻设备。
- Footer / Ticker 保留铁路电显识别度，也能承接低优先级上下文。

---

## 9. 候选布局

### Candidate A：Anchor + Unified Feed + Compact Summary（推荐）

结构：

```
TOP BAR
HERO / ANCHOR
MAIN LIST
SUMMARY MODULES
FOOTER / TICKER
```

适合：
- 默认常驻主页面
- 信息来源较多但每类只需要摘要
- 用户最关心「下一步」和「今天状态」

优点：
- 第一眼有明确重点。
- 跨域信息被统一排序，不像页面拼贴。
- 扩展新 Provider 时，只要能产出 `TYPE / PRIMARY / STATUS / TIME`，即可进入统一列表。
- 与现有设计语言的 header、rows、footer、ticker 完全一致。

风险：
- 需要定义 Anchor 选择逻辑，否则不同信息会争抢主位。
- 需要控制 Main List 行数，避免变成完整日程表。

结论：**推荐作为 Overview Board 第一版方案。**

### Candidate B：Time Anchor + Three Service Strips

结构：

```
TOP BAR
LARGE TIME / DATE
TRAVEL STRIP
WEATHER STRIP
CALENDAR STRIP
FOOTER / TICKER
```

示意：

```
┌────────────────────────────────────────┐
│ 08:42 MON 27 APR            OVERVIEW   │
├────────────────────────────────────────┤
│ 08:42                                  │
│ MONDAY 27 APRIL                        │
├────────────────────────────────────────┤
│ TRAIN  08:57 CAMBRIDGE        ON TIME  │
│ WX     12C LIGHT RAIN FROM 11          │
│ CAL    09:30 DESIGN REVIEW     42 MIN  │
├────────────────────────────────────────┤
│ LIVE DATA · UPDATED 08:40      ALL OK  │
└────────────────────────────────────────┘
```

适合：
- 用户把设备主要当桌面时钟
- 数据量很少
- 无明显优先级判断需求

优点：
- 极稳定、安静，常驻观感好。
- 时间可读性最高。
- 实现心智简单。

风险：
- 容易退化成普通「时钟 + 三条摘要」。
- train / weather / schedule 仍然像三块独立内容条，统一性弱于 Candidate A。
- 当出现延误或紧急日程时，主视觉不够灵活。

结论：可作为低信息密度模式或夜间模式，不推荐作为默认 Overview。

### Candidate C：Incident First Board

结构：

```
TOP BAR
STATUS HERO
INCIDENT / ACTION LIST
NORMAL SUMMARY
FOOTER / TICKER
```

适合：
- 通勤高峰
- 多数据源可能出现异常
- 用户希望优先处理风险

优点：
- 异常状态非常清楚。
- 适合列车延误、天气警告、数据离线时临时接管页面。

风险：
- 如果长期作为默认页面，会显得紧张。
- 过度强调状态颜色，容易偏离复古站牌的克制气质。
- 常态下信息利用率不如 Candidate A。

结论：适合作为 Candidate A 的异常状态变体，而不是独立默认布局。

---

## 10. 示例内容

以下示例使用真实语义内容，不使用 lorem ipsum。实际内容应按数据源动态替换。

### 正常通勤早晨

```
08:42 MON 27 APR                 OVERVIEW
LONDON DESK                         LIVE

NEXT DEPARTURE
CAMBRIDGE
PLATFORM 4 · 08:57               ON TIME

08:57 TRAIN  CAMBRIDGE           ON TIME
09:30 CAL    DESIGN REVIEW       42 MIN
11:00 WX     LIGHT RAIN          UMBRELLA
12:15 CAL    LUNCH WITH MAYA     TODAY
18:10 TRAIN  KING'S CROSS        CHECK

TRAVEL 2 DUE      WX   12C RAIN 11
CAL    3 LEFT     DATA LIVE 2M

LIVE DATA · UPDATED 08:40        ALL OK
>>> RAIN EXPECTED 11:00-13:00 · WIND 18 KM/H
```

### 无通勤的工作日

```
10:18 TUE 28 APR                 OVERVIEW
HOME OFFICE                         LIVE

NEXT EVENT
PRODUCT SYNC
STARTS 10:30 · ZOOM              12 MIN

10:30 CAL    PRODUCT SYNC        12 MIN
11:45 TODO   SEND BOARD NOTES    TODAY
13:00 WX     SUNNY INTERVALS     16C
15:00 CAL    FOCUS BLOCK         2 HR
17:30 NOTE   CALL FAMILY         EVENING

TRAVEL QUIET     WX   16C CLEAR
CAL    4 LEFT     DATA LIVE 1M

ICAL · OPENWEATHER · UPDATED 10:17    ALL OK
>>> NEXT FREE WINDOW 11:00-11:45 · NO TRAIN ALERTS
```

### 异常状态

```
18:04 FRI 01 MAY                 OVERVIEW
KING'S CROSS                        CHECK

SERVICE ALERT
CAMBRIDGE TRAIN DELAYED
EXPECTED 18:32 · PLATFORM 7      DELAYED

18:10 TRAIN  CAMBRIDGE           DELAY
18:20 CAL    DINNER BOOKING      TIGHT
19:00 WX     HEAVY RAIN          TAKE COAT
19:15 TRAIN  ELY                 ON TIME

TRAVEL 1 DELAY    WX   RAIN 19
CAL    1 TIGHT     DATA LIVE 1M

NATIONAL RAIL · UPDATED 18:03    CHECK
>>> DELAYS REPORTED BETWEEN ROYSTON AND CAMBRIDGE
```

---

## 11. 明确禁止

Overview Board 必须避免以下方向：

### 不要做三页拼贴

禁止把 Train、Weather、Schedule 三个页面缩小后堆在同一屏。  
原因：这会保留三个页面各自的视觉中心，Overview 失去统一判断，只剩信息挤压。

不要这样：

```
┌───────────────┐
│ TRAIN PAGE    │
├───────────────┤
│ WEATHER PAGE  │
├───────────────┤
│ SCHEDULE PAGE │
└───────────────┘
```

应该这样：

```
ONE ANCHOR
ONE UNIFIED LIST
ONE SUMMARY LANGUAGE
```

### 不要做普通 dashboard

禁止使用：
- 圆角卡片
- KPI tiles
- 图标网格
- 彩色模块背景
- Material / Fluent 式阴影
- 「天气卡」「日历卡」「交通卡」并列

原因：PiBoard 的核心不是现代 Web dashboard，而是铁路电显语言下的个人信息终端。

### 不要过度科幻

禁止使用：
- 霓虹渐变
- 扫描线装饰
- 粒子背景
- 复杂 HUD 框线
- 大面积蓝紫色冷光
- 动态雷达 / 全息面板语汇

原因：项目方向是复古科技，不是赛博朋克。未来感只作为 10% 的克制调味，用于单像素线、状态色和干净节奏。

### 不要牺牲点阵语法

禁止为了展示更多内容而：
- 缩小到不可读字号
- 混入 TTF 字体
- 使用 emoji 或 SVG icon
- 删除暗点背景
- 将 status 变成彩色装饰

原因：Overview 是主页面，更应该守住项目识别度。

---

## 推荐方案总结

推荐采用 **Candidate A：Anchor + Unified Feed + Compact Summary**。

它最适合当前项目的原因是：

1. **符合「站牌为骨」**：保留 Top Bar、主信息、行列式列表、Footer / Ticker 的铁路电显骨架。
2. **符合「复古科技为皮」**：用点阵、暗底、琥珀色、dim 分割线和状态文字营造电子仪器感，而不是现代卡片 UI。
3. **统一语法**：train、weather、schedule、todo、system 都被翻译为同一种 `TYPE / TIME / TEXT / STATUS` 语言。
4. **易扩展**：未来新增 Provider 不需要新增一个 mini page，只需要提供可排序的摘要项、状态和可选 ticker 文案。
5. **适合 7 寸竖屏常驻**：竖向阅读路径清楚，信息密度足够，但不会让小屏变成拥挤 dashboard。
6. **默认页有判断力**：它能在正常、安静、紧急三种状态之间切换主锚点，而不是静态罗列信息。

Overview Board 的设计目标不是「什么都有一点」，而是「最重要的东西先出现，其余信息服从同一套站牌秩序」。
