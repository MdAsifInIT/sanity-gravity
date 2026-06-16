[CmdletBinding()]
param(
    [string]$TailscaleIP,
    [int]$VncPort = 8444,
    [int]$SshPort = 2222,
    [string]$RemoteAddress = "100.64.0.0/10",
    [switch]$Remove
)

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell session."
}

if (-not $TailscaleIP) {
    $TailscaleIP = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.InterfaceAlias -like "*Tailscale*" -and $_.IPAddress -like "100.*" } |
        Select-Object -First 1 -ExpandProperty IPAddress
}

if (-not $TailscaleIP) {
    throw "Could not detect a Tailscale IPv4 address. Pass -TailscaleIP 100.x.y.z explicitly."
}

function Remove-PortProxy {
    param([int]$Port)

    netsh interface portproxy delete v4tov4 listenaddress=$TailscaleIP listenport=$Port | Out-Null
}

function Add-PortProxy {
    param([int]$Port)

    Remove-PortProxy -Port $Port
    netsh interface portproxy add v4tov4 listenaddress=$TailscaleIP listenport=$Port connectaddress=127.0.0.1 connectport=$Port | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to add portproxy for ${TailscaleIP}:$Port"
    }
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
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalAddress $TailscaleIP `
        -LocalPort $Port `
        -RemoteAddress $RemoteAddress | Out-Null
}

$vncRule = "Sanity Gravity KasmVNC (Tailscale)"
$sshRule = "Sanity Gravity SSH (Tailscale)"

if ($Remove) {
    Remove-PortProxy -Port $VncPort
    Remove-PortProxy -Port $SshPort
    Remove-Rule -Name $vncRule
    Remove-Rule -Name $sshRule
    Write-Host "Removed Sanity Gravity Tailscale portproxy and firewall rules."
    exit 0
}

Add-PortProxy -Port $VncPort
Add-PortProxy -Port $SshPort
Add-Rule -Name $vncRule -Port $VncPort
Add-Rule -Name $sshRule -Port $SshPort

Write-Host "Configured Sanity Gravity Tailscale access:"
Write-Host "  KasmVNC: https://$TailscaleIP`:$VncPort"
Write-Host "  SSH:     ssh developer@$TailscaleIP -p $SshPort"
Write-Host ""
netsh interface portproxy show v4tov4
