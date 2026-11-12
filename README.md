# PiBoard：树莓派复古点阵信息屏

**Retro Dot-Matrix Information Display for Raspberry Pi**

[中文](#中文) | [English](#english)

将天气、个人日历、英国列车动态和自定义文字，显示在一块英式车站风格的复古 LED 点阵屏上。通过手机或电脑上的局域网控制台，即可切换页面、配置数据和调整显示。

Display weather, personal calendars, UK rail updates and custom text on a retro LED dot-matrix screen inspired by British railway departure boards. Switch pages, configure data sources and adjust the display from a phone or computer on your local network.

![PiBoard overview demo](piboard-deploy-final-overview.png)

![PiBoard weather demo](piboard-deploy-weather.png)

## 中文

### 项目与版本

项目面向 Raspberry Pi Zero 2W，使用 Python、pygame 和 SDL2 `kmsdrm` 直接驱动屏幕，无需桌面环境或浏览器；也支持在电脑上窗口预览。真实数据需要配置对应来源，演示数据会明确标注。

当前版本：**`v0.1.2`**，显示与运行修复版。完整运行修复已在 Pi 验证，保留用户私有配置；天气和私人日历读取通过，铁路上游当前 HTTP 500，显示 WAIT，不宣称铁路 live 可用。

### 能展示什么

- Overview：天气、日程、列车状态的综合摘要。
- Train：英国铁路出发板样式；mock 模式明确标为 demo；当前 `main` 默认使用 Huxley2 兼容 live endpoint，并保留原 Huxley2 Azure 地址作为 fallback。
- Weather：无 OpenWeatherMap API Key 时走 Open-Meteo live；有 Key 时保留 OpenWeatherMap 路径。
- Calendar：有 iCal URL 时走日历 live；未配置时显示 mock 日程。
- Custom：手工编辑的自定义看板，不属于 live 数据源。

Web 控制台端口固定为 `8080`，常用检查端点为 `/api/state`、`/api/device-status` 和 `/api/version`。

### 本地运行

在仓库根目录打开终端，然后运行：

```bash
cd piboard
pip install -r requirements.txt
python3 main.py --window
```

打开 `http://localhost:8080` 查看 Web 控制台。

回到仓库根目录运行最小检查（另开终端，或先退出程序）：

```bash
python3 -m compileall -q piboard
python3 tests/smoke_v0_1_1.py
python3 tests/smoke_visual.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

### 部署到 Pi

在仓库根目录使用同步脚本，将占位值替换为自己的 Pi 用户和地址。部署前备份设备上的私有配置；本次文档更新不会自动部署到 Pi。

```bash
piboard/deployment/sync-to-pi.sh 'pi-user@pi-host-or-ip'
```

也可以设置 `PIBOARD_PI_HOST=<pi-user@pi-host-or-ip>` 后运行同一脚本。脚本会同步 `piboard/`，安装 `piboard.service`，并在 Pi 运行目录生成 `BUILD_INFO`。运行时版本可通过：

```bash
curl 'http://<pi-host-or-ip>:8080/api/version'
curl 'http://<pi-host-or-ip>:8080/api/device-status'
```

Pi service 使用 direct `kmsdrm`：

```ini
ExecStart=/usr/bin/python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait --display-rotate 90
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=dummy
```

### 数据真实性边界

| 页面 | 数据边界 |
|---|---|
| Overview | 混合摘要；按各来源的配置与缓存结果标注 LIVE / MOCK / WAIT / STALE |
| Train | 默认 mock/demo；Pi 的 BHM 配置走 Huxley2，但本次主、备用接口均 HTTP 500，概览为 WAIT；历史成功返回不代表当前可用 |
| Weather | 本次 Pi 已验证 Open-Meteo live，使用已保存的位置；OpenWeatherMap 需要用户自己的 API Key，未验收 |
| Calendar | 默认 mock/demo；本次 Pi 使用已有私人订阅读取成功，窗口内 0 事件；不公开链接，不代表重复/跨日日历语义完整验收 |
| Custom | 手工内容，不是 live 数据 |

### 验收记录

- **`v0.1.2` 正式版验收：[docs/v0.1.2.md](docs/v0.1.2.md)**。GitHub Release 附最终版本/commit 的脱敏设备验收 JSON。
- `v0.1.2-rc.1` 整理及待验收项：[docs/v0.1.2-rc.1.md](docs/v0.1.2-rc.1.md)
- 点阵字体前后对比：[字体审查记录](docs/font-review-2026-11-11.md)；下载仓库后可直接打开 [交互对比页](piboard/review_artifacts/font-review-2026-11-11/index.html)。GitHub 文件页本身不执行该 HTML。
- [视觉与交互审查](docs/visual-review-2026-11-11.md) / [运行审计与遗留问题](docs/project-audit-2026-11-10.md)
- `v0.1-demo` 历史记录：[docs/v0.1-demo.md](docs/v0.1-demo.md)
- `v0.1.1` 发布验收记录：[docs/v0.1.1.md](docs/v0.1.1.md)

### 安全说明

不要提交 `piboard/data/state.json`、`piboard/BUILD_INFO`、私有 iCal URL、个人日历链接、API token、真实密钥、本机路径、真实 LAN IP 或真实 Pi 主机名。需要配置时从 `piboard/data/state.example.json` 复制到本地运行态。

### 当前限制

- 本版不新增页面和数据源；Pi 的五页切换、整合回归和配置恢复已验证。公开截图是 Pi 离屏渲染的安全示例，不是物理屏幕照片。
- Calendar 默认配置是 mock；私人订阅不会随源码同步。重复事件和跨日事件尚未完整支持。
- Train live 依赖公开 Huxley2 兼容服务可用性；当前默认 endpoint 已切到短期替代服务，并保留原 Azure endpoint 作为 fallback。
- 控制台没有登录保护，只适用于受信任的局域网，不应直接暴露到公网。浏览器定位需要安全访问环境；普通局域网 HTTP 可改用手动城市。
- 写入 API 已补结构、字段类型和枚举校验；多端并发设置冲突及 OpenWeatherMap 概览兼容性仍有已知缺口，详见审计记录。
- 资源占用尚未达到全部设计目标；本次短采样约 6.4% 单核 CPU、115 MiB RSS，不等于长期性能验收。
- 运行时横竖屏切换仍需要重启进程。

更多实现细节见 [piboard/README.md](piboard/README.md)。

## English

### Project And Version

PiBoard targets the Raspberry Pi Zero 2W. It renders directly to the screen using Python, pygame and SDL2's `kmsdrm` backend, without a desktop environment or browser on the Pi. A windowed preview is also available on a computer. Live data requires the corresponding sources to be configured; demo data is explicitly labelled.

Current version: **`v0.1.2`**, a display and runtime fix release. The integrated runtime fixes have been verified on Pi with private configuration preserved. Weather and private calendar fetching passed; both train upstreams currently return HTTP 500, so Overview shows WAIT. Live train availability is not claimed.

### What It Displays

- **Overview:** a combined summary of weather, calendar events and rail status.
- **Train:** a UK railway departure-board layout. Mock data is labelled as demo. The live path on `main` defaults to a Huxley2-compatible endpoint, with the original Huxley2 Azure endpoint retained as a fallback.
- **Weather:** uses Open-Meteo when no OpenWeatherMap API key is configured; the optional OpenWeatherMap path remains available with a key.
- **Calendar:** reads the configured iCal subscription; without a URL, it shows mock events.
- **Custom:** a manually edited board, not a live data source.

The web console listens on port **`8080`**. Diagnostic endpoints include `/api/state`, `/api/device-status` and `/api/version`.

### Run Locally

Open a terminal at the repository root, then run:

```bash
cd piboard
pip install -r requirements.txt
python3 main.py --window
```

Open `http://localhost:8080` to use the web console.

Run the minimal checks from the repository root in another terminal, or after stopping the app:

```bash
python3 -m compileall -q piboard
python3 tests/smoke_v0_1_1.py
python3 tests/smoke_visual.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

### Deploy To Pi

Run the sync script from the repository root, replacing the placeholder with your Pi user and address. Back up the device's private configuration first. This documentation update does not deploy anything to the Pi.

```bash
piboard/deployment/sync-to-pi.sh 'pi-user@pi-host-or-ip'
```

Alternatively, set `PIBOARD_PI_HOST=pi-user@pi-host-or-ip` and run the same script without an argument. The script syncs `piboard/`, installs `piboard.service` and generates `BUILD_INFO` in the Pi runtime directory. Read the running version and device status with these endpoints, replacing the host placeholder:

```bash
curl 'http://<pi-host-or-ip>:8080/api/version'
curl 'http://<pi-host-or-ip>:8080/api/device-status'
```

The Pi service uses direct `kmsdrm` rendering:

```ini
ExecStart=/usr/bin/python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait --display-rotate 90
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=dummy
```

### Live And Demo Data

| Page | Data boundary |
|---|---|
| Overview | Mixed summary; LIVE / MOCK / WAIT / STALE reflect each configured source and its cached result |
| Train | Mock/demo by default. The Pi uses Huxley2 for BHM, but both endpoints returned HTTP 500 in this check; Overview shows WAIT. Earlier successful responses do not establish current availability |
| Weather | Open-Meteo live passed on Pi using the saved location. OpenWeatherMap needs your own API key and remains unverified |
| Calendar | Mock/demo by default. The existing private subscription fetched successfully on Pi, with 0 events in the current window. Its URL stays private; complete recurrence/multi-day semantics are not claimed |
| Custom | Manual content, not live data |

### Acceptance And Review Records

- **[v0.1.2 release acceptance](docs/v0.1.2.md)**. The GitHub Release includes redacted device acceptance JSON for the final version/commit.
- [v0.1.2-rc.1 candidate and pending checks](docs/v0.1.2-rc.1.md)
- [Font review and before/after evidence](docs/font-review-2026-11-11.md). After downloading the repository, open the [interactive comparison](piboard/review_artifacts/font-review-2026-11-11/index.html) locally; GitHub's file viewer does not execute the HTML.
- [Visual and interaction review](docs/visual-review-2026-11-11.md) / [Runtime audit and known gaps](docs/project-audit-2026-11-10.md)
- [Historical v0.1-demo record](docs/v0.1-demo.md)
- [v0.1.1 release acceptance](docs/v0.1.1.md)

Review records retain their original language; the runtime audit is in Chinese.

### Security

Never commit `piboard/data/state.json`, `piboard/BUILD_INFO`, private iCal URLs, personal calendar links, API tokens, real keys, personal filesystem paths, actual LAN IP addresses or private Pi hostnames. Start your local configuration from `piboard/data/state.example.json`; keep the resulting runtime state private.

### Current Limitations

- This release adds no pages or data-source types. Five-page switching, integrated regressions and configuration restoration passed on Pi. Public screenshots are safe offscreen Pi renders, not panel photographs.
- Calendar defaults to mock data. Private subscriptions are not synced with source code. Recurring and multi-day events are not fully supported.
- Live train data depends on public Huxley2-compatible service availability. The default is a short-term replacement endpoint, with the original Azure endpoint retained as a fallback.
- The console has no authentication and is intended only for a trusted LAN. Do not expose it directly to the public Internet. Browser geolocation requires a secure context; use manual city entry over ordinary LAN HTTP.
- Write APIs now validate object structure, field types and enum values. Concurrent settings conflicts and OpenWeatherMap overview compatibility remain known gaps; see the runtime audit.
- Resource usage does not meet every design target: a short sample measured about 6.4% of one CPU core and 115 MiB RSS. This is not a long-duration performance certification.
- Changing between portrait and landscape still requires a process restart.

For implementation details, see the [technical guide](piboard/README.md), whose main body is in Chinese.
