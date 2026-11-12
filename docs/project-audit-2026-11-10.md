# 项目检查与修复记录（2026-11-10）

后续状态（2026-11-12）：第 1 项的 REST/WebSocket 写入结构、字段类型和枚举校验已在 `v0.1.2` 补齐，新增 8 项回归；这不等于完整鉴权或业务语义校验。整合部署和真实数据复测见 [v0.1.2 验收记录](v0.1.2.md)。下文保留原审计时点的发现。

## 范围与边界

检查了项目结构、应用装配、状态及迁移、后台调度、Source/Binding/Provider、布局与动画、字体和板面绘制、网页前后端、部署入口、预览/截图工具、现有测试和说明资料。图片、字体文件及历史验收记录作为资产保留，不据其年龄判定为冗余。

本次进行本地离线测试及本机 HTTP/WebSocket 实连验证；没有连接树莓派、修改其运行配置或重新核验外部数据服务。既有未跟踪文件 `handover_summary.md` 未改动。不保证穷尽所有运行环境及输入组合。

## 已修复

| 位置 | 原问题 | 修改及验证 |
|---|---|---|
| `piboard/main.py`、`web/server.py` | 单线程 HTTP 服务被 WebSocket 长连接占用；连接空闲 30 秒后主动断开 | 启用请求线程，移除应用层接收超时；保留 WebSocket ping。通过本机真实连接验证并行 HTTP 响应 |
| `data/fetcher.py` | 同一来源可重复入队/并发，慢请求可积压；停止时未等调度线程退出 | 每来源最多一个运行/排队任务及一次合并后续刷新；后续请求仍使用最新配置；停止时取消待刷新并等待调度退出。两个工作线程上限保留 |
| `state.py` | 损坏配置可在异常前覆盖部分全局状态；部分 app 配置缺少默认键 | 在副本完成结构校验和补默认后整体替换，失败保留原状态 |
| `state.py` | 旧天气配置先合并默认值，导致手动城市误变成 auto；旧 London 特殊迁移也失效 | 在补默认值时保留旧配置意图，覆盖 v0/v1 恢复路径；保留原有“旧 London 默认转 auto”策略 |
| `state.py` | `save('state.json')` 因目录名为空而保存失败 | 无目录部分时使用当前目录 |
| `apps/system_status/app.py` | 排版按物理屏幕宽高计算，旋转后的逻辑画布位置错误 | 按实际传入的绘制画布尺寸构建并缓存文字 |
| `apps/uk_station/app.py`、`layouts/carousel.py` | 没有 ticker/clock 时，动画轮播和行翻页没有定时唤醒 | 向 Host 提供下一次切换/翻页截止时间，等待期间仍可休眠 |
| `layouts/single.py`、`dual.py`、`carousel.py` | 同一来源内容行数变更时，翻页器还沿用旧行数 | 行数变化时重新配置分页；测试覆盖三种布局 |
| `providers/mock.py` | 列车失败板和过期缓存仍被概览标成 LIVE；无关联来源的列车演示缺少 demo 标签 | 失败显示 WAIT，过期显示 STALE；独立列车演示明确 DEMO/mock |
| `bindings/calendar_to_uk.py`、`providers/mock.py` | live 日历缓存没有过期时间；概览统一减 600 秒反推所有来源时间 | 日历缓存 300 秒过期；按来源默认刷新周期反推采集时间 |
| `install.sh`、`deployment/sync-to-pi.sh` | 安装服务用户写死 pi、提示端口仍为 5000；自定义服务名只用于启动，安装文件名未同步 | 使用安装用户、提示 8080，并按指定服务名安装。仅完成 shell 语法验证，未在 Pi 执行 |
| `config.py`、README、Host 注释 | 空的 `REGISTERED_PROVIDER_CLASSES` 无任何调用；“零改动现有代码”和线程说明失实 | 删除空占位注册表；修正注册说明、线程模型、方向注释及可移植测试命令 |

## 留待审查

以下未自动扩展功能或批量删除。涉及明确缺陷的项目也注明了未直接修改的原因及建议。

### 1. 高优先级：写入 API 缺少统一字段校验

- 位置：`piboard/web/server.py`、`piboard/state.py` 各写入入口。
- 证据：JSON 对象之外的数据仍进入 `.get()`/`.items()`；layout/slots 与来源字段没有按 schema 验证。比如 slots 内放对象会在 UKStationApp 的字典查找处出错；custom 标题非字符串也可能进入渲染器。
- 影响：错误调用可返回 500，部分错误配置可持久化并使显示主循环出错。本轮状态文件校验不能替代运行时写入校验。
- 建议：REST 和 WebSocket 共用同一套校验，在修改状态前拒绝无效值。需要统一约定旧接口、未知扩展字段及无效值的拒绝/转换规则，因此没有临时加一套只覆盖部分路由的规则。

### 2. 中优先级：OpenWeatherMap 输出与概览读取契约不同

- 位置：`piboard/providers/weather.py::_fetch_owm()` 与 `providers/mock.py::_overview_weather_from_content()`。
- 证据：OWM 把天气描述放在 title、体感文字放在 subtitle；概览却把 title 当温度、subtitle 当天气描述。OWM 预报只取正午条目，也没有计算整日最高/最低温。
- 建议：统一为 WeatherObservation → WeatherToUKBinding，或明确保留两种详情样式并让概览读取原始观测值。没有 API Key，本次未做 OWM 实连验收；保留该付费/密钥路径供审查。

