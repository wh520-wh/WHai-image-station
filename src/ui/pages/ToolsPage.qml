import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property var shell
    readonly property var s: studio.state
    property string chainId: ""
    function edit(chain) {
        chainId = chain.id;
        name.text = chain.name;
        steps.text = chain.tasks.map(x => x.prompt).join("\n");
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 24
        ColumnLayout {
            spacing: 7
            Heading {
                text: "创作工具"
                font.pixelSize: 27
            }
            Caption {
                text: "把重复的工作，整理成可复用的流程。"
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 24
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 14
                RowLayout {
                    Layout.fillWidth: true
                    Heading {
                        text: "顺序生成流程"
                        font.pixelSize: 16
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    MButton {
                        text: "新建"
                        quiet: true
                        iconName: "create"
                        onClicked: {
                            page.chainId = "";
                            name.text = "";
                            steps.text = "";
                        }
                    }
                }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 12
                    clip: true
                    model: s.chains
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Rectangle {
                        required property var modelData
                        width: ListView.view.width
                        height: 150
                        color: Theme.surface
                        radius: 12
                        border.color: page.chainId === modelData.id ? Theme.accent : Theme.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10
                            Heading {
                                text: modelData.name
                                font.pixelSize: 15
                            }
                            Caption {
                                text: ({
                                        idle: "准备就绪",
                                        running: "运行中",
                                        paused: "已暂停",
                                        completed: "已完成",
                                        failed: "执行失败"
                                    })[modelData.status] + " · " + modelData.tasks.filter(x => x.status === "completed").length + "/" + modelData.tasks.length + " 步"
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                MButton {
                                    text: modelData.status === "paused" ? "继续" : modelData.status === "completed" ? "再次运行" : "运行"
                                    primary: true
                                    enabled: modelData.status !== "running"
                                    onClicked: studio.chainAction(modelData.id, "start")
                                }
                                MButton {
                                    text: "暂停"
                                    visible: modelData.status === "running"
                                    onClicked: studio.chainAction(modelData.id, "pause")
                                }
                                MButton {
                                    text: "停止"
                                    visible: modelData.status === "running" || modelData.status === "paused"
                                    onClicked: studio.chainAction(modelData.id, "stop")
                                }
                                MButton {
                                    text: "编辑"
                                    quiet: true
                                    enabled: modelData.status !== "running" && modelData.status !== "paused"
                                    onClicked: page.edit(modelData)
                                }
                                MButton {
                                    text: "删除"
                                    quiet: true
                                    destructive: true
                                    enabled: modelData.status !== "running" && modelData.status !== "paused"
                                    onClicked: shell.confirm("删除这个流程？", () => studio.chainAction(modelData.id, "delete"))
                                }
                            }
                        }
                    }
                    EmptyState {
                        anchors.fill: parent
                        visible: parent.count === 0
                        title: "让创作有条不紊"
                        detail: "每行写一个提示词，流程会依次提交生成。"
                        iconName: "tools"
                    }
                }
            }
            Rectangle {
                Layout.preferredWidth: Math.max(340, page.width * 0.4)
                Layout.fillHeight: true
                color: Theme.surface
                radius: 14
                border.color: Theme.border
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 22
                    spacing: 15
                    Heading {
                        text: page.chainId ? "编辑流程" : "新建流程"
                        font.pixelSize: 18
                    }
                    Caption {
                        text: "流程名称"
                    }
                    MField {
                        id: name
                        Layout.fillWidth: true
                        placeholderText: "例如：四季海报"
                    }
                    Caption {
                        text: "生成步骤 · 每行一个提示词"
                    }
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        MTextArea {
                            id: steps
                            placeholderText: "春日的花园，柔和晨光\n夏夜的海边，清澈星空\n秋天的山林，温暖色彩\n冬日的街角，轻盈落雪"
                        }
                    }
                    Caption {
                        text: "使用创作页当前来源、模型与参数。每一步独立生成，失败后停止；暂停会等待正在生成的步骤完成。"
                        Layout.fillWidth: true
                    }
                    MButton {
                        text: "保存流程"
                        primary: true
                        Layout.fillWidth: true
                        onClicked: studio.saveChain(page.chainId, name.text, steps.text)
                    }
                }
            }
        }
    }
}
