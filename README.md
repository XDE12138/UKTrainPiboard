# CC-UK-TR / PiBoard

PiBoard 是运行在 Raspberry Pi Zero 2W 上的个人信息显示系统，用 Python、pygame 和 SDL2 `kmsdrm` 直接渲染英国火车站 LED 点阵风格看板。

当前版本：`v0.1.1`，真实数据与发布验收修正版。

![PiBoard overview demo](piboard-deploy-final-overview.png)

![PiBoard weather demo](piboard-deploy-weather.png)

## 能展示什么

- Overview：天气、日程、列车状态的综合摘要。
- Train：英国铁路出发板样式；mock 模式明确标为 demo，Huxley2 live 路径已实现但本次发布不把它写成已验收 live。
- Weather：无 OpenWeatherMap API Key 时走 Open-Meteo live；有 Key 时保留 OpenWeatherMap 路径。
- Calendar：有 iCal URL 时走日历 live；未配置时显示 mock 日程。
- Custom：手工编辑的自定义看板，不属于 live 数据源。

Web 控制台端口固定为 `8080`，常用检查端点为 `/api/state`、`/api/device-status` 和 `/api/version`。

## 本地运行

```bash
cd piboard
pip install -r requirements.txt
python3 main.py --window
```

打开 `http://localhost:8080` 查看 Web 控制台。

最小 smoke：

```bash
/opt/anaconda3/bin/python3 -m compileall -q piboard
/opt/anaconda3/bin/python3 tests/smoke_v0_1_1.py
```

## 部署到 Pi

推荐使用同步脚本：

```bash
piboard/deployment/sync-to-pi.sh <pi-user@pi-host-or-ip>
```

也可以设置 `PIBOARD_PI_HOST=<pi-user@pi-host-or-ip>` 后运行同一脚本。脚本会同步 `piboard/`，安装 `piboard.service`，并在 Pi 运行目录生成 `BUILD_INFO`。运行时版本可通过：

```bash
curl http://<pi-host-or-ip>:8080/api/version
curl http://<pi-host-or-ip>:8080/api/device-status
```

Pi service 使用 direct `kmsdrm`：

```ini
ExecStart=/usr/bin/python3 /home/<pi-user>/CC-UK-TR/piboard/main.py --portrait --display-rotate 90
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=SDL_AUDIODRIVER=dummy
```

## 数据真实性边界

| 页面 | v0.1.1 状态 |
|---|---|
| Overview | 混合摘要；每个来源在板面/文档中按 LIVE / MOCK / WAIT 标注 |
| Train | 默认 mock/demo；Huxley2 路径已实现，本次本地公网请求返回 HTTP 500，不能宣称 live 已验收 |
| Weather | Open-Meteo live 已本地验证；OpenWeatherMap 需要用户自己的 API Key |
| Calendar | 默认 mock/demo；iCal live 需要用户提供非公开订阅 URL，本次不宣称 live 已验收 |
| Custom | 手工内容，不是 live 数据 |

## 验收记录

- `v0.1-demo` 历史记录：[docs/v0.1-demo.md](docs/v0.1-demo.md)
- `v0.1.1` 发布验收记录：[docs/v0.1.1.md](docs/v0.1.1.md)

## 安全说明

不要提交 `piboard/data/state.json`、`piboard/BUILD_INFO`、私有 iCal URL、个人日历链接、API token、真实密钥、本机路径、真实 LAN IP 或真实 Pi 主机名。需要配置时从 `piboard/data/state.example.json` 复制到本地运行态。

## 当前限制

- v0.1.1 不新增页面和数据源，只收口现有演示与发布验收。
- Calendar live 需要用户提供安全的公开测试 iCal；默认配置是 mock。
- Huxley2 live 路径由公开服务可用性决定，本次本地公网请求未通过。
- 运行时横竖屏切换仍需要重启进程。

更多实现细节见 [piboard/README.md](piboard/README.md)。
