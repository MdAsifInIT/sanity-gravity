[CmdletBinding()]
param(
    [int]$VncPort = 8444,
    [int]$SshPort = 2222,
    [string]$RemoteAddress = "LocalSubnet",
    [switch]$Remove
)

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell session."
}

function Remove-Rule {
    param([string]$Name)

    Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
}

function Add-Rule {
    param(
        [string]$Name,
        [int]$Port
    )

    Remove-Rule -Name $Name
    New-NetFirewallRule `
        -DisplayName $Name `
        -Profile Any `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -RemoteAddress $RemoteAddress | Out-Null
}

$vncRule = "Sanity Gravity KasmVNC (LAN)"
$sshRule = "Sanity Gravity SSH (LAN)"

if ($Remove) {
    Remove-Rule -Name $vncRule
    Remove-Rule -Name $sshRule
    Write-Host "Removed Sanity Gravity LAN firewall rules."
    exit 0
}

Add-Rule -Name $vncRule -Port $VncPort
Add-Rule -Name $sshRule -Port $SshPort

Write-Host "Configured Sanity Gravity LAN firewall access:"
Write-Host "  KasmVNC: TCP $VncPort from $RemoteAddress"
Write-Host "  SSH:     TCP $SshPort from $RemoteAddress"
