# Executar o cliente contra o emulador

## Linha de comando

```
LandMass.exe login_server=<ip>:7313?version=<versão>?login_num=<token>
```

| Parâmetro | Obrigatório | Efeito |
|-----------|:-----------:|--------|
| `version=` | sim | Versão local (`LocalVersion`). Sem ele o executável encerra. |
| `login_num=` | sim | Token de login (minúsculo). Sem ele o executável encerra. |
| `login_server=` | não | Sobrepõe o Message Server de `landmass.wdb` (`message_server`). |
| `SERVER` | não | Liga modo servidor (`GIsClient=0`); ver [../architecture/06-game-server-host.md](../architecture/06-game-server-host.md). |

## Contas e `.bat` de login

Execute na raiz de `D:\landmass\emulador`:

```
uv run landmass-emu serve
uv run landmass-emu account create --user fulano --nickname Fulano
uv run landmass-emu account token --user fulano
```

| Comando | Efeito |
|---------|--------|
| `serve` | Aplica as migrações e sobe o Message Server em `LANDMASS_BIND_HOST:LANDMASS_MESSAGE_PORT` (padrão `0.0.0.0:7313`). |
| `account create --user U --nickname N` | Cria a conta com um token novo, grava `jogar_U.bat` na pasta do cliente e imprime o caminho do `.bat`. |
| `account token --user U` | Gera novo token, regrava `jogar_U.bat` e invalida o token anterior. |

- `--client-dir` sobrescreve `LANDMASS_CLIENT_DIR` (padrão `../cliente/system`).
- `--user`: 1 a 12 caracteres minúsculos, dígitos ou `_` (vira nome de arquivo `.bat`; sem maiúsculas para evitar colisão no Windows). `--nickname`: 1 a 16 bytes em cp1252.
- A CLI não imprime o token. O `.bat` contém o token: trate-o como senha.
- Se a gravação do `.bat` falhar após a criação da conta, a conta existe sem `.bat`; rode `account token --user U` para regravar.

Jogador: executar `jogar_U.bat` (ou `cliente\system\jogar_local.bat` para teste local, com o token preenchido à mão).

## Scripts

| Arquivo | Uso |
|---------|-----|
| `cliente\system\jogar_local.bat` | Desenvolvimento: aponta para `127.0.0.1:7313`. Substitua `TROQUE_PELO_TOKEN` por um token. |
| `cliente\system\jogar_<user>.bat` | Gerado pela CLI `account`; contém o token do jogador (CRLF). |

## Launcher

Não use `Launcher.exe`: ele tenta FTP de patch inexistente. Inicie `LandMass.exe` diretamente.

## Vídeo

- `LandMass.ini`, `[D3DDrv.D3DRenderDevice]`: `Use16bit=False`. Com `True`, drivers atuais não oferecem modo 16 bits e o cliente aborta em `OpenWindow → SetRes` ("No acceptable display modes found"). Backup do original: `cliente\system\LandMass.ini.bak`.
- O cliente força tela cheia (`WinDrv` grava `UWindowsViewport+0xD0=1` em `TryRenderDevice`; ver [`../../re/fullscreen.md`](../../re/fullscreen.md)). Não há chave de `.ini` nem opção de linha de comando para janela.
- Modo janela: wrapper **dgVoodoo2 v2.87.5** (D3D8 → D3D11), em `D:\landmass\tools\dgvoodoo2`.
  - Instalação por pasta do cliente: copie `extracted\MS\x86\D3D8.dll` e `dgVoodoo.landmass.conf` (renomeado para `dgVoodoo.conf`) para `system\`.
  - Config: `FullScreenMode=false`, `AppControlledScreenMode=false`, `DisableAltEnterToToggleScreenMode=false`, `dgVoodooWatermark=false`.
  - Remoção: apague `system\D3D8.dll` e `system\dgVoodoo.conf`.
- `LandMass.exe` reconstrói a linha de comando e a engine a recebe vazia (`Init: Command line:`): `-windowed`, `EXEC=`, `INI=` e `-server` não têm efeito.

## Testes automatizados com o cliente

- Máximo de 4 instâncias simultâneas. Duas instâncias não compartilham pasta (`LandMass.log`, `User.ini`, `Running.ini`): use `D:\landmass\cliente` e `D:\landmass\cliente2`.
- Captura do Windows (GDI/`PrintWindow`) sai branca com o swapchain D3D11. Use o screenshot do próprio jogo (`F11` = `shot`, grava em `..\ScreenShots`).
- O cursor da GUI é movido por deltas (DirectInput), não por `SetCursorPos`, e não é limitado às bordas.
- Ferramenta: `scripts/gui.py` (malha fechada: screenshot → localiza o cursor → delta).

```
uv run --no-project --with pillow python -I scripts/gui.py shot saida.png [--pid N]
uv run --no-project --with pillow python -I scripts/gui.py click <x> <y> [--double] [--pid N]
uv run --no-project --with pillow python -I scripts/gui.py type <texto> [--pid N]
```

- Coordenadas são da área do jogo (800x600). O script aborta se o jogo não estiver em primeiro plano, para não clicar em outra janela.
- Validação: log do emulador e screenshot do jogo. `LandMass.log` só é gravado por completo no encerramento normal.
