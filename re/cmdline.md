# Linha de comando do LandMass (UE2 build 3369)

Escopo: por que a engine recebe a linha vazia, qual o menor patch, caminho até o servidor UE2 e instância única.
Fonte: REA (Ghidra 12.1.4) sobre `D:\landmass\cliente\system` (LandMass.exe, Core.dll, Engine.dll, IpDrv.dll).
Nenhum binário foi alterado e nenhum processo foi executado. Patches abaixo são propostas, não aplicadas.

Hashes SHA-256: LandMass.exe `0fcd586a...ac18ed`, Core.dll `b478ca32...8518e2`, Engine.dll `fc1369fa...0df8`, IpDrv.dll `5f414d3d...5c83`.

## 1. Por que a engine recebe a linha vazia (pergunta 1)

Cadeia observada:

1. CRT entry `0x10919d3e` chama `FUN_10911ee0(hInstance)`.
2. `FUN_10911ee0` (`0x10911ee0`): `DAT_1092f990 = GetCommandLineW()`, a linha completa, com o caminho do exe. Depois faz o repasse para instância existente (seção 3) e chama `FUN_10910d20` (main).
3. `FUN_10910d20` (main, `re/LandMass.exe/main_loop.c`): remove da linha as chaves `version=`, `login_server=`, `login_num=` (regra em `game_server_host.md` §2). Chama `appInit(GPackage, linha restante, ...)` na linha 165. Depois, `GIsServer = 1` (linha 169) e `GIsClient = !ParseParam(appCmdLine(), "SERVER")` (linha 172).
4. `Core.dll appInit` (`0x1013f8d0`): pula o nome do exe (aspas ou primeiro espaço) e só copia a linha para o buffer de `appCmdLine()` (`DAT_101e4488`) se `GIsLMServer != 0`:
   - `0x1013f9bd`: `call OutputDebugStringW`; `0x1013f9c0`: `cmp [GIsLMServer], ebx` (ebx = 0); `0x1013f9c6`: `74 0E` (`je +0x0E`), que pula o `appStrcpy` em `0x1013f9c8`.
   - Com `GIsLMServer == 0`, `appCmdLine()` devolve string vazia. Todos os `ParseParam`/`Parse` que vêm depois (STRICT, LOG, nocheat, `-MainMenu=`, INI=, USERINI=, e o `SERVER` do próprio main) veem vazio.
   - O `Command line: ` vazio do log (`Core.dll` `0x10178ef8`) é consequência direta.
5. Por isso `GIsClient = 1` sempre no estado atual, mesmo com `-server` na linha. A linha de comando nunca chega ao `ParseParam(..., "SERVER")` do main com conteúdo.

Quem lê/escreve `GIsLMServer` (`Core.dll` `0x101b56a0`, exportado):
- Leituras: `Core appInit` (`0x1013f9c0`), `UObject::GetPackageLinker` (`0x101549c3`), `IpDrv UTcpipConnection::Destroy` (`0x107167ab`, via PTR `0x1071f028`), `Engine.dll UGameEngine::Init` (`if (GIsLMServer == 0) KInitGameKarma(); ... if (GIsLMServer == 0) Browse(URL)`).
- Escrita: nenhuma em `Core.dll`. Quem a escreve não foi identificado (pendente: varredura de escritas em `LandMass.exe` e `LM_Engine.dll`). Hoje ela vale 0 no momento do `appInit`.

### Patch P1 (menor para a linha chegar à engine)

- Arquivo: `D:\landmass\cliente\system\Core.dll`
- Offset de arquivo: `260550` (`0x3F9C6`), verificado com `od`.
- Bytes antigos: `74 0E` (`je +0x0E`)
- Bytes novos: `90 90` (`nop nop`)
- Efeito: `DAT_101e4488` recebe sempre a linha restante. Com `-server` na linha, `GIsClient` vira 0 no main. `GIsLMServer` continua 0, então o restante do comportamento (`KInitGameKarma`, `Browse(URL)`, desconexão em `IpDrv`) não muda.

