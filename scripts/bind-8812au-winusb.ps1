# 把 RTL8812AU (VID_0BDA & PID_881A) 从 Realtek Wi-Fi 驱动切到 WinUSB，
# 让 libusb（内置图传的 devourer 收包代码）能直接访问 USB。需要管理员权限。
# 会对每个插过的 8812AU 实例生效；执行前先把当前注册表导出到脚本目录，
# 想还原回 Realtek 驱动时双击那个 .reg 文件，再拔插网卡。
# 和 scripts\bind-ch340-ch341.ps1 方向相反（那个是把 CH340 绑回串口驱动）。
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Start-Transcript -Path (Join-Path $here 'bind-8812au-winusb.log') -Force | Out-Null

$p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $p.IsInRole('Administrators')) {
    Write-Output '需要管理员权限：右键 PowerShell“以管理员身份运行”后再执行。'
    Stop-Transcript | Out-Null
    exit 1
}

$view = 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_0BDA&PID_881A'
$instances = Get-ChildItem $view -ErrorAction SilentlyContinue
if (-not $instances) {
    Write-Output '没找到 VID_0BDA&PID_881A 设备；插好图传网卡再跑一次。'
    Stop-Transcript | Out-Null
    exit 1
}

$backup = Join-Path $here ("rtl8812au-before-winusb-{0:yyyyMMdd-HHmmss}.reg" -f (Get-Date))
reg export 'HKLM\SYSTEM\CurrentControlSet\Enum\USB\VID_0BDA&PID_881A' $backup /y | Out-Null
Write-Output "已备份原注册表到 $backup"

foreach ($k in $instances) {
    $devId = "USB\VID_0BDA&PID_881A\$($k.PSChildName)"
    Write-Output "== $devId =="
    Set-ItemProperty $k.PSPath -Name Service -Value 'WinUSB'
    Set-ItemProperty $k.PSPath -Name Class -Value 'USBDevice'
    Set-ItemProperty $k.PSPath -Name ClassGUID -Value '{EC185E00-8A54-11e0-B13A-00DD010662DA}'
    Remove-ItemProperty $k.PSPath -Name Driver -ErrorAction SilentlyContinue
    Get-ItemProperty $k.PSPath | Select-Object Service, Class, ClassGUID | Format-List
    Get-PnpDevice -InstanceId $devId -ErrorAction SilentlyContinue | Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Get-PnpDevice -InstanceId $devId -ErrorAction SilentlyContinue | Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 3
pnputil /scan-devices | Out-Null
Start-Sleep -Seconds 3

Write-Output '== 结果（Service 应为 WinUSB）=='
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_0BDA&PID_881A' } | ForEach-Object {
    Write-Output ("Status: {0}  Class: {1}  Name: {2}" -f $_.Status, $_.Class, $_.FriendlyName)
}
Stop-Transcript | Out-Null
