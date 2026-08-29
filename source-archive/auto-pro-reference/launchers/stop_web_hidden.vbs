Option Explicit
Dim sh, fso, root, script
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
script = fso.BuildPath(root, "launchers\stop_web_hidden.ps1")
sh.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File " & Chr(34) & script & Chr(34), 0, False
