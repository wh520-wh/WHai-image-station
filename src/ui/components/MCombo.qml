import QtQuick
import QtQuick.Controls.Basic

ComboBox {
    id: root
    implicitHeight: 42
    implicitWidth: 180
    font.family: Theme.font
    font.pixelSize: 13
    leftPadding: 12
    rightPadding: 34
    contentItem: Text {
        text: root.displayText
        font: root.font
        color: root.enabled ? Theme.ink : Theme.muted
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Icon {
        name: "chevron"
        x: root.width - 28
        y: (root.height - height) / 2
        width: 16
        height: 16
    }
    background: Rectangle {
        radius: 8
        color: Theme.surface
        border.color: root.activeFocus ? Theme.accent : Theme.border
        border.width: root.activeFocus ? 2 : 1
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: root.width
        height: 40
        text: root.textRole ? modelData[root.textRole] : modelData
        font: root.font
        contentItem: Text {
            text: parent.text
            color: Theme.ink
            font: root.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        highlighted: root.highlightedIndex === index
        background: Rectangle {
            color: parent.highlighted ? Theme.accentWash : "transparent"
            radius: 6
        }
    }
    popup: Popup {
        y: root.height + 5
        width: root.width
        padding: 5
        implicitHeight: Math.min(contentItem.implicitHeight + 10, 310)
        transformOrigin: Item.Top
        background: Rectangle {
            radius: 10
            color: Theme.surface
            border.color: Theme.border
        }
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        enter: Transition {
            ParallelAnimation {
                NumberAnimation {
                    property: "opacity"
                    from: 0
                    to: 1
                    duration: 120
                }
                NumberAnimation {
                    property: "scale"
                    from: Theme.reduced ? 1 : 0.98
                    to: 1
                    duration: 160
                    easing.type: Easing.OutCubic
                }
            }
        }
        exit: Transition {
            NumberAnimation {
                property: "opacity"
                to: 0
                duration: 80
            }
        }
    }
}
