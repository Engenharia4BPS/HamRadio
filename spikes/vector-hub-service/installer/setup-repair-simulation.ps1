param(
    [string]$InstallRoot = "C:\Ham\GADX-Vector"
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$InstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleasePath = Join-Path $InstallerRoot "release.json"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

function Get-ReleaseLabel {
    if (-not (Test-Path $ReleasePath -PathType Leaf)) { return "unversioned" }
    try {
        $release = Get-Content -LiteralPath $ReleasePath -Raw | ConvertFrom-Json
        $version = if ($release.version) { [string]$release.version } else { "unknown" }
        $channel = if ($release.channel) { [string]$release.channel } else { "unknown" }
        $phase = if ($release.phase) { [string]$release.phase } else { "" }
        $label = "$version / $channel"
        if ($phase) { $label += " / $phase" }
        return $label
    }
    catch {
        return "invalid release.json"
    }
}

function Get-SimulationPreview {
    $release = Get-ReleaseLabel
    return @"
SIMULATION / NO CHANGES
GADX Vector Setup - D8C Repair UX simulation
Release      : $release
Install root : $InstallRoot
Detected     : CURRENT
Mode         : REPAIR
Payload drift: YES

D7 safety gate that would be used on a real Apply:
  -> GADXVectorHub would be set Disabled and forced Stopped BEFORE runtime/download/update work.
  -> vector.ini and virtual COM pairs would be preserved.
  -> a backup would be created before payload replacement.
  -> service health and PTT=OFF would be required before READY.

SIMULATION ONLY: no backend Apply was executed and the operational station was not touched.
"@
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "GADX Vector Setup - SIMULATION"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(900,700)
$form.MinimumSize = New-Object System.Drawing.Size(820,620)
$form.Font = New-Object System.Drawing.Font("Segoe UI",9)

$title = New-Object System.Windows.Forms.Label
$title.Text = "GADX VECTOR SETUP - SIMULATION"
$title.Font = New-Object System.Drawing.Font("Segoe UI Semibold",18)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(22,16)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "D8C UI simulation - NO CHANGES WILL BE APPLIED"
$subtitle.AutoSize = $true
$subtitle.Location = New-Object System.Drawing.Point(25,54)
$subtitle.ForeColor = [System.Drawing.Color]::DarkRed
$subtitle.Font = New-Object System.Drawing.Font("Segoe UI Semibold",9)
$form.Controls.Add($subtitle)

$group = New-Object System.Windows.Forms.GroupBox
$group.Text = "Simulated installation status"
$group.Location = New-Object System.Drawing.Point(20,82)
$group.Size = New-Object System.Drawing.Size(842,190)
$group.Anchor = 'Top,Left,Right'
$form.Controls.Add($group)

function Add-StatusLabel([string]$caption,[string]$valueText,[int]$x,[int]$y,[switch]$Warning) {
    $cap = New-Object System.Windows.Forms.Label
    $cap.Text = $caption
    $cap.AutoSize = $true
    $cap.Location = New-Object System.Drawing.Point($x,$y)
    $cap.Font = New-Object System.Drawing.Font("Segoe UI Semibold",9)
    $group.Controls.Add($cap)

    $value = New-Object System.Windows.Forms.Label
    $value.Text = $valueText
    $value.AutoSize = $true
    $value.Location = New-Object System.Drawing.Point(($x + 125),$y)
    if ($Warning) { $value.ForeColor = [System.Drawing.Color]::DarkRed }
    $group.Controls.Add($value)
    return $value
}

$releaseValue = Add-StatusLabel "Release" (Get-ReleaseLabel) 18 30
$classValue = Add-StatusLabel "Detected" "CURRENT" 18 60
$modeValue = Add-StatusLabel "Recommended" "REPAIR" 18 90 -Warning
$payloadValue = Add-StatusLabel "Payload drift" "YES" 18 120 -Warning
$serviceValue = Add-StatusLabel "Service" "Running" 420 30
$runtimeValue = Add-StatusLabel "Runtime" "OK" 420 60
$com0comValue = Add-StatusLabel "com0com" "OK" 420 90
$safetyValue = Add-StatusLabel "Safety" "SIMULATION - real Hub untouched" 420 120 -Warning

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
$logBox.Text = "SIMULATION / NO CHANGES`r`nRun Preview to inspect how a CURRENT / REPAIR plan is presented. Apply is permanently disabled in simulation."
$form.Controls.Add($logBox)

$statusBar = New-Object System.Windows.Forms.Label
$statusBar.Text = "Simulation mode. Operational station is untouched."
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
$applyButton.Text = "Apply REPAIR"
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

$refreshButton.Add_Click({
    $releaseValue.Text = Get-ReleaseLabel
    $logBox.Text = "SIMULATION / NO CHANGES`r`nRun Preview to inspect how a CURRENT / REPAIR plan is presented. Apply is permanently disabled in simulation."
    $statusBar.Text = "Simulation mode. Operational station is untouched."
    $applyButton.Enabled = $false
})

$previewButton.Add_Click({
    $logBox.Text = Get-SimulationPreview
    $statusBar.Text = "Simulation Preview passed. Apply remains disabled by design."
    $applyButton.Enabled = $false
})

$closeButton.Add_Click({ $form.Close() })

[void]$form.ShowDialog()
