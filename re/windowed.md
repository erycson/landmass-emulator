# Cliente em janela e minimizado

## Achados

- Com `Use16bit=True` (`[D3DDrv.D3DRenderDevice]`) o cliente tenta tela cheia 16 bits em `UWindowsViewport::OpenWindow` e aborta ("No acceptable display modes found"). Com `Use16bit=False` abre em janela: `Enter SetRes: 800x600 Fullscreen 0` (teste de 2026-10-13).
- `LandMass.exe` limpa a linha de comando antes da engine (`Init: Command line:` vazio): `-windowed` e `EXEC=` não têm efeito.
- Título da janela principal: `Landmass Client`.
- Resolução inicial: `LM_Intro.CheckResolution` executa `TEMPSETRES 800x600` (XInterface.u, inferido).
- `StartupFullscreen` do `.ini`: nenhum leitor encontrado nos binários (inferido: sem efeito).
- Minimizar antes do `Enter SetRes` não foi validado; minimize depois dessa linha no log.
- Comandos de console do WinDrv: `TEMPSETRES`, `SETRES`, `TOGGLEFULLSCREEN`, `ENDFULLSCREEN`, `MINIMIZE`.
- Cliente minimizado (`IsIconic=True`) continua enviando heartbeat ao Message Server (captura do sniffer).

## Receita (PowerShell)

```powershell
$p = Start-Process -FilePath D:\landmass\cliente\system\LandMass.exe `
  -WorkingDirectory D:\landmass\cliente\system -ArgumentList $args -PassThru
do { Start-Sleep -Milliseconds 500; $p.Refresh() } until ($p.HasExited -or $p.MainWindowTitle -eq 'Landmass Client')
Add-Type -Namespace W -Name U -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindowAsync(System.IntPtr h, int c);'
[W.U]::ShowWindowAsync($p.MainWindowHandle, 7) | Out-Null  # 7 = SW_SHOWMINNOACTIVE
```

Valide pelo `cliente\system\LandMass.log` (linhas `Recived from Message Server %d`).

Risco: o render D3D pode pausar minimizado; a rede segue ativa (heartbeat observado).
