from src.widgets.theme import COLORS, RADIUS, button_style, card_style, compact_input_style, input_style


def test_theme_uses_sky_sunset_palette():
    assert COLORS["sky"] == "#48C6F0"
    assert COLORS["panel_alt"] == "#FFF0D6"
    assert COLORS["sunset"] == "#E87828"
    assert COLORS["background"] == "#F7EFE2"
    assert COLORS["panel"] == "#FFF8EC"
    assert COLORS["primary"] == "#E87828"
    assert COLORS["accent"] == "#5BC8F0"
    assert COLORS["text"] == "#2F3538"
    assert RADIUS["card"] == 18


def test_primary_button_uses_sunset_accent():
    style = button_style("primary")
    assert "#E87828" in style
    assert "#667EEA" not in style


def test_spacing_dict_uses_4px_grid():
    from src.widgets.theme import SPACING
    for key, value in SPACING.items():
        assert value % 4 == 0, f"SPACING['{key}'] = {value} is not a multiple of 4"


def test_updated_colors_are_valid_hex():
    from src.widgets.theme import COLORS
    hex_colors = {k: v for k, v in COLORS.items() if v.startswith("#")}
    for key, value in hex_colors.items():
        assert len(value) == 7, f"COLORS['{key}'] = {value} is not a valid hex color"
        int(value[1:], 16)  # raises ValueError if invalid hex


def test_accent_brighter_than_muted():
    from src.widgets.theme import COLORS
    accent_lum = int(COLORS["accent"][1:], 16)
    muted_lum = int(COLORS["muted"][1:], 16)
    assert accent_lum > muted_lum


def test_card_style_is_scoped_to_marked_containers():
    style = card_style()

    assert "QFrame {" not in style
    assert "QWidget {" not in style
    assert "[imageMakerCard=\"true\"]" in style


def test_input_style_resets_editable_combo_inner_line_edit():
    style = input_style()

    assert "QComboBox QLineEdit" in style
    assert "border: none" in style
    assert "background: transparent" in style


def test_compact_combo_style_removes_native_dropdown_underline():
    style = compact_input_style()

    assert "QComboBox::drop-down" in style
    assert "border: none" in style
    assert "subcontrol-origin: padding" in style
    assert "QComboBox::down-arrow" in style
    assert "border-top:" in style
    assert "padding: 4px 28px 4px 8px" not in style
