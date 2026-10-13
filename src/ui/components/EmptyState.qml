import QtQuick
import QtQuick.Layouts

Item {
    property string title: ""
    property string detail: ""
    property string iconName: "gallery"
    implicitHeight: 200
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 40, 400)
        spacing: 14
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 52
            height: 52
            radius: 16
            color: Theme.subtle
            Icon {
                anchors.centerIn: parent
                name: iconName
                width: 25
                height: 25
            }
        }
        Heading {
            text: title
            font.pixelSize: 16
            Layout.alignment: Qt.AlignHCenter
        }
        Caption {
            text: detail
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
