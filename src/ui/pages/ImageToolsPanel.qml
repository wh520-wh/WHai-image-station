import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    objectName: "imageToolsPanel"
    property var shell
    readonly property var s: studio.state
    property string operation: "convert"
    property bool showResult: true
    readonly property var input: s.toolInput || ({})
    readonly property var result: s.toolResult || ({})
    readonly property bool hasInput: !!input.path
    readonly property bool hasResult: !!result.path
    readonly property bool working: s.toolBusy || s.toolLoading
    readonly property bool compact: page.width < 900 || page.height < 570
    readonly property var displayed: hasResult && showResult ? result : input
    ColumnLayout {
        anchors.fill: parent
        spacing: 16
        ScrollView {
            id: bodyScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            GridLayout {
                width: bodyScroll.availableWidth
                columns: page.width >= 650 ? 2 : 1
                columnSpacing: 20
                rowSpacing: 20
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredWidth: page.width >= 650 ? (page.compact ? 270 : 300) : bodyScroll.availableWidth
                    Layout.maximumWidth: page.width >= 650 ? (page.compact ? 270 : 320) : 100000
                    Layout.preferredHeight: controls.implicitHeight + (page.compact ? 32 : 40)
                    color: Theme.surface
                    radius: 14
                    border.color: Theme.border
                    ColumnLayout {
                        id: controls
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: page.compact ? 16 : 20
                        spacing: page.compact ? 10 : 15
                        RowLayout {
                            Icon { name: "image"; tint: Theme.accent }
                            Heading { text: "图片处理"; font.pixelSize: 17 }
                            Item { Layout.fillWidth: true }
                            Caption { text: "本地"; color: Theme.accent }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Repeater {
                                model: [
                                    { id: "convert", title: "格式转换", detail: "PNG、JPEG 与 WebP", icon: "convert" },
                                    { id: "resize", title: "尺寸调整", detail: "保持比例，按最长边缩小", icon: "resize" },
                                    { id: "compress", title: "图片压缩", detail: "优化体积，调整输出品质", icon: "compress" }
                                ]
                                delegate: Button {
                                    id: toolChoice
                                    required property var modelData
                                    objectName: "tool_" + modelData.id
                                    Layout.fillWidth: true
                                    implicitHeight: page.compact ? 48 : 66
                                    padding: 13
                                    enabled: !page.working
                                    Accessible.name: modelData.title
                                    onClicked: page.operation = modelData.id
                                    background: Rectangle {
                                        radius: 10
                                        color: page.operation === toolChoice.modelData.id ? Theme.accentWash : toolChoice.down || toolChoice.hovered ? Theme.subtle : "transparent"
                                        border.color: toolChoice.activeFocus ? Theme.accent : "transparent"
                                        Behavior on color { ColorAnimation { duration: Theme.reduced ? 0 : 100 } }
                                    }
                                    contentItem: RowLayout {
                                        spacing: 12
                                        Icon { name: toolChoice.modelData.icon; tint: page.operation === toolChoice.modelData.id ? Theme.accent : Theme.muted }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 3
                                            Heading { text: toolChoice.modelData.title; font.pixelSize: 13 }
                                            Caption { text: toolChoice.modelData.detail; font.pixelSize: 11; visible: !page.compact }
                                        }
                                        Icon { name: "check"; tint: Theme.accent; visible: page.operation === toolChoice.modelData.id; width: 17; height: 17 }
                                    }
                                }
                            }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                        Caption { text: "输出格式"; color: Theme.ink }
                        MCombo {
                            id: formatChoice
                            objectName: "toolFormat"
                            Layout.fillWidth: true
                            model: ["PNG", "JPEG", "WebP"]
                            currentIndex: page.operation === "compress" ? 2 : 0
                            enabled: !page.working
                        }
                        ColumnLayout {
                            visible: page.operation === "resize"
                            Layout.fillWidth: true
                            spacing: 8
                            Caption { text: "最长边 · 像素"; color: Theme.ink }
                            MField {
                                id: edgeField
                                objectName: "toolEdge"
                                Layout.fillWidth: true
                                text: "2048"
                                validator: IntValidator { bottom: 64; top: 8192 }
                                inputMethodHints: Qt.ImhDigitsOnly
                                enabled: !page.working
                            }
                            Caption { text: "保持原比例，不放大小图。"; font.pixelSize: 11; Layout.fillWidth: true; visible: !page.compact }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            visible: formatChoice.currentIndex !== 0
                            RowLayout {
                                Layout.fillWidth: true
                                Caption { text: "输出品质"; color: Theme.ink }
                                Item { Layout.fillWidth: true }
                                Caption { text: Math.round(qualitySlider.value); color: Theme.accent }
                            }
                            Slider {
                                id: qualitySlider
                                objectName: "toolQuality"
                                Layout.fillWidth: true
                                from: 1; to: 100; value: 85; stepSize: 1
                                enabled: !page.working
                                Accessible.name: "输出品质"
                                palette.highlight: Theme.accent
                            }
                        }
                        Caption {
                            Layout.fillWidth: true
                            font.pixelSize: 11
                            text: formatChoice.currentIndex === 1 ? "透明区域会填充为白色。" : formatChoice.currentIndex === 0 ? "PNG 保留透明度，使用无损压缩。" : "WebP 保留透明度，适合较小的文件。"
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: page.width >= 650 ? Math.max(controls.implicitHeight + (page.compact ? 32 : 40), page.compact ? 370 : 440) : 410
                    color: Theme.surface
                    radius: 14
                    border.color: drop.containsDrag ? Theme.accent : Theme.border
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 12
                        RowLayout {
                            Layout.fillWidth: true
                            Heading { text: page.hasInput ? "画面预览" : "选择一张图片"; font.pixelSize: 17 }
                            Item { Layout.fillWidth: true }
                            MButton { text: "更换图片"; quiet: true; iconName: "folder"; visible: page.hasInput; enabled: !page.working; onClicked: studio.chooseToolImage() }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 210
                            color: Theme.subtle
                            radius: 10
                            clip: true
                            Image {
                                objectName: "toolImagePreview"
                                anchors.fill: parent
                                anchors.margins: 12
                                source: page.displayed.imageUrl || ""
                                asynchronous: true
                                autoTransform: true
                                fillMode: Image.PreserveAspectFit
                                sourceSize: Qt.size(1400, 1400)
                                opacity: page.working ? 0.45 : 1
                                Behavior on opacity { NumberAnimation { duration: Theme.reduced ? 0 : 120 } }
                            }
                            ColumnLayout {
                                anchors.centerIn: parent
                                width: Math.min(parent.width - 40, 310)
                                visible: !page.hasInput && !page.working
                                spacing: 14
                                Rectangle {
                                    Layout.alignment: Qt.AlignHCenter
                                    width: 56; height: 56; radius: 16
                                    color: Theme.accentWash
                                    Icon { anchors.centerIn: parent; name: "image"; tint: Theme.accent; width: 26; height: 26 }
                                }
                                Heading { text: "从一张图片开始"; font.pixelSize: 18; Layout.alignment: Qt.AlignHCenter }
                                Caption { text: "拖入图片，或从本地选择。\n支持 PNG、JPEG、WebP。"; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
                                MButton { text: "选择图片"; objectName: "chooseToolImage"; primary: true; iconName: "folder"; Layout.alignment: Qt.AlignHCenter; onClicked: studio.chooseToolImage() }
                            }
                            BusyIndicator { anchors.centerIn: parent; running: page.working; visible: running; palette.highlight: Theme.accent }
                        }
                        RowLayout {
                            visible: page.hasInput
                            Layout.fillWidth: true
                            Caption { text: page.displayed.width + " × " + page.displayed.height + " · " + page.displayed.format + " · " + page.displayed.sizeText; Layout.fillWidth: true; color: Theme.ink }
                            MButton { text: page.showResult ? "查看原图" : "查看结果"; quiet: true; visible: page.hasResult; onClicked: page.showResult = !page.showResult }
                        }
                        Caption {
                            visible: page.hasResult
                            Layout.fillWidth: true
                            text: !page.result.recordSaved ? "已生成新文件，可另存为" : page.result.savedPercent > 0 ? "体积减少 " + page.result.savedPercent + "% · 已保存到作品库" : page.result.savedPercent < 0 ? "体积增加 " + Math.abs(page.result.savedPercent) + "% · 已保存到作品库" : "体积与原图相同 · 已保存到作品库"
                            color: Theme.accent
                            font.pixelSize: 12
                        }
                    }
                    DropArea {
                        id: drop
                        anchors.fill: parent
                        enabled: !page.working
                        onDropped: event => {
                            if (event.hasUrls && event.urls.length > 0) {
                                studio.loadToolImage(String(event.urls[0]));
                                event.acceptProposedAction();
                            }
                        }
                    }
                }
            }
        }
        Caption { text: s.toolError || ""; visible: !!s.toolError; color: Theme.danger; Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            MButton {
                objectName: "runImageTool"
                text: s.toolBusy ? "正在处理…" : "处理并保存"
                primary: true
                iconName: "check"
                enabled: page.hasInput && !page.working && (page.operation !== "resize" || edgeField.acceptableInput)
                onClicked: { page.showResult = true; studio.runImageTool(page.operation, formatChoice.currentText, Number(edgeField.text), Math.round(qualitySlider.value)); }
            }
            Caption { text: "原图保留"; font.pixelSize: 11; visible: page.width >= 830 }
            Item { Layout.fillWidth: true }
            MButton { text: "另存为"; enabled: page.hasResult && !page.working; onClicked: studio.saveImage(page.result.path) }
            MButton { text: "复制"; enabled: page.hasResult && !page.working; onClicked: studio.copyImage(page.result.path) }
            MButton { text: "作为参考图"; enabled: page.hasResult && !page.working && s.caps.reference; onClicked: studio.useImageAsReference(page.result.path) }
        }
    }
}
