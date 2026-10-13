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

## Vídeo (`LandMass.ini`)

- Defina `Use16bit=False` em `[D3DDrv.D3DRenderDevice]`. Com `True`, drivers atuais não oferecem modo 16 bits e o cliente aborta em `OpenWindow → SetRes` com "No acceptable display modes found".
- Com `Use16bit=False` o cliente abre em janela 800x600 (`Enter SetRes: 800x600 Fullscreen 0`).
- `LandMass.exe` limpa a linha de comando antes da engine (`Init: Command line:` vazio): `-windowed`, `EXEC=` e `INI=` não têm efeito.
- Backup do original: `cliente\system\LandMass.ini.bak`.

## Testes automatizados com o cliente

- Máximo de 4 instâncias simultâneas.
- Inicie e minimize conforme [`../../re/windowed.md`](../../re/windowed.md).
- Valide pelo log do servidor (`login de <user>`) e pela UI; `LandMass.log` só é gravado por completo no encerramento normal.
