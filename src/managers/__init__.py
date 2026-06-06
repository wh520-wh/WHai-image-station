__all__ = ["QueueManager", "PromptManager", "HistoryManager"]


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
