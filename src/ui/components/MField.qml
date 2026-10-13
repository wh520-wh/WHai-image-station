import QtQuick
import QtQuick.Controls.Basic

TextField {
    id: root
    implicitHeight: 42
    leftPadding: 12
    rightPadding: 12
    color: Theme.ink
    placeholderTextColor: Theme.muted
    selectionColor: Theme.accentWash
    selectedTextColor: Theme.ink
    font.family: Theme.font
    font.pixelSize: 13
    selectByMouse: true
    background: Rectangle {
        color: Theme.surface
        radius: 8
        border.color: root.activeFocus ? Theme.accent : Theme.border
        border.width: root.activeFocus ? 2 : 1
        Behavior on border.color {
            ColorAnimation {
                duration: 120
            }
        }
    }
}
