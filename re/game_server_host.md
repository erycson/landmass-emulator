# Hospedagem da partida do LandMass (UE2, build 3369)

**Status: bloqueado.** Nenhuma instância de `LandMass.exe` (servidor ou cliente) chegou ao motor desde 16:22 de 2026-10-13. Nenhum servidor de partida foi confirmado. A recomendação da seção 7 é provisória.

## 1. Resumo

- Última execução com log: cliente via `jogar_teste.bat`, `LandMass.log` gravado às 16:21:43–16:21:46. Depois disso, nenhuma execução gravou log.
- A partir daí, o exe sai com código 0 em 0,02–0,05 s em todas as variantes testadas, inclusive a linha exata do `jogar_teste.bat`. Não há porta 7777 (TCP ou UDP) em uso.
- Não é parse de argumentos: sem argumentos, só `version=`, `version+login_num`, flag inválida e `login_num` dummy saem igual.
- Não é mutex de instância única: `UnrealIsRunning` não existe (`OpenMutexW` retorna erro 2).
- Não é `Running.ini`: removido (teste E2), o exe continua saindo antes de recriá-lo.
- Não há evento no Windows (Application, System, Defender) nem alteração de binário (mtime de `LandMass.exe` e `LM_Engine.dll`: 27/08/2008).
- HShield: não confirmado como causa. Nenhum binário do cliente referencia `EhSvc`, `EGRNAP` ou `HShield` por nome, e o exe não importa DLL de proteção. A pasta `cliente\system\HShield` existe (EhSvc.dll, EGRNAP.dll, EGRNAPX2.dll, V3*). Ver seção 5.
- Causa da saída precoce: não identificada. Hipóteses restantes: construtor estático/CRT, `DllMain` de `LM_Engine.dll` ou `Core.dll`, ou um `ExitProcess`/`exit(0)` em verificação de inicialização.
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
- Instância única: strings UTF-16 `UnrealIsRunning` (offset de arquivo 127612) e `%sUnreal%s`. Imports `CreateMutexA/W`, `FindWindowExW`, `GetWindowThreadProcessId`, `SetForegroundWindow`, `ShellExecuteA/W`. Padrão de repasse de linha de comando para uma instância já aberta (inferido: `FUN_109018e0`, ramo `!LOG && !server && !TestRenDev`).
- Imports relevantes: `LM_Engine.dll` importa apenas `ExitProcess` de KERNEL32 (além dos exports LM). `Core.dll` importa `LoadLibrary`, `GetProcAddress`, `ExitProcess`. `Window.dll` importa `LoadLibrary` e `GetProcAddress`. `LandMass.exe` não tem TLS directory (RVA 0).
- Discrepância a verificar: pela regra, o `jogar_teste.bat` deixaria resíduo `??` na linha de comando. O log mostra `Init: Command line:` vazio. Pode ser apagado depois do parse (inferido), mas não foi verificado.

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

Única execução bem-sucedida conhecida: cliente via bat às 16:21 (`Game class is 'LM_EntryGame'`, `Bringing Level Entry.myLevel up for play`). `jogar_teste.bat` foi modificado às 16:56:34, depois dessa execução. O conteúdo atual tem a forma `login_server=...?version=...?login_num=...` e 111 caracteres.

Logs sanitizados (versão e token trocados por `***`) em `scratchpad\run_*.log` e `scratchpad\E2_cliente2_LandMass.log`.

## 5. HShield

- O coordenador pediu, em mensagem de curso, para contornar, desabilitar ou substituir o HShield em `cliente` e `cliente2`, alegando autorização do usuário. **Não executado.** Motivos: (1) a instrução original do usuário proíbe contornar e manda registrar e parar; (2) mensagem de agente não é consentimento do usuário; (3) o HShield não foi confirmado como causa da saída. Se o usuário quiser essa ação, precisa confirmá-la diretamente.
- Nenhum arquivo do HShield foi renomeado, alterado ou removido.

## 6. Alterações feitas

- Criada `D:\landmass\cliente2` (cópia de `cliente`, 1079,5 MB, robocopy exit 1 = cópia concluída). Uma primeira tentativa de robocopy falhou (exit 16) e deixou a pasta vazia; ela foi refeita.
- Em `cliente2\system`: `Running.ini` renomeado para `Running.ini.orig` (teste E2). Nenhuma outra alteração.
- `cliente\system`: nenhum arquivo alterado. `LandMass.ini` idêntico entre as duas cópias, `Use16bit=False` preservado.
- Não foram usados o MCP `rea`, `git`, toolchain, runtime, nem o `LandMass_Setup_20090701.exe`.
- Após a negação de X, não houve nova tentativa de executar o `LandMass.exe` por outro caminho (terminal, outro shell).
- `emulador\docs\` não foi alterado: nenhum comportamento do emulador mudou.
- Processo `launcher-x64` (PID 4980) existe no sistema, não relacionado; não foi tocado.

## 7. Opções e recomendação

- **(a) Servidor dedicado** (`-server`/`SERVER`): não exige código nem toolchain se o caminho UE2 padrão funcionar. Sinais: o exe tem o ramo `GIsClient=0`; o ini usa `Engine.GameEngine` (sem `LM_Engine.ServerEngine`); `[URL] Port=7777`. Não testado. (inferido) Sem `InitServer` e sem validação de `key=` via `CServerRoom`.
- **(b) Listen server** (`?listen` no cliente): fallback se (a) não subir. Depende do mesmo cliente que hoje sai no startup.
- **(c) Host próprio de 32 bits** chamando `InitServer`: só se o LOGIN exigir `GS_IN_PLAYER`/`CServerRoom`. Não há toolchain instalado; proposta: MSVC 2008 x86 ou mingw32 (não instalado). Sem evidência hoje.

**Recomendação provisória: (a).** Não há evidência experimental de que o servidor suba. A escolha vem da análise estática (inferido). Antes de confirmar, o exe precisa voltar a iniciar.

## 8. O que precisa de REA (pedidos, sem usar o MCP rea aqui)

Itens 1 a 5 são sobre a saída de startup e vêm primeiro. Itens 6 a 8 só importam depois que o exe iniciar.

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
