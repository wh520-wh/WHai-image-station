import QtQuick
import QtQuick.Controls.Basic

TextArea {
    id: root
    // Wrapped placeholder height must not feed back into the ScrollView width.
    implicitHeight: Math.max(100, contentHeight + topPadding + bottomPadding)
    color: Theme.ink
    placeholderTextColor: Theme.muted
    selectionColor: Theme.accentWash
    selectedTextColor: Theme.ink
    font.family: Theme.font
    font.pixelSize: 14
    wrapMode: TextEdit.Wrap
    selectByMouse: true
    padding: 14
    background: Rectangle {
        color: Theme.surface
        radius: 10
        border.color: root.activeFocus ? Theme.accent : Theme.border
        border.width: root.activeFocus ? 2 : 1
    }
}
