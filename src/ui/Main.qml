import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"

ApplicationWindow {
    id: appWindow
    objectName: "studioWindow"
    width: 1320
    height: 860
    minimumWidth: 1000
    minimumHeight: 680
    visible: true
    title: "WHai Image Station"
    color: Theme.canvas
    font.family: Theme.font
    font.pixelSize: 13
    palette.window: Theme.surface
    palette.windowText: Theme.ink
    palette.text: Theme.ink
    palette.buttonText: Theme.ink
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.accentText
    property string currentPage: "create"
    readonly property bool modalOpen: viewer.visible || confirmDialog.visible
    property var visitedPages: ["create"]
    onCurrentPageChanged: if (visitedPages.indexOf(currentPage) < 0)
        visitedPages = visitedPages.concat([currentPage])
    readonly property Item activePageLoader: s.ready && pageRepeater.count ? pageRepeater.itemAt(pageStack.currentIndex) : null
    readonly property var s: studio.state
    readonly property var pages: [
        {
            id: "create",
            label: "创作",
            icon: "create",
            file: "CreatePage"
        },
        {
            id: "gallery",
            label: "作品库",
            icon: "gallery",
            file: "GalleryPage"
        },
        {
            id: "prompts",
            label: "提示词",
            icon: "prompts",
            file: "PromptsPage"
        },
        {
            id: "sources",
            label: "来源",
            icon: "sources",
            file: "SourcesPage"
        },
        {
            id: "tools",
            label: "工具",
            icon: "tools",
            file: "ToolsPage"
        },
        {
            id: "settings",
            label: "设置",
            icon: "settings",
            file: "SettingsPage"
        }
    ]
    function confirm(detail, action) {
        confirmDialog.detail = detail;
        confirmDialog.action = action;
        confirmDialog.open();
    }
    Connections {
        target: studio
        function onNavigate(page) {
            appWindow.currentPage = page;
            if (page === "tools")
                Qt.callLater(() => { if (appWindow.activePageLoader && appWindow.activePageLoader.item) appWindow.activePageLoader.item.toolTab = 0; });
        }
        function onMessage(text, error) {
            toast.text = text;
            toast.error = error;
            toast.visible = true;
            toastTimer.restart();
        }
        function onViewerRequested(record) {
            viewer.record = record;
            viewer.imageIndex = record.selected_image_index || 0;
            viewer.zoom = 1;
            viewer.angle = 0;
            viewer.open();
        }
    }
    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 184
            Layout.fillHeight: true
            color: Theme.surface
            Rectangle {
                anchors.right: parent.right
                height: parent.height
                width: 1
                color: Theme.border
            }
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 8
                RowLayout {
                    Layout.topMargin: 18
                    Layout.bottomMargin: 30
                    Layout.leftMargin: 8
                    spacing: 12
                    BrandMark {
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                    }
                    ColumnLayout {
                        spacing: 1
                        Heading {
                            text: "WHai"
                            font.pixelSize: 20
                        }
                        Caption {
                            text: "IMAGE STATION"
                            font.pixelSize: 8
                            font.letterSpacing: 1.1
                        }
                    }
                }
                Repeater {
                    id: navigationRepeater
                    model: appWindow.pages.filter(x => x.id !== "settings")
                    delegate: Button {
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 46
                        enabled: s.ready
                        Accessible.name: modelData.label
                        objectName: "nav_" + modelData.id
                        onClicked: appWindow.currentPage = modelData.id
                        background: Rectangle {
                            radius: 10
                            color: appWindow.currentPage === modelData.id ? Theme.accentWash : parent.hovered ? Theme.subtle : "transparent"
                            border.color: parent.activeFocus ? Theme.accent : "transparent"
                            Behavior on color {
                                ColorAnimation {
                                    duration: Theme.reduced ? 0 : 160
                                }
                            }
                        }
                        contentItem: RowLayout {
                            spacing: 14
                            Icon {
                                name: modelData.icon
                                tint: appWindow.currentPage === modelData.id ? Theme.accent : Theme.muted
                            }
                            Text {
                                text: modelData.label
                                font.family: Theme.font
                                font.pixelSize: 13
                                font.weight: appWindow.currentPage === modelData.id ? Font.DemiBold : Font.Normal
                                color: appWindow.currentPage === modelData.id ? Theme.accent : Theme.ink
                                Layout.fillWidth: true
                            }
                        }
                        leftPadding: 16
                        rightPadding: 16
                    }
                }
                Item {
                    Layout.fillHeight: true
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 64
                    radius: 10
                    color: Theme.canvas
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 4
                        Caption {
                            text: s.activeCount ? "正在创作 " + s.activeCount + " 个任务" : "本地工作台"
                            color: Theme.ink
                            font.pixelSize: 11
                        }
                        Caption {
                            text: s.activeCount ? "图片会自动保存" : "你的作品，由你保管"
                            font.pixelSize: 10
                        }
                    }
                }
                MButton {
                    objectName: "nav_settings"
                    Layout.fillWidth: true
                    text: "设置"
                    quiet: true
                    iconName: "settings"
                    onClicked: appWindow.currentPage = "settings"
                }
                Caption {
                    text: "v" + s.version
                    Layout.leftMargin: 14
                    font.pixelSize: 10
                    Layout.bottomMargin: 8
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 62
                color: Theme.canvas
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 32
                    anchors.rightMargin: 32
                    Caption {
                        text: "工作台  /  " + (appWindow.pages.find(x => x.id === appWindow.currentPage) || {}).label
                        font.pixelSize: 12
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Rectangle {
                        width: 6
                        height: 6
                        radius: 3
                        color: Theme.accent
                    }
                    Caption {
                        text: s.busy ? "正在处理…" : s.ready ? "已就绪" : "正在加载"
                        font.pixelSize: 11
                    }
                }
                Rectangle {
                    height: 1
                    width: parent.width
                    anchors.bottom: parent.bottom
                    color: Theme.border
                }
            }
            StackLayout {
                id: pageStack
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: 32
                currentIndex: Math.max(0, appWindow.pages.findIndex(x => x.id === appWindow.currentPage))
                opacity: 1
                NumberAnimation {
                    id: pageEntrance
                    target: pageStack
                    property: "opacity"
                    from: 0
                    to: 1
                    duration: Theme.reduced ? 80 : 150
                }
                onCurrentIndexChanged: pageEntrance.restart()
                Repeater {
                    id: pageRepeater
                    model: appWindow.pages
                    delegate: Loader {
                        required property var modelData
                        objectName: appWindow.currentPage === modelData.id ? "pageLoader" : ""
                        active: s.ready && appWindow.visitedPages.indexOf(modelData.id) >= 0
                        source: "pages/" + modelData.file + ".qml"
                        onLoaded: item.shell = appWindow
                    }
                }
            }
        }
    }
    Rectangle {
        id: splash
        anchors.fill: parent
        color: Theme.canvas
        opacity: s.ready ? 0 : 1
        visible: opacity > 0
        enabled: !s.ready
        Behavior on opacity {
            NumberAnimation {
                duration: Theme.reduced ? 80 : 200
                easing.type: Easing.OutCubic
            }
        }
        ColumnLayout {
            anchors.centerIn: parent
            width: 520
            spacing: 22
            BrandMark {
                id: launchMark
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 66
                Layout.preferredHeight: 66
                scale: 1
                opacity: 1
                ParallelAnimation {
                    running: true
                    NumberAnimation {
                        target: launchMark
                        property: "scale"
                        from: Theme.reduced ? 1 : 0.92
                        to: 1
                        duration: 240
                        easing.type: Easing.OutCubic
                    }
                    NumberAnimation {
                        target: launchMark
                        property: "opacity"
                        from: 0
                        to: 1
                        duration: 180
                    }
                }
            }
            Heading {
                text: "WHai Image Station"
                Layout.alignment: Qt.AlignHCenter
                font.pixelSize: 24
            }
            Caption {
                text: s.loadingText
                Layout.alignment: Qt.AlignHCenter
            }
            RowLayout {
                Layout.topMargin: 18
                spacing: 14
                ColumnLayout {
                    spacing: 14
                    Skeleton {
                        width: 218
                        height: 38
                    }
                    Skeleton {
                        width: 218
                        height: 116
                    }
                    Skeleton {
                        width: 218
                        height: 38
                    }
                }
                Skeleton {
                    width: 288
                    height: 220
                }
            }
        }
    }
    Rectangle {
        id: toast
        property string text: ""
        property bool error: false
        visible: false
        z: 20
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        width: Math.min(680, toastText.implicitWidth + 70)
        height: toastText.implicitHeight + 28
        radius: 12
        color: Theme.surface
        border.color: error ? Theme.danger : Theme.border
        Text {
            id: toastText
            anchors.fill: parent
            anchors.margins: 14
            anchors.rightMargin: 44
            text: toast.text
            color: toast.error ? Theme.danger : Theme.ink
            font.family: Theme.font
            font.pixelSize: 13
            wrapMode: Text.WordWrap
        }
        MButton {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 36
            text: "×"
            quiet: true
            onClicked: toast.visible = false
        }
    }
    Timer {
        id: toastTimer
        interval: toast.error ? 10000 : 4000
        onTriggered: toast.visible = false
    }
    Dialog {
        id: confirmDialog
        property string detail: ""
        property var action
        anchors.centerIn: parent
        width: 420
        modal: true
        padding: 24
        title: "确认操作"
        background: Rectangle {
            color: Theme.surface
            radius: 14
            border.color: Theme.border
        }
        ColumnLayout {
            width: parent.width
            spacing: 22
            Caption {
                text: confirmDialog.detail
                color: Theme.ink
                font.pixelSize: 14
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 12
                MButton {
                    text: "取消"
                    onClicked: confirmDialog.close()
                }
                MButton {
                    text: "确认删除"
                    destructive: true
                    onClicked: {
                        confirmDialog.close();
                        if (confirmDialog.action)
                            confirmDialog.action();
                    }
                }
            }
        }
    }
    Popup {
        id: viewer
        property var record: ({})
        property int imageIndex: 0
        property real zoom: 1
        property real angle: 0
        readonly property string currentPath: (record.result_paths || [])[imageIndex] || record.image_path || ""
        x: 24
        y: 24
        width: appWindow.width - 48
        height: appWindow.height - 48
        modal: true
        padding: 18
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            color: Theme.surface
            radius: 16
            border.color: Theme.border
        }
        enter: Transition {
            NumberAnimation {
                property: "opacity"
                from: 0
                to: 1
                duration: 140
            }
        }
        exit: Transition {
            NumberAnimation {
                property: "opacity"
                to: 0
                duration: 100
            }
        }
        RowLayout {
            anchors.fill: parent
            spacing: 22
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12
                Flickable {
                    id: imageViewport
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    contentWidth: Math.max(width, viewer.angle % 180 === 0 ? fullImage.width : fullImage.height)
                    contentHeight: Math.max(height, viewer.angle % 180 === 0 ? fullImage.height : fullImage.width)
                    Image {
                        id: fullImage
                        x: (imageViewport.contentWidth - width) / 2
                        y: (imageViewport.contentHeight - height) / 2
                        width: (viewer.angle % 180 === 0 ? imageViewport.width : imageViewport.height) * viewer.zoom
                        height: (viewer.angle % 180 === 0 ? imageViewport.height : imageViewport.width) * viewer.zoom
                        rotation: viewer.angle
                        fillMode: Image.PreserveAspectFit
                        source: (viewer.record.images || [])[viewer.imageIndex] || viewer.record.imageUrl || ""
                        sourceSize: Qt.size(4096, 4096)
                        asynchronous: true
                        cache: false
                    }
                    WheelHandler {
                        onWheel: event => {
                            viewer.zoom = Math.max(1, Math.min(5, viewer.zoom + (event.angleDelta.y > 0 ? 0.2 : -0.2)));
                            event.accepted = true;
                        }
                    }
                    EmptyState {
                        anchors.fill: parent
                        visible: !fullImage.source || fullImage.status === Image.Error
                        title: viewer.record.status === "FAILED" ? "这次生成没有完成" : "图片不可用"
                        detail: "右侧保留了提示词、参数与诊断，可以调整后重新创作。"
                    }
                    Skeleton {
                        anchors.fill: parent
                        visible: fullImage.status === Image.Loading
                    }
                }
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10
                    MButton {
                        text: "上一张"
                        visible: (viewer.record.images || []).length > 1
                        enabled: viewer.imageIndex > 0
                        onClicked: {
                            viewer.imageIndex--;
                            viewer.zoom = 1;
                        }
                    }
                    Caption {
                        text: (viewer.imageIndex + 1) + " / " + Math.max(1, (viewer.record.images || []).length)
                        visible: (viewer.record.images || []).length > 1
                    }
                    MButton {
                        text: "下一张"
                        visible: (viewer.record.images || []).length > 1
                        enabled: viewer.imageIndex < (viewer.record.images || []).length - 1
                        onClicked: {
                            viewer.imageIndex++;
                            viewer.zoom = 1;
                        }
                    }
                    MButton {
                        text: "适应窗口"
                        onClicked: {
                            viewer.zoom = 1;
                            viewer.angle = 0;
                        }
                    }
                    MButton {
                        text: "放大"
                        onClicked: viewer.zoom = Math.min(5, viewer.zoom + 0.5)
                    }
                    MButton {
                        text: "旋转"
                        onClicked: viewer.angle += 90
                    }
                }
            }
            ColumnLayout {
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                spacing: 16
                RowLayout {
                    Layout.fillWidth: true
                    Heading {
                        text: "作品详情"
                        font.pixelSize: 18
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    MButton {
                        text: "关闭"
                        quiet: true
                        onClicked: viewer.close()
                    }
                }
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ColumnLayout {
                        width: parent.width
                        spacing: 16
                        Caption {
                            text: viewer.record.modelText || ""
                        }
                        TextArea {
                            text: viewer.record.prompt || ""
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            color: Theme.ink
                            font.family: Theme.font
                            font.pixelSize: 14
                            Layout.fillWidth: true
                            background: null
                            padding: 0
                        }
                        Caption {
                            text: viewer.record.dateText || ""
                        }
                        Caption {
                            text: viewer.record.isLocalEdit ? "处理参数" : "生成参数"
                            font.weight: Font.DemiBold
                        }
                        TextArea {
                            text: JSON.stringify(viewer.record.params || {}, null, 2)
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            color: Theme.muted
                            font.pixelSize: 12
                            Layout.fillWidth: true
                            background: null
                            padding: 0
                        }
                        Caption {
                            text: "诊断"
                            font.weight: Font.DemiBold
                            visible: !!viewer.record.error
                        }
                        TextArea {
                            text: viewer.record.error || ""
                            visible: !!text
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            color: Theme.danger
                            font.family: Theme.font
                            font.pixelSize: 12
                            Layout.fillWidth: true
                            background: null
                            padding: 0
                        }
                        MButton {
                            text: "复制诊断"
                            visible: !!viewer.record.error
                            onClicked: studio.copyText(JSON.stringify(viewer.record.diagnostic || {}, null, 2))
                        }
                    }
                }
                MButton {
                    text: "复用提示词与参数"
                    visible: !viewer.record.isLocalEdit
                    Layout.fillWidth: true
                    primary: true
                    onClicked: {
                        studio.reuseRecord(viewer.record);
                        viewer.close();
                    }
                }
                MButton {
                    text: viewer.record.isLocalEdit ? "复制说明" : "复制提示词"
                    Layout.fillWidth: true
                    onClicked: studio.copyText(viewer.record.prompt || "")
                }
                MButton {
                    text: "在图片工具中处理"
                    iconName: "resize"
                    Layout.fillWidth: true
                    visible: !!viewer.currentPath
                    onClicked: {
                        studio.editImage(viewer.currentPath);
                        viewer.close();
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: !!viewer.currentPath
                    MButton {
                        text: "另存图片"
                        Layout.fillWidth: true
                        onClicked: studio.saveImage(viewer.currentPath)
                    }
                    MButton {
                        text: "复制图片"
                        Layout.fillWidth: true
                        onClicked: studio.copyImage(viewer.currentPath)
                    }
                }
                MButton {
                    text: "作为参考图"
                    Layout.fillWidth: true
                    visible: !!viewer.currentPath
                    enabled: s.caps.reference
                    onClicked: {
                        studio.useImageAsReference(viewer.currentPath);
                        viewer.close();
                    }
                }
                MButton {
                    text: "打开图片"
                    Layout.fillWidth: true
                    visible: !!viewer.currentPath
                    onClicked: studio.openPath(viewer.currentPath)
                }
            }
        }
    }
}