### 3. 中优先级：日历只处理原始 VEVENT，未展开重复事件

- 位置：`piboard/sources/calendar.py::_live_data()`。
- 证据：直接遍历 VEVENT、读取 DTSTART/DTEND；未处理 RRULE、EXDATE、RECURRENCE-ID、跨日覆盖区间或 DURATION。
- 影响：重复事件起始日期早于窗口时，其后续实例可能不显示；跨日事件也不按覆盖日期展示。
- 待决定：是否承诺完整订阅日历语义。若需要，应引入带时区的重复展开及例外处理，并用公开测试日历验收，不能只补一个简单循环。

### 4. 中优先级：设置/表单在异步更新时仍有覆盖可能

- 位置：`piboard/web/static/app.js` 的 `pushSettings()`、`applyStateToUI()`、`saveSource()`，以及服务器 source-config 写入路由。
- 证据：设置保存会同时提交全部 app/device 字段；状态推送会重绘设置和槽位；来源配置先持久化，再等待刷新，刷新失败直接返回错误且跳过配置变化广播。
- 待决定：采用字段级保存、版本冲突提示，还是“最后提交者覆盖”；同时区分“配置保存成功”和“数据刷新失败”。目前保留既有交互，避免未设计清楚的并发规则影响多设备使用。

### 5. 部署默认值与失败恢复策略

- 位置：`piboard/install.sh`、`piboard/piboard.service`、`deployment/piboard-kmsdrm.service`、`deployment/sync-to-pi.sh`。
- 证据：安装脚本与旧 service 没有新版模板的固定旋转/竖屏参数和 display-manager 冲突配置；同步脚本先停服务再原地同步，途中失败没有回滚。新版模板固定 `--portrait`，因此会覆盖网页保存的 landscape，即使重启也一样。
- 待决定：安装入口是否全部统一为当前竖装屏专用配置，还是支持不同安装方向；失败部署是否要保留完整上一版目录用于回滚。没有改用户的设备启动策略。

### 6. 性能需硬件测量，不据代码外观声称过慢

- 位置：`board/dot_font.py` 字符缓存、`board/board_renderer.py` ticker 分页，以及 `docs/v0.1.1.md` 的设备记录。
- 证据：字符缓存没有数量上限；ticker 分页在查询时重算。历史验收 RSS 约 119 MiB，超过 README 的 <80MB 目标，但这是历史记录，并非当前版本测量。
- 建议：在 Pi 上测长时间运行、中文长文本和动画模式的 RSS/CPU，再决定缓存上限和分页缓存。当前没有足够证据支持整体性能重写。

### 7. 可删除候选，需要确认保留用途

- `piboard/renderer.py`：明确 deprecated，主入口已由 ScreenHost 替代；保留理由写的是“回归对照”。可移入历史目录或在确认不再需要后删除。
- `providers/train.py`、`weather.py`、`calendar_provider.py`：不能整批删除。bridge 仍复用它们的 schema；Train 的 TransportAPI 和 Weather 的 OWM 仍委托旧实现。应先拆出 schema/仍在用的路径，再删除真正无调用的旧代码。
- `review_artifacts/`、根目录部署截图、两种 bundled 字体：可能是验收/风格对照资产，没有按文件年龄或相似文件名自动删除。
- `handover_summary.md`：是本轮开始前已有的未跟踪文件，描述旧 Chromium kiosk 且含设备信息，与当前 KMSDRM 主线不符。保留原文件；若打算提交，先确认用途并脱敏。
- 若清理注释，`sources/base.py`、`bindings/base.py`、`host/registry.py` 尚有早期 Task 脚手架说明；历史审计报告中的旧结论应视为历史记录，不能直接当现状待办。

### 8. 控制台访问边界

- 位置：`config.py::WEB_HOST` 与 `web/server.py` 状态/配置接口。
- 当前监听所有网卡，没有登录；状态和来源接口返回配置，包括密钥或日历订阅地址。
- 待决定：是否继续只用于受信任局域网，还是需要登录及配置脱敏。没有替用户新增认证门槛或修改监听地址。

## 验证

本机使用已有的 Python 3.9.18 / pygame 2.6.1 环境：

```sh
python3 -m compileall -q piboard tests
python3 tests/smoke_v0_1_1.py
python3 tests/smoke_visual.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n piboard/install.sh piboard/deployment/sync-to-pi.sh
git diff --check
```

- 原有 smoke：6 项；视觉/排版 smoke：4 项。
- 新增回归：17 项，涉及状态恢复、刷新合并/停止、真实性标签、分页唤醒/更新、WebSocket 和旋转逻辑画布。
- 回归检查还在临时副本上使用修改前源码运行，确认能暴露旧行为；不修改工作区进行此项对照。
- 额外做了临时本机 WebSocket 实连：连接保持期间 `/api/state` 返回 200，随后同一 WebSocket 仍可收到状态消息。
- Pi 上安装、KMSDRM 实屏、外部 live 服务和资源占用不在本次验证结论内。
