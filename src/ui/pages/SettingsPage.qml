import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

ScrollView {
    id: page
    property var shell
    readonly property var s: studio.state
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        width: page.availableWidth
        spacing: 22
        ColumnLayout {
            spacing: 7
            Heading {
                text: "工作台设置"
                font.pixelSize: 27
            }
            Caption {
                text: "按自己的节奏，安排创作环境。"
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: appearance.implicitHeight + 44
            radius: 14
            color: Theme.surface
            border.color: Theme.border
            ColumnLayout {
                id: appearance
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14
                Heading {
                    text: "外观与运行"
                    font.pixelSize: 17
                }
                RowLayout {
                    Layout.fillWidth: true
                    Caption {
                        text: "深色外观"
                        color: Theme.ink
                        font.pixelSize: 13
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Switch {
                        id: darkSwitch
                        checked: s.dark
                        onToggled: studio.savePreferences(checked, s.reducedMotion, s.concurrent)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Caption {
                            text: "减少动态效果"
                            color: Theme.ink
                            font.pixelSize: 13
                        }
                        Caption {
                            text: "保留清晰反馈，减少位移和循环动画。"
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Switch {
                        checked: s.reducedMotion
                        onToggled: studio.savePreferences(s.dark, checked, s.concurrent)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Caption {
                            text: "同时生成"
                            color: Theme.ink
                            font.pixelSize: 13
                        }
                        Caption {
                            text: "根据服务商速率限制调整。"
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    MCombo {
                        model: ["1", "2", "3", "4"]
                        currentIndex: s.concurrent - 1
                        onActivated: studio.savePreferences(s.dark, s.reducedMotion, Number(currentText))
                    }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: backupColumn.implicitHeight + 44
            radius: 14
            color: Theme.surface
            border.color: Theme.border
            ColumnLayout {
                id: backupColumn
                anchors.fill: parent
                anchors.margins: 22
                spacing: 16
                Heading {
                    text: "备份与迁移"
                    font.pixelSize: 17
                }
                Caption {
                    text: "备份包含图片、历史记录、模板、来源、流程与设置。默认不包含密钥和敏感请求头。"
                    Layout.fillWidth: true
                }
                CheckBox {
                    id: withKeys
                    text: "包含密钥与敏感请求头（使用密码加密）"
                    palette.windowText: Theme.ink
                }
                MField {
                    id: password
                    visible: withKeys.checked
                    Layout.fillWidth: true
                    echoMode: TextInput.Password
                    placeholderText: "备份密码，至少 8 位"
                }
                RowLayout {
                    spacing: 12
                    MButton {
                        text: s.busy ? "正在处理…" : "导出备份"
                        enabled: !s.busy
                        primary: true
                        onClicked: studio.backup("export", password.text, withKeys.checked)
                    }
                    MButton {
                        text: "导入备份"
                        enabled: !s.busy
                        onClicked: studio.backup("import", password.text, withKeys.checked)
                    }
                }
                Caption {
                    text: "导入会保留已有的重名配置；已有作品不会被覆盖。"
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: paths.implicitHeight + 44
            radius: 14
            color: Theme.surface
            border.color: Theme.border
            ColumnLayout {
                id: paths
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14
                Heading {
                    text: "本地存储"
                    font.pixelSize: 17
                }
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true
                        Caption {
                            text: "生成图片"
                            color: Theme.ink
                        }
                        Caption {
                            text: s.imagePath
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                            maximumLineCount: 1
                        }
                    }
                    MButton {
                        text: "打开"
                        iconName: "folder"
                        onClicked: studio.openPath(s.imagePath)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true
                        Caption {
                            text: "配置与数据库"
                            color: Theme.ink
                        }
                        Caption {
                            text: s.dataPath
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                            maximumLineCount: 1
                        }
                    }
                    MButton {
                        text: "打开"
                        iconName: "folder"
                        onClicked: studio.openPath(s.dataPath)
                    }
                }
            }
        }
        RowLayout {
            spacing: 12
            Layout.bottomMargin: 22
            BrandMark {
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30
            }
            Caption {
                text: "WHai Image Station  " + s.version
            }
        }
    }
}
