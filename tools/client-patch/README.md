# Client Patch do LandMass

Ajustes do cliente: endereço do servidor, memória de 4 GB, botão de iniciar sozinho contra bots e vídeo para PC atual (janela sem borda, widescreen, FOV corrigido e texturas na qualidade máxima). Cada parte é opcional. Não inclui texturas novas.

Armas, equipamento e bots não mudam nada no cliente: vêm do servidor.

## Jeito fácil

Dois cliques em `configurar.bat`. Ele pergunta, uma por vez:

1. A pasta do jogo.
2. O IP do servidor (IP ou IP:porta), que vai para `system\jogar.bat`.
3. Se liga os 4 GB de memória.
4. Se libera o botão de iniciar sozinho.
5. Se configura o vídeo, e nesse caso a pasta do dgVoodoo2.

Depois chama o `aplicar.ps1` com as respostas. Para jogar, abra `system\jogar.bat` e entre com usuário e senha na tela do jogo.

## 1. Baixe o dgVoodoo2 (só para o vídeo)

O dgVoodoo2 converte o Direct3D 8 do jogo para Direct3D 11. É ele que permite a janela sem borda e evita os erros de vídeo em placas atuais. É um programa de terceiro, gratuito, e não vem neste repositório.

1. Baixe o zip da versão **2.87.5** (ou mais nova) na página oficial de releases: <https://github.com/dege-diosg/dgVoodoo2/releases>. Exemplo de arquivo: `dgVoodoo2_87_5.zip`.
2. Extraia numa pasta, por exemplo `C:\Downloads\dgVoodoo2_87_5`.
3. Confira se existe `MS\x86\D3D8.dll` dentro dela. O LandMass é 32 bits, então use o `x86`, não o `x64`.

Não use o `dgVoodooCpl.exe` do zip para configurar o LandMass. A configuração certa é o `system\dgVoodoo.conf` deste patch.

## 2. Aplique pela linha de comando

```
powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\caminho\do\LandMass" -Servidor 203.0.113.10 -Memoria4GB -DgVoodoo "C:\Downloads\dgVoodoo2_87_5"
```

| Opção | Efeito |
|---|---|
| `-Cliente` | Pasta do jogo, a que contém `system\`. Obrigatória. |
| `-Servidor` | IP ou IP:porta do servidor (porta padrão 7313). Grava `system\jogar.bat`, que abre a tela de usuário e senha, e troca o `login_server` dos `jogar_*.bat` que já existem. |
| `-Memoria4GB` | Liga `LARGE_ADDRESS_AWARE` no `LandMass.exe`: até 4 GB de memória em Windows 64 bits, em vez de 2 GB. |
| `-IniciarSozinho` | Patch do `XInterface.u`: o dono da sala inicia sem outro jogador pronto, para jogar contra bots. |
| `-DgVoodoo` | Pasta extraída do dgVoodoo2 (ou uma pasta que já tem o `D3D8.dll`). Liga a parte de vídeo; sem ela, o vídeo não muda. |
| `-Largura` e `-Altura` | Resolução da partida, com `-DgVoodoo`. Sem elas, usa a do monitor principal, com a escala do Windows. |

Pode rodar de novo quantas vezes quiser. Na primeira vez, os originais ficam salvos como `*.antes-patch` (configuração) e `*.orig` (`LandMass.exe` e `XInterface.u`).

## O que muda

| Arquivo do cliente | Mudança |
|---|---|
| `system\jogar.bat` | Só com `-Servidor`. |
| `system\LandMass.exe` | Só com `-Memoria4GB`: 1 bit no cabeçalho. |
| `system\XInterface.u` | Só com `-IniciarSozinho`. |
| `system\D3D8.dll` | dgVoodoo2, com `-DgVoodoo`. |
| `system\dgVoodoo.conf` | Configuração abaixo, com `-DgVoodoo`. |
| `system\LandMass.ini` | 32 bits, texturas no máximo e resolução widescreen, com `-DgVoodoo`. |
| `system\User.ini` | FOV para a proporção da tela, com `-DgVoodoo`. |

### `dgVoodoo.conf`

- Janela sem borda do tamanho da tela (`WindowedAttributes = borderless, fullscreensize`) e proporção do jogo mantida (`ScalingMode = stretched_ar`).
- Sem marca d'água. Alt+Enter alterna para tela cheia.
- `VRAM = 1024`. Com 256, o jogo dava "General protection fault" em `UD3DRenderDevice::Present` ao sair da janela durante o carregamento.
- Resolução `max_qhd` e antialiasing 2x.
- `ExtraEnumeratedResolutions`: a resolução da tela e a 4:3 da mesma altura, gravadas pelo `aplicar.ps1`.

### `LandMass.ini`

- `Use16bit=False` e `Use16bitTextures=False`. Placas atuais não têm modo 16 bits, e o jogo fecha com "No acceptable display modes found".
- `TextureDetail*=UltraHigh`. Com `Normal`, o motor carrega as texturas reduzidas.
- `FullscreenViewportX/Y` na resolução da tela (partida) e `MenuViewportX/Y` em 4:3 da mesma altura.

### `User.ini`

- `DesiredFOV`, `DefaultFOV` e `FOVAngle` com a mesma visão vertical do FOV 90 em 4:3 (Hor+). Em 21:9, fica perto de 122.

### `XInterface.u` (opcional)

- `LM_RoomPlayerListPanel.IsReadyToStart` sempre verdadeiro (3 bytes em `0xE70BC`). O botão de iniciar do dono fica ativo sem outro jogador pronto. O servidor recusa o início sozinho quando os bots estão desligados nele, então o patch sozinho não abre partida vazia.

## Remoção

1. Apague `system\D3D8.dll`, `system\dgVoodoo.conf` e `system\jogar.bat`.
2. Se existirem cópias `*.antes-patch` ou `*.orig`, renomeie-as de volta, tirando o sufixo.

## Observações

- Saia da janela com Alt+Tab ou com a tecla Windows. Evite sair durante o carregamento do mapa.
- O jogo expulsa por inatividade depois de 3 minutos (`GameAfkLimit=3` no `User.ini`). Isso é do jogo original e foi mantido.
- O HUD é desenhado por fração da tela e estica na horizontal em widescreen.
- As opções gráficas do jogo podem regravar o `TextureDetail` e a resolução. Se isso acontecer, rode o `aplicar.ps1` de novo.
