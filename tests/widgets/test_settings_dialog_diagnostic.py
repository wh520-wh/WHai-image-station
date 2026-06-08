from src.adapters.errors import Category, Diagnostic, Field
from src.widgets.settings_dialog import SettingsDialog


def test_settings_dialog_validation_failure_renders_card(qapp, monkeypatch):
    from src.adapters import init_adapters
    init_adapters()
    diag = Diagnostic(
        category=Category.AUTH,
        fields=(Field(name="URL", value="https://x", issue="请求地址"),),
        hint="请检查 API Key",
        original="401",
    )
    dlg = SettingsDialog(db=None)
    dlg.show()
    dlg._show_validation_diagnostic(diag)
    assert dlg.validation_card is not None
    assert dlg.validation_card.isVisible()
