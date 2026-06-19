Set FSO = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
ps1Path = scriptDir & "\start_user_journey.ps1"

WshShell.Run "pwsh -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1Path & """"", 0, False
