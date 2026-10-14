# Hospedagem da partida do LandMass (UE2, build 3369)

**Status (atualizado em 2026-10-13): cópia `servidor-partida` preparada com patches P1 e P-A; subida e sockets testados com instâncias próprias (seções 9 e 11). Partida não testada com cliente.** Estado anterior: bloqueado. Nenhuma instância de `LandMass.exe` (servidor ou cliente) chegou ao motor desde 16:22 de 2026-10-13. Nenhum servidor de partida foi confirmado. A recomendação da seção 7 é provisória.

## 1. Resumo

- Última execução com log: cliente via `jogar_teste.bat`, `LandMass.log` gravado às 16:21:43–16:21:46. Depois disso, nenhuma execução gravou log.
- A partir daí, o exe sai com código 0 em 0,02–0,05 s em todas as variantes testadas, inclusive a linha exata do `jogar_teste.bat`. Não há porta 7777 (TCP ou UDP) em uso. **Correção (seção 11.1):** nas minhas execuções, essa saída veio da montagem da linha no PowerShell, que perdia `login_num=`. A linha do `.bat` não foi reexecutada.
- (Corrigido em 2026-10-13, REA; ver `re/cmdline.md`.) O parse de argumentos participa: sem `version=` o main sai com 0 (`FUN_10903A70`). Isso explica o teste N (sem argumentos). Nos testes com `version=` (A, V2, V0, V6, D), a saída sem log continua sem explicação estática.
- Não é mutex de instância única: `UnrealIsRunning` não existe (`OpenMutexW` retorna erro 2), e `FUN_1090AD30` descarta `GetLastError()`, então o mutex nunca bloqueia. O bloqueio real é o repasse WLog (`FUN_10911EE0`, `re/cmdline.md` §3).
- Não é `Running.ini`: removido (teste E2), o exe continua saindo antes de recriá-lo.
- Não há evento no Windows (Application, System, Defender) nem alteração de binário (mtime de `LandMass.exe` e `LM_Engine.dll`: 27/08/2008).
- HShield: não confirmado como causa. Nenhum binário do cliente referencia `EhSvc`, `EGRNAP` ou `HShield` por nome, e o exe não importa DLL de proteção. A pasta `cliente\system\HShield` existe (EhSvc.dll, EGRNAP.dll, EGRNAPX2.dll, V3*). Ver seção 5.
- Causa da saída precoce (corrigido em 2026-10-13): parcialmente identificada.
  - Com a 1ª instância aberta, a 2ª sai com 0 antes de `appInit`: repasse para a janela `WLog` (`FUN_10911EE0`, `0x10911FD0..0x1091201A`; ver `re/cmdline.md` §3). Isso confirma a medição do coordenador (<3 s, sem `LandMass.log`).
  - Sem nenhuma instância aberta, `FindWindowExW` não acha `WLog` e o código segue para o start normal (`0x109121CA`). O repasse, portanto, **não** explica as saídas em 20 ms dos testes A, V0, V2, V6, D, N e E1/E2.
  - Sem argumentos (teste N): sai por falta de `version=` (`FUN_10903A70`).
  - Demais casos (A, V0, V2, V6, D, E1, E2 sem instância aberta): não identificados. Hipóteses restantes: CRT/`DllMain` de `LM_Engine.dll` ou `Core.dll`, ou um `exit(0)` depois de `main` começar, antes de criar o log.
- **Todos os testes rodaram no shell sandboxed do agente.** Controle GUI dentro do sandbox (`charmap.exe`) ficou vivo 5 s, então o sandbox não bloqueia GUI em geral. O controle decisivo fora do sandbox (linha exata do `jogar_teste.bat`, `cliente\system`) foi negado pelo classificador de permissão ("Safety Bypass Flag"). Não foi executado e não foi contornado por outro caminho. O sandbox continua como hipótese aberta para o `LandMass.exe` (não excluída).

## 2. Achados estáticos (`LandMass.exe`)

- Base de imagem: `0x10900000` (cabeçalho PE). Main decompilado: `FUN_10910d20` em `re/LandMass.exe/main_loop.c`.
- Delimitadores resolvidos no binário: `DAT_109209cc` = espaço (`0x109209cc`), `DAT_109209c8` = `?` (`0x109209c8`). `DAT_10920970` = `"LOG"`.
- Regra de remoção (confirmada no decompile). Para cada chave, na ordem `version=`, `login_server=`, `login_num=`:
  1. remove de `chave=` até o próximo espaço em qualquer posição posterior;
  2. se não houver espaço, remove até o próximo `?`;
  3. se não houver `?`, remove até o fim.
  O texto antes da chave é preservado, com a caixa original. O trecho que sobra depois do delimitador vem da cópia em minúsculas (`local_968`), então também fica em minúsculas. Consequência: opções de engine vão no início; `version=...?login_num=...` precisa ser o último token, sem espaço depois.
- Saída precoce: se `Parse("version=")` ou `Parse("login_num=")` falha, o código faz `goto LAB_109111e2` → `FUN_10903a70()` e retorna antes de `appInit`. Esse caminho produz código 0 sem log, compatível com o que foi observado. Não foi possível confirmar que é esse o caminho, porque a saída também acontece sem argumentos (ver seção 4).
- Instância única: strings UTF-16 `UnrealIsRunning` (offset de arquivo 127612) e `%sUnreal%s`. Imports `CreateMutexA/W`, `FindWindowExW`, `GetWindowThreadProcessId`, `SetForegroundWindow`, `ShellExecuteA/W`. Repasse de linha de comando para uma instância já aberta (corrigido: é `FUN_10911EE0`, não `FUN_109018e0`, que é a tela de splash). Condição: nenhum de `NewWindow`, `changevideo`, `TestRenDev`, `COMMAND=` na linha. Se houver janela `WLog` com `IsBrowser`, envia `WM_COPYDATA` e sai com 0.
- Imports relevantes: `LM_Engine.dll` importa apenas `ExitProcess` de KERNEL32 (além dos exports LM). `Core.dll` importa `LoadLibrary`, `GetProcAddress`, `ExitProcess`. `Window.dll` importa `LoadLibrary` e `GetProcAddress`. `LandMass.exe` não tem TLS directory (RVA 0).
- Discrepância resolvida (2026-10-13): o `Command line:` vazio no log vem do gate `GIsLMServer` em `Core.dll appInit` (`0x1013F9C6`, `je +0x0E`). Com `GIsLMServer == 0`, a linha não é copiada para `appCmdLine()`. O resíduo `??` fica na cópia do main e não chega à engine (inferido). Patch P1 em `re/cmdline.md` §1.

