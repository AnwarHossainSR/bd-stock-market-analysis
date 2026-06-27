$action = New-ScheduledTaskAction -Execute "$PSScriptRoot\..\.venv\Scripts\python.exe" -Argument "tools\refresh.py" -WorkingDirectory "$PSScriptRoot\.."
$trigger = New-ScheduledTaskTrigger -Daily -At 5pm
Register-ScheduledTask -TaskName "DSE Daily Refresh" -Action $action -Trigger $trigger -Force