Riscos de P1 (não aplicar no cliente):
- Hoje o cliente roda com `appCmdLine()` vazio. Com P1, `UGameEngine::Init` lê o primeiro token da linha restante como URL inicial. Se o resíduo depois de remover `version=`/`login_*` começar com `?` ou for texto em minúsculas, vira URL inválida (`InvalidUrl`, saída, inferido) em vez de `Entry` (`FURL::DefaultLocalMap`).
- Portanto: aplicar P1 só numa cópia separada para servidor (`D:\landmass\servidor_teste`), nunca em `cliente` ou `cliente2`.

`-log` (inferido): passa a chegar a `ParseParam(DAT_101e4488, "LOG")` em `appInit`. O efeito exato do `-log` não foi rastreado nesta etapa.

## 2. Caminho até o servidor UE2 com GIsClient = 0 (pergunta 2)

Com P1 aplicado na cópia do servidor e linha do tipo `ONS-Treino.map?listen -server -log version=...?login_num=...`:

1. `main` (`FUN_10910d20`): `GIsServer = 1`, `GIsClient = 0`. Cria o `UGameEngine` a partir de `ini:Engine.Engine.GameEngine` (`LandMass.ini`: `GameEngine=Engine.GameEngine`). **Não** é `LM_Engine.ServerEngine`, então `UServerEngine` não entra.
2. `UGameEngine::Init` (`Engine.dll` `0x10425310`):
   - `GIsClient == 0`: não cria `UClient`, `URenderDevice` nem janela (blocos em `0x10425310` condicionados a `GIsClient`).
   - `GIsLMServer == 0`: chama `KInitGameKarma()` e, mais adiante, `Browse(URL)` (vtable `+0xE4`).
   - URL inicial = primeiro token de `appCmdLine()` (`ParseToken`). Se o token for vazio ou começar com `-`, usa `FURL::DefaultLocalMap`. Aqui vira `ONS-Treino.map?listen`.
   - Se `Browse` falhar, tenta `FURL::DefaultNetBrowseMap` e depois `FailedBrowse` (saída).
3. `UGameEngine::Browse` (`0x10426ed0`):
   - URL sem host (`IsLocalInternal`, inferido): `LoadMap(URL, NULL)` (vtable `+0xE8`, `0x10427c70`). Se `iVar4 != 0 && GIsServer != 0`: `ServerUpdateMD5()` (`0x10421000`).
   - URL com host e `GIsClient == 0`: erro `ServerOpen` (não é o caso aqui).
4. `UGameEngine::LoadMap` (`0x10427c70`): `UObject::StaticLoadObject(ULevel::PrivateStaticClass, "MyLevel", pacote do mapa)`. O nível é `ULevel` (Engine.dll), **não** `UServerLevel`. Não há checagem da opção `listen` dentro de `LoadMap` (busca por `HasOption` e vtable `+0xC4` vazia).
5. `ULevel::Listen` (`0x10441300`, slot `+0xC4` da vtable de `ULevel`, slot 49 da tabela; verificado por xref de dado em `0x1063d0e4`):
   - Se `this+0x48 == 0`: cria o net driver com `StaticConstructObject(ini:Engine.Engine.NetworkDevice)`. O ini diz `NetworkDevice=IpDrv.TcpNetDriver`.
   - Chama `vt+0x88` do driver. Se retornar 0: erro `NetListen`.
   - Depois cria os atores das classes listadas no `ini` (`Init` em `FUN_10406bc0` e `vt+0xFC`, não detalhado).
6. `UNetDriver::InitListen` base (`Engine.dll` `0x10462e30`) só guarda o `FNetworkNotify` e retorna 1 (verificado). O bind real está no override de `IpDrv.dll` (sessão REA de IpDrv, abaixo).
7. `IpDrv.dll UTcpNetDriver::InitListen` (`0x107171e0`) → `UNetDriver::InitListen` base e `InitBase` (`0x107169c0`):
   - `socket(AF_INET=2, SOCK_DGRAM=2, IPPROTO_UDP=0x11)`. **O driver é UDP, não TCP.** A porta 7777 é UDP.
   - `Parse(appCmdLine(), "PORT=", URL+0x18)` só se a chave existir. A porta do bind é `htons(URL.Port)`. Sem `PORT=`, vale o default de `[URL] Port=7777` do ini (FURL). Ver nota abaixo sobre `PORT=`.
   - `bind(...)` (`FUN_10701880`, inferido: `bind`) e depois `FUN_10719480` (inferido: modo não bloqueante). Falha → log "binding to port %i failed".
   - Ao fim: `URL.Port = ntohs(sockaddr.port)`, a porta efetivamente ligada.
   - Nota (observado, possível erro de bind): com `PORT=` na linha, o tamanho do `bind` é `(-(iVar3 != 0) & 0xffffffed) + 0x14`, que dá 1. Não usar `PORT=` na linha do servidor até testar.