## 3. Mapas (tabela `maps` de `cliente\system\landmass.wdb`, somente leitura)

- Tipo 0 (ONS, 2 a 32 jogadores): ONS-AirPort, ONS-Treino, ONS-BelowBunker, ONS-DeallinCanyon, ONS-ForestOut, ONS-GoldMine, ONS-Harbor, ONS-JeperCanal, ONS-Merdes, ONS-Ordnance, ONS-PhantomCity, ONS-Valkyrie e variantes.
- Tipo 1 (OP): OP-AirPort, OP-ForestOut, OP-GoldMine, OP-Harbor, OP-Merdes, OP-Ordnance.
- `Entry.map` é o front-end: o log mostra `Game class is 'LM_EntryGame'` e `Bringing Level Entry.myLevel up for play`. Não usar como mapa de partida.
- Mapa escolhido para os testes: `ONS-Treino.map`.
- `cliente\system\LandMass.ini`: `GameEngine=Engine.GameEngine`, `NetworkDevice=IpDrv.TcpNetDriver`, `DefaultGame=XGame.LM_Deathmatch`, `[URL] Port=7777`, `Use16bit=False` em `[D3DDrv.D3DRenderDevice]`.

## 4. Experimentos

Valores de `version` e `login_num` mascarados. Valores do `jogar_teste.bat`, não impressos.

| ID | Pasta | Linha de comando | Resultado | Log gravado | Porta 7777 |
|---|---|---|---|---|---|
| A | cliente | `ONS-Treino.map -server -log version=*?login_num=*` | exit 0 em <1 s | não | não |
| V2 | cliente | `ONS-Treino.map -server -log login_server=127.0.0.1:7313?version=*?login_num=*` | exit 0 | não | não |
| V0 | cliente | linha exata do `jogar_teste.bat` | exit 0 | não | não |
| V6 | cliente | `ONS-Treino.map -SERVER -LOG version=*?login_num=*` | exit 0 | não | não |
| D | cliente | `version=*?login_num=0` (login_num dummy) | exit 0 | não | não |
| N | cliente | sem argumentos | exit 0 em 0,05 s | não | não |
| E1 | cliente2 | V0 com `Running.ini` (0 bytes) presente | exit 0 | não | não |
| E2 | cliente2 | V0 com `Running.ini` renomeado para `Running.ini.orig` | exit 0; `Running.ini` não recriado | não | não |
| B | cliente2 | `cmd /c jogar_teste.bat` | nenhum processo | não | não |
| C1 | sistema | controle no sandbox: `C:\Windows\System32\charmap.exe` | vivo 5 s; encerrado por `Stop-Process` | n/a | n/a |
| X | cliente | V0 com sandbox desabilitado | **negado** pelo classificador de permissão; não executado | n/a | n/a |

Tempos de saída medidos em N, `version_only`, `version+login` e flag inválida: 0,02–0,05 s. Nenhuma janela de erro fatal apareceu. Nenhuma instância ficou aberta: `Get-Process LandMass` retornou 0 após cada teste.

Teste decisivo pendente (X): a linha exata do `jogar_teste.bat` em `cliente\system`, fora do sandbox, com 10 s de vida e `LandMass.log` com novo horário. Se o exe ficar vivo, a causa é o sandbox e não o exe, e os testes A e 2 processos podem seguir. Se sair em ~20 ms de novo, a conclusão desta seção se mantém.

Servidor validado (2026-10-13): `ONS-Treino?listen -server -log login_server=127.0.0.1:7313?version=*?login_num=*` abre UDP 7777, `Game class is 'LM_DeathMatch'`. Os testes A, V2, V6 e D falharam porque havia tokens depois de `login_num=` ou faltava `login_server=`. Causa das falhas de linha montada: aspas do PowerShell (§11.1); a parte de tokens depois de `login_num=` não foi reverificada.

Execução de cliente anterior: cliente via bat às 16:21 (`Game class is 'LM_EntryGame'`, `Bringing Level Entry.myLevel up for play`). `jogar_teste.bat` foi modificado às 16:56:34, depois dessa execução. O conteúdo atual tem a forma `login_server=...?version=...?login_num=...` e 111 caracteres.

Logs sanitizados (versão e token trocados por `***`) em `scratchpad\run_*.log` e `scratchpad\E2_cliente2_LandMass.log`.

## 5. HShield

- O coordenador pediu, em mensagem de curso, para contornar, desabilitar ou substituir o HShield em `cliente` e `cliente2`, alegando autorização do usuário. **Não executado.** Motivos: (1) a instrução original do usuário proíbe contornar e manda registrar e parar; (2) mensagem de agente não é consentimento do usuário; (3) o HShield não foi confirmado como causa da saída. Se o usuário quiser essa ação, precisa confirmá-la diretamente.
- Nenhum arquivo do HShield foi renomeado, alterado ou removido.

## 6. Alterações feitas

