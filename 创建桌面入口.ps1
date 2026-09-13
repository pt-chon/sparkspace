$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskExe = Join-Path $taskRoot '灵感屿.exe'
$taskUseExe = Test-Path -LiteralPath $taskExe -PathType Leaf
if (-not $taskUseExe) {
    $taskPython = 'C:\msys64\ucrt64\bin\pythonw.exe'
    if (-not (Test-Path -LiteralPath $taskPython)) {
        $taskPython = (Get-Command pythonw.exe -ErrorAction Stop).Source
    }
}
$taskDesktop = [Environment]::GetFolderPath('DesktopDirectory')
$taskShell = New-Object -ComObject WScript.Shell
foreach ($taskEntry in @(@{ Name = '灵感屿'; Extra = '' }, @{ Name = '灵感屿 · 悬浮速记'; Extra = ' --quick' })) {
    $taskLink = $taskShell.CreateShortcut((Join-Path $taskDesktop ($taskEntry.Name + '.lnk')))
    if ($taskUseExe) {
        $taskLink.TargetPath = $taskExe
        $taskLink.Arguments = $taskEntry.Extra.Trim()
    } else {
        $taskLink.TargetPath = $taskPython
        $taskLink.Arguments = '"' + (Join-Path $taskRoot 'launch.pyw') + '"' + $taskEntry.Extra
    }
    $taskLink.WorkingDirectory = $taskRoot
    $taskLink.Description = '记录灵感、发散思考，让 AI 帮你继续完善。'
    if ($taskUseExe) { $taskLink.IconLocation = $taskExe + ',0' }
    elseif (Test-Path -LiteralPath (Join-Path $taskRoot 'public\icon.ico')) { $taskLink.IconLocation = (Join-Path $taskRoot 'public\icon.ico') + ',0' }
    $taskLink.Save()
}
Write-Output '已创建桌面入口：灵感屿、灵感屿 · 悬浮速记。'
