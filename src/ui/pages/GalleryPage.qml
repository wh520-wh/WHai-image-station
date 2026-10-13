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
        spacing: 20
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 7
                Heading {
                    text: "作品库"
                    font.pixelSize: 27
                }
                Caption {
                    text: s.galleryTotal + " 条记录 · 保存每一次创作"
                }
            }
            Item {
                Layout.fillWidth: true
            }
            MButton {
                text: "打开图片文件夹"
                iconName: "folder"
                onClicked: studio.openPath(s.imagePath)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            MField {
                id: search
                objectName: "gallerySearch"
                Layout.fillWidth: true
                placeholderText: "搜索提示词、分类或标签"
                onTextEdited: debounce.restart()
            }
            MCombo {
                id: status
                model: ["全部记录", "已完成", "失败"]
                onActivated: debounce.restart()
            }
            MButton {
                text: "刷新"
                onClicked: studio.searchGallery(search.text, status.currentIndex === 1 ? "COMPLETED" : status.currentIndex === 2 ? "FAILED" : "")
            }
        }
        Rectangle {
            visible: s.selected.length > 0
            Layout.fillWidth: true
            implicitHeight: 52
            color: Theme.accentWash
            radius: 10
            RowLayout {
                anchors.fill: parent
                anchors.margins: 6
                spacing: 8
                Caption {
                    text: "已选择 " + s.selected.length + " 条"
                    color: Theme.accent
                    Layout.leftMargin: 10
                }
                Item {
                    Layout.fillWidth: true
                }
                MButton {
                    text: "导出"
                    quiet: true
                    onClicked: studio.batchAction("export", "")
                }
                MButton {
                    text: "分类"
                    quiet: true
                    onClicked: {
                        batchDialog.action = "category";
                        batchDialog.open();
                    }
                }
                MButton {
                    text: "标签"
                    quiet: true
                    onClicked: {
                        batchDialog.action = "tags";
                        batchDialog.open();
                    }
                }
                MButton {
                    text: "删除"
                    quiet: true
                    destructive: true
                    onClicked: shell.confirm("删除选中的记录和本地图片？此操作无法撤销。", () => studio.batchAction("delete", ""))
                }
                MButton {
                    text: "完成"
                    quiet: true
                    onClicked: studio.clearSelection()
                }
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            GridView {
                id: grid
                objectName: "galleryGrid"
                anchors.fill: parent
                clip: true
                reuseItems: true
                cellWidth: width / Math.max(2, Math.floor(width / 240))
                cellHeight: cellWidth + 74
                model: studio.galleryModel
                cacheBuffer: cellHeight * 2
                ScrollBar.vertical: ScrollBar {}
                onAtYEndChanged: if (atYEnd)
                    studio.moreGallery()
                delegate: Item {
                    required property var record
                    width: grid.cellWidth
                    height: grid.cellHeight
                    Rectangle {
                        anchors.fill: parent
                        anchors.rightMargin: 14
                        anchors.bottomMargin: 14
                        radius: 12
                        color: Theme.surface
                        border.width: s.selected.indexOf(record.task_id) >= 0 ? 2 : 1
                        border.color: s.selected.indexOf(record.task_id) >= 0 ? Theme.accent : Theme.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 8
                            Item {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 8
                                    color: Theme.subtle
                                }
                                Image {
                                    id: picture
                                    property string failedThumbnail: ""
                                    anchors.fill: parent
                                    source: record.thumbnailUrl === failedThumbnail ? record.imageUrl : record.thumbnailUrl
                                    asynchronous: true
                                    sourceSize: Qt.size(420, 420)
                                    fillMode: Image.PreserveAspectCrop
                                    onStatusChanged: if (status === Image.Error && source.toString() === record.thumbnailUrl && record.imageUrl !== record.thumbnailUrl)
                                        failedThumbnail = record.thumbnailUrl
                                }
                                Skeleton {
                                    anchors.fill: parent
                                    visible: picture.status === Image.Loading
                                }
                                ColumnLayout {
                                    anchors.centerIn: parent
                                    visible: !record.thumbnailUrl || picture.status === Image.Error
                                    Icon {
                                        Layout.alignment: Qt.AlignHCenter
                                        name: "image"
                                        width: 30
                                        height: 30
                                    }
                                    Caption {
                                        text: record.status === "FAILED" ? "生成失败" : "图片不可用"
                                        color: record.status === "FAILED" ? Theme.danger : Theme.muted
                                    }
                                }
                                TapHandler {
                                    onTapped: studio.viewRecord(record)
                                }
                                Rectangle {
                                    visible: (record.images || []).length > 1
                                    anchors.left: parent.left
                                    anchors.bottom: parent.bottom
                                    anchors.margins: 8
                                    width: resultCount.implicitWidth + 18
                                    height: 25
                                    radius: 8
                                    color: Theme.surface
                                    border.color: Theme.border
                                    Caption {
                                        id: resultCount
                                        anchors.centerIn: parent
                                        text: (record.images || []).length + " 张"
                                        color: Theme.ink
                                        font.weight: Font.DemiBold
                                        font.pixelSize: 11
                                    }
                                }
                                Rectangle {
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 8
                                    width: 30
                                    height: 30
                                    radius: 9
                                    color: s.selected.indexOf(record.task_id) >= 0 ? Theme.accent : Theme.surface
                                    border.color: Theme.border
                                    Icon {
                                        anchors.centerIn: parent
                                        name: "check"
                                        width: 16
                                        height: 16
                                        tint: s.selected.indexOf(record.task_id) >= 0 ? Theme.accentText : Theme.muted
                                    }
                                    TapHandler {
                                        onTapped: studio.toggleSelection(record.task_id)
                                    }
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: record.prompt || "未命名作品"
                                font.family: Theme.font
                                font.pixelSize: 12
                                color: Theme.ink
                                elide: Text.ElideRight
                            }
                            Caption {
                                Layout.fillWidth: true
                                text: record.modelText + " · " + record.dateText
                                elide: Text.ElideRight
                                maximumLineCount: 1
                                font.pixelSize: 10
                            }
                        }
                    }
                }
                footer: Item {
                    width: grid.width
                    height: s.galleryHasMore ? 54 : 24
                    MButton {
                        anchors.centerIn: parent
                        visible: s.galleryHasMore
                        text: s.galleryLoading ? "正在加载…" : "加载更多"
                        enabled: !s.galleryLoading
                        onClicked: studio.moreGallery()
                    }
                }
            }
            EmptyState {
                anchors.fill: parent
                visible: grid.count === 0 && !s.galleryLoading
                title: search.text ? "没有匹配的记录" : "作品会在这里积累"
                detail: search.text ? "换个关键词，或查看全部记录。" : "完成的图片、参数和失败诊断都会自动保存。"
            }
            Grid {
                anchors.fill: parent
                columns: 3
                spacing: 14
                visible: s.galleryLoading && grid.count === 0
                Repeater {
                    model: 6
                    Skeleton {
                        width: (page.width - 28) / 3
                        height: width * 1.15
                    }
                }
            }
        }
    }
    Timer {
        id: debounce
        interval: 220
        onTriggered: studio.searchGallery(search.text, status.currentIndex === 1 ? "COMPLETED" : status.currentIndex === 2 ? "FAILED" : "")
    }
    Dialog {
        id: batchDialog
        property string action: "category"
        anchors.centerIn: parent
        width: 360
        modal: true
        padding: 22
        title: action === "tags" ? "设置标签" : "设置分类"
        background: Rectangle {
            color: Theme.surface
            radius: 14
            border.color: Theme.border
        }
        ColumnLayout {
            width: parent.width
            spacing: 14
            MField {
                id: batchValue
                Layout.fillWidth: true
                placeholderText: batchDialog.action === "tags" ? "多个标签用英文逗号分隔" : "分类名称，留空清除"
            }
            MButton {
                text: "应用到所选作品"
                primary: true
                Layout.fillWidth: true
                onClicked: {
                    studio.batchAction(batchDialog.action, batchValue.text);
                    batchDialog.close();
                }
            }
        }
    }
}