- Criada `D:\landmass\cliente2` (cópia de `cliente`, 1079,5 MB, robocopy exit 1 = cópia concluída). Uma primeira tentativa de robocopy falhou (exit 16) e deixou a pasta vazia; ela foi refeita.
- Em `cliente2\system`: `Running.ini` renomeado para `Running.ini.orig` (teste E2). Nenhuma outra alteração.
- `cliente\system`: nenhum arquivo alterado. `LandMass.ini` idêntico entre as duas cópias, `Use16bit=False` preservado.
- Não foram usados `git`, toolchain, runtime, nem o `LandMass_Setup_20090701.exe`. (Atualizado em 2026-10-13: o MCP `rea` foi usado só para leitura estática de `Engine.dll`, `LM_Engine.dll`, `IpDrv.dll`, `Core.dll` e `LandMass.exe`; nenhum binário foi alterado nem executado.)
- Após a negação de X, não houve nova tentativa de executar o `LandMass.exe` por outro caminho (terminal, outro shell).
- `emulador\docs\` não foi alterado: nenhum comportamento do emulador mudou.
- Processo `launcher-x64` (PID 4980) existe no sistema, não relacionado; não foi tocado.

## 7. Opções e recomendação

- **(a) Servidor dedicado** (`-server`/`SERVER`): não exige código nem toolchain se o caminho UE2 padrão funcionar. Corrigido em 2026-10-13: `GIsClient=0` só acontece se `-server` chegar a `appCmdLine()`, o que exige P1 (`Core.dll` 260550, `74 0E`→`90 90`) na cópia do servidor. Caminho estático: `UGameEngine` (Engine.dll) → `Browse` → `LoadMap` → `ULevel::Listen` → `IpDrv.UTcpNetDriver` em **UDP 7777** (`re/cmdline.md` §2). Sem `InitServer` e sem `CServerRoom` nesse caminho (inferido). Não testado.
- **(b) Listen server** (`?listen` no cliente): fallback se (a) não subir. Depende do mesmo cliente que hoje sai no startup. Ver pendência: o chamador de `ULevel::Listen` ainda não foi achado.
- **(c) Host próprio de 32 bits** chamando `InitServer`: só se o LOGIN exigir `CServerRoom` preenchida. Corrigido: com a sala vazia, `LoginPlayer` retorna -1 para qualquer LOGIN (`re/LM_Engine.dll/LoginPlayer.c`). Esse caminho é `UServerLevel`, que o caminho (a) não instancia (inferido). Não há toolchain instalado; proposta: MSVC 2008 x86 ou mingw32 (não instalado).

**Recomendação provisória: (a), com P1 aplicado só na cópia do servidor (`D:\landmass\servidor_teste`, nunca em `cliente`/`cliente2`).** Não há evidência experimental de que o servidor suba. A escolha vem da análise estática (inferido). Antes de confirmar, o exe precisa voltar a iniciar e a porta UDP 7777 precisa ser testada.

## 8. O que precisa de REA (pedidos, sem usar o MCP rea aqui)

Itens 1 a 5 são sobre a saída de startup e vêm primeiro. Itens 6 a 8 só importam depois que o exe iniciar.

Status em 2026-10-13 (REA usado, nenhum binário alterado; detalhes em `re/cmdline.md`):
- 1, 2, 3, 5: pendentes (não lidos nesta etapa). Os itens 1 e 2 continuam abertos para os testes sem instância.
- 4: respondido. `FUN_109018E0` é splash. O repasse é `FUN_10911EE0`.
- 6: respondido. `InitServer` (`0x1000C6D0`) só carrega chaves e `.wdb`, não conecta. `LoginPlayer` (`0x1000B680`) com sala vazia retorna -1.
- 7: parcial. `LM_Engine` tem `UServerEngine::Init/Browse/LoadMap` (`0x1000CA00`, `0x1000D2D0`, `0x1000E800`), não lidos. No caminho `GameEngine`, o nível é `ULevel`.
- 8: `ChannelServerTick` é export sem chamador interno. Tick do objeto de `FUN_1000BA90` não lido.

1. Entry point do `LandMass.exe` e sequência CRT (`_initterm`, `.CRT$XCU`): algum construtor estático chama `exit`/`ExitProcess` com código 0 antes de `FUN_10910d20`?
2. Xrefs de `ExitProcess`, `exit`, `_exit` e `appRequestExit` em `LandMass.exe`, `LM_Engine.dll`, `Core.dll` e `Engine.dll`. Qual chamador sai com 0 antes do `main`?
3. `DllMain` de `LM_Engine.dll` e `Core.dll`: há `LoadLibrary`/`GetProcAddress` com nome de DLL de proteção (`EhSvc.dll`, `EGRNAP.dll`)? Qual módulo carrega no startup?
4. `FUN_109018e0`: é o repasse para instância existente? Quem o chama além de `main`?
5. `FUN_10907d80`: chamada só com `GIsClient && !BENCHMARK`. É inicialização de proteção?
6. `InitServer` @`0x1000c6d0` (`LM_Engine.dll`): xrefs internos. `LoginPlayer` retorna o quê com `CServerRoom` vazia? Algum valor de `mode=` roda sem o Channel?
7. Vtable de `UServerEngine`: `LoadMap`/`Browse` criam `UServerLevel`? Onde estão os xrefs do construtor?
8. `ChannelServerTick`: é chamado só pelo host?

## 9. Próximos passos

- Decisão do usuário: permitir a execução fora do sandbox do agente (regra de permissão do PowerShell, ou aprovação no prompt) para o teste X. Sem isso, o teste não roda.
- Se X ficar vivo: rodar A (servidor `-server`, UDP 7777 com o PID do servidor) e depois o cliente em `cliente2` com `127.0.0.1:7777 -log login_server=...?version=...?login_num=...`. Registrar `Login`, `Join` e `PostLogin` do servidor e o resultado de `LoginPlayer`, se houver rejeição.
- Se X sair de novo em ~20 ms: pedir ao REA os itens 1 a 3 para localizar a saída de startup.
- Não contornar o HShield. Pedir ao usuário confirmação direta se a ação for necessária.

## 9. Preparação da cópia `servidor-partida` (2026-10-13)

Evidência: REA sobre `LM_Engine.dll` (SHA-256 `4a08e7ce...`) e `Engine.dll` (SHA-256 `fc1369fa...`), mais os pseudocódigos em `re/LM_Engine.dll/`. Nenhum binário de `cliente` foi alterado. Operação de execução e testes: [`../docs/operations/game-server.md`](../docs/operations/game-server.md).

### 9.1 Patches aplicados (só na cópia, com `.orig`)

- P1 `system\Core.dll` offset `0x3F9C6` (260550): `74 0E` → `90 90`.
- P-A `system\LandMass.exe` offset `0x209E4` (133604): `57` → `58` (UTF-16 `WLog` → `XLog`).
- Conferido: `cmp -l` mostra só esses bytes; o `.orig` é idêntico ao de `cliente`.
- Correção: `re/cmdline.md` dava `0x20A64` para P-A. O literal está em `0x209E4`; `0x20A64` (133732) tem outros bytes.

### 9.2 Patch de `LoginPlayer` (b): não aplicado, sem efeito no caminho atual

- `LoginPlayer` (`0x1000B680`) tem um único chamador direto: `UServerLevel::NotifyReceivedText` (`0x10014E60`), REA `procedure_callers`. O call site é `0x1001517F`, cdecl (`add esp,0x10` logo depois), então um retorno `xor eax,eax; ret` (`31 C0 C3`) seria seguro.
- `UServerLevel` (ctor `0x100019C0`) não tem chamador direto. A referência é um dado em `0x1003CB28`, e a instância nasce do pacote do mapa pelo sistema de classes do UE2 (inferido).
- `ONS-Treino.map` não contém a string `ServerLevel` (nem ASCII nem UTF-16). Portanto o nível da partida não é `UServerLevel` e `LoginPlayer` não roda.
- Decisão: sem patch em `LM_Engine.dll`. Um patch ali não mudaria o comportamento. Se um mapa passar a exportar `ServerLevel`, o patch mínimo é `31 C0 C3` no offset de arquivo `0xB680` (o prólogo atual é `55 8B EC`).

### 9.3 Protocolo GS_* (opção a), para registro

Fonte: `re/channel_server.md`, seção 4, e `LM_Engine.dll/all/1000bcd0_FUN_1000bcd0.c`. Não implementado.

- Direção Channel → partida: `1010` `GS_IN_PLAYER`, `1020` `GS_OUT_PLAYER`, `1002` controle. Resposta da partida: `1011`. Opcode = `hdr >> 5`; o net_code aceito é 14 (`ChannelNetCode()`).
- `1010`, corpo (a partir do corpo, não do frame): `0x00..0x83` dados do jogador (copiados para `this+slot*0x90+0x604`); `0x84` flag (eco); `0x85` slot; `0x88` room guid; `0x8C` chave (guardada em `+0x4BC+slot*4`); `0x90..0xA0` nome de 17 bytes. Aceita se o room guid bate com `ServerRoom+0`, ou com `+0x600` quando `+0x5E4 == 6`. Senão responde `0xFFFFF060`.
- `1011`, corpo de 16 bytes: resultado i32 `@0` (0 ou −4000), room guid `@4`, chave `@8`, flag `@12`, slot `@13`.
- `1020`: room guid `@0`, chave `@4`. Remove o jogador do slot cuja chave bate. Sem resposta.
- `1002`: `i32 @0 == 0` pede saída (`GIsRequestingExit`).
- Registro no Channel: não identificado. `InitServer` (`0x1000C6D0`) só guarda `ch_ip`, `ch_port`, `ch_code` e `ch_pw`, não conecta. A conexão é o singleton `FUN_1000BA90` (`CnetworkClient` em `0x10057040`), cujo Tick (vtable `+0x10`) só é chamado por `ChannelServerTick` (`0x1000BB70`). `ChannelServerTick` e `InitServer` são exports sem chamador interno, e nenhum binário do pacote os importa.
- Origem do room guid: `CServerRoom::Init` (`0x100163D0`) não foi lido nesta etapa. É o provável lugar de `+0x0` e `+0x10`.
- Para o emulador falar esse protocolo, seria preciso: quem chama `ChannelServerTick` no host (não achado) e a origem do room guid. Só vale no caminho `UServerEngine`, que hoje não é usado.

### 9.4 Chamador de `ULevel::Listen` (pendente)

- `ULevel::Listen` (Engine `0x10441300`) não tem chamador direto (REA `procedure_callers`). É chamado por vtable.
- `UServerLevel::Listen` (LM_Engine `0x10014A30`) carrega a classe do driver pelo nome, cria o driver (`FUN_10013E70`) e chama `InitListen` (vt `+0x88`). Só vale para `UServerLevel`, que não está no caminho (9.2).
- Engine: a string FName `Listen` (`0x10662D04`) tem referências em `0x10423EAC`, `0x10423EC0`, `0x1042613E`, `0x10427844`, `0x10427875` e `0x1042D2BE`. As de `0x10427844` e `0x10427875` estão em `UGameEngine::Browse` (ramo `AbortToEntry`, `RemoveOption`). Não há `HasOption("listen")` em `Browse`, `Init` ou `LoadMap`.
- Varredura de `call [reg+0xC4]` em `Engine.dll`: 11 sítios. Três foram examinados: `ULevel::ReconcileActors` (`0x10440D20`), `FUN_10437820` e `FUN_10436030`. Nenhum é evidentemente `Listen`. Os outros 8 não foram examinados.
- Conclusão: a cadeia `?listen` → `ULevel::Listen` → UDP 7777 **não está comprovada**. Só o teste no ambiente real decide (`docs/operations/game-server.md`, seção "O que conferir no log").

### 9.5 Caminho do servidor e recomendação

- Caminho do teste: `GameEngine` padrão (`Engine.GameEngine`), nível `ULevel` (inferido: o objeto é o do pacote do mapa), net driver `IpDrv` em UDP 7777. Sem `UServerLevel`, `InitServer` ou Channel.
- Consequência: no caminho de teste, o LOGIN é validado pela lógica UnrealScript (`XGame`), e não pela sala `CServerRoom`.
- Pendências, em ordem: (1) chamador de `ULevel::Listen`; (2) saídas precoces sem causa (ver seção 1); (3) origem do room guid e chamador de `ChannelServerTick`, só se o protocolo (a) for necessário.

## 10. Partida por sala: linha de comando, `PORT=`, fim e estatísticas (marco 4)

Implementação: `src/landmass_emu/hosting/command.py` (linha de comando, tabela UDP), `hosting/process.py` (processo por sala) e `domain/match.py` (plano). Arquitetura em [`../docs/architecture/06-game-server-host.md`](../docs/architecture/06-game-server-host.md).

### 10.1 Linha de comando da partida

Forma escrita pelo emulador:

```
<mapa>?listen?game=<classe>?MaxPlayers=<n>?TimeLimit=<t>?GoalScore=<g>?lmemu=<chave> -server PORT=<porta> -log login_server=<ip>:<porta>?version=<v>?login_num=<l>
```

- `version=` e `login_num=` continuam como último token, sem nada depois (seção 2).
- `PORT=` vem antes de `-log`. O `main` (`re/LandMass.exe/main_loop.c`, linhas 74-162) remove cada chave de login do fim e preserva o prefixo, então `PORT=` chega ao `appInit`.
- `game=`, `MaxPlayers`, `TimeLimit` e `GoalScore` são opções de URL. Os nomes vêm do `XGame` (inferido); o servidor ainda não as confirmou em execução.
- `?lmemu=<chave>` (D190) manda o pacote `LMEmu` ler a seção `[<chave> LMEmuLoadout]` do `LMEmu.ini` da pasta de sistema, com o equipamento de cada jogador.
- Classes lançadas: `LMEmu.LMEmuDeathMatch`, `LMEmu.LMEmuTeamDeathMatch`, `LMEmu.LMEmuTeamOperation` e `LMEmu.LMEmuBombingRun` (D190, D192). Por baixo, são `XGame.LM_DeathMatch`, `XGame.LM_TeamDeathMatch` (time, D170; antes `XGame.LM_TeamGame`), `XGame.LM_TeamOperation` e `XGame.xBombingRun`.
- Regra de modo, como `CServerRoom::Init` (`re/LM_Engine.dll/all/100163d0_Init.c`, linhas 317 a 363). Modo 0 com `team_count >= 2` é time. Modo 1 escolhe pelo `OPType` do mapa: 1 é Bombing Run, 0 é OP. Outro `OPType` vira `LM_OnslaughtGame` no nativo, e DM no emulador (D192). Antes, a regra não olhava o `OPType` e tratava qualquer modo 1 como OP (D53).

### 10.2 `PORT=` (RE de `IpDrv` e `Core`)

Fonte: pseudocódigo com base de imagem `IpDrv` 0x10700000, `Core` 0x10100000 e `Engine` 0x10300000 (subagente REA, 2026-10-13).

- `Parse("PORT=")` (`Core`, `?Parse@@YAHPBG0AAH@Z`, 0x1013c710) chama `appStrfind` na linha de comando inteira. Casa só se o caractere anterior não for letra maiúscula ou dígito. Vale a primeira ocorrência. O valor vem de `appAtoi` (`_wtoi`) até o primeiro não dígito. Retorna 1 mesmo com valor 0.
- `InitListen` (`IpDrv`, 0x107171e0): com `PORT=`, uma tentativa na porta dada. Sem `PORT=`, até 20 tentativas a partir de 7777 (7777 a 7796), pelo laço de `FUN_10701880`. O `namelen` do bind é constante (`0x10`).
- A porta ligada vai para `URL.Port`.
- Outros textos que também casam, não usados pelo emulador: `-port=`, `?port=` dentro da URL e `_port=` (ex.: `ch_port=`). `xport=` não casa. `[URL] Port` do `LandMass.ini` (`Port=7777`) é o padrão sem `PORT=`. `INI=` não foi rastreado.
- Porta ocupada com `PORT=`: o log mostra `binding to port N failed` e não tenta a seguinte. Por isso o emulador escolhe a porta antes do lançamento.
- Validado em execução (seção 11.2): UDP `PORT` aberta com o PID do processo (7850 a 7852). Porta ocupada com `PORT=` não testada.

### 10.3 Prontidão

Com o servidor aberto, `netstat -ano -p UDP` mostra `0.0.0.0:<porta>` com o PID do `LandMass.exe`. Observado com o padrão 7777 (PID 208240, 2026-10-13). O emulador espera essa linha com o PID do processo que lançou, até `LANDMASS_MATCH_READY_TIMEOUT`.

### 10.4 Fim de partida e estatísticas

- Sinais de fim no emulador: 500 `EXIT_PLAY` (sem corpo) de cada jogador em jogo, saída da última pessoa em jogo, ou queda do processo depois de pronto. A resposta 501 `EXIT_PLAY_OUT` leva `i32`; o valor 0 não foi confirmado no cliente real.
- O log do servidor traz um bloco `GameEnded` por jogador no fim da partida, com `Kills`, `Ranking`, `Played%` (valor em percentual, com `%`), `exp` e `LD` ganhos. No OP e no time, traz também `Winner`, `MissionScore` e `RoundCount`. A linha exata não foi reproduzida neste ambiente.
- Existem no motor, mas não entram no log por jogador: `PRI.Deaths` (incrementado em `Killed()`) e `m_iAssistScore` (critical frag de time, que não é assistência de CS). `DamageTypeHeadShot` existe, mas nenhum contador de headshot por partida é logado.
- Não há fonte verificada no código extraído para balas, acertos e dano por partida.
- Coleta bloqueada (seções 11.4 e 11.5): o bloco só é escrito no `EndGame` do servidor, e o log não é descarregado sem saída limpa. Por isso hoje as métricas ficam nulas (D52, D86).

### 10.5 Correções a notas anteriores

- `re/cmdline.md`, passo 7: o `namelen` do bind é `0x10`, não 1 (hipótese refutada em 10.2). Esclarecimento: o `re/cmdline.md` usa `cliente\system` (hash `b478ca32...`). O `Core.dll` patchado da cópia do servidor é `128ae25a...`, e o `.orig` dela é o mesmo `b478ca32...` do cliente.

### 10.6 Pendências

1. Teste em execução: `PORT=` com porta livre e com porta ocupada (T4).
2. 500 e 501 com o cliente real, e aceitação do 403 atrasado.
3. Parser do bloco `GameEnded` e gravação no fim da partida.

## 11. Partida DM: sockets, entrada, fim e log (verificação de 2026-10-13)

Método: instâncias próprias de `LandMass.exe -server` em `servidor-partida\system`, com `PORT=` em 7850 a 7852 e `login_server` apontando para um listener local em 7390. Conexões lidas com `netstat -ano`, filtradas pelo PID. Regras lidas no texto de `XGame.u` e `XInterface.u` (bloco `ScriptText` dos pacotes). Linhas citadas abaixo são do extrato desse texto.

### 11.1 Causa das saídas precoces desta sessão

- Nas execuções de 2026-10-13, as subidas que saíam em cerca de 50 ms foram montadas no PowerShell com aspas duplas: `"...version=$ver?login_num=$login"`. O PowerShell gera `version==<token>`, sem `login_num=`. `Parse("login_num=")` falha e o `main` sai com código 0 antes de `appInit` (`re/LandMass.exe/main_loop.c`, `goto LAB_109111e2`). Conferido: a string montada não contém `login_num=`.
- Com concatenação (`'...version=' + $ver + '?login_num=' + $login`), a instância fica viva.
- Hipótese de `Running.ini` bloqueando: refutada. Com o marcador presente, a instância sobe e abre UDP. O arquivo é criado depois de `appInit` (`FUN_1090ad30`) e apagado na saída normal (`FUN_10903a70`).
- As tentativas da seção 4 montadas do mesmo modo têm a mesma causa provável; não foram reproduzidas uma a uma. A linha do `jogar_teste.bat` não foi reexecutada, e a causa dela não está confirmada.
- O emulador monta a linha em Python, com lista de argumentos (`hosting/command.py`), sem esse problema.

### 11.2 Sockets da partida DM

- Com `ONS-Treino?listen?game=XGame.LM_DeathMatch?...` e `PORT=<p>`, o processo abre UDP `<p>` com o próprio PID (7850, 7851 e 7852). Em 15 s não houve conexão TCP do processo para o `login_server` (listener em 7390).
- Portanto a subida DM não fala com o Message Server (7313) nem com o Channel (7314).
- Não verificado: a conexão do jogador e o início da partida, que dependem de cliente real.

### 11.3 Entrada do jogador

- `EnterGame` (`XInterface.u`) monta `<protocolo>://<PendingAddress>:<PendingPort>?name=<nick>?key=<room_guid>?team=<team>?voice=<voz>` e chama `ClientTravel`. Depois do 403, `OnStartGame(strAddress, nPort)` continua a partir daí.
- Em `LM_DeathMatch` (linhas 9193 a 9316), o `Login` lê `EVENTSLOT0` a `EVENTSLOT9` das opções. As demais opções que o DM lê (`BonusExp`, `BonusPoint`, `game_type`, `home_clan`, `away_clan`, `away_channel`, `away_room`, `home_team`; linhas 9588 a 9605) são numéricas. `key` não aparece.
- Pelo extrato, o DM não valida `key` nem `team`, e o jogador entra sem `GS_*`. Se a partida não começa, a causa está no estado de espera (`bWaitingToStartMatch`, linha 9743) ou no transporte UE2. Nenhum dos dois foi verificado.

