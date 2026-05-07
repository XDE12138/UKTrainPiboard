# PiBoard 代码审计报告

**日期**：2026-04-15（v2，2026-04-15 修订）
**审计范围**：只读，0 文件改动
**覆盖文件**：main.py / config.py / state.py / renderer.py / board/全部 / providers/全部 / layouts/全部 / data/fetcher.py / web/server.py / web/templates/index.html / web/static/app.js / README.md / piboard_prompt_v2.md

> **修订说明**：本版相对 v1 有三处实质修订，已用 `【修订】` 标注：
> 1. layouts 保留判断从"直接保留"改为"带已知缺陷迁移"
> 2. `--mock` 修复方案从单行补丁改为跨 Provider 统一策略
> 3. 新增"与远程控制直接相关的关键断链"小节

---

## 一、总体评价

代码整体结构干净，核心渲染层 (`board/`) 与内容层 (`providers/`) 的解耦方向是对的。但存在几个**架构层级缺失**、**实现与文档不符**以及**远程控制链路断裂**的问题，需要在向 host/app/source/binding 架构迁移前明确处理。

---

## 二、可保留 vs 必须重构

| 模块 | 状态 | 说明 |
|---|---|---|
| `board/content.py` | **直接保留** | BoardContent / BoardRow 是清晰的数据契约，不需要改 |
| `board/dot_font.py` | **直接保留** | 点阵字体渲染引擎，逻辑完整，可迁移到 apps/uk_station/ |
| `board/board_renderer.py` | **直接保留** | 与 content 解耦良好，迁移到 apps/uk_station/ |
| `board/animations.py` | **直接保留** | 三个动画类本身独立、干净 |
| `layouts/single.py` | **带缺陷迁移** | 主体结构和渲染逻辑可用；`_is_animating()` 对 Single 可正确识别 `_anim`，无问题 |
| `layouts/dual.py` | **【修订】带已知缺陷迁移** | 持有 `_anims`（列表），而 `renderer._is_animating()` 只查找 `_anim`（单数），导致 Dual 布局的所有动画无法触发高帧率，ticker/翻页实际跑在 1fps；迁移前须同步修复 |
| `layouts/carousel.py` | **【修订】带已知缺陷迁移** | 持有独立的 `self._transition`，但 `_is_animating()` 只检查 `layout._anim.transition`，不检查独立 `_transition`；切换过渡动画期间 dirty 不保持为 True，过渡效果实际跑在 1fps；迁移前须同步修复 |
| `layouts/base.py` | **保留并扩展** | 需要感知"属于哪个 App" |
| `data/fetcher.py` | **直接保留** | DataFetcher 调度器完整，可复用 |
| `state.py` | **保留并扩展** | 状态模型需加入 `current_app` 字段；持久化时机需改（见第三节） |
| `providers/base.py` | **必须拆分** | 目前 BaseProvider = 数据拉取 + 内容格式化，这两件事要分离 |
| `providers/train.py` 等 | **必须拆分** | 每个 Provider 同时做 HTTP fetch 和 BoardContent 构造，binding 层缺失 |
| `config.py` | **保留** | 颜色主题、分辨率常量无问题 |
| `renderer.py` | **需要重构** | 没有 App 概念，切换 App 时无法换渲染器；`_is_animating()` 有上述识别缺陷 |
| `main.py` | **需要重构** | Provider 注册硬编码；`--mock` 参数解析了但未生效；日志端口写死为 5000 |
| `web/server.py` | **保留并扩展** | REST + WS 结构清晰，需增加 App 切换 API；orientation API 存在断链（见第三节） |
| `web/templates/index.html` + `app.js` | **保留并扩展** | 控制台风格合理，需增加 App 选择 UI |

---

## 三、当前最阻碍后续开发的问题

### 3.1 架构层面（5 个）

#### 问题 A：无 App 抽象层，无法添加第二种视觉风格

**位置**：`renderer.py` 整体、`layouts/base.py:16`

目前所有 Layout 都硬依赖 `BoardRenderer`（dot_font 点阵风格）。要新增 cyberpunk dashboard，必须绕过整个 Layout/Renderer 体系，因为没有 `BaseApp` 接口让 Host 知道"切换到哪个 App"。新增 App 目前的唯一出路是改动 `renderer.py` 的主循环逻辑——这是架构级缺口，不是配置级扩展。

