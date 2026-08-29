Option Explicit

Dim sh, fso, root, ps1, powershell, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
ps1 = fso.BuildPath(root, "launchers\run_web_hidden.ps1")
powershell = sh.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"

If Not fso.FileExists(ps1) Then
  MsgBox "Thiếu file launcher:" & vbCrLf & ps1, vbCritical, "AUTO KVTM WEB"
  WScript.Quit 1
End If

cmd = Chr(34) & powershell & Chr(34) & _
      " -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File " & _
      Chr(34) & ps1 & Chr(34)

sh.Run cmd, 0, False
WScript.Quit 0
