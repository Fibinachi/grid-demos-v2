# Send GRID sales outreach emails via Outlook COM
# Reads .eml files and sends one every 3 minutes
param(
    [int]$IntervalSeconds = 180,
    [switch]$DryRun
)

$emlDir = "E:\grid\outputs\outreach\eml_files"
$sentLog = "E:\grid\outputs\outreach\outlook_sent.txt"

# Load list of already-sent
$sent = @{}
if (Test-Path $sentLog) {
    Get-Content $sentLog | ForEach-Object { $sent[$_] = $true }
}

$files = Get-ChildItem "$emlDir\*.eml" | Sort-Object Name
$pending = @($files | Where-Object { -not $sent.ContainsKey($_.Name) })

Write-Host "Outlook COM Sender"
Write-Host "=================="
Write-Host "Total .eml files : $($files.Count)"
Write-Host "Already sent     : $($files.Count - $pending.Count)"
Write-Host "Pending          : $($pending.Count)"
Write-Host "Interval         : $IntervalSeconds seconds ($([math]::Round($IntervalSeconds/60)) min)"
Write-Host "ETA              : $(if($pending.Count -gt 0){ "$([math]::Round($pending.Count * $IntervalSeconds / 60)) min" } else { "N/A" })"
if ($DryRun) { Write-Host "*** DRY RUN - no emails will be sent ***" -ForegroundColor Yellow }
Write-Host ""

if ($pending.Count -eq 0) {
    Write-Host "All done!" -ForegroundColor Green
    exit 0
}

# Connect to Outlook
try {
    $outlook = New-Object -ComObject Outlook.Application
} catch {
    Write-Host "ERROR: Cannot connect to Outlook. Is it installed and running?" -ForegroundColor Red
    exit 1
}

# Find the specified account
$targetEmail = "charlesaprescott@outlook.com"
$selected = $null
for ($i = 1; $i -le $namespace.Accounts.Count; $i++) {
    $acct = $namespace.Accounts.Item($i)
    if ($acct.SmtpAddress -eq $targetEmail) {
        $selected = $acct
        break
    }
}

if (-not $selected) {
    Write-Host "ERROR: Account '$targetEmail' not found in Outlook." -ForegroundColor Red
    Write-Host "Available accounts:" -ForegroundColor Yellow
    for ($i = 1; $i -le $namespace.Accounts.Count; $i++) {
        Write-Host "  $($namespace.Accounts.Item($i).SmtpAddress)"
    }
    exit 1
}
Write-Host "Using: $($selected.SmtpAddress)" -ForegroundColor Green

$success = 0
$fail = 0

foreach ($file in $pending) {
    $name = $file.Name
    Write-Host "[$($success + $fail + 1)/$($pending.Count)] $name" -NoNewline

    if ($DryRun) {
        Write-Host " [DRY RUN - skipped]" -ForegroundColor Yellow
        $success++
        continue
    }

    try {
        # Read .eml and send via Outlook
        $mail = $outlook.CreateItemFromTemplate($file.FullName)
        $mail.SendUsingAccount = $selected
        $mail.Send()
        
        # Log sent
        Add-Content -Path $sentLog -Value $name
        Write-Host " SENT" -ForegroundColor Green
        $success++
    } catch {
        Write-Host " FAILED: $_" -ForegroundColor Red
        $fail++
    }

    # Wait before next send
    if ($success + $fail -lt $pending.Count) {
        $waitMin = [math]::Round($IntervalSeconds / 60, 1)
        Write-Host "  Waiting $waitMin min..."
        Start-Sleep -Seconds $IntervalSeconds
    }
}

Write-Host ""
Write-Host "Done: $success sent, $fail failed" -ForegroundColor $(if($fail -eq 0){'Green'}else{'Yellow'})
