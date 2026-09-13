param([string]$Pythonw = '')
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $taskCompiler)) { throw '未找到 Windows .NET Framework 4 编译器。' }
if (-not $Pythonw) {
    $Pythonw = 'C:\msys64\ucrt64\bin\pythonw.exe'
    if (-not (Test-Path -LiteralPath $Pythonw)) {
        $taskCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        if ($taskCommand) { $Pythonw = $taskCommand.Source }
    }
}
if (-not (Test-Path -LiteralPath $Pythonw -PathType Leaf)) {
    throw '请用 -Pythonw 指定已安装且包含 Tkinter 的 Python 3.10+ 的 pythonw.exe。'
}
$Pythonw = (Resolve-Path -LiteralPath $Pythonw).Path
$taskBuild = Join-Path $taskRoot 'qa-output\exe-build'
[IO.Directory]::CreateDirectory($taskBuild) | Out-Null
$taskResource = Join-Path $taskBuild 'pythonw-path.txt'
[IO.File]::WriteAllText($taskResource, $Pythonw, (New-Object Text.UTF8Encoding($false)))
$taskExe = Join-Path $taskRoot '灵感屿.exe'
& $taskCompiler /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 /reference:System.Windows.Forms.dll "/resource:$taskResource,Sparkspace.PythonwPath" "/win32icon:$(Join-Path $taskRoot 'public\icon.ico')" "/out:$taskExe" (Join-Path $taskRoot 'Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw '启动器编译失败。' }
& (Join-Path $taskRoot 'test_exe.ps1') -ExePath $taskExe
Write-Output "已构建：$taskExe"
Write-Output "首选 Python：$Pythonw；不存在时查找 PATH 和标准 Python 注册表安装位置。"
