from dataclasses import dataclass, field


@dataclass
class PlatformConfig:
    id: str
    name: str
    api_base_url: str
    api_key: str = ""
    custom_headers: dict[str, str] = field(default_factory=dict)
    model_name: str = ""
    source_id: str = ""
    model_config_id: str = ""
    source_name: str = ""
    model_display_name: str = ""
    auth_preset: str = "openai"
    interface_type: str = "openai_images"
    response_format: str = "openai"
    proxy: str | None = None
    is_active: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "api_base_url": self.api_base_url,
            "api_key": self.api_key,
            "custom_headers": self.custom_headers,
            "model_name": self.model_name,
            "source_id": self.source_id,
            "model_config_id": self.model_config_id,
            "source_name": self.source_name,
            "model_display_name": self.model_display_name,
            "auth_preset": self.auth_preset,
            "interface_type": self.interface_type,
            "response_format": self.response_format,
            "proxy": self.proxy,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlatformConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            api_base_url=data["api_base_url"],
            api_key=data.get("api_key", ""),
            custom_headers=data.get("custom_headers", {}),
            model_name=data.get("model_name", ""),
            source_id=data.get("source_id", ""),
            model_config_id=data.get("model_config_id", ""),
            source_name=data.get("source_name", ""),
            model_display_name=data.get("model_display_name", ""),
            auth_preset=data.get("auth_preset", "openai"),
            interface_type=data.get("interface_type", "openai_images"),
            response_format=data.get("response_format", "openai"),
            proxy=data.get("proxy"),
            is_active=data.get("is_active", True),
        )