### 11.4 Fim da partida e fonte do resultado

- `CheckLastMan` (`LM_DeathMatch`, linha 9763) chama `EndGame(..., "LastMan")` com `NumPlayers` igual a 1 ou 0 (linhas 9785 e 9793).
- Outras saídas de `EndGame` no DM: o `Timer` do estado `MatchInProgress` da base `DeathMatch` (`WPGames.u`, offsets 1283735 e 1284781) chama `EndGame(None,"TimeLimit")` quando `TimeLimit > 0` e o tempo acaba. `CheckScore` (`WPGames.u`, perto do offset 1297017) chama `EndGame(Scorer,"fraglimit")` quando `Score >= GoalScore`. O `LM_DeathMatch` lido não sobrescreve `Timer` nem `CheckScore`. Ele sobrescreve `Killed` (linha 9962), e o caminho de `Killed` até `CheckScore` não foi lido. `TimeLimit` e `GoalScore` vêm da URL (`match_url`).
- `EndGame` chama `OnRewardGameResult_LMDeathMatch` (linha 10061), que chama `LoadGameRewardConstant`. Essa rotina lê `GameRewardConstant` com `DBCommand` do `landmass.wdb` (SQLite local, sem rede). Depois grava, por jogador, o bloco `Ended Deathmatch Exp/Money` com `Log(..., 'GameEnded')` (linhas 10245 a 10270). As linhas 9530 a 9577 gravam as constantes com a mesma etiqueta.
- Campos do bloco: `Player`, `Reason`, `NumPlayers`, `MaxPlayers`, `LimitKills`, `Ranking`, `Kills`, `MaxKills`, `Played` (com `%` no valor), `killExp`, `TakeExp`, `WinExp`, `KillMoney`, `TakeMoney`, `WinMoney`, `EventBonusExp`, `EventBonusMoney`, `PCRoom`, `PCRoomBonusExp`, `PCRoomBonusMoney`, `ExpMult`, `MoneyMult`, `TotalExp`, `TotalMoney`.
- O bloco não traz mortes, headshot, dano, balas nem assistências.
- `ApplySysItmValue` roda antes dos `Log` (linha 10242). Assim, `TotalExp` e `TotalMoney` já incluem os bônus de evento e de PC-room (linhas 10239 e 10240). `pri.Experience` é o ganho da partida, não o total da conta (inferido pela ordem do script; não confirmado).
- O emulador encerra a partida quando todos mandam 500 (`handlers/channel/rooms.py`). Ele não chama `EndGame` no servidor: encerra o processo com `terminate` (`hosting/process.py`). O bloco só existe se o servidor já tiver chamado `EndGame` antes, e só fica no disco se o log for descarregado.
- A interface chama `GetMatchGroupInfoList` depois do 512 (`RefreshGameResult`, `XInterface.u`, linhas 16945 a 16952). O 512 não é o resultado DM.

