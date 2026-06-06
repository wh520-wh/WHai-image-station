import os

APP_NAME = "imageMaker"
APP_VERSION = "1.0.0"

USER_HOME = os.path.expanduser("~")
DEFAULT_SAVE_DIR = os.path.join(USER_HOME, "Pictures", "imageMaker")
DEFAULT_DB_PATH = os.path.join(USER_HOME, ".imageMaker", "data.db")
DEFAULT_KEY_FILE = os.path.join(USER_HOME, ".imageMaker", "key.enc")

GENERATIONS_DIR = os.path.join(DEFAULT_SAVE_DIR, "generations")
THUMBNAILS_DIR = os.path.join(DEFAULT_SAVE_DIR, "thumbnails")

MAX_CONCURRENT_TASKS = 3
DEFAULT_CONCURRENT = 3

TASK_STATUS = {
    "WAITING": "等待中",
    "PENDING": "待处理",
    "GENERATING": "生成中",
    "COMPLETED": "已完成",
    "FAILED": "失败",
}

PLATFORM_DEFAULTS = {
    "openai": {
        "name": "DALL·E / OpenAI Compatible",
        "api_base_url": "https://api.openai.com/v1",
        "model_default": "dall-e-3",
    },
    "stability": {
        "name": "Stable Diffusion",
        "api_base_url": "https://api.stability.ai/v1",
        "model_default": "stable-diffusion-xl-1024-v1-0",
    },
    "midjourney": {
        "name": "Midjourney",
        "api_base_url": "https://api.midjourney.com/v1",
        "model_default": "midjourney",
    },
}

SIZE_OPTIONS = {
    "openai": [
        ("1024x1024", "1:1 正方形"),
        ("1792x1024", "16:9 横屏"),
        ("1024x1792", "9:16 竖屏"),
    ],
    "stability": [
        ("1024x1024", "1:1 正方形"),
        ("1280x720", "16:9 横屏"),
        ("768x1024", "3:4 竖屏"),
    ],
}

QUALITY_OPTIONS = {
    "openai": ["标准", "HD"],
    "stability": ["标准", "艺术"],
}

REQUEST_TIMEOUT = 300
RETRY_COUNT = 3
RETRY_BACKOFF = [1, 3, 10]
