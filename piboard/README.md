# PiBoard

树莓派 Zero 2W 上的轻量级个人信息显示系统。

将任意内容（列车时刻、天气、日程、自定义文字）以**英国火车站 LED 点阵报站大屏**的视觉风格呈现在屏幕上，并通过局域网 Web 控制台实时管理。

---

## 目录

- [项目背景](#项目背景)
- [v0.1.1 当前状态](#v011-当前状态)
- [系统架构](#系统架构)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [启动参数](#启动参数)
- [内置 Provider 说明](#内置-provider-说明)
- [布局系统](#布局系统)
- [Web 控制台](#web-控制台)
- [已完成内容](#已完成内容)
- [TODO](#todo)
- [已知问题](#已知问题)
- [可改进内容](#可改进内容)
- [注意事项](#注意事项)
- [性能指标](#性能指标)
- [如何新增 Provider](#如何新增-provider)
- [部署到树莓派](#部署到树莓派)

---

## 项目背景

**硬件**：树莓派 Zero 2W（ARMv8 四核 1GHz，512MB RAM）+ 7 寸屏幕

**核心问题**：Zero 2W 资源极其有限，传统桌面环境（X11 + Chromium）在其上几乎无法流畅运行。本项目绕开桌面环境，直接使用 pygame SDL2 kmsdrm 后端渲染，将 CPU 静止占用控制在 3% 以内。

**视觉定位**：完全还原英国火车站 LED 点阵报站屏风格——自定义 5×7 / 7×9 点阵字体，每个像素渲染为带高光的圆点，背景 #080808，琥珀色主光 #FF9500，暗点 #1C1000。车站大屏风格是系统内置的第一套「主题」，未来可扩展更多主题。

**控制方式**：手机或电脑在局域网内访问 Web 控制台（Flask + WebSocket），无需连接键盘鼠标到 Pi。

---

## v0.1.1 当前状态

- Web 控制台端口固定为 `8080`，验收检查以 `/api/state` 和 `/api/device-status` 为主。
- 当前 MVP 是低功耗展示版：`single/mock + cycle`，默认轮换 `overview/train/weather/calendar`，动画关闭。
- 运行版本可通过 `/api/version` 和 `/api/device-status.version` 回读；Pi 同步脚本会生成 `BUILD_INFO`。
- 天气无 API Key 时走 Open-Meteo live path；本次 v0.1.1 已用 London 验证无 Key live 返回。
- Train 的 mock/demo 板面会显示 `DEMO` 和 `Rail demo data (mock)`；当前 `main` 使用 Huxley2 兼容 live endpoint，原 Azure endpoint 保留为 fallback。
- Calendar 无 iCal URL 时是 mock/demo；本次没有安全公开 iCal 测试源，不写成 live 已验收。
- 亮度滑杆已通过 host-level dimming overlay 生效，持久化字段是 `device_settings.brightness`，范围 `0.1-1.0`。
- v0.1.1 验收记录见 `../docs/v0.1.1.md`；v0.1-demo 历史记录见 `../docs/v0.1-demo.md`。
- `data/state.json` 是本机私有运行态，不能提交；公开示例配置是 `data/state.example.json`。

---

## 系统架构

```
┌─────────────────────────────────────────────────┐
│            点阵渲染引擎（固定，不变）              │
│         dot_font.py / board_renderer.py          │
└─────────────────┬───────────────────────────────┘
                  │ 只认识 BoardContent 数据结构
┌─────────────────┴───────────────────────────────┐
│           ContentProvider 抽象接口               │
└──────┬──────────┬──────────┬────────────────────┘
       │          │          │          │
  列车时刻      天气预报    个人日程    自定义文本
TrainProvider WeatherProvider CalendarProvider CustomProvider
```

**渲染与内容完全解耦**：
- 渲染层永远不知道内容从哪里来
- 内容层永远不知道自己怎么被画出来
- 新增一种内容 = 新建一个 Provider 文件，零改动渲染代码

**线程模型**：
```
主线程（pygame 渲染）
  └── 读取 app_state（只读）

Flask 线程（daemon）
  └── 读写 app_state（RLock 保护）

DataFetcher 线程（daemon）
  └── ThreadPoolExecutor(max_workers=2)
      └── 调用各 Provider.fetch()（后台）
```

---

## 目录结构

```
piboard/
├── main.py                    # 入口：解析参数、初始化、启动各子系统
├── config.py                  # 全局配置（分辨率、颜色、动画参数等）
├── state.py                   # 线程安全全局状态单例（含持久化）
├── renderer.py                # pygame 主渲染循环（dirty flag 帧控制）
│
├── board/
│   ├── content.py             # ★ BoardContent / BoardRow 数据契约
│   ├── dot_font.py            # ★ 5×7 / 7×9 点阵字体引擎（含 Surface 缓存）
│   ├── board_renderer.py      # ★ 把 BoardContent 画到 pygame Surface
│   └── animations.py         # 跑马灯、翻页、板面切换动画
│
├── providers/
│   ├── base.py                # BaseProvider 抽象基类
│   ├── mock.py                # Mock Provider（内置3个预设，无需API）
│   ├── train.py               # 列车时刻（支持 mock/huxley2/transportapi）
│   ├── weather.py             # 天气（默认 Open-Meteo，可选 OpenWeatherMap）
│   ├── calendar_provider.py   # 日程（支持 mock/iCal URL）
│   └── custom.py              # 自定义文本（Web 端直接编辑）
│
├── layouts/
│   ├── base.py                # Layout 抽象基类
│   ├── single.py              # 单板全屏
│   ├── dual.py                # 双板（横屏左右 / 竖屏上下，自动感知）
│   └── carousel.py            # 多板轮播（默认10秒切换）
│
├── web/
│   ├── server.py              # Flask + flask-sock，全部 REST API + WebSocket
│   ├── templates/index.html   # Web 控制台（Dashboard 风格，响应式）
│   └── static/app.js          # 前端逻辑（Vanilla JS，无框架）
│
├── data/
│   └── fetcher.py             # 后台数据拉取调度器
│
├── preview_font.py            # 开发工具：点阵字体可视化预览
├── preview_board.py           # 开发工具：板面渲染效果预览
├── requirements.txt
├── install.sh                 # 一键安装脚本（在 Pi 上运行）
└── piboard.service            # systemd 服务文件
```

---

## 快速开始

### 开发机（Mac / Linux 桌面）

```bash
# 进入应用目录
cd piboard

# 安装依赖
pip install -r requirements.txt

# 窗口模式（无需 Pi）
python3 main.py --window

# 预览点阵字体效果
python3 preview_font.py

# 预览板面渲染效果（SPACE 键切换预设）
python3 preview_board.py
```

启动后在浏览器访问 `http://localhost:8080` 打开 Web 控制台。

### 树莓派 Pi

```bash
git clone <repo> /home/pi/piboard
cd /home/pi/piboard
chmod +x install.sh && ./install.sh
sudo systemctl start piboard
```

---

## 启动参数

| 参数 | 说明 |
|------|------|
| `--window` | 窗口模式（开发调试，不需要 Pi） |
| `--mock` | 兼容保留参数；当前不改变 Provider 行为 |
| `--portrait` | 竖屏模式（默认 600×1024）；**仅影响本次启动，不写入持久化状态**。长期改方向请用 Web 控制台 |
| `--display-rotate <0/90/180/270>` | direct kmsdrm 场景下旋转物理输出；v0.1-demo Pi 使用 `90` |
| `--provider <id>` | 指定启动后显示的 Provider（会持久化到 state.json） |
| `--layout <id>` | 指定启动布局（single / dual / carousel）（会持久化到 state.json） |
| `--width <px>` | 自定义屏幕宽度（仅影响本次启动） |
| `--height <px>` | 自定义屏幕高度（仅影响本次启动） |

**启动尺寸 precedence**（高→低）：`--width/--height` > `--portrait` > 持久化 `device_settings.orientation` > 默认 landscape。

示例：

```bash
# 竖屏双板 Mock 演示
python3 main.py --window --layout dual --portrait

# 横屏轮播，显示天气 Provider
python3 main.py --window --provider weather --layout carousel

# 自定义分辨率
python3 main.py --window --width 800 --height 480
```

---

## 内置 Provider 说明

### Mock（`mock`）
内置概览、火车、天气、日程预设，按时间轮换。**无需任何 API Key**，是默认的开发调试 Provider。mock/demo 内容必须按 demo 或 mock 标注，不能作为 live 数据宣传。

### 列车时刻（`train`）
| 配置项 | 说明 |
|--------|------|
| `station_crs` | 出发站 CRS 代码（如 `KGX` = King's Cross） |
| `destination_crs` | 目的地 CRS（可选，留空显示所有方向） |
| `data_source` | `mock` / `huxley2` / `transportapi` |
| `huxley2_base_url` | Huxley2 兼容 endpoint；默认 `https://national-rail-api.davwheat.dev` |
| `api_key` | transportapi 模式需要 |

Huxley2 是免费的 Darwin 数据代理，无需注册。v0.1.1 发布验收时原公开 endpoint 返回 HTTP 500；当前 `main` 已切到短期替代的 Huxley2 兼容 endpoint，并在 BHM 上验证 live 返回。

### 天气（`weather`）

无 `api_key` 时默认使用 Open-Meteo：手动城市模式会先做 Open-Meteo geocoding，自动位置模式使用 Web 控制台保存的经纬度。有 OpenWeatherMap API Key 时保留旧 OpenWeatherMap 路径。

| 配置项 | 说明 |
|--------|------|
| `city` | 城市名（如 `London`、`Beijing`） |
| `location_mode` | `auto` / `manual` |
| `api_key` | 可选 OpenWeatherMap API Key；留空使用 Open-Meteo |
| `units` | `metric`（摄氏度）/ `imperial`（华氏度） |

### 日程（`calendar`）
| 配置项 | 说明 |
|--------|------|
| `ical_url` | iCal 订阅链接（Google/Apple Calendar 均支持） |
| `lookahead_days` | 显示未来几天（默认 3） |

未配置 `ical_url` 时显示 mock/demo 日程。v0.1.1 没有提交或使用任何私有 iCal URL，也不声明 Calendar live 已验收。

### 自定义文本（`custom`）
所有字段直接在 Web 控制台编辑，无任何网络请求。支持自定义 header、title、subtitle、内容行、footer、状态文字、跑马灯。

---

## 布局系统

| 布局 | 说明 | Slot 数 |
|------|------|---------|
| `single` | 单板全屏 | 1 |
| `dual` | 双板（横屏左右/竖屏上下，自动感知） | 2 |
| `carousel` | 多板轮播，默认每 10 秒切换 | 最多 3 |

Dual 布局的方向感知基于 `is_portrait(w, h)`（`h > w` 即为竖屏），无需手动配置。

---

## Web 控制台

访问 `http://<Pi的IP>:8080`

**Display 页**：选择布局（Single/Dual/Carousel），为每个 Slot 绑定 Provider，点击 Apply 生效。

**Content 页**：配置各 Provider 参数。Train Provider 配置面板有专属的琥珀色车站大屏风格区分。修改后点 Save，自动触发数据刷新。

**Settings 页**：
- 亮度、颜色主题（Amber / Green / White）、动画开关
- 屏幕方向切换（Landscape / Portrait）——修改后需重启 PiBoard 生效

WebSocket 实时双向通信，所有设置即时推送到 Pi 屏幕，断线自动重连。

### API 端点

```
GET  /api/state                   # 完整状态 JSON
GET  /api/providers               # 已注册 Provider 列表及 schema
POST /api/layout                  # { "layout": "dual", "slots": ["train", "weather"] }
POST /api/provider/<id>/config    # 更新 Provider 配置
POST /api/provider/<id>/refresh   # 强制立即刷新数据
POST /api/settings                # { "brightness": 0.8, "color_theme": "green" }
POST /api/orientation             # { "orientation": "portrait" }（重启生效）
WS   /ws                          # 双向实时通信
```

---

## 已完成内容

### 核心渲染
- [x] `BoardContent` / `BoardRow` 数据契约
- [x] 5×7 + 7×9 完整 ASCII 点阵字体（手工 bitmap，含圆点渲染 + 高光 + 暗点）
- [x] 板面布局渲染器（header / title / rows / footer / ticker 五区域，百分比分配）
- [x] 字符 Surface 缓存（按 char+size+color 为 key，避免重复渲染）
- [x] 跑马灯动画（基于时间戳，无 sleep）
- [x] 内容行自动翻页（超出显示区时 ease-in-out 上滑）
- [x] 板面切换过渡动画（旧内容上滑淡出，新内容从下淡入）
- [x] dirty flag 帧率控制（静止 1fps，动画/变更时 30fps）

### 布局系统
- [x] Single 全屏布局
- [x] Dual 双板布局（横屏左右 / 竖屏上下自动感知）
- [x] Carousel 轮播布局（最多 3 个 Slot，10秒切换）

### Provider 系统
- [x] `BaseProvider` 抽象基类（含 schema / fetch / cache 机制）
- [x] Mock Provider（4 个完整预设：概览/火车/天气/日程）
- [x] Train Provider（mock 已验收；当前 main 的 Huxley2 兼容 live endpoint 已用 BHM 验证；Transport API 为兼容路径）
- [x] Weather Provider（默认 Open-Meteo 已验收 + 可选 OpenWeatherMap）
- [x] Calendar Provider（mock 已验收；iCal live 需要安全测试源，v0.1.1 未声明已验收）
- [x] Custom Provider（Web 端直接编辑内容）

### 系统基础设施
- [x] 线程安全全局状态单例（`state.py`，RLock 保护）
- [x] 状态持久化（`data/state.json`，重启恢复）
- [x] 后台数据调度器（`ThreadPoolExecutor(max_workers=2)`，失败保留缓存）
- [x] 颜色主题系统（Amber / Green / White）
- [x] 亮度 overlay（`device_settings.brightness`，0.1-1.0）
- [x] Pi direct kmsdrm 竖屏验收（`--portrait --display-rotate 90`）

### Web 控制台
- [x] Dashboard 风格控制台（Display / Content / Settings 三页导航）
- [x] 桌面左侧边栏 + 手机底部导航栏（响应式自动切换）
- [x] 布局选择 + Slot 绑定 + 一键应用
- [x] Provider 配置表单（按 schema 自动生成）
- [x] Train Provider 配置面板独立琥珀色车站风格
- [x] 自定义 Provider 行编辑器（动态增删行）
- [x] 全局设置（亮度、主题、动画、屏幕方向）
- [x] WebSocket 实时双向通信 + 断线自动重连

### 部署
- [x] `--window` 开发机调试模式
- [x] `--portrait` 竖屏模式（600×1024）
- [x] systemd 服务文件
- [x] 一键安装脚本（`install.sh`）
- [x] Pi runtime 版本 marker（部署时生成 `BUILD_INFO`，API 暴露 `/api/version`）

---

## TODO

### 高优先级

- [ ] **Train live 稳定性复测** — 当前使用短期 Huxley2 兼容 endpoint；v0.2 前需要决定长期数据源策略或更清晰的 UI 失败状态。
- [ ] **Calendar iCal 公开测试源** — 使用不含个人日程的测试订阅验证 live path。
- [ ] **Provider 刷新状态指示** — Web 端显示各 Provider 最后成功/失败时间。

### 中优先级

- [ ] **横竖屏运行时切换** — 当前需重启 main.py；目标是 Web 端点击后自动重启（可用 `os.execv` 重启进程）。

### 低优先级

- [ ] **更多布局** — 三板（左1+右2）、PiP（画中画）等
- [ ] **中文字符支持** — 当前点阵字体只覆盖 ASCII 32-126，中文需要另一套方案（TTF 回退或扩展 bitmap）
- [ ] **插件式 Provider 发现** — 扫描 providers/ 目录自动注册，无需修改 config.py
- [ ] **多屏输出** — 通过 pygame 多窗口或 SDL 多显示器支持
- [ ] **状态 WebSocket 推送频率** — 目前仅事件触发推送，可增加定期心跳 + 内容摘要推送

---

## 已知问题

| 问题 | 影响 | 临时方案 |
|------|------|---------|
| **macOS 端口 5000 冲突** | AirPlay 接收器占用 5000 端口，导致 403 | 已改为 8080；或关闭「AirPlay 接收器」 |
| **竖屏运行时不可切换** | `pygame.display.set_mode()` 只能在启动时设置尺寸 | 在 Web 控制台 Settings 页修改 orientation，重启后按 `device_settings.orientation` 自动恢复。`--portrait` 仅用于一次性临时调试，不是长期方案 |
| **部分特殊字符乱码** | 点阵字体仅覆盖 ASCII，°C 等需特殊处理 | 已在 bitmap 中手动定义 `°`，其余特殊字符显示为空白 |
| **Carousel 第一次切换无过渡** | `_prev_surf` 首次为 None | 低影响，仅首次切换无动画 |
| **Flask 单线程模式下 WebSocket 阻塞** | 每次只能服务一个 WS 客户端 | 控制台通常只有一个用户，实际影响小 |
| **state.json 并发写入** | ~~多个事件同时触发 save() 可能竞争~~ | Task 10 已修复：串行化（persist_lock）+ 临时文件原子替换（os.replace），文件不会出现半写状态 |

---

## 可改进内容

### 渲染质量

- **抗锯齿圆点** — 当前使用 `pygame.draw.circle`（无抗锯齿），可改用 pre-rendered 的 AA 圆点 Surface 进一步提升视觉质量
- **发光效果** — 亮点目前有两层圆（主色 + 高光），可增加高斯模糊模拟真实 LED 光晕（但会增加 CPU 开销，需评估）
- **字体紧排** — 当前字符等宽排列，可实现按字符宽度紧排（proportional）减少空白

### 内容扩展

- **股票/加密货币 Provider** — 实时价格看板
- **系统状态 Provider** — Pi CPU 温度、负载、内存
- **RSS/新闻 Provider** — 头条新闻跑马灯
- **时钟 Provider** — 大号数字时钟（利用 XLARGE 字号）
- **倒计时 Provider** — 距重要日期倒计时

### 工程改进

- **Provider 热加载** — 修改 Provider 文件后无需重启（`importlib.reload`）
- **配置 Schema 版本控制** — 防止升级后 state.json 字段不兼容
- **日志分级输出** — 当前全部输出到 stdout，可加文件日志轮转
- **单元测试** — 目前无测试覆盖，核心模块（dot_font、board_renderer、animations）可加 pytest 测试
- **Docker 开发环境** — 提供带 SDL 的开发容器，消除开发机环境差异

### Web 控制台

- **拖拽排序 Slot** — 直观调整 Carousel 轮播顺序
- **暗/亮主题切换** — 控制台本身支持 light mode
- **Provider 在线状态指示** — 显示最后成功/失败时间、数据新鲜度
- **键盘快捷键** — `L` 切换布局，`R` 刷新，`S` 保存

---

## 注意事项

### 硬件限制（Zero 2W 必须遵守）

1. **并发请求上限 2 个** — `DataFetcher` 中 `ThreadPoolExecutor(max_workers=2)` 不要调高，否则 Zero 2W 会过载
2. **内存目标 < 80MB** — 不要在主线程缓存大量 Surface；字体缓存按需增长，极端情况可调用 `dot_font.clear_cache()` 释放
3. **不要在主线程做网络请求** — 所有 Provider.fetch() 必须在后台线程（DataFetcher）中调用
4. **不要在 Provider.fetch() 中调用 pygame API** — pygame 不是线程安全的

### kmsdrm 后端（Pi 上运行）

- 必须在 `/boot/firmware/config.txt`（或 `/boot/config.txt`）中启用 `dtoverlay=vc4-kms-v3d`，否则 SDL kmsdrm 无法初始化
- 设置 `gpu_mem=64` 为 GPU 分配足够显存
- 若出现黑屏，检查 `/dev/dri/card0` 是否存在，确认用户在 `video` 和 `render` 组中

### 开发机调试

- 始终使用 `--window` 参数，不要设置 `SDL_VIDEODRIVER=kmsdrm`（macOS/Linux 桌面不支持）
- macOS 上 port 5000 被 AirPlay 占用，使用 8080（已配置）
- conda 环境需单独 `pip install pygame`，系统 Python 的 pygame 不会自动继承

### 状态管理

- `state.py` 是单例，多线程共享，修改时务必通过其公开方法（`set_layout`、`update_settings` 等），不要直接访问 `_state` 字典
- **Task 10 后**：Web 控制台的任何修改（orientation、layout、source config、app settings、current app）都会在修改后立即写盘（串行化 + 原子替换），不依赖程序正常退出。进程被 `kill -9` 也不会丢失已提交的变更
- 屏幕方向由 `device_settings.orientation` 管理，重启后自动按持久化值恢复。`--portrait` 只是本次启动的临时覆盖
- 若配置损坏，删除 `data/state.json` 重置为默认值

---

## 性能指标

| 指标 | 目标 | 当前实现方案 |
|------|------|------------|
| 静止画面 CPU | < 3% | dirty flag 降至 1fps |
| 动画运行 CPU | < 25% | 30fps，字体 Surface 缓存 |
| 总内存占用 | < 80MB | 按需缓存，无预加载 |
| 启动时间 | < 5秒 | 延迟 Provider 首次 fetch |
| 后台并发请求 | 最多 2 个 | `ThreadPoolExecutor(max_workers=2)` |

---

## 如何新增 Provider

只需三步，**零改动现有代码**：

**第一步**：新建 `providers/my_provider.py`

```python
from providers.base import BaseProvider
from board.content import BoardContent, BoardRow

class MyProvider(BaseProvider):
    provider_id = "my_provider"
    display_name = "我的内容"
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
            rows=[BoardRow("Item 1", "Value 1")],
            footer="My Provider",
            status_text="OK",
            status_color="green",
            provider_id=self.provider_id,
        )
```

**第二步**：在 `main.py` 的 `build_providers()` 函数中添加一行：

```python
from providers.my_provider import MyProvider
# ...在 providers 字典中加入：
# MyProvider 会自动出现在 Web 控制台
```

**第三步**：重启 PiBoard，Web 控制台 Content 页自动出现新 Provider。

---

## 部署到树莓派

```bash
# 1. 在 Pi 上克隆代码
git clone <repo> /home/<pi-user>/CC-UK-TR

# 2. 运行安装脚本（自动配置 GPU、安装依赖、注册服务）
cd /home/<pi-user>/CC-UK-TR/piboard
chmod +x install.sh
./install.sh

# 3. 启动服务
sudo systemctl start piboard

# 4. 查看日志
sudo journalctl -u piboard -f

# 5. 从手机/电脑访问控制台
# http://<Pi的IP>:8080
```

v0.1-demo 的 Pi service 针对当前竖装 7 寸屏固定使用 `--portrait --display-rotate 90`。若换屏或安装方向相反，只改 `--display-rotate` 为 `270`，再 reload/restart service。

```ini
ExecStart=/usr/bin/python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait --display-rotate 90
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=dummy
```

若需临时调试竖屏，可在 shell 中一次性运行：

```bash
sudo systemctl stop piboard
python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait --display-rotate 90
# 调试完毕后 sudo systemctl start piboard 恢复服务
```

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 显示渲染 | Python + pygame（SDL2 kmsdrm 后端） |
| 点阵字体 | 自定义 bitmap + pygame.draw.circle |
| Web 控制台后端 | Flask + flask-sock（WebSocket） |
| Web 控制台前端 | Vanilla JS（无框架） |
| 数据获取 | requests + icalendar |
| 状态管理 | threading.RLock 单例 + JSON 持久化 |
| 部署 | systemd service |