---

#### 问题 B：`--mock` 参数解析了但从未对所有 Provider 生效 【修订】

**位置**：`main.py:31` 解析，`main.py:73` 的 `build_providers()` 完全忽略 `args.mock`

```python
# args.mock 存在，但 build_providers(args) 内部无任何分支
for cls in [MockProvider, TrainProvider, WeatherProvider, ...]:
    cfg = app_state.get_provider_config(cls.provider_id)  # 直接读持久化配置
    p = cls(config=cfg)
```

**为什么只改 `data_source` 不够**：各 Provider 的 mock 判断逻辑不统一——
- `train.py`：通过 `config.get("data_source", "mock")` 决定是否 mock
- `weather.py`：通过 `api_key` 是否为空决定是否 mock
- `calendar.py`：通过 `ical_url` 是否为空决定是否 mock

因此只在 config 里注入 `data_source: "mock"` 只能修复 train，weather 和 calendar 仍受持久化配置影响。

**正确修复策略**：在 `BaseProvider.__init__()` 加入 `force_mock: bool` 参数，存为 `self.force_mock`。每个 provider 的 `fetch()` 首先判断 `if self.force_mock: return self._mock_content()`，在所有数据源分支之前短路。`build_providers()` 中当 `args.mock=True` 时构造每个 provider 时传入 `force_mock=True`。这样 mock 行为与持久化配置完全隔离。

---

#### 问题 C：Source 和 Binding 混在 Provider 里，数据无法跨 App 复用

**位置**：`providers/train.py`、`providers/weather.py` 等

以 `train.py` 为例：`_fetch_huxley2()` 做了两件事——调 API 拿原始列车数据，然后直接构造 `BoardContent`（UK Station Board 格式）。如果未来 cyberpunk dashboard 也要显示列车数据，只能复制 HTTP 拉取逻辑，因为格式化逻辑（Binding）和数据获取逻辑（Source）完全耦合。

---

#### 问题 D：颜色主题和亮度设置在运行时无法生效

**位置**：`renderer.py:65-68`、`state.py:48-49`

颜色主题变更只在 `layout_id` 或 `slots` 变化时触发 `_switch_layout()`。仅改主题不改布局时，渲染循环不重建，颜色不更新。亮度值存在 state 里但 `renderer.py` 从不读取。Web 控制台的 Settings 页颜色主题和亮度滑块实际是"假控件"——写入成功但对屏幕无效。

---

#### 问题 E：Provider 注册硬编码，与文档承诺的"零改动"矛盾

**位置**：`main.py:73-89` vs README 第十五节

`build_providers()` 中硬编码了所有 Provider 类。README 说"新增 Provider 完全不修改任何现有代码"，但实际要改 `main.py`。README 第十五节第二步甚至前后矛盾——正文说改 `config.py`，但 `config.py` 里的 `REGISTERED_PROVIDER_CLASSES = []` 是空的从不被用到。这个矛盾会在引入 App 动态注册时造成混乱。

---

### 3.2 与远程控制直接相关的关键断链 【新增小节】

以下问题不属于架构抽象层面，但直接影响"从电脑远程控制 Pi 上的显示系统"这一核心目标，必须在 Task 2 中处理。

#### 断链 1：Web 端修改屏幕方向对本次运行无效

**位置**：`web/server.py:92-102`

`POST /api/orientation` 把 orientation 写入 state 并返回 `restart_required: True`，但进程实际的屏幕尺寸在 `main.py::setup_pygame()` 启动时已固定（由 `--portrait` / `--width` / `--height` CLI 参数决定），运行时无法通过 `pygame.display.set_mode()` 重设。Web 端点击"Portrait"后屏幕没有任何变化，提示"重启生效"的前提是用对启动参数——但下次启动仍然读 CLI 参数而不是持久化的 state，导致方向设置被忽略。

**具体表现**：`state.json` 存了 `"orientation": "portrait"`，但 `main.py` 启动时完全不读这个字段，仍然以 CLI 参数为准。

---

