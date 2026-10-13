import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Button {
    id: root
    property bool primary: false
    property bool quiet: false
    property bool destructive: false
    property string iconName: ""
    implicitHeight: 40
    implicitWidth: contentItem.implicitWidth + 28
    padding: 14
    font.family: Theme.font
    font.pixelSize: 13
    font.weight: Font.DemiBold
    Accessible.name: text
    scale: down && !Theme.reduced ? 0.97 : 1
    Behavior on scale {
        enabled: !Theme.reduced
        SpringAnimation {
            spring: 5
            damping: 1
            epsilon: 0.002
        }
    }
    background: Rectangle {
        radius: 9
        color: root.primary ? (root.down ? Qt.darker(Theme.accent, 1.12) : Theme.accent) : root.down ? Theme.border : root.hovered ? Theme.subtle : root.quiet ? "transparent" : Theme.surface
        border.color: root.activeFocus ? Theme.accent : root.primary || root.quiet ? "transparent" : Theme.border
        border.width: root.activeFocus ? 2 : 1
        opacity: root.enabled ? 1 : 0.45
        Behavior on color {
            ColorAnimation {
                duration: 100
            }
        }
    }
    contentItem: RowLayout {
        spacing: 8
        opacity: root.enabled ? 1 : 0.45
        Icon {
            visible: root.iconName !== ""
            name: root.iconName
            tint: root.primary ? Theme.accentText : Theme.muted
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
        }
        Text {
            text: root.text
            color: root.primary ? Theme.accentText : root.destructive ? Theme.danger : Theme.ink
            font: root.font
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
        }
    }
}
