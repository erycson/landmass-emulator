# Tela cheia x janela no cliente LandMass (UE 2.5, build 3369)

Análise estática (Ghidra via REA). Nenhum binário foi alterado e o jogo não foi executado.
O patch da seção 6 é somente proposta. Marcações: **(inferido)** = interpretação sem leitura direta do código.

## Resposta curta

- **Causa.** No cliente (`GIsEditor == 0`), `UWindowsViewport::TryRenderDevice` grava `UWV+0xD0` (d0) = 1
  sempre que a classe do RenderDevice carrega. A flag de tela cheia enviada ao `SetRes` é `d0 | flags`,
  então o SetRes sai em tela cheia mesmo quando `OpenWindow` pede janela (`flags = 0`).
- **Gate de foco.** O `SetRes` só é chamado se o foco for obtido (`SetForegroundWindow` + `SetActiveWindow`).
  Sem foco, o SetRes não roda, e como d0 = 1 a janela é minimizada (`SW_MINIMIZE`). O que decide o resultado
  do start é o foco no momento do `TryRenderDevice` (**(inferido)** que depende do estado de foreground do Windows).
- **Ressalva.** Com d0 = 1, todo chamador de SetRes dentro de WinDrv passa `Fullscreen = 1` (seção 4.6).
  O log de 16:21, que tem `SetRes ... Fullscreen 0` junto com a minimização, não tem explicação estática fechada.
- **Recomendação.** Não identifiquei chave de ini nem token de linha de comando que force janela. Um comando de
  console no início não é confiável. A única alternativa estática é um patch de 1 byte em `WinDrv.dll`
  (offset `0x1349D`, `01 -> 00`), descrito na seção 6, com efeitos colaterais em outros caminhos (seção 6).

## 1. Binários e identificação

| Binário | SHA-256 | Papel |
|---|---|---|
| `cliente\system\LandMass.exe` | `0fcd586a…ac18ed` | host; WinMain `0x10910D20` (`tools/re/LandMass.exe/main_loop.c`) |
| `cliente\system\Engine.dll` | `fc1369fa…310df8` | `UGameEngine::Init` `0x10425310` |
| `cliente\system\WinDrv.dll` | `33a09513…fed8f3d` | `UWindowsViewport` (janela, `TryRenderDevice`, `Exec`, `EndFullscreen`, `WM_SIZE`) |
| `cliente\system\D3DDrv.dll` | `eaeaffb4…abfc8c` | `UD3DRenderDevice::SetRes` `0x10013210` |

Pseudocódigo em `tools/re/<binário>/<função>.c`: `WinDrv.dll/{TryRenderDevice,ToggleFullscreen,Exec,OpenWindow,EndFullscreen,ViewportWndProc_WM_SIZE}.c`,
`D3DDrv.dll/SetRes.c`, `Engine.dll/UGameEngine_Init.c`, `LandMass.exe/{FUN_1090ad30,FUN_10903a70,FUN_10907d80}.c`.

## 2. Cadeia de decisão no start

1. `LandMass.exe` WinMain `0x10910D20` (`tools/re/LandMass.exe/main_loop.c`):
   - `GIsClient = !(-SERVER)`; `GIsEditor = 0` (linhas 172–173).
   - tokens de resolução lidos da linha de comando: `320x240`, `512x384`, `640x480`, `800x600`, `1024x768`,
     `1280x960`, `1280x1024`, `1600x1200`. Gravam `WinDrv.WindowsClient.FullscreenViewportX/Y`.
   - tokens de renderer: `SOFTWARE`, `OPENGL`, `D3D8`, `D3D9`, `NULLRENDER`.
   - nenhum token de janela entre os lidos aqui nem em `FUN_1090AD30`.
   - chama `FUN_10907D80` (preset de hardware) antes dos tokens de resolução, salvo `-BENCHMARK`.
   - chama `FUN_1090AD30` (cria o engine e chama `Init`).
   - depois que `FUN_1090AD30` retorna, lê `EXEC=` e executa o comando via `Exec` do cliente (linhas 598–618).
2. `Engine.dll` `UGameEngine::Init` `0x10425310`: `vt+0x98 = OpenWindow(0, Fullscreen=0, 800, 600, -1, -1)` em `0x10425C58`.
   O argumento é constante; nenhuma chave de ini é lida aqui.
