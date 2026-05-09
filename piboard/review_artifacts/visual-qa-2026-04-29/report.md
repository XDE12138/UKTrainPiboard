# Visual QA Report - 2026-04-29

本报告基于同目录下现有 600x1024 竖屏截图进行视觉审查。它是 QA 输出，记录截图中观察到的问题和建议，不声明推荐修复已经完成。

## Screenshot Files

- Overview: `<repo>/piboard/review_artifacts/visual-qa-2026-04-29/overview-portrait-600x1024.png`
- Rail: `<repo>/piboard/review_artifacts/visual-qa-2026-04-29/rail-portrait-600x1024.png`
- Weather: `<repo>/piboard/review_artifacts/visual-qa-2026-04-29/weather-portrait-600x1024.png`
- Schedule: `<repo>/piboard/review_artifacts/visual-qa-2026-04-29/schedule-portrait-600x1024.png`

## Overall Judgment

整体方向符合「站牌为骨，复古科技为皮」：点阵字体、暗底、顶部 header、两栏 rows、footer/status/ticker 都保留了 railway display language。当前页面没有退化成普通 dashboard，也没有出现卡片化、图标化、渐变背景或多字体混用。

Overview 最接近完整桌面终端主界面，有明确 hero、统一 feed、summary 和底部状态。Rail、Weather、Schedule 三个 Detail Boards 基本属于同一设计系统，但视觉 QA 中可以看到 Detail Boards 下半屏信息密度偏低，部分 footer/ticker/status 重复主信息，导致底部比预期更抢眼。

## Findings by Severity

### 1. Medium-High: Detail Boards have too much lower-screen empty space

- Pages: Rail, Weather, Schedule
- Areas:
  - Rail: rows 后到 carriage/footer 之前的空间偏空。
  - Weather: forecast rows 后到 footer 之前有较大空白。
  - Schedule: `THIS WEEK` rows 后到 footer 之前有较大空白。
- Impact: 7 寸竖屏的信息密度没有被充分利用，Detail Board 看起来像内容未填满，而不是完整站牌。
- Recommended fix: 优先在 binding/mock 内容层补足有价值 rows，不改 renderer。Rail 可补更多 calling-at 或 service meta；Weather 可补 rain window、pressure、next change、updated；Schedule 可补 later today、free window、next week count。
- Priority: Must fix before visual finalization.

### 2. Medium: Footer/status/ticker repeats primary information on some pages

- Pages: Weather, Schedule
- Areas:
  - Weather: status `PARTLY CLOUDY` 与 title/subtitle 重复。
  - Schedule: status `NEXT 09:00` 与 hero 重复。
- Impact: Hero 已经表达主判断，底部重复亮色状态会制造第二视觉焦点。
- Recommended fix: 内容层调整。Weather status 可改为更短健康判断，如 `OK`、`DRY`、`CHECK`；Schedule 可保留 status 但减少 ticker 或避免完全重复 hero。
- Priority: Must fix before visual finalization.

### 3. Medium: Rail footer/carriage block is visually heavier than sparse service rows

- Page: Rail
- Area: carriage diagram、operator、ticker、status 区域。
- Impact: 铁路味很强，但 rows 内容不足时，底部结构比服务内容更显眼。
- Recommended fix: 先增加主 rows 的服务信息密度，如更多 calling-at 或 service rows。只有内容层补足后仍不平衡，才考虑轻量 renderer 调整。
- Priority: Must fix content layer; renderer change can wait.

### 4. Low-Medium: Overview bottom area is slightly crowded

- Page: Overview
- Area: ticker/footer/status 底部区域。
- Impact: Overview 主体结构良好，但底部三层文字靠得较紧，`ALL OK` 状态贴近底边。
- Recommended fix: 先缩短 ticker/footer 文案，避免滚动内容过长。不建议优先改 renderer。
- Priority: Can defer.

### 5. Low: Dim future/context rows may be weak at viewing distance

- Pages: Weather, Schedule
- Areas:
  - Weather: forecast rows.
  - Schedule: `TOMORROW` and `THIS WEEK` rows.
- Impact: 语义正确，但远距离可读性可能下降。
- Recommended fix: 保持 `dim` 语义；如果硬件实测太暗，再局部调整内容数量或 right_color。不要先改全局调色盘。
- Priority: Can defer.

## Basic Visual Checks Passed

- Overview passed basic visual structure check: one hero, unified feed, summary rows, footer/status/ticker present.
- Rail passed railway display identity check: header/platform, destination title, calling-at rows, carriage/status/ticker language are present.
- Weather passed non-icon weather expression check: uses text and values, no weather icons or dashboard cards.
- Schedule passed station-board schedule language check: informative hero, grouped rows, today/future distinction.
- All pages passed basic renderer safety check: no visible text overlap, no obvious truncation, no font fallback, no card/grid UI, no emoji/icons.

## Must Fix vs Can Defer

Must fix:

- Detail Board lower-screen empty space.
- Repeated bottom status/ticker stealing focus from Weather and Schedule hero.
- Rail sparse rows versus visually heavy footer/carriage block, starting with content-layer density.

Can defer:

- Overview bottom crowding, unless it becomes worse with live data.
- Dim future/context row readability, pending hardware viewing-distance check.

