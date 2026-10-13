import QtQuick

Item {
    implicitWidth: 34
    implicitHeight: 34
    Accessible.role: Accessible.Graphic
    Accessible.name: "WHai 图片生成"
    Image {
        anchors.fill: parent
        source: Qt.resolvedUrl("../assets/logo.png")
        sourceSize.width: Math.ceil(width * 2)
        sourceSize.height: Math.ceil(height * 2)
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }
}
