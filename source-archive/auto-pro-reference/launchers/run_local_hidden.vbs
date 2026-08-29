Option Explicit

Dim sh, fso, root, dataDir, comspec, rc, scriptPath, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
dataDir = fso.BuildPath(root, "local_data")
If Not fso.FolderExists(dataDir) Then fso.CreateFolder(dataDir)
scriptPath = fso.BuildPath(root, "local_launcher_v10.py")
comspec = sh.ExpandEnvironmentStrings("%ComSpec%")
sh.CurrentDirectory = root

Function Q(ByVal s)
  Q = Chr(34) & s & Chr(34)
End Function

' Best path: pyw.exe uses Python 3.11 without creating a console at all.
rc = sh.Run(Q(comspec) & " /d /c " & Q("pyw -3.11 --version >nul 2>&1"), 0, True)
If rc = 0 Then
  sh.Run "pyw -3.11 " & Q(scriptPath), 0, False
  WScript.Quit 0
End If

' Second best: pythonw.exe, but only if it is Python 3.11.
cmd = Q(comspec) & " /d /s /c " & Q(Q("pythonw") & " -c " & Q("import sys; raise SystemExit(0 if sys.version_info[:2]==(3,11) else 1)") & " >nul 2>&1")
rc = sh.Run(cmd, 0, True)
If rc = 0 Then
  sh.Run "pythonw " & Q(scriptPath), 0, False
  WScript.Quit 0
End If

' Compatibility fallback: Python launcher inside a hidden console host.
rc = sh.Run(Q(comspec) & " /d /c " & Q("py -3.11 --version >nul 2>&1"), 0, True)
If rc = 0 Then
  cmd = Q(comspec) & " /d /s /c " & Q(Q("py") & " -3.11 " & Q(scriptPath))
  sh.Run cmd, 0, False
  WScript.Quit 0
End If

MsgBox "Không tìm thấy Python 3.11 64-bit." & vbCrLf & vbCrLf & _
       "Cài bằng:" & vbCrLf & "winget install -e --id Python.Python.3.11", _
       vbCritical, "AUTO KVTM PRO"
WScript.Quit 1