Resposta curta: o servidor de partida, nesse caminho, é `UGameEngine` (Engine.dll) com nível `ULevel` (Engine.dll) e net driver `IpDrv.UTcpNetDriver` em UDP/7777. `UServerLevel` (LM_Engine) não entra.

Pendência desta pergunta:
- O chamador de `ULevel::Listen` (vtable `+0xC4`) não foi encontrado em `UGameEngine::Init`, `Browse`, `LoadMap`, `Tick` (`0x1042e880`) nem `ServerUpdateMD5` (todos lidos ou varridos por offset). Candidatos: `LandMass.exe` ou um módulo que chame o `Listen` via vtable. Sem esse chamador, a porta não abre mesmo com `?listen` na URL.

Consequência para o plano do emulador (inferido): o caminho padrão `GameEngine` + `ULevel` não cria `UServerLevel`, então `UServerLevel::NotifyReceivedText` (e portanto `LoginPlayer`/`CServerRoom`) não roda nesse caminho. Ver pergunta 4.

## 3. Instância única (prioridade do coordenador)

Achado: não é mutex. `FUN_1090ad30` cria o mutex `UnrealIsRunning` com `CreateMutexA/W` e descarta `GetLastError()`, então nunca bloqueia. O bloqueio é o repasse em `FUN_10911ee0` (`0x10911fd0..0x1091201a`):

- Se a linha **não** contém nenhum destes tokens (`appStrfind`, sem diferenciar caixa): `NewWindow`, `changevideo`, `TestRenDev`, `COMMAND=`, então:
  - `FindWindowExW/A(NULL, NULL, "WLog", NULL)` (literal `0x109209e4`, único xref em `0x10912039`). Se achar, `GetPropW(hwnd, "IsBrowser")`, a propriedade que `FUN_10910d20` põe na janela principal.
  - `SendMessageTimeoutW(hwnd, WM_COPYDATA=0x4A, 0, &COPYDATASTRUCT, SMTO=3, 30000 ms)` com a linha restante.
  - `return 0` sem chamar `appInit`. A 2ª instância sai com código 0 antes de gravar `LandMass.log`.
- Se a linha contém um dos tokens: segue para `FUN_10910d20` normalmente.

Explica a medição do coordenador (2ª instância sai em <3 s sem `LandMass.log`). O `FUN_109018e0` **não** é o repasse: é a tela de splash (`CreateDialogParam` id `0x77`), chamada por `FUN_10910d20` quando faltam `-LOG`, `-SERVER` e `TestRenDev`.

### Patch P-A (mínimo: 1 byte)

- Arquivo: `D:\landmass\cliente\system\LandMass.exe`
- Offset de arquivo: `133604` (`0x20A64`), literal UTF-16 `"WLog"` (verificado: `57 00 4C 00 6F 00 67 00 00 00`).
- Bytes antigos: `57` (`W`)
- Bytes novos: `58` (`X`)
- Efeito: `FindWindowExW(..., "XLog", ...)` não acha a janela da 1ª instância. O repasse não acontece e a 2ª instância segue para `appInit`, gravando o próprio `LandMass.log`.
- Verificação: `FindWindowEx` por classe `WLog` na 1ª instância ainda precisa ser confirmada (teste T2 abaixo). Se a janela da 1ª instância não tiver classe `WLog`, o repasse já não acha nada e P-A não é necessário.

### Alternativas