#### 断链 2：状态只在进程正常退出时保存，崩溃或断电丢失所有远程修改

**位置**：`main.py:177`

```python
try:
    rend.run()
finally:
    fetcher.stop()
    app_state.save(STATE_FILE)   # 只在这里保存
```

Web 端通过控制台修改的 layout、provider config、settings 全部只存在内存里，只有 `rend.run()` 正常结束后才写入 `state.json`。Pi 断电、系统 OOM kill、pygame 崩溃，本次会话所有远程修改全部丢失。对于常驻运行的 Pi 来说这是高频故障场景。

---

#### 断链 3：启动日志端口与实际端口不一致

**位置**：`main.py:170`

```python
log.info(f"Web server starting on port 5000")   # 硬编码写死
```

但实际端口由 `config.WEB_PORT = 8080` 决定。开发者或用户根据日志去访问 `http://pi:5000` 会得到 AirPlay 403 或连接失败，而实际控制台在 `http://pi:8080`。应改为 `log.info(f"Web server starting on {WEB_HOST}:{WEB_PORT}")`。

---

#### 断链 4：`install.sh:55` 输出的访问地址仍为 5000 端口（已确认）

**位置**：`install.sh:55`

```bash
echo "Web:  http://$(hostname -I | awk '{print $1}'):5000"
```

安装完成后的提示信息硬写 5000，而实际端口是 8080。用户按照安装脚本的指引去访问会直接失败（Pi 上 5000 无监听）。README 的"已知问题"表虽然写了"已改为 8080"，但 install.sh 的这行从未同步更新。应改为明确写出 8080 或从 `config.py` 读取 `WEB_PORT`。

---

## 四、建议目录结构

```
piboard/
├── main.py                    # 入口：瘦身，只负责 parse args + 拼装；启动时读 state 中的 orientation
├── config.py                  # 保留，无改动
├── state.py                   # 保留并扩展：current_app；写入时机改为事件触发
│
├── host/                      # ★ 新增：宿主系统
│   ├── __init__.py
│   ├── host.py                # pygame 主循环，App 生命周期管理；修复 _is_animating()
│   └── registry.py            # App + Source 自动发现/注册
│
├── apps/                      # ★ 新增：应用层（每个 App 可有独立渲染器）
│   ├── __init__.py
│   ├── base.py                # BaseApp 抽象类
│   └── uk_station/            # UK Station Board（现有代码迁入 + 动画检测修复）
│       ├── __init__.py
│       ├── app.py             # UKStationApp 实现 BaseApp
│       ├── content.py         # 从 board/content.py 迁入
│       ├── dot_font.py        # 从 board/dot_font.py 迁入
│       ├── renderer.py        # 从 board/board_renderer.py 迁入
│       ├── animations.py      # 从 board/animations.py 迁入
│       └── layouts/
│           ├── base.py
│           ├── single.py      # 可直接迁入
│           ├── dual.py        # 迁入时修复 _anims → _anim 检测
│           └── carousel.py    # 迁入时修复独立 _transition 检测
│
├── sources/                   # ★ 重命名 providers/ → sources/，去掉内容格式化逻辑
│   ├── __init__.py
│   ├── base.py                # BaseSource：fetch() → RawData；加 force_mock 参数
│   ├── train.py               # 拉取列车原始数据，返回 dict
│   ├── weather.py
│   ├── calendar.py
│   ├── custom.py
│   ├── mock.py
│   └── fetcher.py             # 从 data/fetcher.py 迁入
│
├── bindings/                  # ★ 新增：Source 原始数据 → App 内容格式 的适配器
│   ├── __init__.py
│   ├── base.py                # BaseBinding
│   ├── train_to_uk.py         # TrainSource → BoardContent（现在在 train.py 里）
│   ├── weather_to_uk.py
│   └── calendar_to_uk.py
│
├── web/                       # 结构保留，API 扩展
│   ├── server.py              # 增加 /api/apps、/api/bindings；state 写入改为事件触发
│   ├── templates/index.html
│   └── static/app.js
│
└── data/
    └── state.json
```

---

## 五、模块职责表

