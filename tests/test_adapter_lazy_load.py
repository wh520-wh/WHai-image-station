# tests/test_adapter_lazy_load.py
import pytest

def test_get_adapter_returns_none_without_init():
    """验证在不调用init_adapters()时，get_adapter返回None"""
    from src import adapters

    # 清空注册表
    adapters.ADAPTER_REGISTRY.clear()

    # 在 init_adapters() 前，get_adapter 应该返回 None
    result = adapters.get_adapter('openai')
    assert result is None, "get_adapter should return None before init_adapters()"

def test_adapter_classes_registered_not_instantiated():
    """验证init_adapters()注册类而非实例"""
    # 注意: httpx 会被 base.py 导入，所以我们检查具体的适配器模块
    from src.adapters import init_adapters, ADAPTER_REGISTRY

    # 初始状态：具体适配器模块未导入
    # （由于 pytest 收集机制，某些模块可能已预加载，我们主要检查类vs实例）
    init_adapters()

    # init_adapters 只是注册类，不实例化
    # 验证 ADAPTER_REGISTRY 存储的是类引用
    for key, value in ADAPTER_REGISTRY.items():
        assert isinstance(value, type), f"{key} should be a class, not instance"

def test_get_adapter_instantiates_on_demand():
    """验证get_adapter按需实例化"""
    from src.adapters import init_adapters, get_adapter, ADAPTER_REGISTRY

    init_adapters()

    # 此时 openai_adapter 模块已加载，但适配器是类引用
    openai_cls = ADAPTER_REGISTRY.get('openai')
    assert isinstance(openai_cls, type), "Should be a class before get_adapter"

    # 获取适配器时才实例化
    adapter = get_adapter('openai')
    assert adapter is not None, "Should get a valid adapter"

    # 之后 registry 中的 openai 变成实例
    assert not isinstance(ADAPTER_REGISTRY.get('openai'), type), "Should be instance after get_adapter"

def test_get_all_adapters_returns_only_instantiated():
    """验证get_all_adapters只返回已实例化的适配器"""
    from src.adapters import init_adapters, get_all_adapters, ADAPTER_REGISTRY

    init_adapters()

    # 获取所有适配器 - 这会实例化所有注册但未实例化的
    adapters_list = get_all_adapters()

    # 验证返回的都是 BaseAdapter 实例
    from src.adapters.base import BaseAdapter
    for adapter in adapters_list:
        assert isinstance(adapter, BaseAdapter), f"Expected BaseAdapter instance, got {type(adapter)}"

def test_same_adapter_instance_cached():
    """验证同一platform_id返回同一实例"""
    from src.adapters import init_adapters, get_adapter, ADAPTER_REGISTRY

    init_adapters()

    # 清空已实例化的（如果需要测试初始状态）
    for key in list(ADAPTER_REGISTRY.keys()):
        if not isinstance(ADAPTER_REGISTRY[key], type):
            del ADAPTER_REGISTRY[key]

    # 首次获取
    adapter1 = get_adapter('openai')
    # 再次获取
    adapter2 = get_adapter('openai')

    assert adapter1 is adapter2, "Should return same cached instance"