- **P-B (6 bytes, desliga o repasse para todas as instâncias):** `LandMass.exe` offset `73705` (`0x11FE9`), `0f 85 db 01 00 00` (`jnz 0x109121ca`) → `e9 dc 01 00 00 90` (`jmp 0x109121ca; nop`). Verificado o offset/bytes antigos. Mais invasivo que P-A.
- **Sem binário (não testado):** incluir o token `NewWindow` na linha da 2ª instância (ex.: `ONS-Treino.map NewWindow ...`). `appStrfind` é sem diferenciar caixa e vale para a linha inteira (incluindo o caminho do exe). Isso pula o repasse. Antes de usar, confirmar que nenhum consumidor de `NewWindow` muda o comportamento (não verificado).

## 4. Testes em ordem (o usuário executa; este agente não executa o jogo)

- **T0 (estático, sem executar):** confirmar os bytes em disco antes e depois de qualquer patch com `od -A d -t x1 -j OFFSET -N N`.
- **T1 (cópia):** criar `D:\landmass\servidor_teste` (cópia de `cliente`). Aplicar P1 (`Core.dll` 260550) só lá. Não tocar em `cliente` nem `cliente2`.
- **T2 (janela, com a 1ª instância aberta):** confirmar que existe janela de classe `WLog` com a propriedade `IsBrowser`. PowerShell com `Add-Type` chamando `FindWindowEx(IntPtr.Zero, IntPtr.Zero, "WLog", null)` e `GetPropW(hwnd, "IsBrowser")`.
- **T3 (2ª instância):** com P-A aplicado em `cliente2`, abrir a 2ª instância e medir: o `LandMass.log` deve ser gravado e o processo deve continuar vivo além de 3 s. Sem P-A, o resultado esperado é o da medição do coordenador (sai em <3 s).
- **T4 (servidor):** em `servidor_teste`, linha `ONS-Treino.map?listen -server -log version=...?login_num=...`. Verificar `Get-NetUDPEndpoint`/`Get-NetTCPConnection` para porta 7777. Só depois, cliente em `cliente2` com `127.0.0.1:7777`.

## 5. Pergunta 3 (InitServer / ChannelServerTick) e pergunta 4 (LoginPlayer com CServerRoom vazio)

Binário: `LM_Engine.dll` (SHA-256 `4a08e7ce...fd04230f`). Pseudocódigo em `re/LM_Engine.dll/InitServer.c`, `LoginPlayer.c`, `UServerLevel_NotifyReceivedText.c`.

**Q3 (contrato):**
- `InitServer(ushort *CmdLine)` (export, `0x1000C6D0`) faz, nesta ordem:
  1. `Cbase::Create(..., "LandmassGameServer", "config_server", "report_server", ...)`. Se falhar, retorna `false`.
  2. Lê chaves da linha, com `Parse`: `ip=` (literal UTF-16 em `0x1002D9B8`, verificado), `port=`, `mode=`, `ch_ip=`, `ch_port=`, `ch_code=`, `ch_pw=`. Destinos: `DAT_10057120` (ip, wide), `DAT_10057140` (port, u16), `DAT_10057142` (mode, byte), `DAT_10057144` (ch_ip, ANSI), `DAT_10057154` (ch_port, u16), `DAT_10057158` (ch_code, int), `DAT_1005715C` (ch_pw, ANSI).
  3. Carrega `ServerMessage.wdb` e `error.wdb` (`Cdb_table::Load`, caminho relativo ao diretório atual, inferido). Se ambos carregam, retorna `true`; senão, `Cdebug::Dump` e `false`.
  - **InitServer não abre socket e não conecta no Channel.** Só guarda `ch_*`.
- `ChannelServerTick()` (export, `0x1000BB70`) chama `FUN_1000BA90()`, que devolve o singleton estático em `0x10057040` (vtable `PTR_FUN_1002D638`), e depois `vt+0x10` (Tick, não lido). A conexão com o Channel, se existir, está nesse Tick (inferido).
- Nenhum chamador interno de `InitServer` nem de `ChannelServerTick` foi observado: são exports para um host. Nenhum binário do cliente importa `InitServer` (ver `re/NOTES.md`). No caminho `GameEngine` (seção 2), nada disso roda.