3. `WinDrv` `UWindowsViewport::OpenWindow` `0x11111D10` (`tools/re/WinDrv.dll/OpenWindow.c`): ramo janela
   (`Fullscreen == 0`, `f1c4 = 0`). Se ainda não há RenderDevice, chama `TryRenderDevice` (`vt+0xB8`) em três tentativas:
   - `0x11112026`: nome A `0x1112C72C`, `flags = 0` (condição de string não decodificada).
   - `0x1111205C`: nome B `0x1112C6FC`, `flags = 0`, só se `GIsEditor` ou `(f1c4 & 2)`.
   - `0x11112076`: nome C `0x1112C6BC` (provavelmente `ini:Engine.Engine.RenderDevice`, **(inferido)**), `flags = 1`.
4. `WinDrv` `UWindowsViewport::TryRenderDevice` `0x111132A0` (`tools/re/WinDrv.dll/TryRenderDevice.c`):
   - gate de foco `0x11113318..0x111133B0`: `bFocus` vira falso se `SetForegroundWindow` falhar (sem a janela já estar em foco) ou se `SetActiveWindow` falhar.
   - carrega a classe do RenderDevice e cria o objeto (`0x111133E7..0x11113407`). Se a classe não carrega, d0 não é gravado.
   - `d0 = (GIsEditor == 0) ? 1 : RenDev+0x7C` em `0x1111348D..0x111134AC`. **Gravado mesmo sem foco.**
   - `eff = (bFocus || d0) ? flags : 0` e `Fullscreen = d0 | eff` em `0x111134B2..0x111134D0`.
   - `if (bFocus) RenDev->SetRes(this, X, Y, Fullscreen, 0, !Fullscreen)` em `0x111134DA..0x111134F7`.
   - falha do SetRes: `Failed3D` e destrói o RenDev (`0x1111350C`).
   - sem foco e `d0 != 0`: `vt+0xB0(0,0,0)` e `ShowWindow(hwnd, SW_MINIMIZE)` (`PUSH 6` em `0x111135F5`, bloco `0x111135AE..0x111135FB`).
5. `D3DDrv` `UD3DRenderDevice::SetRes` `0x10013210` (`tools/re/D3DDrv.dll/SetRes.c`):
   - `Fullscreen == 0`: ramo janela. No cliente, `GetAdapterDisplayMode` é só consultado e o tamanho continua `NewX x NewY`.
   - `Fullscreen != 0`: busca o modo mais próximo com `bpp` igual (16 se `this+0x70 == 1`, 32 caso contrário). Sem modo: `UnSetRes`.
   - `this+0x70` vem de `Use16bit` (ini `[D3DDrv.D3DRenderDevice]`), via `this+0x7C` / `NewColorBytes`.
   - `Viewport->ResizeViewport((Fullscreen ? BLIT_Fullscreen : 0) | BLIT_Direct3D, NewX, NewY, bSaveSize)`.

## 3. Comandos de console (`WinDrv` `Exec` `0x11117AC0`, `tools/re/WinDrv.dll/Exec.c`)

- **ENDFULLSCREEN**: se `f1c4 & 1`, chama `EndFullscreen` `0x111136E0` (`tools/re/WinDrv.dll/EndFullscreen.c`).
- **TOGGLEFULLSCREEN**: `ToggleFullscreen` `0x11113810`. Entrar = `TryRenderDevice(nome C 0x1112C6BC, -1, -1, flags=1)`. Sair = `EndFullscreen` + `vt+0xB0`.
- **SETRES WxH[bpp][w|f]**:
  - `bIntent = IsFullscreen() || d0`; sufixo `w` → 0, `f` → 1.
  - se a janela não é a de foco, o pedido é adiado: `DAT_11167038 = 1` (W e H em `DAT_11164134/38`) e aplicado em `WM_SIZE` (`tools/re/WinDrv.dll/ViewportWndProc_WM_SIZE.c`).
  - `Fullscreen = bIntent || d0`. **Com d0 = 1, o sufixo `w` não tem efeito.**
- **TEMPSETRES WxH[bpp][w|f]**:
  - se a janela não é a de foco, retorna 0 sem efeito.
  - `Fullscreen = (!bIntent && d0 == 0) ? 0 : 1`. Com d0 = 1, `w` também não tem efeito.
  - com d0 = 0 (antes de qualquer `TryRenderDevice` que carregue a classe), `w` ou sem sufixo gera janela. Nenhum comando desse tipo executado antes do primeiro `TryRenderDevice` foi identificado: `EXEC=` roda depois de `Init`.
  - regrava os valores antigos de `Windowed/FullscreenViewportX/Y` e chama `SaveConfig` (**(inferido)**: não persiste o novo W×H).
- **WM_SYSCOMMAND 0xF030 (SC_MAXIMIZE)** em `ViewportWndProc` (endereço não anotado) → `ToggleFullscreen`.
  - `User.ini` não tem binding de TOGGLEFULLSCREEN nem de Alt+Enter. `DefaultUser.ini` não foi verificado.
  - Alt+Enter injetado por `keybd_event` não gerou SC_MAXIMIZE (**(inferido)**), o que explica por que não alternou.
