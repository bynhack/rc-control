# 把 exe 依赖的第三方 DLL 复制到 exe 旁，这样 target\release\rc-control.exe
# 可以不带 MSYS2 环境直接双击运行（发布前同样要把这些一起打包）。
# 用法：powershell -File scripts\deploy-dlls.ps1 [exe路径，默认 target\release\rc-control.exe]

param(
    [string]$Exe = "target\release\rc-control.exe"
)

$MsysBin = "C:\msys64\ucrt64\bin"
if (-not (Test-Path $Exe)) { Write-Error "找不到 $Exe，先 cargo build"; exit 1 }
$dest = Split-Path (Resolve-Path $Exe)
if (-not (Test-Path "$MsysBin\gcc.exe")) { Write-Error "MSYS2 不在 C:\msys64"; exit 1 }

$frontier = @("avcodec-63.dll", "avformat-63.dll", "avutil-61.dll", "swscale-10.dll", "libsodium-26.dll", "libusb-1.0.dll")
$done = @{}

while ($frontier.Count -gt 0) {
    $dll = $frontier[0]
    $frontier = @($frontier | Select-Object -Skip 1)
    if ($done.ContainsKey($dll)) { continue }
    $done[$dll] = $true
    $src = Join-Path $MsysBin $dll
    if (-not (Test-Path $src)) { Write-Warning "缺 $src"; continue }
    Copy-Item $src (Join-Path $dest $dll) -Force
    Write-Output "copied $dll"
    # 递归：这些 DLL 自己还 import 谁（只看 msys2 一侧的非系统 DLL）
    & C:\msys64\ucrt64\bin\objdump.exe -p $src |
        Select-String 'DLL Name' |
        ForEach-Object { $_.Line.Trim() -replace '^DLL Name: ', '' } |
        Where-Object { $_ -notmatch '^ntdll|api-ms-win-|^(advapi32|bcryptprimitives|cfgmgr32|dwmapi|gdi32|imm32|kernel32|ntdll|ole32|oleaut32|opengl32|setupapi|shell32|shlwapi|user32|uxtheme|uiautomationcore|ws2_32|ws2_32)\.dll$' } |
        ForEach-Object { $frontier += $_ }
}

Write-Output "完成：$($done.Count) 个 DLL 已复制"