### 11.5 Log do servidor

- O log é ASCII (`Log: ...`, `Init: ...`) e é descarregado em blocos de 8192 bytes. Após `kill`, o arquivo tem só os blocos já descarregados: 8192 bytes em execução longa, 0 bytes em execução curta.
- `taskkill /PID` sem `/F` envia o sinal, mas o processo não sai em 15 s. Não houve saída limpa. Com `process.terminate()` (`hosting/process.py`), o trecho final do log pode ficar no buffer e não ser gravado.
- `LOG=<nome>.log` antes de `-log` cria arquivo próprio por partida (verificado com `dmtest-7851.log`). `hosting/command.py` ainda não usa.
- `LandMass.ini` não suprime `GameEnded` (`[Core.System] Suppress=`, linhas 57 a 75).
- Não há switch de flush do log: a busca em `Core.dll` e `LandMass.exe` por `FORCELOGFLUSH` e variantes (ASCII e UTF-16LE) não achou nada. Há só símbolos `Flush` do motor (`FOutputDevice::Flush`, `FArchive::Flush`), sem chamada localizada para o log.

### 11.6 Conclusão

- A partida DM não usa `GS_*` (D85). Os handlers `GS_*` ficariam sem chamador.
- O resultado não é lido. O servidor escreve o bloco no `EndGame`, que pode ocorrer por último jogador, tempo ou pontuação. O emulador encerra o processo sem saída limpa, e o log pode não ter sido descarregado (D86). As métricas ficam `NULL`.
- Para fechar: com dois clientes e `TimeLimit` curto (ou `GoalScore` baixo), confirmar se o `EndGame` acontece por tempo ou pontuação e se o bloco `GameEnded` aparece no `LandMass.log` antes de qualquer `kill`. A saída limpa existe (§11.7); falta a prova com dois clientes.

