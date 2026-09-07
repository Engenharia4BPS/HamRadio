param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $InstallerRoot "setup-vector.ps1"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $args = @(
        '-NoProfile',
        '-ExecutionPolicy','Bypass',
        '-File',("`"{0}`"" -f $PSCommandPath),
        '-InstallRoot',("`"{0}`"" -f $InstallRoot)
    )
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $args | Out-Null
    exit 0
}

if (-not (Test-Path $SetupScript -PathType Leaf)) {
    throw "setup-vector.ps1 was not found: $SetupScript"
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

function Invoke-SetupState {
    $raw = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript -InstallRoot $InstallRoot -AsJson 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($raw | Out-String).Trim()
    if ($exitCode -ne 0) {
        throw "Setup state query failed (exit $exitCode).`r`n$text"
    }
    try { return ($text | ConvertFrom-Json) }
    catch { throw "Setup state JSON is invalid.`r`n$text" }
}

function Invoke-SetupBackend([switch]$Apply) {
    $arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$SetupScript,'-InstallRoot',$InstallRoot)
    if ($Apply) { $arguments += '-Apply' }
    $raw = & powershell.exe @arguments 2>&1
    $exitCode = $LASTEXITCODE
    [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($raw | Out-String).TrimEnd()
    }
}

function Runtime-Label($runtime) {
    if (-not $runtime.python_exe) { return "MISSING" }
    if ($runtime.tkinter -and $runtime.pyserial -and $runtime.pywin32) { return "OK" }
    return "INCOMPLETE"
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "GADX Vector Setup"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(900,700)
$form.MinimumSize = New-Object System.Drawing.Size(820,620)
$form.Font = New-Object System.Drawing.Font("Segoe UI",9)

$title = New-Object System.Windows.Forms.Label
$title.Text = "GADX VECTOR SETUP"
$title.Font = New-Object System.Drawing.Font("Segoe UI Semibold",18)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(22,16)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "D8 product launcher over the validated D1-D7 backend"
$subtitle.AutoSize = $true
$subtitle.Location = New-Object System.Drawing.Point(25,54)
$form.Controls.Add($subtitle)

$group = New-Object System.Windows.Forms.GroupBox
$group.Text = "Installation status"
$group.Location = New-Object System.Drawing.Point(20,82)
$group.Size = New-Object System.Drawing.Size(842,190)
$group.Anchor = 'Top,Left,Right'
$form.Controls.Add($group)

function Add-StatusLabel([string]$caption,[int]$x,[int]$y) {
    $cap = New-Object System.Windows.Forms.Label
    $cap.Text = $caption
    $cap.AutoSize = $true
    $cap.Location = New-Object System.Drawing.Point($x,$y)
    $cap.Font = New-Object System.Drawing.Font("Segoe UI Semibold",9)
    $group.Controls.Add($cap)

    $value = New-Object System.Windows.Forms.Label
    $value.Text = "..."
    $value.AutoSize = $true
    $value.Location = New-Object System.Drawing.Point(($x + 125),$y)
    $group.Controls.Add($value)
    return $value
}

$releaseValue = Add-StatusLabel "Release" 18 30
$classValue = Add-StatusLabel "Detected" 18 60
$modeValue = Add-StatusLabel "Recommended" 18 90
$payloadValue = Add-StatusLabel "Payload drift" 18 120
$serviceValue = Add-StatusLabel "Service" 420 30
$runtimeValue = Add-StatusLabel "Runtime" 420 60
$com0comValue = Add-StatusLabel "com0com" 420 90
$safetyValue = Add-StatusLabel "Safety" 420 120

$detailsLabel = New-Object System.Windows.Forms.Label
$detailsLabel.Text = "Preview / execution log"
$detailsLabel.AutoSize = $true
$detailsLabel.Location = New-Object System.Drawing.Point(20,282)
$detailsLabel.Font = New-Object System.Drawing.Font("Segoe UI Semibold",9)
$form.Controls.Add($detailsLabel)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ReadOnly = $true
$logBox.ScrollBars = "Both"
$logBox.WordWrap = $false
$logBox.Font = New-Object System.Drawing.Font("Consolas",9)
$logBox.Location = New-Object System.Drawing.Point(20,306)
$logBox.Size = New-Object System.Drawing.Size(842,285)
$logBox.Anchor = 'Top,Bottom,Left,Right'
$form.Controls.Add($logBox)

$statusBar = New-Object System.Windows.Forms.Label
$statusBar.Text = "Ready."
$statusBar.AutoSize = $true
$statusBar.Location = New-Object System.Drawing.Point(22,607)
$statusBar.Anchor = 'Bottom,Left'
$form.Controls.Add($statusBar)

$refreshButton = New-Object System.Windows.Forms.Button
$refreshButton.Text = "Refresh"
$refreshButton.Size = New-Object System.Drawing.Size(100,32)
$refreshButton.Location = New-Object System.Drawing.Point(432,615)
$refreshButton.Anchor = 'Bottom,Right'
$form.Controls.Add($refreshButton)

$previewButton = New-Object System.Windows.Forms.Button
$previewButton.Text = "Run Preview"
$previewButton.Size = New-Object System.Drawing.Size(110,32)
$previewButton.Location = New-Object System.Drawing.Point(542,615)
$previewButton.Anchor = 'Bottom,Right'
$form.Controls.Add($previewButton)

$applyButton = New-Object System.Windows.Forms.Button
$applyButton.Text = "Apply"
$applyButton.Size = New-Object System.Drawing.Size(100,32)
$applyButton.Location = New-Object System.Drawing.Point(662,615)
$applyButton.Anchor = 'Bottom,Right'
$applyButton.Enabled = $false
$form.Controls.Add($applyButton)

$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = "Close"
$closeButton.Size = New-Object System.Drawing.Size(90,32)
$closeButton.Location = New-Object System.Drawing.Point(772,615)
$closeButton.Anchor = 'Bottom,Right'
$form.Controls.Add($closeButton)

$script:currentState = $null
$script:previewPassed = $false

function Set-Busy([bool]$busy,[string]$message) {
    $form.UseWaitCursor = $busy
    $refreshButton.Enabled = -not $busy
    $previewButton.Enabled = -not $busy
    $closeButton.Enabled = -not $busy
    if ($busy) { $applyButton.Enabled = $false }
    $statusBar.Text = $message
    $form.Refresh()
    [System.Windows.Forms.Application]::DoEvents()
}

function Refresh-State {
    Set-Busy $true "Reading installation state..."
    try {
        $state = Invoke-SetupState
        $script:currentState = $state
        $script:previewPassed = $false

        $releaseValue.Text = [string]$state.release
        $classValue.Text = [string]$state.classification
        $modeValue.Text = [string]$state.recommended_mode
        $payloadValue.Text = $(if ($state.payload_drift) { "YES" } else { "NO" })

        $svc = $state.detector.services.current
        $serviceValue.Text = $(if ($svc.exists) { [string]$svc.status } else { "not installed" })
        $runtimeValue.Text = Runtime-Label $state.detector.runtime
        $com0comValue.Text = $(if ($state.detector.com0com.found) { "OK" } else { "MISSING" })

        if ($state.classification -eq 'CURRENT' -and $state.recommended_mode -eq 'REPAIR') {
            $safetyValue.Text = "Hub will be Disabled / Stopped before Apply"
        } elseif ($state.recommended_mode -eq 'NONE') {
            $safetyValue.Text = "No changes required"
        } else {
            $safetyValue.Text = "Backend fail-safe rules active"
        }

        $applyButton.Text = $(if ($state.recommended_mode -eq 'NONE') { "Apply" } else { "Apply $($state.recommended_mode)" })
        $applyButton.Enabled = $false

        if ($state.recommended_mode -eq 'NONE') {
            $logBox.Text = "Installation is healthy and matches this installer generation.`r`nNo repair or migration is required."
            $statusBar.Text = "Healthy installation."
        } else {
            $logBox.Text = "Run Preview to inspect the backend plan. Apply remains disabled until Preview succeeds."
            $statusBar.Text = "Preview required before Apply."
        }
    }
    catch {
        $script:currentState = $null
        $logBox.Text = $_.Exception.Message
        $statusBar.Text = "Unable to read installation state."
        [System.Windows.Forms.MessageBox]::Show($form,$_.Exception.Message,"GADX Vector Setup",'OK','Error') | Out-Null
    }
    finally {
        $form.UseWaitCursor = $false
        $refreshButton.Enabled = $true
        $previewButton.Enabled = $true
        $closeButton.Enabled = $true
    }
}

$refreshButton.Add_Click({ Refresh-State })

$previewButton.Add_Click({
    Set-Busy $true "Running read-only Preview..."
    try {
        $result = Invoke-SetupBackend
        $logBox.Text = $result.Output
        $script:previewPassed = ($result.ExitCode -eq 0)
        $canApply = ($script:previewPassed -and $script:currentState -and $script:currentState.recommended_mode -ne 'NONE')
        $applyButton.Enabled = $canApply
        if ($script:previewPassed) {
            $statusBar.Text = $(if ($canApply) { "Preview passed. Review the plan before Apply." } else { "Preview passed. No Apply is required." })
        } else {
            $statusBar.Text = "Preview failed. Apply remains disabled."
        }
    }
    catch {
        $logBox.Text = $_.Exception.Message
        $script:previewPassed = $false
        $applyButton.Enabled = $false
        $statusBar.Text = "Preview failed."
    }
    finally {
        $form.UseWaitCursor = $false
        $refreshButton.Enabled = $true
        $previewButton.Enabled = $true
        $closeButton.Enabled = $true
        if ($script:previewPassed -and $script:currentState -and $script:currentState.recommended_mode -ne 'NONE') { $applyButton.Enabled = $true }
    }
})

$applyButton.Add_Click({
    if (-not $script:previewPassed -or -not $script:currentState) { return }

    $mode = [string]$script:currentState.recommended_mode
    $warning = "Apply the $mode plan now?`r`n`r`nThe validated D1-D7 backend will perform backup, fail-safe and rollback rules."
    if ($script:currentState.classification -eq 'CURRENT' -and $mode -eq 'REPAIR') {
        $warning += "`r`n`r`nFor radio safety, GADXVectorHub will be Disabled and Stopped before runtime/update work."
    }

    $answer = [System.Windows.Forms.MessageBox]::Show($form,$warning,"Confirm GADX Vector Apply",'YesNo','Warning','Button2')
    if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }

    Set-Busy $true "Applying $mode..."
    try {
        $result = Invoke-SetupBackend -Apply
        $logBox.Text = $result.Output
        if ($result.ExitCode -eq 0) {
            $statusBar.Text = "Apply completed successfully. Refreshing state..."
            [System.Windows.Forms.MessageBox]::Show($form,"The backend completed successfully. The installation state will now be refreshed.","GADX Vector Setup",'OK','Information') | Out-Null
            Refresh-State
        } else {
            $statusBar.Text = "Apply failed. Review the preserved backend diagnostics above."
            [System.Windows.Forms.MessageBox]::Show($form,"Apply failed. The backend output is shown in the log area. Safety/rollback behavior remains controlled by D1-D7.","GADX Vector Setup",'OK','Error') | Out-Null
        }
    }
    catch {
        $logBox.Text = $_.Exception.Message
        $statusBar.Text = "Apply failed."
        [System.Windows.Forms.MessageBox]::Show($form,$_.Exception.Message,"GADX Vector Setup",'OK','Error') | Out-Null
    }
    finally {
        $form.UseWaitCursor = $false
        $refreshButton.Enabled = $true
        $previewButton.Enabled = $true
        $closeButton.Enabled = $true
        $applyButton.Enabled = $false
        $script:previewPassed = $false
    }
})

$closeButton.Add_Click({ $form.Close() })
$form.Add_Shown({ Refresh-State })

[void]$form.ShowDialog()
