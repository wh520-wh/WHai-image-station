"""Shared pytest fixtures and configuration for imageMaker test suite."""
import os
import sys
import asyncio
import pytest


@pytest.fixture(scope="session")
def qapp():
    """Provide a single QApplication instance for the whole test session."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
    app.quit()


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database file path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def sample_task():
    """Provide a sample GenerationTask for tests."""
    from src.models.task import GenerationTask
    return GenerationTask(platform_id="openai", prompt="a cat in space")


@pytest.fixture
def mock_config():
    """Provide a mock PlatformConfig with valid fields."""
    from src.models.platform_config import PlatformConfig
    return PlatformConfig(
        api_key="test-key",
        api_base_url="https://api.example.com/v1",
        auth_preset="openai",
        interface_type="openai_images",
        model_name="dall-e-3",
        response_format="openai",
    )