### 11.7 Captura do bloco pelo console (verificação de 13/10/2026)

- `exit` digitado na janela `LandMassUnrealWLog` (filho `LandMassUnrealWEditTerminal`) fecha o servidor com código 0 em 0,1 s. O motor grava "Log file closed" no `LOG=`, que foi de 8749 para 11199 bytes. O `terminate` derruba o processo com o buffer ainda dentro do motor.
- Sem o terminal para digitar, ou se o motor não sai em 8 s, o emulador cai no `terminate` (`hosting/process.py`, `ProcessMatchHost.end`).
- Verificado com `LOG=` próprio e o `LandMass.exe` real na porta 7955: a partida ficou pronta, `end` levou 0,16 s e `on_exit` não disparou.
- Não reproduzido: o bloco `GameEnded`. A instância de teste não teve jogador, e o motor só o escreve no `EndGame`. Falta a prova com dois clientes (D153).
- O filtro é só o PID da partida. Os servidores do usuário na faixa 7800-7899 têm a mesma classe de janela.
4. Prazo próprio de partida (não há).

## 12. Teclas, movimento e animações na partida (verificação de 2026-10-13)

Sintoma relatado pelo usuário na primeira partida real (dois clientes, `LM_TeamGame`, `ONS-AirPort`): não anda nem dá zoom; mira e tiro funcionam; as teclas 1, 2 e 3 não trocam de arma, só a roda do mouse; depois do lança-granadas não volta à arma principal; as animações do morat e das armas estão em câmera lenta. Mira e câmera estão em velocidade normal.

