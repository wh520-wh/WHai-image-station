import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property var shell
    readonly property var s: studio.state
    ColumnLayout {
        anchors.fill: parent
        spacing: 22
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 7
                Heading {
                    text: "提示词模板"
                    font.pixelSize: 27
                }
                Caption {
                    text: "收藏好用的提示词，同时记住来源和生成参数。"
                }
            }
            Item {
                Layout.fillWidth: true
            }
            MButton {
                text: "去创作并保存模板"
                iconName: "create"
                onClicked: shell.currentPage = "create"
            }
        }
        MField {
            id: search
            Layout.fillWidth: true
            placeholderText: "搜索模板名称、分类或提示词"
        }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 12
            model: s.prompts.filter(x => !search.text || (x.name + x.prompt + (x.category || "")).toLowerCase().indexOf(search.text.toLowerCase()) >= 0)
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width
                height: promptColumn.implicitHeight + 36
                radius: 12
                color: Theme.surface
                border.color: Theme.border
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 24
                    ColumnLayout {
                        id: promptColumn
                        Layout.fillWidth: true
                        spacing: 9
                        Heading {
                            text: modelData.name
                            font.pixelSize: 16
                        }
                        Caption {
                            text: modelData.prompt
                            color: Theme.ink
                            font.pixelSize: 13
                            Layout.fillWidth: true
                            maximumLineCount: 3
                            elide: Text.ElideRight
                        }
                        Caption {
                            text: modelData.category || "未分类"
                        }
                    }
                    MButton {
                        text: "使用模板"
                        onClicked: studio.usePrompt(modelData)
                    }
                    MButton {
                        text: "删除"
                        destructive: true
                        quiet: true
                        onClicked: shell.confirm("删除模板「" + modelData.name + "」？", () => studio.deletePrompt(modelData.id))
                    }
                }
            }
            EmptyState {
                anchors.fill: parent
                visible: parent.count === 0
                title: "留住你的灵感"
                detail: "在创作页填写提示词，再选择「存为模板」。"
                iconName: "prompts"
            }
        }
    }
}
