__all__ = [
    "MainWindow", "PromptPanel", "GenerationPanel", "HistoryPanel",
    "SettingsDialog", "ImageViewer", "PromptCard", "TaskCard",
]


def __getattr__(name):
    if name == "MainWindow":
        from .main_window import MainWindow
        return MainWindow
    if name == "PromptPanel":
        from .prompt_panel import PromptPanel
        return PromptPanel
    if name == "GenerationPanel":
        from .generation_panel import GenerationPanel
        return GenerationPanel
    if name == "HistoryPanel":
        from .history_panel import HistoryPanel
        return HistoryPanel
    if name == "SettingsDialog":
        from .settings_dialog import SettingsDialog
        return SettingsDialog
    if name == "ImageViewer":
        from .image_viewer import ImageViewer
        return ImageViewer
    if name in {"PromptCard", "TaskCard"}:
        from .components.prompt_card import PromptCard, TaskCard
        return {"PromptCard": PromptCard, "TaskCard": TaskCard}[name]
    raise AttributeError(name)
