from .base import BaseAdapter, GenerationResult

ADAPTER_REGISTRY: dict[str, type[BaseAdapter] | BaseAdapter] = {}


def register_adapter(adapter_cls: type[BaseAdapter], platform_id: str | None = None):
    """注册适配器类（延迟实例化）"""
    pid = platform_id or adapter_cls.platform_id
    ADAPTER_REGISTRY[pid] = adapter_cls


def init_adapters():
    """初始化适配器注册表（不实例化，按需懒加载）"""
    from .midjourney_adapter import MidjourneyAdapter
    from .native_adapters import FluxAdapter, GeminiAdapter, MiniMaxAdapter
    from .openai_adapter import OpenAIAdapter
    from .stability_adapter import StabilityAdapter

    register_adapter(OpenAIAdapter)
    register_adapter(OpenAIAdapter, "custom")
    register_adapter(StabilityAdapter)
    register_adapter(MidjourneyAdapter)
    register_adapter(GeminiAdapter)
    register_adapter(MiniMaxAdapter)
    register_adapter(FluxAdapter)


def get_adapter(platform_id: str) -> BaseAdapter | None:
    """延迟获取适配器实例（按需实例化）"""
    cls = ADAPTER_REGISTRY.get(platform_id)
    if cls is None:
        return None
    if not isinstance(cls, type):
        return cls
    # 实例化并缓存
    instance = cls()
    ADAPTER_REGISTRY[platform_id] = instance
    return instance


def get_all_adapters() -> list[BaseAdapter]:
    """获取所有已实例化的适配器"""
    return [v for v in ADAPTER_REGISTRY.values() if isinstance(v, BaseAdapter)]


__all__ = [
    "BaseAdapter",
    "GenerationResult",
    "ADAPTER_REGISTRY",
    "init_adapters",
    "get_adapter",
    "get_all_adapters",
]
