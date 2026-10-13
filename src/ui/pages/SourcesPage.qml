import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property var shell
    readonly property var s: studio.state
    property string selectedId: ""
    property var editing: ({})
    property var modelEdits: []
    property string signature: ""
    property string lastAddedId: ""
    function loadSource(sourceId) {
        var source = s.sources.find(x => x.id === sourceId);
        if (!source)
            source = s.sources[0];
        selectedId = source ? source.id : "";
        editing = source ? JSON.parse(JSON.stringify(source)) : ({});
        modelEdits = s.models.filter(x => x.source_id === selectedId).map(x => JSON.parse(JSON.stringify(x)));
        keyField.text = "";
    }
    Component.onCompleted: {
        signature = JSON.stringify(s.sources) + JSON.stringify(s.models);
        lastAddedId = s.editSourceId || "";
        loadSource(s.editSourceId || "");
    }
    Connections {
        target: studio
        function onStateChanged() {
            var next = JSON.stringify(page.s.sources) + JSON.stringify(page.s.models);
            if (page.s.editSourceId && page.s.editSourceId !== page.lastAddedId) {
                page.lastAddedId = page.s.editSourceId;
                page.loadSource(page.lastAddedId);
            } else if (page.signature !== next) {
                page.signature = next;
                page.loadSource(page.selectedId);
            }
        }
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 22
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 7
                Heading {
                    text: "来源与模型"
                    font.pixelSize: 27
                }
                Caption {
                    text: "一次配置，随时切换。密钥保存在本机。"
                }
            }
            Item {
                Layout.fillWidth: true
            }
            MCombo {
                id: presetChoice
                model: s.presets
                textRole: "name"
                Layout.preferredWidth: 195
            }
            MButton {
                text: "添加来源"
                primary: true
                enabled: !s.busy
                onClicked: studio.addPreset(s.presets[presetChoice.currentIndex].id)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 22
            ListView {
                Layout.preferredWidth: 210
                Layout.fillHeight: true
                clip: true
                spacing: 8
                model: s.sources
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width
                    height: 76
                    radius: 11
                    color: page.selectedId === modelData.id ? Theme.accentWash : Theme.surface
                    border.color: page.selectedId === modelData.id ? Theme.accent : Theme.border
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 6
                        Text {
                            text: modelData.name
                            color: Theme.ink
                            font.family: Theme.font
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                        Caption {
                            text: !modelData.is_active ? "已停用" : modelData.has_key ? "密钥已保存" : "待填写密钥"
                            color: modelData.has_key ? Theme.accent : Theme.muted
                        }
                    }
                    TapHandler {
                        onTapped: page.loadSource(modelData.id)
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 14
                color: Theme.surface
                border.color: Theme.border
                EmptyState {
                    anchors.fill: parent
                    visible: !page.selectedId
                    title: "添加你的第一个来源"
                    detail: "从预置服务开始，或配置兼容接口。"
                    iconName: "sources"
                }
                ScrollView {
                    id: sourceEditor
                    visible: !!page.selectedId
                    anchors.fill: parent
                    anchors.margins: 24
                    clip: true
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: sourceEditor.availableWidth
                        spacing: 15
                        Heading {
                            text: page.editing.name || "来源设置"
                        }
                        Caption {
                            text: "基本设置"
                            font.weight: Font.DemiBold
                            Layout.topMargin: 6
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            MField {
                                Layout.fillWidth: true
                                text: page.editing.name || ""
                                placeholderText: "来源名称"
                                onTextEdited: page.editing.name = text
                            }
                            CheckBox {
                                text: "启用"
                                checked: !!page.editing.is_active
                                palette.windowText: Theme.ink
                                onToggled: page.editing.is_active = checked ? 1 : 0
                            }
                        }
                        Caption {
                            text: "接口类型"
                        }
                        MCombo {
                            Layout.fillWidth: true
                            model: s.interfaces
                            textRole: "name"
                            currentIndex: s.interfaces.findIndex(x => x.id === page.editing.interface_type)
                            onActivated: {
                                page.editing.interface_type = s.interfaces[currentIndex].id;
                                page.editing.auth_preset = page.editing.interface_type === "gemini" ? "gemini" : page.editing.interface_type === "bfl" ? "bfl" : "openai";
                            }
                        }
                        Caption {
                            text: "API 地址"
                        }
                        MField {
                            Layout.fillWidth: true
                            text: page.editing.api_base_url || ""
                            placeholderText: "https://…"
                            onTextEdited: page.editing.api_base_url = text
                        }
                        Caption {
                            text: "API Key"
                        }
                        MField {
                            id: keyField
                            objectName: "sourceKey"
                            Layout.fillWidth: true
                            echoMode: TextInput.Password
                            placeholderText: page.editing.has_key ? "已保存 · 留空保留原密钥" : "填入服务商提供的密钥"
                        }
                        Caption {
                            text: "模型"
                            font.weight: Font.DemiBold
                            Layout.topMargin: 10
                        }
                        Caption {
                            text: "显示名称用于选择；模型 ID 需与服务商文档一致。"
                        }
                        Repeater {
                            model: page.modelEdits
                            delegate: RowLayout {
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                spacing: 8
                                MField {
                                    Layout.fillWidth: true
                                    text: modelData.display_name || ""
                                    placeholderText: "显示名称"
                                    onTextEdited: page.modelEdits[index].display_name = text
                                }
                                MField {
                                    Layout.fillWidth: true
                                    text: modelData.model_id || ""
                                    placeholderText: "模型 ID"
                                    onTextEdited: page.modelEdits[index].model_id = text
                                }
                                CheckBox {
                                    checked: !!modelData.is_active
                                    palette.windowText: Theme.ink
                                    Accessible.name: "启用这个模型"
                                    onToggled: page.modelEdits[index].is_active = checked ? 1 : 0
                                }
                                MButton {
                                    text: "移除"
                                    quiet: true
                                    onClicked: {
                                        var list = page.modelEdits.slice();
                                        list.splice(index, 1);
                                        page.modelEdits = list;
                                    }
                                }
                            }
                        }
                        MButton {
                            text: "添加模型"
                            iconName: "create"
                            quiet: true
                            onClicked: page.modelEdits = page.modelEdits.concat([
                                {
                                    display_name: "",
                                    model_id: "",
                                    is_active: 1
                                }
                            ])
                        }
                        MButton {
                            id: advanced
                            text: "连接与响应选项"
                            iconName: "settings"
                            quiet: true
                            checkable: true
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: advanced.checked
                            spacing: 10
                            Caption {
                                text: "认证方式"
                            }
                            MCombo {
                                Layout.fillWidth: true
                                model: ["openai", "gemini", "bfl", "none"]
                                currentIndex: model.indexOf(page.editing.auth_preset || "openai")
                                onActivated: page.editing.auth_preset = currentText
                            }
                            Caption {
                                text: "响应格式（兼容来源）"
                            }
                            MCombo {
                                Layout.fillWidth: true
                                model: ["auto", "openai", "minimax"]
                                currentIndex: model.indexOf(page.editing.response_format || "auto")
                                onActivated: page.editing.response_format = currentText
                            }
                            Caption {
                                text: "代理地址"
                            }
                            MField {
                                Layout.fillWidth: true
                                text: page.editing.proxy || ""
                                placeholderText: "可选，例如 http://127.0.0.1:7890"
                                onTextEdited: page.editing.proxy = text
                            }
                            Caption {
                                text: "自定义请求头（JSON 对象）"
                            }
                            MField {
                                Layout.fillWidth: true
                                text: page.editing.custom_headers || "{}"
                                placeholderText: "{}"
                                onTextEdited: page.editing.custom_headers = text
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 10
                            MButton {
                                text: s.busy ? "正在保存…" : "保存配置"
                                primary: true
                                enabled: !s.busy
                                onClicked: studio.saveSource(page.editing, page.modelEdits, keyField.text)
                            }
                            Item {
                                Layout.fillWidth: true
                            }
                            MButton {
                                text: "服务商文档"
                                quiet: true
                                onClicked: {
                                    var preset = s.presets.find(x => x.interface_type === page.editing.interface_type);
                                    if (preset && preset.docs_url)
                                        studio.openLink(preset.docs_url);
                                }
                            }
                            MButton {
                                text: "删除来源"
                                quiet: true
                                destructive: true
                                onClicked: shell.confirm("删除「" + page.editing.name + "」及其模型配置？已生成的作品会保留。", () => studio.deleteSource(page.selectedId))
                            }
                        }
                        Caption {
                            text: "保存配置会检查地址与参数，不会发送生图请求。"
                            Layout.bottomMargin: 15
                        }
                    }
                }
            }
        }
    }
}
