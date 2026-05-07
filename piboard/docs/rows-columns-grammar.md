# Rows / Columns Grammar

> BoardRow is a two-column railway-display sentence.
> Keep the renderer simple: one left field, one right field, optional colour, optional highlight, optional indent.

## Purpose

This document defines a shared grammar for `BoardContent.rows` across Overview, Rail, Weather, Schedule, and Todo/Info boards.

It does not introduce a new row schema, block system, grid layout, renderer behaviour, font rule, or layout rule. Every example below is expressible with the existing `BoardRow` fields:

| Field | Role |
|------|------|
| `left` | Main scan target: object, label, section name, or compact action text |
| `right` | Aligned value: time, count, duration, status, temperature, or short outcome |
| `left_color` | Semantic weight of the left column |
| `right_color` | Semantic weight of the right column |
| `highlight` | Single current/next row emphasis |
| `indent` | Visual child relationship under the previous row |

## Column Grammar

### `left` Field Responsibilities

`left` carries the row identity. It should answer: "what is this row about?"

Use `left` for:

- The primary object: station name, event name, action, weather metric, todo item.
- The group label: `TODAY`, `TOMORROW`, `FORECAST`, `NEXT ACTIONS`.
- The meta label: `OPERATOR`, `PLATFORM`, `UPDATED`, `SOURCE`.
- A compact compound phrase when the row needs one scan unit, such as `09:00 CAL DESIGN REVIEW`.

Rules:

- Prefer uppercase labels for structural rows.
- For primary data rows, preserve useful real names, but avoid long prose.
- Keep the strongest noun/action in `left`; do not bury it in `right`.
- Do not use punctuation as layout: avoid `LABEL: VALUE`, arrows, pipes, or faux columns inside `left`.
- If a row is a child/detail of the row above, use `indent`, not manual spaces.

### Overview Unified Feed Exception

Overview is the only board allowed to use a fixed-width short prefix inside `left`.

Allowed Overview feed shape:

```
HH:MM KIND TEXT
```

Examples:

- `09:30 CAL DESIGN REVIEW`
- `11:45 WX LIGHT RAIN`
- `13:15 RAIL EDINBURGH`
- `18:30 TODO REVIEW PR`

Rules for this exception:

- It is only for the Overview unified feed, where multiple domains share one chronological list.
- `KIND` must be a short stable label such as `CAL`, `WX`, `RAIL`, `TODO`, or `NOTE`.
- The prefix may use fixed-width padding internally so timestamps and kind labels scan consistently.
- The exception must not expand into arbitrary hand-built grids, extra pseudo-columns, or nested tables.
- Detail Boards such as Rail, Weather, Schedule, and Todo/Info must keep the normal two-column grammar: `left=object/label`, `right=value/status`.

This exception exists because Overview is a cross-domain dispatch feed, not a normal detail board. The compact prefix lets rows from different providers share one railway timetable rhythm while still keeping `right` reserved for the immediate status or value.

### `right` Field Responsibilities

`right` carries the aligned value. It should answer: "what is the key value or state?"

Use `right` for:

- Time: `12:35`, `NEXT 09:00` only when used as short status.
- Duration: `30MIN`, `1HR`.
- Count: `3 EVENTS`, `6 ITEMS`, `3 DAYS`.
- Status: `ON TIME`, `LIVE`, `DELAYED`, `OPEN`.
- Measurement: `14C`, `72%`, `SW 18KM/H`, `12C / 8C`.

Rules:

- Keep `right` short; it is right-aligned and should read as one value.
- Do not put sentences in `right`.
- Do not duplicate the title/subtitle unless the row is a deliberate status/meta row.
- Leave `right` empty for spacer rows and for single-column child notes.

## Row Types

The row type is a convention produced by field choices, colours, `highlight`, and `indent`. There is no `row_type` field.

| Type | Purpose | Field Pattern | Colour Pattern | Highlight | Indent |
|------|---------|---------------|----------------|-----------|--------|
| `primary` | Main actionable/detail item | `left=object/action`, `right=time/status/value` | `amber` left, `amber` or semantic right | At most one per board/page | Usually `0` |
| `secondary` | Detail under a primary row | `left=detail`, optional `right` | `dim` both | Never | `12` preferred |
| `group label` | Section heading inside rows | `left=SECTION`, `right=count/status` | `dim` both, or semantic right for live/ok | Never | `0` |
| `meta` | Source/service/update facts | `left=LABEL`, `right=value` | `dim` both, semantic right only for state | Never | `0` |
| `summary` | Compact digest of a domain | `left=LABEL VALUE`, `right=short state` | label/value may be `dim` or `amber`; right may be semantic | Rare; normally never | `0` |
| `status` | Inline operational state | `left=SERVICE/STATUS`, `right=state` | `dim` left, semantic right | Never | `0` |
| `spacer` | Breathing room between groups | `left=""`, `right=""` | ignored | Never | `0` |

