import QtQuick

Item {
    id: root
    property string name: "create"
    property color tint: Theme.muted
    width: 20
    height: 20
    implicitWidth: 20
    implicitHeight: 20
    readonly property var paths: ({
            create: '<path d="M12 3v18M3 12h18"/><path d="m5 5 2 2m10 10 2 2m0-14-2 2M7 17l-2 2"/>',
            gallery: '<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8" cy="8" r="1.5"/><path d="m4 17 5-5 4 4 3-3 5 5"/>',
            prompts: '<path d="M5 3h14v18l-7-4-7 4z"/><path d="M9 8h6m-6 4h4"/>',
            sources: '<path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/>',
            tools: '<rect x="3" y="4" width="7" height="6" rx="2"/><rect x="14" y="14" width="7" height="6" rx="2"/><path d="M10 7h7v7M7 10v7h7"/>',
            settings: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="none"/><circle cx="15" cy="17" r="3" fill="none"/>',
            arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
            check: '<path d="m5 12 4 4L19 6"/>',
            folder: '<path d="M3 7V5h7l2 2h9v12H3z"/>',
            search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
            close: '<path d="m6 6 12 12M18 6 6 18"/>',
            chevron: '<path d="m7 10 5 5 5-5"/>',
            image: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m4 17 6-6 5 5 3-3 3 3"/>',
            bolt: '<path d="m13 2-9 12h7l-1 8 10-13h-7z"/>'
        })
    Image {
        anchors.fill: parent
        sourceSize: Qt.size(40, 40)
        source: "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="' + root.tint + '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + (root.paths[root.name] || root.paths.create) + '</svg>')
    }
}