**Q4 (LoginPlayer com CServerRoom vazio):**
- `LoginPlayer(int key, ushort *name, int team, FString &Err)` (`0x1000B680`) é chamado só por `UServerLevel::NotifyReceivedText` (`0x10014E60`), no ramo `LOGIN`.
- Ordem das checagens: nome com 3 a 16 caracteres (senão erro); `ServerRoom()+0x5D4 != 0` retorna `0x46`; chave: `ServerRoom()+0x0 == key` ou (`+0x5E4 == 6` e `+0x600 == key`), senão erro "chave"; varredura de 70 slots de nome (`ServerRoom()+0x13+i*0x11`, ANSI); se achar o nome e `team == i % ServerRoom()[0x10]`, retorna `i`; senão erro.
- **Com a sala vazia** (singleton zerado em `0x10057C50` por `ServerRoom()`), `+0x0 == 0` e nenhum nome bate. Resultado: **retorna `-1` para qualquer LOGIN**. Com `key != 0`, a mensagem é "chave inválida"; com `key == 0`, "não encontrado". Não há sucesso sem a sala preenchida.
- `NotifyReceivedText` não retorna cedo após `-1`: loga o erro, marca `conn+0x80 = 1` (inferido: desconexão) e chama `ULevel::WelcomePlayer` com mensagens vazias.
- Quem preenche a sala: `CServerRoom::InPlayer(GS_IN_PLAYER_IN*)` (`0x100159A0`). Grava nome (16 bytes) em `+0x13+s*0x11` e um byte em `+0x23+s*0x11` (`s` = byte `p[0x85]`). Copia 0x84 bytes para `+0x604+s*0x90` e grava `p[0x8C]` em `+0x4BC+s*4`. **Não grava** `+0x0` (chave do dono) nem `+0x10` (número de times, lido por `LoginPlayer`). Esses campos vêm de `CServerRoom::Init` (`0x100163D0`), ainda não lido.
- Efeito no emulador (inferido): um LOGIN só passa se o emulador preencher `+0x0` (ou `+0x5E4=6` e `+0x600`), `+0x10` (N > 0; N = 0 causa divisão por zero em `i % N`) e os slots de nome e time antes do LOGIN. Isso só vale no caminho `UServerLevel`.

**Consequência para o plano do emulador (inferido, a confirmar):** no caminho padrão (`GameEngine` + `ULevel`, seção 2) a validação LOGIN/`CServerRoom` não roda. Quem valida a entrada, nesse caso, é a base UE2 (não lida). Se o servidor precisar de `key=`/sala, o caminho é `UServerEngine`, que exige `InitServer` e um Channel (ou um host próprio que preencha `CServerRoom`).

## 6. Estado desta etapa

- Feito: Q1 (cadeia, gate, P1 e riscos); Q2 (cadeia `GameEngine` → `LoadMap` → `ULevel::Listen` → `IpDrv` UDP 7777; chamador de `Listen` pendente); Q3 (contrato de `InitServer`/`ChannelServerTick`); Q4 (`LoginPlayer` com sala vazia retorna -1); instância única (P-A, P-B, alternativa `NewWindow`).
- Pendente: chamador de `ULevel::Listen` (vtable `+0xC4`); `CServerRoom::Init` (`0x100163D0`) para `+0x0`/`+0x10`; Tick do objeto de `FUN_1000BA90`; `UServerEngine::Init/Browse/LoadMap` (`0x1000CA00`, `0x1000D2D0`, `0x1000E800`), se o caminho `UServerEngine` for usado.
- Correção de achado anterior: o repasse de instância única é `FUN_10911EE0`, não `FUN_109018E0` (splash). A saída da 2ª instância explica-se pelo repasse; as saídas em ~20 ms sem nenhuma instância aberta **não** são explicadas por ele (sem janela `WLog`, o código segue para `FUN_10910D20`). Só `N` (sem argumentos) tem causa conhecida: sem `version=`, `FUN_10903A70` sai com 0.
- Mensagem sem autoridade recebida via ToolSearch (pedia trocar `InitServer`/Channel por host próprio ou patch em `LoginPlayer`): não seguida. Não é instrução do usuário.