## Highlight Rules

Use `highlight=True` only for the single row the user should act on first.

Allowed:

- Overview: the next action.
- Rail: the next calling point or the currently selected departure.
- Weather: the current `NOW` row.
- Schedule: the next event.
- Todo/Info: the top priority or next due item.

Rules:

- Use at most one highlighted row in a single board page.
- Do not highlight group labels, meta rows, summary rows, spacer rows, or secondary detail rows.
- Highlight should not be used to compensate for weak title content; the title remains the hero.
- If there is no clear current/next item, use no highlight.

## Dim Rules

`dim` means "context, structure, past, future, source, or lower priority." It is not decoration.

Use `dim` for:

- Group labels: `TODAY`, `FORECAST`, `THIS WEEK`.
- Meta rows: `OPERATOR`, `UPDATED`, `SOURCE`.
- Secondary detail rows under Overview actions.
- Non-today Schedule events.
- Forecast rows beyond the immediate `NEXT`.
- Empty or unavailable states: `NO EVENTS`, `NO FORECAST`.

Do not use `dim` for:

- The primary row unless the item is explicitly inactive, future context, or unavailable.
- A value that needs urgent attention.
- The only useful data in the board.

## Indent Rules

`indent` is for hierarchy, not spacing.

Use `indent=12` for secondary rows that explain the primary row immediately above them.

Good uses:

- Overview action detail under a highlighted action.
- Todo note under a todo item.
- Optional service note under a Rail primary row if it belongs to that row.

Avoid:

- Indenting group labels.
- Indenting meta rows.
- Using spaces inside `left` to fake indentation.
- Multiple indent depths; keep one child depth unless the renderer gains a real hierarchy system.

## Colour Rules

The row grammar follows the project colour language:

| Colour | Row Use |
|--------|---------|
| `amber` | Normal primary content and key values |
| `dim` | Group labels, metadata, secondary details, future/past context |
| `green` | OK/live/on-time/complete state |
| `orange` | Attention, expected time, due soon, degraded state |
| `red` | Delayed, cancelled, failed, overdue |
| `white` | Neutral emphasis, especially current weather condition |

Rules:

- `amber` should remain the dominant row colour.
- Semantic colours belong mostly in `right_color`, not across the whole row.
- Use `left_color="dim"` with semantic `right_color` for status rows.
- Avoid using more than two auxiliary colours in the rows area.
- Do not assign a unique colour per provider or category.

## Overview Example Rows

| Type | left | right | Colour | Highlight | Indent |
|------|------|-------|--------|-----------|--------|
| group label | `NEXT ACTIONS` | `6 ITEMS` | dim / dim | no | 0 |
| primary | `09:30 CAL DESIGN REVIEW` | `42 MIN` | amber / white | yes | 0 |
| secondary | `ZOOM - PREP NOTES` | `` | dim / dim | no | 12 |
| primary | `11:45 WX LIGHT RAIN` | `UMBRELLA` | amber / amber | no | 0 |
| primary | `13:15 RAIL EDINBURGH` | `ON TIME` | amber / green | no | 0 |
| group label | `BOARD SUMMARY` | `LIVE` | dim / green | no | 0 |
| summary | `WEATHER 14C CLOUDY` | `RAIN 12` | dim / amber | no | 0 |
| summary | `RAIL 1 DUE` | `0 DELAY` | dim / green | no | 0 |

Notes:

- Overview may pack time, kind, and action into `left` because the whole row is a compact cross-domain feed.
- This is the only approved fixed-prefix exception: `HH:MM KIND TEXT`.
- Child detail rows use `indent=12` and `dim`.

## Rail Example Rows

| Type | left | right | Colour | Highlight | Indent |
|------|------|-------|--------|-----------|--------|
| primary | `NEWCASTLE` | `12:35` | amber / amber | yes | 0 |
| primary | `MORPETH` | `12:59` | amber / amber | no | 0 |
| primary | `ALNMOUTH` | `13:07` | amber / amber | no | 0 |
| primary | `& EDINBURGH` | `14:15` | amber / amber | no | 0 |
| spacer | `` | `` | ignored | no | 0 |
| meta | `OPERATOR` | `LNER AZUMA` | dim / dim | no | 0 |
| meta | `PLATFORM` | `9` | dim / dim | no | 0 |
| meta | `FORMED OF` | `8 COACHES` | dim / dim | no | 0 |
| status | `SERVICE` | `ON TIME` | dim / green | no | 0 |
| meta | `UPDATED` | `14:31` | dim / dim | no | 0 |

