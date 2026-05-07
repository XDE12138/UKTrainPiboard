"""
UK Station app 装配入口。

将 uk_station 专属的 layout 构建和 Registry 注册收拢到此模块，
使 main.py 无需感知 uk_station 的内部细节（布局种类、类名等）。

本轮定位：临时适配层。
Task 3+ 可将此函数替换为更完整的 App 自描述 / 自注册机制，
届时 main.py 只需调用通用接口，无需感知任何具体 App 细节。
"""
from host.registry import Registry


def setup(registry: Registry, providers: dict, app_settings: dict) -> dict:
    """
    构建 UK Station 所需 layouts，向 Registry 注册 UKStationApp。

    Args:
        registry:     模块级 Registry 单例
        providers:    已构建的 provider 实例字典
        app_settings: app 级设置字典（color_theme, animations_enabled），
                      由 main.py 通过 app_state.get_app_settings("uk_station") 传入。
                      此函数不直接读取 app_state，保持纯装配函数语义。

    Returns:
        layouts dict（键为 layout_id，值为 BaseLayout 实例），供 ScreenHost 使用
    """
    from config import COLOR_THEMES, COLORS
    from layouts.single import SingleLayout
    from layouts.dual import DualLayout
    from layouts.carousel import CarouselLayout
    from apps.uk_station.app import UKStationApp

    colors = COLOR_THEMES.get(app_settings.get("color_theme", "amber"), COLORS)
    anim_enabled = app_settings.get("animations_enabled", True)

    layouts = {
        "single":   SingleLayout(colors, anim_enabled),
        "dual":     DualLayout(colors, anim_enabled),
        "carousel": CarouselLayout(colors, anim_enabled),
    }
    registry.register_app("uk_station", UKStationApp)

    # Task 3：过渡阶段的 app-coupled 注册点。
    # 让 train 链路进入真实 registry，不是最终全局 source/binding 路由归属。
    # 当后续 Task 建立更完整的路由机制时，这几行会迁移到更合适的位置。
    from sources.train import TrainSource
    from bindings.train_to_uk import TrainToUKBinding
    registry.register_source("train", TrainSource)
    registry.register_binding("train_to_uk", TrainToUKBinding)

    # Task 4：weather 链路注册，与 train 同位置，过渡阶段 app-coupled 注册点。
    from sources.weather import WeatherSource
    from bindings.weather_to_uk import WeatherToUKBinding
    registry.register_source("weather", WeatherSource)
    registry.register_binding("weather_to_uk", WeatherToUKBinding)

    # Task 5：calendar 链路注册，过渡阶段 app-coupled 注册点。
    from sources.calendar import CalendarSource
    from bindings.calendar_to_uk import CalendarToUKBinding
    registry.register_source("calendar", CalendarSource)
    registry.register_binding("calendar_to_uk", CalendarToUKBinding)

    # Overview MVP：跨域摘要输出到现有 info template。
    # 当前由 MockProvider 直接使用 binding；注册点先纳入 uk_station registry。
    from bindings.overview_to_uk import OverviewToUKBinding
    registry.register_binding("overview_to_uk", OverviewToUKBinding)

    return layouts