| 模块 | 唯一职责 | 不应做的事 |
|---|---|---|
| `host/host.py` | pygame 主循环；检测状态变更；委托给当前 App 渲染；统一的动画状态查询 | 不直接渲染任何内容 |
| `host/registry.py` | 扫描 apps/ 和 sources/ 目录，返回可用实例列表 | 不持有业务逻辑 |
| `apps/base.py` | 定义 BaseApp 接口：`render(screen, bindings)`、`is_animating() → bool` | |
| `apps/uk_station/app.py` | 管理 UK Station Board 的布局实例，把 Binding 输出渲染到屏幕 | 不做网络请求 |
| `apps/uk_station/content.py` | 定义 BoardContent / BoardRow 数据结构 | 不做渲染 |
| `apps/uk_station/renderer.py` | 把 BoardContent 画到 Surface | 不持有动画状态 |
| `apps/uk_station/animations.py` | 持有动画状态，提供 offset 参数 | 不直接画到 Surface |
| `sources/base.py` | 定义 BaseSource：`fetch() → RawData`，缓存；接受 `force_mock` | 不知道 BoardContent 是什么 |
| `sources/train.py` | HTTP 拉取列车数据，返回原始 dict | 不构造 BoardContent |
| `bindings/base.py` | 定义 BaseBinding：`adapt(raw_data) → AppContent` | |
| `bindings/train_to_uk.py` | 把列车原始 dict 格式化为 BoardContent | 不做网络请求 |
| `state.py` | 线程安全状态单例；事件触发式持久化（不只在退出时） | 不持有业务逻辑 |
| `web/server.py` | REST API + WebSocket；读写 state；每次写入后触发持久化 | 不直接操作 pygame |

---

## 六、状态模型建议

```python
# state.py 扩展后的 _state 结构
{
    # 新增：当前激活的 App
    "current_app": "uk_station",       # App ID，对应 apps/ 子目录名

    # 原有，含义扩展
    "current_layout": "single",        # 在当前 App 下使用的布局
    "layout_slots": [                  # 槽位绑定：App内槽位 → Binding ID
        {
            "slot_index": 0,
            "binding_id": "train_to_uk",   # bindings/ 中的 Binding
            "source_id": "train"            # sources/ 中的 Source
        }
    ],

    # 重命名：providers_config → sources_config（含义更准确）
    "sources_config": {
        "train":    { "station_crs": "KGX", "data_source": "huxley2" },
        "weather":  { "city": "London", "api_key": "" },
        "calendar": { "ical_url": "" },
        "custom":   { ... },
    },

    # 新增：App 级配置（每个 App 自己定义 schema）
    "apps_config": {
        "uk_station": {
            "color_theme": "amber",
            "animations_enabled": True,
        }
        # 未来 cyberpunk_dashboard: {...}
    },

    # 设备级设置（与任何 App 无关）
    "device_settings": {
        "brightness": 1.0,
        "orientation": "landscape",    # 启动时 main.py 应读此字段，而非只靠 CLI 参数
    },

    "dirty": True,
}
```

关键变化：
- `settings` 拆为 `apps_config`（App 级，颜色主题/动画）和 `device_settings`（设备级，亮度/方向）
- `providers_config` 改名 `sources_config`，语义更准确
- `layout_slots` 从字符串列表改为对象列表，明确 source + binding 的组合关系
- `device_settings.orientation` 需要被 `main.py` 在启动时读取，以修复远程设置方向后重启不生效的问题

---

## 七、迁移顺序（最小可运行原则）

每步完成后项目必须仍可正常运行。

**Step 1（修 bug）：修复 `--mock` 不生效 + 端口日志不一致** 【修订】

`--mock` 不能只改一个 config 字段，因为各 Provider 的 mock 判断逻辑不统一。正确做法：
- 在 `BaseProvider.__init__()` 加 `force_mock: bool = False`，存为 `self.force_mock`
- 每个 provider 的 `fetch()` 第一行加 `if self.force_mock: return self._mock_content()`
- `build_providers()` 当 `args.mock=True` 时，构造每个 provider 传入 `force_mock=True`

同步修复端口日志：`main.py:170` 改为 `log.info(f"Web server starting on {WEB_HOST}:{WEB_PORT}")`

**Step 2（修 bug）：修复动画状态检测 + 颜色主题运行时生效** 【修订】

