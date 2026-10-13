__all__ = ["QueueManager", "PromptManager", "HistoryManager"]
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .history_manager import HistoryManager
    from .prompt_manager import PromptManager
    from .queue_manager import QueueManager


def __getattr__(name):
    if name == "QueueManager":
        from .queue_manager import QueueManager

        return QueueManager
    if name == "PromptManager":
        from .prompt_manager import PromptManager

        return PromptManager
    if name == "HistoryManager":
        from .history_manager import HistoryManager

        return HistoryManager
    raise AttributeError(name)
