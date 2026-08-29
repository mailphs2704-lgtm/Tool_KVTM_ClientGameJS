@echo off
setlocal EnableExtensions
title KVTM VM C003 Network Diagnostic

set "ROOT=%~dp0"
set "VBox=C:\Program Files\ldplayer9box\VBoxManage.exe"
set "ADB=C:\platform-tools\adb.exe"
set "VM=KVTM_C003_SIDECAR_v01"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "OUT=%ROOT%local_data\kvtm_vm\c003_diag_%STAMP%"
set "ZIP=%ROOT%local_data\kvtm_vm\c003_diag_%STAMP%.zip"

mkdir "%OUT%" 2>nul

echo KVTM VM C003 network diagnostic
echo.
echo SAFETY:
echo   - read-only diagnostic only
echo   - targets ONLY %VM%
echo   - does NOT start or stop any VM
echo   - does NOT modify NIC, NAT, disk, ADB configuration, WHPX, Hyper-V, or LDPlayer
echo   - guest interaction is console text injection plus screenshots only
echo.

if not exist "%VBox%" (
  echo ERROR: VBoxManage not found: %VBox%
  exit /b 1
)

if not exist "%ADB%" (
  echo ERROR: adb.exe not found: %ADB%
  exit /b 1
)

"%VBox%" list runningvms | findstr /I /C:"%VM%" >nul
if errorlevel 1 (
  echo ERROR: %VM% is not currently running.
  echo Start C003 and enter Android console first, then run this diagnostic again.
  exit /b 2
)

(
  echo ===== C003 HOST DIAGNOSTIC =====
  echo Generated: %date% %time%
  echo VM: %VM%
  echo.
  echo ===== RUNNING VMS =====
  "%VBox%" list runningvms
  echo.
  echo ===== VM NETWORK =====
  "%VBox%" showvminfo "%VM%" --machinereadable ^| findstr /I "nic1 nictype1 natnet1 cableconnected1 macaddress1 natpf1"
  echo.
  echo ===== HOST PORTS =====
  netstat -ano ^| findstr /I ":5585 :15685 :5037 :5038"
  echo.
  echo ===== ADB SERVER 5037 =====
  "%ADB%" devices -l
  echo.
  echo ===== ADB SERVER 5038 =====
  "%ADB%" -P 5038 devices -l
  echo.
  echo ===== HOST PROCESSES =====
  tasklist ^| findstr /I "adb.exe VirtualBoxVM.exe VBoxSVC.exe"
) > "%OUT%\host_diag.txt" 2>&1

call :GuestShot "01_props.png" "echo ===C003_PROP===; getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.product.cpu.abi; getprop ro.secure; getprop ro.adb.secure; getprop ro.debuggable; getprop service.adb.tcp.port; getprop init.svc.adbd"
call :GuestShot "02_link_addr.png" "echo ===C003_LINK===; ip -s link show wifi_eth; echo ===ADDR===; ip addr show wifi_eth"
call :GuestShot "03_rules_routes.png" "echo ===C003_RULE===; ip rule; echo ===ROUTE===; ip route show table all"
call :GuestShot "04_neigh_arp.png" "echo ===C003_NEIGH===; ip neigh show dev wifi_eth; echo ===ARP===; cat /proc/net/arp"
call :GuestShot "05_sysfs.png" "echo ===C003_SYSFS===; cat /sys/class/net/wifi_eth/operstate; cat /sys/class/net/wifi_eth/carrier; cat /sys/class/net/wifi_eth/address"
call :GuestShot "06_adb.png" "echo ===C003_ADB===; ps -A | grep adbd; ls -ldZ /data/misc/adb; ls -lZ /data/misc/adb/adb_keys; wc -c /data/misc/adb/adb_keys"
call :GuestShot "07_dmesg.png" "echo ===C003_DMESG===; dmesg | grep -i -E 'e1000|wifi_eth|eth0|netlink|avc|denied' | tail -n 35"
call :GuestShot "08_adblog.png" "echo ===C003_ADBLOG===; logcat -d -b all 2>/dev/null | grep -i -E 'adbd|adb_auth|auth' | tail -n 35"

(
  echo KVTM C003 diagnostic bundle
  echo Generated: %date% %time%
  echo VM: %VM%
  echo.
  echo Purpose:
  echo   Diagnose the current C003 network / NAT / ADB blocker without changing VM state.
  echo.
  echo Current investigation checkpoint before this collector:
  echo   - Android-x86 booted successfully.
  echo   - wifi_eth carrier was up.
  echo   - IPv4 10.0.2.15/24 and main-table route had been added at runtime.
  echo   - policy rule lookup main had been added at runtime.
  echo   - ARP resolution for 10.0.2.2 was failing.
  echo   - ADB guest daemon was listening on TCP 5555 but host transports remained offline / failed to connect.
  echo.
  echo Files:
  echo   host_diag.txt       Host VirtualBox / port / ADB snapshot
  echo   01_props.png        Android properties
  echo   02_link_addr.png    Interface counters and addresses
  echo   03_rules_routes.png Android policy rules and routes
  echo   04_neigh_arp.png    Neighbor and ARP state
  echo   05_sysfs.png        Link carrier and MAC
  echo   06_adb.png          adbd and adb_keys state
  echo   07_dmesg.png        Network / SELinux kernel messages
  echo   08_adblog.png       ADB authentication log messages
) > "%OUT%\README.txt"

powershell -NoProfile -Command "Compress-Archive -Path '%OUT%\*' -DestinationPath '%ZIP%' -Force" >nul 2>&1
if errorlevel 1 (
  echo WARNING: ZIP creation failed. Upload the folder instead:
  echo   %OUT%
  exit /b 3
)

echo.
echo ==============================================
echo C003 diagnostic collection completed safely.
echo ==============================================
echo Upload this ONE file to ChatGPT:
echo   %ZIP%
echo.
exit /b 0

:GuestShot
set "SHOT=%~1"
set "GCMD=%~2"
echo Collecting %SHOT%...
"%VBox%" controlvm "%VM%" keyboardputstring "%GCMD%" >nul 2>&1
if errorlevel 1 (
  echo WARNING: guest text injection failed for %SHOT%>>"%OUT%\collector_warnings.txt"
  goto :eof
)
"%VBox%" controlvm "%VM%" keyboardputscancode 1c 9c >nul 2>&1
timeout /t 2 /nobreak >nul
"%VBox%" controlvm "%VM%" screenshotpng "%OUT%\%SHOT%" >nul 2>&1
if errorlevel 1 echo WARNING: screenshot failed for %SHOT%>>"%OUT%\collector_warnings.txt"
goto :eof
