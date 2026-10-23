# 把 CH340 (VID_1A86 & PID_7523) 从 WinUSB 绑回 WCH CH341 串口驱动，
# 让它重新以 COM 口出现。调用时 Windows 会弹 UAC 确认框。
# 对比 scripts\bind-8812au-winusb.ps1：那个是把 8812AU 绑成 WinUSB，方向相反。
# 背景：Windows 对没匹配到 INF 的 CH340 会自动绑 WinUSB，设备就不出 COM 口了。
$ErrorActionPreference = 'Continue'

$view = 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_1A86&PID_7523'
$instances = Get-ChildItem $view -ErrorAction SilentlyContinue
if (-not $instances) { Write-Output '没找到 VID_1A86&PID_7523 设备；确认插好了再跑一次。'; Read-Host '按回车关闭'; exit 1 }

# 驱动服务名：官方安装包（CH341SER）装的服务。没有就说明驱动没装。
$svc = Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Services' |
    Where-Object { $_.PSChildName -like 'CH341S*' } |
    Select-Object -First 1 -ExpandProperty PSChildName
if (-not $svc) { Write-Output '系统里没有 WCH CH341 驱动服务，先装官网 CH341SER。'; Read-Host '按回车关闭'; exit 1 }
Write-Output "使用驱动服务: $svc"

foreach ($k in $instances) {
    Write-Output "== 装置 $($k.PSChildName) =="
    Set-ItemProperty $k.PSPath -Name Service -Value $svc
    Set-ItemProperty $k.PSPath -Name Class -Value 'Ports'
    Set-ItemProperty $k.PSPath -Name ClassGUID -Value '{4d36e978-e325-11ce-bfc1-08002be10318}'
    Get-ItemProperty $k.PSPath | Select-Object Service, Class, ClassGUID | Format-List
    Get-PnpDevice -InstanceId $k.PSChildName.Replace('&','`&') 2>$null |
        Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue
    Get-PnpDevice -InstanceId $k.PSChildName.Replace('&','`&') 2>$null |
        Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2
pnputil /scan-devices | Out-Null
Start-Sleep -Seconds 3

Write-Output '== 结果 =='
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_1A86' } | ForEach-Object {
    Write-Output ("Status: {0}  Class: {1}  Name: {2}" -f $_.Status, $_.Class, $_.FriendlyName)
}
Read-Host '完成，按回车关闭'
