import json
import pytest

from src.adapters.errors import Category, Diagnostic, Field
from src.widgets.components.diagnostic_card import DiagnosticCard


@pytest.fixture
def sample_diag():
    return Diagnostic(
        category=Category.AUTH,
        fields=(
            Field(name="URL", value="https://api.example.com/v1/images/generations", issue="请求地址"),
            Field(name="HTTP status", value="401", issue="响应状态码"),
        ),
        hint="请检查设置中的 API Key 是否正确。",
        original="HTTP错误 401: Unauthorized",
        platform="openai",
    )


def test_card_renders_category_badge(qapp, sample_diag):
    card = DiagnosticCard(sample_diag)
    badge_text = card.badge_label.text().lower()
    assert "鉴权" in badge_text or "auth" in badge_text


def test_card_renders_fields_table(qapp, sample_diag):
    card = DiagnosticCard(sample_diag)
    visible_rows = [r for r in card.field_rows if r.isVisible()]
    assert len(visible_rows) == 2


def test_card_copy_button_writes_json(qapp, sample_diag):
    card = DiagnosticCard(sample_diag)
    card.copy_button.click()
    from PySide6.QtWidgets import QApplication
    text = QApplication.clipboard().text()
    parsed = json.loads(text)
    assert parsed["category"] == "auth"
    assert parsed["original"] == "HTTP错误 401: Unauthorized"


def test_card_hides_when_diagnostic_none(qapp):
    card = DiagnosticCard(None)
    assert not card.isVisible()


def test_card_redacted_field_serialized_as_stars(qapp):
    diag = Diagnostic(
        category=Category.AUTH,
        fields=(Field(name="Authorization", value="sk-secret", issue="invalid", redact=True),),
    )
    card = DiagnosticCard(diag)
    card.copy_button.click()
    from PySide6.QtWidgets import QApplication
    parsed = json.loads(QApplication.clipboard().text())
    assert parsed["fields"][0]["value"] == "***"


def test_card_long_original_collapses_by_default(qapp):
    diag = Diagnostic(
        category=Category.UNKNOWN,
        original="x" * 3000,
    )
    card = DiagnosticCard(diag)
    assert not card.original_text.isVisible()
    card.toggle_original()
    assert card.original_text.isVisible()