- `renderer._is_animating()` 需要改为通过 App 接口查询，或直接修复对 `_anims` 和独立 `_transition` 的识别
- DualLayout：`_is_animating()` 需遍历 `_anims` 列表
- CarouselLayout：`_is_animating()` 需额外检查 `layout._transition.is_active`
- 在 `renderer.py` 的 `run()` 主循环中检测 `settings["color_theme"]` 变化，触发 `_switch_layout()`
- 顺带实现 brightness（添加 overlay Surface）

**Step 3（修 bug）：state 持久化改为事件触发；orientation 启动时优先级规则明确化**

- `state.py` 的 `update_provider_config()`、`update_settings()`、`set_layout()` 在写入后调用 `self.save(STATE_FILE)`（去掉对 STATE_FILE 的依赖，改为注入路径或在 init 时存储）
- `main.py::setup_pygame()` 的屏幕方向按以下三级优先级确定（从高到低）：
  1. `--width` / `--height` 均明确传入 → 直接使用，忽略其他所有来源
  2. `--portrait` 传入（且未同时传 `--width`/`--height`）→ 使用竖屏默认尺寸（600×1024）
  3. 以上均未传入 → 读 `app_state.device_settings["orientation"]`，`"portrait"` 对应 600×1024，`"landscape"` 对应 1024×600

  注意：当前 CLI 没有 `--landscape` 标志。在 state 已被 Web 端设为 portrait 的情况下，若要从命令行强制回横屏，必须显式传入 `--width 1024 --height 600`，直到后续添加 `--landscape` 标志为止。此规则需在 `setup_pygame()` 的注释和 README 启动参数表里同步说明。

**Step 4（引入 BaseApp，不移动现有代码）**

- 新建 `apps/base.py`：`BaseApp(render, on_activate, get_layouts, is_animating)`
- 新建 `apps/uk_station/app.py`：`UKStationApp` 包装现有 `board/` + `layouts/`
- `renderer.py` 改为通过 App 接口渲染，现有 board/ layouts/ 路径暂不移动

**Step 5（拆分 Source 和 Binding）**

- 新建 `sources/` 目录，`BaseSource` 只负责 `fetch() → dict`；含 `force_mock` 参数
- 新建 `bindings/` 目录，`BaseBinding.adapt(dict) → BoardContent`
- 把 `train.py` 的 HTTP 拉取部分迁入 `sources/train.py`，格式化部分迁入 `bindings/train_to_uk.py`
- `providers/` 目录作为兼容别名保留，逐步废弃

**Step 6（状态模型迁移）**

- 扩展 `state.py` 加入 `current_app` 和 `apps_config`，`settings` 拆为 `apps_config` + `device_settings`
- 更新 `web/server.py` 添加 `/api/apps` 端点
- 更新 Web 控制台加入 App 选择 UI

**Step 7（自动注册）**

- `host/registry.py` 扫描 `apps/` 和 `sources/` 目录自动发现
- 删除 `main.py` 中的硬编码导入列表

---

## 八、审查结论

| 检查项 | 结果 |
|---|---|
| 是否改动代码 | **否，0 文件改动** |
| 可直接迁移模块 | board/（4个文件）、data/fetcher.py、state.py 结构、config.py、web/server.py 结构 |
| 带已知缺陷迁移 | layouts/dual.py（_anims 检测缺陷）、layouts/carousel.py（独立 _transition 检测缺陷）|
| 必须重构模块 | providers/（拆 Source + Binding）、renderer.py（引入 App 层 + 修复动画检测）、main.py（mock bug + 注册机制 + 端口日志）|
| 新增抽象层 | host/、apps/base.py、bindings/ |
| 已确认 bug（未修复）| 1. --mock 不生效（跨 Provider）；2. DualLayout 动画不驱动高帧率；3. CarouselLayout 过渡动画不驱动高帧率；4. 颜色主题/亮度运行时不生效；5. 状态只在退出时写盘；6. Web 端 orientation 修改重启后不生效；7. 日志端口写死 5000 |
| 文档与代码不符 | README 第十五节"步骤二"写"改 config.py"，实际需改 main.py；README 提端口 5000 已改 8080 但日志仍写 5000 |