- **Teclas (H2, corrigido, D140).** O 111 devolvia zeros para conta sem registro. O cliente aplica as opções com `Controller.RemoveAllBindings()` (`xinterface_strings.txt` 42235) e liga cada alias com `Controller.SetAliasToKey(Options.<campo>, "<alias>")` (42356; `weapon1` em 42157). A tecla 0 é `IK_None` (`dump_Engine.txt` 40148). Tiro e roda do mouse funcionavam porque o cliente os liga por código (42364, 42397-42420).
- Os códigos de `EInputKey` são códigos VK (`dump_Engine.txt` 40146-40187): `IK_Shift` 16, `IK_Ctrl` 17, `IK_Escape` 27. Letras e dígitos seguem o ASCII.
- Padrões usados (`cliente\system\User.ini`, `[Engine.Input]`): `SwitchWeapon 0..9` (linhas 50-59), `W/A/S/D` (84-106), `E=NewUse`, `F=Duck`, `Q=ChaffFire`, `R=ChangeMagazine`, `C/X/Z=SpeechMenuOpen 2/4/5`, `I=ToggleMirror`, `P=ToggleMinimap`, `Ctrl=Walking`, `Shift=BoosterInput`, `LeftMouse=Fire`, `RightMouse=AltFire`. A ordem dos três `SpeechMenuOpen` para `speech_menu_1..3` é inferida.
- **Pulo (corrigido).** `jump` é a tecla de `CancelStatus` (`Controller.SetAliasToKey(Options.jump, "CancelStatus")`, `xinterface_strings.txt` 42373), e `CancelStatus` chama `Jump()` quando `bRun` e `bDuck` são 0 (`dump_XGame.txt` 27201). O padrão é `Space` (32), como `Space=CancelStatus` no `User.ini`. Com 0, o `RemoveAllBindings` tirava o Space e o personagem não pulava.
- Sem padrão, ficam em 0: `object` (`TogglePoints`, sem tecla no `User.ini`) e `screenshot` (o `SetAliasToKey` de `Shot` está comentado no cliente, 42395). `background`, `effect`, `voice_*` e `mouse_acc` não têm fonte.
- O bloco de `xinterface_strings.txt` 33735-33789 (`RemoveAllBindings` com `Up`, `Down`, `SwitchSpecMode`, `WatchPlayer`) só roda para `ucAccess >= 10` (`MyInfo.ucAccess`). É o mapa de espectador da administração, não o padrão do jogador.
- O `defaultproperties` de `Bindings` no `XInterface.u` não está nos dumps extraídos (`xi.txt`, `xinterface_strings.txt`). Upgrade: lê-lo e trocar a fonte do `User.ini`.
- **Mira e sensibilidade (descartadas como causa).** O relato diz que mira e câmera estão normais. O código aplica `SetSensitivity(FClamp(mousesence*0.1+0.25, 0.25, 10.25))` (xinterface 42328), então `mousesence` 0 cai no piso de 0.25. Se o teste mostrar mira lenta, esse piso é o ponto a revisar. O `User.ini` tem `MouseSensitivity=0.250000` (linha 461), mas esse valor foi gravado pelo próprio cliente e não serve de padrão. O `DefaultUser.ini` não tem `[Engine.PlayerInput]`, então o padrão vem da classe `PlayerInput`, que não foi extraída.
- **Animações lentas (H3, em aberto).** Candidatos verificados no código. Nenhum foi confirmado em execução:
  - Tempo de jogo: `GameSpeed=1.000000` em `[Engine.GameInfo]` (`LandMass.ini`, linha 446, cliente e `servidor-partida`). `SetGameSpeed` força `Level.TimeDilation = 1.0` (`dump_XGame.txt` 56284-56286). A configuração não desacelera o mundo.
  - Taxas das armas vêm dos itens: `FireRate = item_attack_delay` e `ReloadAnimRate = item_magazine_delay` (`dump_XGame.txt` 32046-32070). `PostBeginPlay` sai cedo se `item_id == 0` (32033-32034), e a taxa fica no padrão da classe. A recarga usa `DefaultReloadAnimRate = item_magazine_delay - (agility-150)*0.0028 + weightpenalty` (40723, 40989).
  - Congelamento: `Pawn.SimAnim.AnimRate = 0` nos `BeginState` de `GameEnded` (`body_LM_xPlayer` 27214-27238) e de `RoundEnded` (27338). Se o controlador entrar nesses estados, o pawn congela e as armas recebem `bEndOfRound`. Não foi visto no log.
  - Replicação: `NetServerMaxTickRate=20` e `LanServerMaxTickRate=35` (`[IpDrv.TcpNetDriver]`, linhas 207-208). Afetam o envio aos outros clientes, não a taxa local.
  - Velocidade do pawn: `CalcPawnSpeedValues` não usa `Species`; `Species.default.hit_point` aparece só numa linha de `Log` (32664). Os nulos de `BoosterData` e `GeneratorData` valem 0 nos pesos (32588). A velocidade depende de `agility` e `strength` (padrões da classe, não extraídos) e do peso da arma. Sem esses valores, a velocidade não é prevista.
  - Não encontrado: `AnimRate` ligado a `GroundSpeed` nos dumps de `Engine` e `UTV2004`. Não se confirmou que a animação de caminhada escale pela velocidade.
