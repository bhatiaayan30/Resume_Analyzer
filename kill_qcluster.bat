@echo off
echo Killing all running manage.py qcluster processes...
powershell -Command "Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'manage.py qcluster'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Done!
