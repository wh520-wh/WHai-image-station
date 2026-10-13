import QtQuick

Rectangle {
    id: root
    property bool animate: true
    color: Theme.subtle
    radius: 9
    clip: true
    Rectangle {
        width: parent.width
        height: parent.height
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop {
                position: 0
                color: "transparent"
            }
            GradientStop {
                position: 0.5
                color: Theme.dark ? "#154B6654" : "#A0FFFFFF"
            }
            GradientStop {
                position: 1
                color: "transparent"
            }
        }
        x: -width
        NumberAnimation on x {
            from: -root.width
            to: root.width
            duration: 1400
            loops: Animation.Infinite
            running: root.visible && root.animate && !Theme.reduced
        }
    }
}
