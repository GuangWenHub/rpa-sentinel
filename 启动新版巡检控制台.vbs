Option Explicit
Dim shell, files, folder, pythonwPath, scriptPath, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = files.BuildPath(files.BuildPath(files.BuildPath(folder, ".venv"), "Scripts"), "pythonw.exe")
scriptPath = files.BuildPath(files.BuildPath(folder, "app"), "qt_console.py")

If Not files.FileExists(pythonwPath) Then
  MsgBox "The Qt environment is missing. Run: python -m venv .venv", vbCritical, "RPA Monitor"
  WScript.Quit 1
End If

If Not files.FileExists(scriptPath) Then
  MsgBox "The Qt console entry is missing.", vbCritical, "RPA Monitor"
  WScript.Quit 1
End If

command = """" & pythonwPath & """ """ & scriptPath & """"
shell.Run command, 0, False
