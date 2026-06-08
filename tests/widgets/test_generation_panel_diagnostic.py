from src.adapters.errors import Category, Diagnostic, Field
from src.widgets.generation_panel import GenerationPanel
from src.managers.queue_manager import QueueManager


def test_update_diagnostic_renders_card(qapp):
    panel = GenerationPanel(queue_manager=QueueManager())
    panel.show()
    qapp.processEvents()
    diag = Diagnostic(
        category=Category.AUTH,
        fields=(Field(name="URL", value="https://x", issue="请求地址"),),
        hint="请检查 API Key",
        original="401",
    )
    panel.update_diagnostic(diag, expand=True)
    qapp.processEvents()
    assert panel.diagnostic_frame.isVisible()


def test_update_diagnostic_none_hides_frame(qapp):
    panel = GenerationPanel(queue_manager=QueueManager())
    panel.show()
    qapp.processEvents()
    panel.update_diagnostic(None, expand=True)
    qapp.processEvents()
    assert not panel.diagnostic_frame.isVisible()