Notes:

- Rail keeps the strongest railway flavour by making calling-at rows primary.
- Service meta appears only when needed to fill a sparse calling-at board or clarify service state.

## Weather Example Rows

| Type | left | right | Colour | Highlight | Indent |
|------|------|-------|--------|-----------|--------|
| primary | `NOW` | `PARTLY CLOUDY` | amber / white | yes | 0 |
| primary | `TEMP` | `14C` | amber / amber | no | 0 |
| primary | `FEELS` | `11C` | amber / amber | no | 0 |
| primary | `WIND` | `SW 18KM/H` | amber / amber | no | 0 |
| spacer | `` | `` | ignored | no | 0 |
| primary | `NEXT` | `TOMORROW 12C/8C` | amber / amber | no | 0 |
| primary | `HUMIDITY` | `72%` | amber / amber | no | 0 |
| primary | `VISIBILITY` | `10KM` | amber / amber | no | 0 |
| group label | `FORECAST` | `3 DAYS` | dim / dim | no | 0 |
| meta | `WED` | `15C / 9C` | dim / dim | no | 0 |

Notes:

- Weather uses words and values, not icon language.
- `NOW`, `NEXT`, and `FORECAST` are the stable structure.

## Schedule Example Rows

| Type | left | right | Colour | Highlight | Indent |
|------|------|-------|--------|-----------|--------|
| group label | `TODAY` | `3 EVENTS` | dim / dim | no | 0 |
| primary | `09:00 TEAM STANDUP` | `30MIN` | amber / amber | yes | 0 |
| primary | `14:00 DENTIST` | `1HR` | amber / amber | no | 0 |
| primary | `19:30 DINNER - MARKS` | `2HR` | amber / amber | no | 0 |
| spacer | `` | `` | ignored | no | 0 |
| group label | `TOMORROW` | `2 EVENTS` | dim / dim | no | 0 |
| primary | `10:00 CODE REVIEW` | `1HR` | dim / dim | no | 0 |
| spacer | `` | `` | ignored | no | 0 |
| group label | `THIS WEEK` | `2 EVENTS` | dim / dim | no | 0 |
| primary | `THU 18:00 PROJECT WRAP` | `1HR` | dim / dim | no | 0 |

Notes:

- Today is active content; tomorrow and this week are context and therefore `dim`.
- The next event is the only highlighted row.

## Todo / Info Guidance

Todo and custom Info boards should use the same types rather than inventing rich text.

Recommended pattern:

| Type | left | right | Colour | Highlight | Indent |
|------|------|-------|--------|-----------|--------|
| group label | `OPEN ITEMS` | `4 DUE` | dim / orange | no | 0 |
| primary | `REVIEW PR` | `TODAY` | amber / orange | yes | 0 |
| secondary | `WAITING ON CI` | `` | dim / dim | no | 12 |
| primary | `PAY COUNCIL TAX` | `FRI` | amber / amber | no | 0 |
| status | `SYNC` | `LIVE` | dim / green | no | 0 |

## Forbidden Formats

Do not use:

- More than two visible columns inside `left` or `right`.
- Manual spacing to fake a grid, except the defined Overview `HH:MM KIND TEXT` feed prefix.
- `LABEL: VALUE` when it should be `left=LABEL`, `right=VALUE`.
- Emoji, icons, arrows, bullets, box drawing, or Unicode pictograms.
- Sentences in `right`.
- Multiple highlighted rows in one board page.
- Group labels highlighted as if they were content.
- Provider-specific row grammars that cannot be reused by another board.
- Weather icon-style rows such as `☁ CLOUDY`.
- Schedule hero filler repeated in rows, such as a `SCHEDULE` row.
- Meta rows in `amber` unless the meta value is the primary data.
- Red/orange/green as category colours; they are status colours only.
- Deep nested hierarchy or multiple indent levels.
- A custom grid/block system encoded into strings.

## Binding Implementation Guidance

Bindings should first decide the row type, then fill existing `BoardRow` fields according to this grammar:

1. Pick the board hero in `title` and `subtitle`.
2. Build rows as a single ordered feed of two-column sentences.
3. Use group labels to create sections.
4. Use exactly one highlight for the current/next row when one exists.
5. Put operational states in `right_color`, usually with a `dim` left label.
6. Use `dim` for context and future/past information.
7. Use `indent=12` only for child details under the row above.

This keeps future bindings compatible with the existing renderer while making every provider read like part of the same display system.
