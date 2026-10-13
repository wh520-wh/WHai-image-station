import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property var shell
    readonly property var s: studio.state
    readonly property var preview: s.preview || ({})
    readonly property var previewImages: preview.images || []
    readonly property int imageIndex: s.previewImageIndex || 0
    readonly property string imagePath: (preview.result_paths || [])[imageIndex] || preview.image_path || ""
    readonly property string imageUrl: previewImages[imageIndex] || preview.imageUrl || ""
    readonly property bool compact: page.height < 650
    function statusText(status) {
        return ({
                WAITING: "排队中",
                PENDING: "准备请求",
                GENERATING: "正在生成",
                COMPLETED: "生成完成",
                FAILED: "生成失败",
                CANCELLED: "已取消"
            })[status] || "等待创作";
    }
    Shortcut {
        sequence: "Ctrl+Return"
        enabled: page.visible && !templateDialog.visible && !(page.shell && page.shell.modalOpen)
        onActivated: studio.generate()
    }
    RowLayout {
        anchors.fill: parent
        spacing: 24
        ColumnLayout {
            Layout.preferredWidth: Math.max(370, Math.min(480, page.width * 0.47))
            Layout.minimumWidth: 350
            Layout.maximumWidth: Layout.preferredWidth
            Layout.fillHeight: true
            spacing: 12
            ScrollView {
                id: composer
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout {
                    width: composer.availableWidth
                    spacing: 14
                    Heading {
                        text: "把想象，变成画面。"
                        font.pixelSize: 27
                    }
                    Caption {
                        text: "专注创作，其余交给工作台。"
                        Layout.bottomMargin: 8
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 7
                            Caption {
                                text: "来源"
                            }
                            MCombo {
                                objectName: "sourceChoice"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                model: s.activeSources
                                textRole: "name"
                                currentIndex: s.activeSources.findIndex(x => x.id === s.sourceId)
                                onActivated: studio.selectSource(s.activeSources[currentIndex].id)
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 7
                            Caption {
                                text: "模型"
                            }
                            MCombo {
                                objectName: "modelChoice"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                model: s.activeModels
                                textRole: "display_name"
                                currentIndex: s.activeModels.findIndex(x => x.id === s.modelId)
                                onActivated: studio.selectModel(s.activeModels[currentIndex].id)
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Caption {
                            text: "画面描述"
                            font.weight: Font.DemiBold
                            color: Theme.ink
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        Caption {
                            text: s.draft.prompt.length + " 字"
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        visible: !s.sourceConfigured
                        Caption {
                            text: "这个来源还没有配置密钥。"
                            Layout.fillWidth: true
                        }
                        MButton {
                            text: "去配置"
                            quiet: true
                            onClicked: studio.configureSource()
                        }
                    }
                    ScrollView {
                        id: promptScroll
                        Layout.fillWidth: true
                        Layout.preferredHeight: 180
                        clip: true
                        contentWidth: availableWidth
                        MTextArea {
                            objectName: "promptInput"
                            width: promptScroll.availableWidth
                            text: s.draft.prompt
                            placeholderText: "描述主体、氛围、光线与构图…\n\n例如：雨后的街角咖啡馆，暖色灯光映在石板路上，安静的电影画面。"
                            onTextChanged: if (activeFocus && text !== s.draft.prompt)
                                studio.setDraft("prompt", text)
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 7
                            Caption {
                                text: s.caps.size_label
                            }
                            MCombo {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                model: s.caps.sizes
                                displayText: s.draft.size
                                currentIndex: s.caps.sizes.indexOf(s.draft.size)
                                onActivated: studio.setDraft("size", currentText)
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 7
                            Caption {
                                text: s.caps.quality_label
                            }
                            MCombo {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                model: s.caps.qualities
                                displayText: String(s.draft.quality)
                                currentIndex: s.caps.qualities.indexOf(s.draft.quality)
                                onActivated: studio.setDraft("quality", currentText)
                            }
                        }
                        ColumnLayout {
                            Layout.preferredWidth: 80
                            spacing: 7
                            Caption {
                                text: "数量"
                            }
                            MCombo {
                                Layout.fillWidth: true
                                model: s.caps.counts.map(x => String(x))
                                displayText: String(s.draft.n)
                                currentIndex: model.indexOf(String(s.draft.n))
                                onActivated: studio.setDraft("n", Number(currentText))
                            }
                        }
                    }
                    Rectangle {
                        visible: s.caps.reference
                        Layout.fillWidth: true
                        implicitHeight: referenceRow.implicitHeight + 22
                        color: Theme.subtle
                        radius: 10
                        RowLayout {
                            id: referenceRow
                            anchors.fill: parent
                            anchors.margins: 11
                            spacing: 10
                            Icon {
                                name: "image"
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4
                                Caption {
                                    text: "参考图"
                                    color: Theme.ink
                                    font.weight: Font.DemiBold
                                }
                                Caption {
                                    text: s.draft.reference ? s.draft.reference.split(/[\\/]/).pop() : "可选 · PNG、JPEG 或 WebP"
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                    maximumLineCount: 1
                                }
                            }
                            MButton {
                                text: s.draft.reference ? "更换" : "添加"
                                quiet: true
                                onClicked: studio.chooseReference()
                            }
                            MButton {
                                visible: !!s.draft.reference
                                text: "移除"
                                quiet: true
                                onClicked: studio.setDraft("reference", "")
                            }
                        }
                    }
                    MButton {
                        id: advanced
                        text: checked ? "收起高级选项" : "高级选项"
                        iconName: "settings"
                        quiet: true
                        checkable: true
                    }
                    ColumnLayout {
                        visible: advanced.checked
                        Layout.fillWidth: true
                        spacing: 10
                        Caption {
                            visible: s.caps.custom_size
                            text: "自定义尺寸 · 宽 x 高"
                        }
                        MField {
                            visible: s.caps.custom_size
                            Layout.fillWidth: true
                            text: s.draft.size
                            placeholderText: "例如 1280x768，实际范围以服务商为准"
                            onTextEdited: studio.setDraft("size", text)
                        }
                        Caption {
                            visible: s.caps.negative
                            text: "排除内容"
                        }
                        MField {
                            visible: s.caps.negative
                            Layout.fillWidth: true
                            placeholderText: "不希望出现在画面中的元素"
                            text: s.draft.negative_prompt
                            onTextEdited: studio.setDraft("negative_prompt", text)
                        }
                        Caption {
                            visible: s.caps.seed
                            text: "随机种子"
                        }
                        MField {
                            visible: s.caps.seed
                            Layout.fillWidth: true
                            placeholderText: "留空使用随机值"
                            text: String(s.draft.seed)
                            validator: IntValidator {
                                bottom: 0
                                top: 2147483647
                            }
                            onTextEdited: studio.setDraft("seed", text)
                        }
                        RowLayout {
                            visible: s.caps.format
                            Layout.fillWidth: true
                            Caption {
                                text: "文件格式"
                            }
                            MCombo {
                                model: ["png", "jpeg", "webp"]
                                currentIndex: model.indexOf(s.draft.output_format)
                                onActivated: studio.setDraft("output_format", currentText)
                            }
                            CheckBox {
                                text: "透明背景"
                                checked: s.draft.transparent
                                onToggled: studio.setDraft("transparent", checked)
                                palette.windowText: Theme.ink
                            }
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                MButton {
                    objectName: "generateButton"
                    text: "开始生成"
                    iconName: "arrow"
                    primary: true
                    Layout.fillWidth: true
                    enabled: !!s.modelId && !!s.draft.prompt.trim()
                    onClicked: studio.generate()
                }
                MButton {
                    text: "存为模板"
                    enabled: !!s.draft.prompt.trim()
                    onClicked: templateDialog.open()
                }
            }
            Caption {
                text: "Ctrl + Enter 提交 · 图片会自动保存到本地"
                Layout.bottomMargin: 14
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 160
                radius: 16
                color: Theme.surface
                border.color: Theme.border
                clip: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10
                    RowLayout {
                        visible: !!page.preview.task_id
                        Layout.fillWidth: true
                        Caption {
                            text: page.statusText(page.preview.status)
                            font.weight: Font.DemiBold
                            color: page.preview.status === "FAILED" ? Theme.danger : Theme.accent
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        Caption {
                            text: s.previewElapsed || ""
                        }
                    }
                    Caption {
                        visible: !!page.preview.task_id
                        text: [page.preview.sourceText, page.preview.modelText].filter(x => !!x).join(" · ")
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Image {
                            id: previewPicture
                            objectName: "previewPicture"
                            anchors.fill: parent
                            source: page.imageUrl
                            sourceSize: Qt.size(1600, 1600)
                            asynchronous: true
                            fillMode: Image.PreserveAspectFit
                            visible: source !== ""
                        }
                        Skeleton {
                            anchors.fill: parent
                            visible: previewPicture.status === Image.Loading
                        }
                        EmptyState {
                            anchors.fill: parent
                            visible: !!page.preview.task_id && (!page.imageUrl || previewPicture.status === Image.Error)
                            title: page.preview.status === "FAILED" ? "这次生成没有完成" : page.statusText(page.preview.status)
                            detail: page.preview.status === "FAILED" ? "查看原因后，可以调整提示词与参数再试。" : page.preview.status === "WAITING" ? "轮到这个任务时会自动开始，你可以继续编辑。" : page.preview.status === "CANCELLED" ? "这个任务已取消，可以选择其他任务查看。" : page.imageUrl ? "图片暂时无法读取，作品详情保留了生成记录。" : "正在等待模型返回结果，完成后图片会出现在这里。"
                            iconName: page.preview.status === "FAILED" ? "image" : "bolt"
                        }
                    }
                    ListView {
                        id: imageStrip
                        objectName: "previewImageStrip"
                        visible: page.previewImages.length > 1
                        Layout.fillWidth: true
                        Layout.preferredHeight: 58
                        orientation: ListView.Horizontal
                        spacing: 8
                        clip: true
                        model: page.previewImages
                        currentIndex: page.imageIndex
                        onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                        delegate: MButton {
                            required property int index
                            required property string modelData
                            width: 58
                            height: 58
                            padding: 4
                            Accessible.name: "选择第 " + (index + 1) + " 张图片"
                            background: Rectangle {
                                radius: 8
                                color: Theme.subtle
                                border.color: index === page.imageIndex || parent.activeFocus ? Theme.accent : Theme.border
                                border.width: index === page.imageIndex || parent.activeFocus ? 2 : 1
                            }
                            contentItem: Image {
                                source: modelData
                                sourceSize: Qt.size(116, 116)
                                asynchronous: true
                                fillMode: Image.PreserveAspectFit
                            }
                            onClicked: studio.selectPreviewImage(index)
                        }
                    }
                    RowLayout {
                        visible: !!page.preview.task_id
                        Layout.fillWidth: true
                        Caption {
                            visible: page.previewImages.length > 1
                            text: "第 " + (page.imageIndex + 1) + " / " + page.previewImages.length + " 张"
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        MButton {
                            id: viewPreviewButton
                            objectName: "viewPreviewButton"
                            text: page.preview.status === "FAILED" ? "查看原因" : "作品详情"
                            quiet: true
                            onClicked: studio.viewPreview()
                        }
                    }
                    Flow {
                        visible: !!page.imagePath
                        Layout.fillWidth: true
                        spacing: 6
                        MButton {
                            id: copyPreviewButton
                            objectName: "copyPreviewButton"
                            text: "复制图片"
                            quiet: true
                            onClicked: studio.copyImage(page.imagePath)
                        }
                        MButton {
                            id: savePreviewButton
                            objectName: "savePreviewButton"
                            text: "另存图片"
                            quiet: true
                            onClicked: studio.saveImage(page.imagePath)
                        }
                        MButton {
                            id: referencePreviewButton
                            objectName: "referencePreviewButton"
                            text: "作为参考图"
                            quiet: true
                            enabled: s.caps.reference
                            ToolTip.visible: hovered && !enabled
                            ToolTip.text: "当前模型不支持参考图，请先更换模型。"
                            onClicked: studio.useImageAsReference(page.imagePath)
                        }
                    }
                }
                Item {
                    anchors.fill: parent
                    visible: !page.preview.task_id && !page.imageUrl
                    Rectangle {
                        anchors.centerIn: parent
                        width: Math.min(parent.width * 0.48, 220)
                        height: width * 1.13
                        rotation: -6
                        color: Theme.subtle
                        radius: 12
                        border.color: Theme.border
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: Math.min(parent.width * 0.48, 220)
                        height: width * 1.13
                        rotation: 4
                        color: Theme.surface
                        radius: 12
                        border.color: Theme.border
                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width * 0.55
                            height: width
                            radius: width / 2
                            color: Theme.accentWash
                            Icon {
                                anchors.centerIn: parent
                                name: "image"
                                width: 40
                                height: 40
                                tint: Theme.accent
                            }
                        }
                    }
                    Caption {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 30
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "你的下一张作品，从这里开始。"
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Heading {
                    text: "任务队列"
                    font.pixelSize: 15
                }
                Item {
                    Layout.fillWidth: true
                }
                Caption {
                    text: s.activeCount ? s.activeCount + " 个进行中" : "准备就绪"
                }
            }
            ListView {
                Layout.fillWidth: true
                Layout.preferredHeight: page.compact ? 106 : 146
                clip: true
                spacing: 8
                model: s.tasks
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: taskCard
                    required property var modelData
                    readonly property bool selected: modelData.task_id === s.selectedTaskId
                    objectName: "queueTask_" + modelData.task_id
                    width: ListView.view.width
                    height: 68
                    radius: 10
                    color: selected ? Theme.accentWash : Theme.surface
                    border.color: selected || activeFocus ? Theme.accent : Theme.border
                    border.width: activeFocus ? 2 : 1
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.prompt + "，" + page.statusText(modelData.status)
                    Accessible.onPressAction: studio.selectTask(modelData.task_id)
                    Keys.onReturnPressed: studio.selectTask(modelData.task_id)
                    Keys.onEnterPressed: studio.selectTask(modelData.task_id)
                    Keys.onSpacePressed: studio.selectTask(modelData.task_id)
                    TapHandler {
                        onTapped: {
                            taskCard.forceActiveFocus();
                            studio.selectTask(taskCard.modelData.task_id);
                        }
                    }
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12
                        Rectangle {
                            width: 7
                            height: 7
                            radius: 4
                            color: modelData.status === "FAILED" ? Theme.danger : Theme.accent
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                text: modelData.prompt
                                color: Theme.ink
                                font.family: Theme.font
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Caption {
                                text: page.statusText(modelData.status)
                                color: modelData.status === "FAILED" ? Theme.danger : Theme.muted
                            }
                        }
                        MButton {
                            visible: modelData.status === "WAITING"
                            text: "取消"
                            quiet: true
                            onClicked: studio.cancelTask(modelData.task_id)
                        }
                    }
                }
                EmptyState {
                    anchors.fill: parent
                    visible: s.tasks.length === 0
                    title: "还没有任务"
                    detail: "提交后可继续编辑，不必等待生成完成。"
                    iconName: "bolt"
                }
            }
        }
    }
    Dialog {
        id: templateDialog
        anchors.centerIn: parent
        width: 380
        modal: true
        padding: 22
        title: "保存当前创作为模板"
        background: Rectangle {
            color: Theme.surface
            radius: 14
            border.color: Theme.border
        }
        ColumnLayout {
            width: parent.width
            spacing: 12
            MField {
                id: templateName
                Layout.fillWidth: true
                placeholderText: "模板名称"
            }
            MField {
                id: templateCategory
                Layout.fillWidth: true
                placeholderText: "分类（可选）"
            }
            MButton {
                text: "保存模板"
                primary: true
                Layout.fillWidth: true
                onClicked: {
                    studio.savePrompt(templateName.text, templateCategory.text);
                    templateDialog.close();
                }
            }
        }
    }
}
