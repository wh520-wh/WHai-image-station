pragma Singleton
import QtQuick

QtObject {
    readonly property bool dark: studio.state.dark
    readonly property bool reduced: studio.state.reducedMotion
    readonly property color canvas: dark ? "#141916" : "#F4F5F2"
    readonly property color surface: dark ? "#1D2420" : "#FFFFFF"
    readonly property color subtle: dark ? "#28312B" : "#EFF2ED"
    readonly property color ink: dark ? "#EEF3EE" : "#202C25"
    readonly property color muted: dark ? "#A2B2A8" : "#65736A"
    readonly property color border: dark ? "#354038" : "#E1E7E0"
    readonly property color accent: dark ? "#90CDAA" : "#285D45"
    readonly property color accentWash: dark ? "#2B4033" : "#E5EFE6"
    readonly property color accentText: dark ? "#14281C" : "#FFFFFF"
    readonly property color danger: dark ? "#FFAFA3" : "#AC3E32"
    readonly property string font: Qt.platform.os === "windows" ? "Microsoft YaHei UI" : "sans-serif"
}