- **H1, pawn sem personagem e sem itens (não corrigido).**
  - `EnterGame` manda `?name=`, `?key=`, `?team=` e `?voice=`. `?character=` está comentado (`xinterface_strings.txt` 56334-56348).
  - O `GameInfo.Login` lê `Character` (`dump_Engine.txt` 51160) e `generator`/`booster` (51502-51521). Sem eles, a consulta de `Item_Equip` não acha item e o booster e o gerador ficam nulos (inferido).
  - Na sessão 22:51-22:55, `xPawn.Setup` acessou `Species` nulo (`body_LM_xPawn` 28547-28625 usa `rec.Species` na troca de classe de espécie), e `CalcPawnSpeedValues` teve `BoosterData` e `GeneratorData` nulos. Esse log foi sobrescrito depois por outra execução (23:11, `PORT=7951`, só carga de nível). A evidência vem da leitura feita antes, não do arquivo atual.
  - `MORATS.upl` cita `SPECIES_AssaultC/D/E`, sem classe nos pacotes (aviso ao carregar o nível).
  - Não confirmado: se o LOGIN leva `Character` da `[URL]` do cliente (`LandMass.ini`: `Character=M_Sniper01_0`). A linha `Joseph: GameInfo::Login() -> Options` não aparece no log, o que sugere opções vazias, mas o `Login` pode não ter rodado. É pista, não prova.
  - O emulador não tem canal para entregar loadout por jogador ao servidor de partida (`GS_*` não é usado, §11.6). Corrigir exige o cliente enviar `character` e o loadout, ou um default no servidor de partida. Ver D141.
- **Previsão para andar depois do H2.** Não é prevista pelos dados. Com as teclas ligadas, o pawn anda só se `agility` e `strength` dos padrões da classe derem velocidade positiva com o peso da arma. Esses padrões não foram extraídos.

## 13. Respawn em TDM, mouse, animações e fim por tempo (verificação de 2026-10-14)

Fonte: `XGame.u` e `XInterface.u` do cliente, extraídos em UTF-16 e ASCII (o mesmo pacote está no `servidor-partida`, com o mesmo tamanho). As linhas citadas são de um dump de extração feito na sessão, não versionado. Decisões: D170 a D177.

- **Classe de time (D170).** `class LM_TeamGame extends LM_DeathMatch` (UTF-16, linha 6695) não sobrescreve `BecomeSpectator`. Herda `LM_DeathMatch.BecomeSpectator`, que retorna `false` (linha 16028). `class LM_TeamDeathMatch extends LM_TeamGame` (ASCII 0x00235415) sobrescreve `BecomeSpectator` (0x00238782, retorna `true` com a partida começada) e `AllowBecomeActivePlayer` (0x00238A00). Sem `game=` na sala, o `CServerRoom::Init` nativo escolhe `XGame.LM_TeamDeathMatch` para modo 0 com `team_count >= 2` (`re/LM_Engine.dll/all/100163d0_Init.c`, linhas 317 a 339). O emulador manda `game=XGame.LM_TeamGame` (`domain/match.py`).
- **Respawn (D171).** `state Dead` do `LM_xPlayer` (ASCII 0x0018A764, linhas 1083 a 1102 do dump de respawn): `Timer` chama `BecomeSpectator()` se `bTeamGame` e `RespawnCountDown <= RespawnDelay * 0.8`, e esse ramo não decrementa o contador. `LM_xPlayer.BecomeSpectator` (0x001842C4) sai cedo quando `Level.Game.BecomeSpectator` é falso. Resultado: o contador para em 0,8 do prazo. O prazo (`var const int RespawnDelay`) não tem valor no texto; com 10 s, o HUD mostra "8 s". Os estados `BehindCamera` e `Spectating` chamam `BecomeActivePlayer()` quando o contador chega a 1, e o pawn nunca chega lá.
- **Time nulo (não é a causa do 8 s).** `LM_xPawn.TakeDamage` acessa `Team` nulo no log do servidor. `RatePlayerStart` (UTF-16, linha 7788) recusa todo ponto quando `bSpawnInTeamArea` e o time não casa; isso bloquearia o spawn depois do congelamento. O envio de time e de loadout é do outro agente.
- **Mouse (D172).** `OnApply` do slider grava `mousesence` = `fMouseSence` (XInterface UTF-16, linhas 14346 a 14351). O motor recebe `FClamp(v * 0.1 + 0.25, 0.25, 10.25)`. Leitura inversa: `(MouseSensitivity - 0.25) * 10` (linha 14395). `cliente\system\User.ini` tem `MouseSensitivity=0.250000` (linha 461), gravado pelo próprio cliente depois de aplicar 0. `tools\UT2004\Installer\User.ini` tem `MouseSensitivity=1.000000` (linha 345), `bInvertMouse=False` (338) e `bNoMouseSmoothing=True` (344). Mínimo e máximo do slider não foram lidos.
- **Animações (D174).** `PlayAnim: Sequence IdleSmg01Shot not found for mesh Assault01` e `Invalid bone index (-1) for GetBoneRotation` no log do cliente; `Accessed null class context 'Species'` em `xPawn.Setup` e `xPawn.PlayDying: No Species` no servidor. Os `SPECIES_*` não estão nos pacotes do cliente. Taxas de tick não foram alteradas.
- **Fim por tempo (D175).** `RemainingTime = 60 * TimeLimit` (UTF-16, linhas 4300 e 4622). `TimeLimit` da URL vem da sala, em minutos. A partida acabou ~413 s após a entrada dos jogadores, não aos 600 s esperados. Não explicado.
