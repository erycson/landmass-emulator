# Servidor de partida (cópia `servidor-partida`)

Status: cópia preparada e patches aplicados. **Não testado** (o jogo não roda no ambiente de agente). A evidência de engenharia reversa e as pendências estão em [`../../re/game_server_host.md`](../../re/game_server_host.md).

## Montagem da cópia

A cópia é `D:\landmass\servidor-partida`, feita de `D:\landmass\cliente` (1082 MB):

```
robocopy "D:\landmass\cliente" "D:\landmass\servidor-partida" /E
```

`cliente` e `cliente2` não são alterados. O instalador `LandMass_Setup_20090701.exe` não é tocado.

### Patches (somente na cópia)

| Arquivo | Offset (arquivo) | Antes | Depois | Motivo | Original |
|---------|------------------|-------|--------|--------|----------|
| `system\Core.dll` | `0x3F9C6` (260550) | `74 0E` (`je +0x0E`) | `90 90` (`nop nop`) | Em `appInit`, o `je` pula a cópia da linha de comando para `appCmdLine()`. Com o patch, `-server` chega ao `main`, que faz `GIsClient = 0` (sem janela nem renderização). | `Core.dll.orig` |
| `system\LandMass.exe` | `0x209E4` (133604) | `57` (`W`) | `58` (`X`) | Literal UTF-16 `WLog` (janela da instância já aberta) vira `XLog`. O repasse de linha de comando não acha a janela e a segunda instância segue o próprio caminho e grava o próprio log. | `LandMass.exe.orig` |

Conferência após aplicar (deve mostrar só esses bytes):

```
cmp -l system\Core.dll system\Core.dll.orig        # 2 bytes: 260551 e 260552
cmp -l system\LandMass.exe system\LandMass.exe.orig # 1 byte: 133605
```

Não foi aplicado patch em `LM_Engine.dll`. O patch mínimo em `LoginPlayer` (aceitar qualquer jogador) não teria efeito com os mapas atuais: `LoginPlayer` só é chamado por `UServerLevel::NotifyReceivedText`, e o nível da partida não é `UServerLevel` (ver `re/game_server_host.md`, seção 9).

### Não tocado

- `HShield` (`system\HShield`): nenhum arquivo alterado, removido ou desabilitado nesta cópia.

## Como iniciar

Execute `system\servidor.bat` (a janela fica aberta enquanto o servidor roda). A linha é:

```
LandMass.exe ONS-Treino?listen -server -log login_server=127.0.0.1:7313?version=<V>?login_num=<L>
```

- Argumentos do motor vêm ANTES de `login_server=`. Qualquer token depois de `login_num=...` faz o executável sair com código 0, sem log (validado em 2026-10-13: UDP 7777 aberta, `Game class is 'LM_DeathMatch'`, `Bringing Level ONS-Treino.myLevel up for play`).
- `version=` e `login_num=` são copiados de `cliente\system\jogar_teste.bat`. Sem eles o executável também sai com 0 (ver [`../../re/cmdline.md`](../../re/cmdline.md)).
- O servidor não usa `login_server=`: ele não fala com o Message Server.
- `-log` sem valor: o nome do arquivo de log segue o padrão do motor (`system\LandMass.log`). `-log=Server.log` não foi testado.
- Não rode o servidor dentro de `cliente` ou `cliente2`. Cada pasta tem seu próprio `LandMass.log` e `User.ini`.

## Porta

- Protocolo UDP, porta **7777** (`[URL] Port=7777` em `LandMass.ini`). O driver é `IpDrv.TcpNetDriver`, mas o socket é `SOCK_DGRAM` (ver `re/cmdline.md`, seção 2).
- Conferir com o servidor no ar:

```
netstat -ano -p UDP | findstr :7777
```

- Se o cliente estiver em outra máquina, liberar UDP 7777 no firewall do Windows para `LandMass.exe`.

## Como um cliente conecta

1. Subir o emulador conforme [`running-client.md`](running-client.md).
2. Subir o servidor de partida (`servidor.bat`) antes do cliente.
3. O 403 `NotifyStartGame` leva o endereço da partida, configurado no emulador:
   - `LANDMASS_GAME_HOST=127.0.0.1` (padrão)
   - `LANDMASS_GAME_PORT=7777` (padrão)
   Ver [`../architecture/05-configuration.md`](../architecture/05-configuration.md). A porta do 403 precisa ser a mesma do `servidor.bat`.
4. Iniciar o cliente de teste em `cliente2` com o `jogar_<usuário>.bat`. Criar sala, o dono inicia (401), o cliente recebe o 403 e tenta `127.0.0.1:7777`.

(Inferido: o cliente monta o `open` com o endereço e a porta do 403. A conexão real não foi observada.)

## O que conferir no log

Arquivo: `D:\landmass\servidor-partida\system\LandMass.log`, gravado no encerramento normal (ver [`running-client.md`](running-client.md)).

| Sinal | Significado |
|-------|-------------|
| Processo vivo e UDP 7777 em `netstat` | O servidor subiu. |
| `Game class is '...'` e `Bringing Level ... up for play` | Mapa carregado (padrão observado no cliente; a linha exata do servidor não foi observada). |
| `binding to port ... failed` (IpDrv) ou `Failed to listen` / `NetListen` (Engine) | A porta não abriu. |
| Saída em poucos segundos, sem `LandMass.log` | Argumento depois de `login_num=`, ou falta `login_server=`/`version=`/`login_num=`. Ponha os argumentos do motor no início. |
| Log de LOGIN recusado | A validação está na lógica UnrealScript (`XGame`), não em `LM_Engine.dll` (ver `re/game_server_host.md`). |

## Riscos e pendências

- Não testado. A porta UDP 7777 não está comprovada: não foi achado o chamador de `ULevel::Listen` (ver `re/game_server_host.md`, seção 9). Se o servidor não abrir a porta, esse é o primeiro ponto a investigar.
- Saídas precoces (~20 ms, sem log) ainda sem causa comprovada; podem afetar o servidor.
- A conexão com o Channel (`GS_*`, `CServerRoom`) não está no caminho desta cópia. Um LOGIN recusado não vem do `LM_Engine.dll`.
- Os patches são binários de 2008 alterados à mão. Restaure com os arquivos `.orig` se algo se comportar de forma estranha.