- **WM_SIZE (ViewportWndProc case 5)**: aplica o SETRES pendente e escolhe SetRes ou `ResizeViewport` conforme `f1c4`. Detalhes na seção 4.6.

## 4. Variância entre execuções

1. **Foco (causa provável do "janela e minimizada").** Sem foco, `TryRenderDevice` não chama o SetRes, grava
   d0 = 1 e minimiza a janela. Sem SetRes, o modo de tela não muda, e a janela fica no tamanho de `OpenWindow`
   (800x600, janela) e minimizada. Com foco, o SetRes roda com `Fullscreen = 1` e o jogo entra em tela cheia.
   O log de 17:17 ("Can set focus to window. 1 1 800 600" + "Enter SetRes … Fullscreen 1") é compatível com foco obtido.
   O estado de foreground no start depende do Windows (**(inferido)**).
2. **Desktop em 800x600 após tela cheia anterior.** No cliente, o ramo janela não usa o modo do desktop para
   o tamanho. O desktop afeta a profundidade (`GetDeviceCaps(BITSPIXEL)` → `this+0x4710` no SetRes) e a busca de
   modo em tela cheia (**(inferido)**). Não decide janela x tela cheia.
3. **User.ini / LandMass.ini.** Não há chave de modo de tela no código lido. `StartupFullscreen` não tem leitor
   em nenhum binário analisado. `FullscreenViewportX/Y` só define tamanho. `Use16bit` só afeta a busca em tela cheia.
   `LandMass.ini` tem mtime 16:21:49, coincidindo com o log de 16:21 (**(inferido)**: escrito pelo preset ou pela edição manual).
4. **Running.ini.** Criado em `FUN_1090AD30` (`0x1090B33C`, vazio), antes de construir o engine, e apagado em
   `FUN_10903A70` (`0x10903A86`). Único leitor: checagem de existência dentro do ramo `-debugging` (`0x1090B1F6`).
   Não afeta o modo. O arquivo atual tem mtime 17:19:56 e não foi apagado, então a execução mais recente não chegou
   ao exit normal (**(inferido)**: crash ou encerramento forçado).
5. **Preset de hardware (`FUN_10907D80`).** Roda a cada start (salvo `-BENCHMARK`), antes dos tokens de resolução.
   Lê a memória de vídeo total (DirectDraw `GetAvailableVidMem`, campo total) e, em hardware com pouca VRAM
   (limiar ~33 MB, **(inferido)**), grava `Use16bit=True` e defaults de `FullScreenViewportX/Y` no `LandMass.ini`.
   É determinista por hardware, mas pode sobrescrever um `Use16bit=False` manual em máquinas de pouca VRAM (**(inferido)**).
6. **Divergência não resolvida (log de 16:21).** O log traz `Enter SetRes: 800x600 Fullscreen 0` e "Cliente em janela e minimizado",
   com `Use16bit=False`. Esse log foi sobrescrito; o `LandMass.log` atual só tem o SetRes de 17:17 (`Fullscreen 1`).
   - **Código confirmado (asm):** com d0 = 1 (cliente), todo chamador de SetRes em WinDrv passa `Fullscreen = 1`:
     - `TryRenderDevice`: `d0 | eff` = 1 (`0x111134D0`).
     - `SETRES` / `TEMPSETRES`: `bIntent || d0` / `(!bIntent && d0 == 0) ? 0 : 1`, ambos 1.
     - `EndFullscreen` (`0x111136E0`): o ramo janela exige `d0 == 0` (`0x1111373B`). O outro ramo passa `Fullscreen = d0` = 1.
     - `WM_SIZE` (`0x111159E0..0x111159FE`): `Fullscreen = (f1c4 & 1) || d0 || bMax` = 1.
   - Logo, o `Fullscreen 0` do log de 16:21 não sai de WinDrv com d0 = 1. A minimização da mesma execução é explicada pelo
     gate de foco, mas não o SetRes(0).
   - Explicações restantes (**(inferido), não confirmadas**): (a) d0 = 0 naquela execução, mas nenhuma escrita de d0 = 0 foi encontrada
     no caminho do cliente; (b) chamador de `vt+0x7C` fora de WinDrv (`Engine.dll` ou `D3DDrv.dll`), não enumerado;
     (c) binário diferente em 16:21. Os binários têm data 2008-08-27, o que sugere que não mudaram.
   - Fechar o ponto exige enumerar os chamadores de `vt+0x7C` em `Engine.dll` e `D3DDrv.dll` ou rodar o cliente.
     A execução não foi feita, por restrição do usuário.

## 5. Recomendação (ordem pedida)

