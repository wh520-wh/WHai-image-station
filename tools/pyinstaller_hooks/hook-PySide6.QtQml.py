"""Collect only the QML modules used by this app, avoiding unrelated 3D/WebEngine plugins."""

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()


def used_module(entry):
    destination = entry[1].replace("\\", "/")
    module = destination.split("/qml/", 1)[-1].split("/")
    if module[0] == "QtQml":
        return True
    if module[0] != "QtQuick":
        return False
    if len(module) == 1:
        return True
    if module[1] not in {"Controls", "Templates", "Layouts", "Window", "Shapes"}:
        return False
    if module[1] == "Controls" and len(module) > 2:
        return module[2] in {"Basic", "impl"}
    return True


binaries += [entry for entry in qml_binaries if used_module(entry)]
datas += [entry for entry in qml_datas if used_module(entry)]
