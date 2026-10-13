import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property var shell
    property int toolTab: 0
    ColumnLayout {
        anchors.fill: parent
        spacing: 20
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 7
                Heading { text: "创作工具"; font.pixelSize: 27 }
                Caption { text: page.toolTab === 0 ? "把图片整理成恰到好处的样子。" : "把重复的创作，整理成可复用的流程。" }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                Layout.preferredWidth: tabs.implicitWidth + 8
                Layout.preferredHeight: 44
                radius: 11
                color: Theme.subtle
                RowLayout {
                    id: tabs
                    anchors.centerIn: parent
                    spacing: 4
                    Repeater {
                        model: ["图片处理", "生成流程"]
                        delegate: MButton {
                            required property string modelData
                            required property int index
                            text: modelData
                            objectName: index === 0 ? "imageToolsTab" : "workflowTab"
                            implicitHeight: 36
                            checked: page.toolTab === index
                            onClicked: page.toolTab = index
                            background: Rectangle {
                                radius: 8
                                color: parent.checked ? Theme.surface : parent.down ? Theme.border : "transparent"
                                border.color: parent.activeFocus ? Theme.accent : "transparent"
                                Behavior on color { ColorAnimation { duration: Theme.reduced ? 0 : 120 } }
                            }
                        }
                    }
                }
            }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: page.toolTab
            ImageToolsPanel { shell: page.shell }
            WorkflowPanel { shell: page.shell }
        }
    }
}