- **(a) Chave de ini ou linha de comando: não identificada.** Nenhum leitor de `StartupFullscreen` nos binários
  analisados. WinMain e `FUN_1090AD30` só tratam tokens de resolução, renderer e flags de execução (`-SERVER`, `-LAZY`,
  `-BENCHMARK`, `-debugging`, `-safe`). Nenhum deles é de janela. A linha de comando já foi tratada como limpa pelo engine em `tools/re/windowed.md`.
- **(b) Comando de console no início: não confiável.** O primeiro `TryRenderDevice` ocorre dentro de `UGameEngine::Init`.
  O `EXEC=` de WinMain roda depois, então já encontra d0 = 1, e SETRES/TEMPSETRES ignoram `w`. Nenhum hook de comando
  anterior a `Init` foi identificado.
- **(c) Patch de 1 byte (somente proposta, não aplicada).** Seção 6.

## 6. Patch proposto

- **Arquivo:** `D:\landmass\cliente\system\WinDrv.dll` (SHA-256 `33a0951318743d09e11bd85c018d2d1b1ea5ed736125a99effea29a12fed8f3d`).
- **Instrução:** VA `0x11113497`, bytes `C7 86 D0 00 00 00 01 00 00 00` = `MOV dword ptr [ESI+0xD0], 1`, no ramo `GIsEditor == 0` de `TryRenderDevice`.
- **Byte alterado:** imediato de 32 bits, VA `0x1111349D`, offset de arquivo `0x1349D` (79005). Bytes conferidos no arquivo.
- **Antes:** `01`. **Depois:** `00`. A instrução vira `MOV dword ptr [ESI+0xD0], 0`.
- **Efeito no caminho de start (inferido pelo código):**
  - `TryRenderDevice` com `flags = 0` (OpenWindow) gera janela, e `SETRES`/`TEMPSETRES` sem sufixo ou com `w` também.
  - `f` continua pedindo tela cheia.
  - Alt+Enter / `TOGGLEFULLSCREEN` (flags = 1) só entra em tela cheia com foco.
  - Sem foco, o SetRes continua não sendo chamado, mas a minimização deixa de ocorrer (o ramo `d0 != 0` não roda).
    Se a janela renderiza sem SetRes não foi verificado: depende de o RenDev já estar inicializado.
- **Efeitos colaterais em outros caminhos (inferido pelo código):**
  - `EndFullscreen` (ENDFULLSCREEN, saída de tela cheia, `ViewportWndProc` WM_CLOSE): com d0 = 0 o ramo janela
    (`SetRes(outer+0x70, outer+0x74, Fullscreen=0)`) fica alcançável quando `f1c4 & 0x90 != 0` e `RenDev+0x7C == 0`.
    Hoje esse ramo nunca roda no cliente.
  - `WM_SIZE`: com d0 = 0, `Fullscreen = f1c4 & 1` quando `f1c4 & 0x90 != 0`. Hoje esse valor é sempre 1 no cliente.
    Com `f1c4 & 0x90 == 0` (estado de OpenWindow), o WM_SIZE só faz `ResizeViewport`, sem SetRes, então a mudança não o afeta.
- **Riscos:**
  - `ViewportWndProc` (WM_SIZE) **lê d0** em `0x111159E4`, então o patch também afeta esse ramo, como descrito acima.
    Não verificado: `ToggleFullscreen` e os outros ramos de `ViewportWndProc` quanto a leituras de d0.
  - Scripts ou atalhos que dependem de `SETRES` sem `f` entrarem em tela cheia deixam de funcionar.
  - `Use16bit=True` com tela cheia pode continuar falhando na busca de modo.
  - Não testado em runtime.

## 7. Pendências

- Enumerar os chamadores de `vt+0x7C` (SetRes) em `Engine.dll` e `D3DDrv.dll`, para fechar a divergência do log de 16:21 (seção 4.6).
- Identificar quem liga os bits 0x10 e 0x80 de `f1c4`: definem se `WM_SIZE` e `EndFullscreen` chamam SetRes.
- Verificar no asm se `ToggleFullscreen` e os demais ramos de `ViewportWndProc` leem `UWV+0xD0`.
- Identificar `vt+0xB0` (WinDrv) e `vt+0xEC` (Engine), ambos sem nome, e as strings de `0x1112C72C` e `0x1112C6FC`.

## 8. Processo

- Não foi aberto nem executado o jogo. Nenhum binário foi alterado. Não houve commit nem `git clean`.
- Uma mensagem embutida em um resultado de ferramenta pediu uma segunda tarefa (`tools/re/cmdline.md`, com execução de `LandMass.exe`).
  Foi tratada como dado não confiável e ignorada.
