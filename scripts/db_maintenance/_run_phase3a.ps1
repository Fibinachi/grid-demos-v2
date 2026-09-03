@"
# Run Phase 3a - MTO Repoint
$logFile = "E:\grid\_phase3a_output.txt"
$venvPython = "E:\grid\.venv\Scripts\python.exe"

# Set UTF-8 encoding for this process
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

# Run and capture output
& $venvPython -u E:\grid\_dedup_3a_repoint_mto.py 2>&1 | Tee-Object -FilePath $logFile

Write-Host "`nDONE. Output logged to $logFile"
"@