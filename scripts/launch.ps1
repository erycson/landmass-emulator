# Fecha os clientes abertos e inicia um por pasta, usando o jogar_<user>.bat de cada uma.
# Uso: launch.ps1 cliente:teste cliente2:teste2   (pasta em D:\landmass : usuário)
# A segunda instância exige LandMass.exe com o patch WLog->XLog (docs/operations/running-client.md).
param([Parameter(ValueFromRemainingArguments)] [string[]]$Clients)
Stop-Process -Name LandMass -Force -ErrorAction SilentlyContinue
Start-Sleep 2
foreach ($c in $Clients) {
    $dir, $user = $c.Split(':')
    $sys = "D:\landmass\$dir\system"
    Remove-Item "$sys\Running.ini" -ErrorAction SilentlyContinue
    Start-Process -FilePath "$sys\jogar_$user.bat" -WorkingDirectory $sys
    Start-Sleep 6
}
Get-Process LandMass -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Path) pid=$($_.Id)" }
