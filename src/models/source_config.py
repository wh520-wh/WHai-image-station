from dataclasses import dataclass, field


@dataclass
class SourceConfig:
    id: str
    name: str
    interface_type: str = "openai_images"
    auth_preset: str = "openai"
    api_base_url: str = ""
    api_key: str = ""
    custom_headers: dict[str, str] = field(default_factory=dict)
    proxy: str | None = None
    is_active: bool = True


@dataclass
class SourceModel:
    id: str
    source_id: str
    display_name: str
    model_id: str
    default_size: str = "1024x1024"
    default_quality: str = "standard"
    default_n: int = 1
    sort_order: int = 0
    is_active: bool = True
