param([string]$ExePath = (Join-Path $PSScriptRoot '灵感屿.exe'))
$ErrorActionPreference = 'Stop'
$ExePath = (Resolve-Path -LiteralPath $ExePath).Path
$taskBytes = [IO.File]::ReadAllBytes($ExePath)
$taskPe = [BitConverter]::ToInt32($taskBytes, 0x3c)
if ([BitConverter]::ToUInt32($taskBytes, $taskPe) -ne 0x4550 -or
    [BitConverter]::ToUInt16($taskBytes, $taskPe + 24 + 68) -ne 2) {
    throw '启动器不是 Windows GUI 可执行文件。'
}
$taskStart = New-Object Diagnostics.ProcessStartInfo
$taskStart.FileName = $ExePath
$taskStart.Arguments = '--self-test'
$taskStart.WorkingDirectory = [IO.Path]::GetTempPath()
$taskStart.UseShellExecute = $false
$taskStart.CreateNoWindow = $true
$taskStart.RedirectStandardOutput = $true
$taskStart.RedirectStandardError = $true
$taskStart.StandardOutputEncoding = New-Object Text.UTF8Encoding($false)
$taskStart.StandardErrorEncoding = New-Object Text.UTF8Encoding($false)
$taskProcess = [Diagnostics.Process]::Start($taskStart)
try {
    $taskOutput = $taskProcess.StandardOutput.ReadToEnd()
    $taskError = $taskProcess.StandardError.ReadToEnd()
    $taskProcess.WaitForExit()
    if ($taskProcess.ExitCode -ne 0) { throw "启动器自检失败：$taskError" }
    Write-Output 'PASS: Windows GUI subsystem; launch is independent of current working directory'
    Write-Output $taskOutput.Trim()
} finally { $taskProcess.Dispose() }
