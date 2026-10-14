# Client Patch do LandMass

Ajustes do cliente para rodar em PC atual: janela sem borda, widescreen, FOV corrigido e texturas na qualidade máxima. Não inclui texturas novas.

## 1. Baixe o dgVoodoo2

O dgVoodoo2 converte o Direct3D 8 do jogo para Direct3D 11. É ele que permite a janela sem borda e evita os erros de vídeo em placas atuais. É um programa de terceiro, gratuito, e não vem neste repositório.

1. Baixe o zip da versão **2.87.5** (ou mais nova) na página oficial de releases: <https://github.com/dege-diosg/dgVoodoo2/releases>. Exemplo de arquivo: `dgVoodoo2_87_5.zip`.
2. Extraia numa pasta, por exemplo `C:\Downloads\dgVoodoo2_87_5`.
3. Confira se existe `MS\x86\D3D8.dll` dentro dela. O LandMass é 32 bits, então use o `x86`, não o `x64`.

Não use o `dgVoodooCpl.exe` do zip para configurar o LandMass. A configuração certa é o `system\dgVoodoo.conf` deste patch.

## 2. Aplique

```
powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\caminho\do\LandMass" -DgVoodoo "C:\Downloads\dgVoodoo2_87_5"
```

| Opção | Efeito |
|---|---|
| `-Cliente` | Pasta do jogo, a que contém `system\`. Obrigatória. |
| `-DgVoodoo` | Pasta extraída do dgVoodoo2. Sem ela, o script usa um `D3D8.dll` copiado para `system\` desta pasta. |
| `-Largura` e `-Altura` | Resolução da partida. Sem elas, usa a do monitor principal, com a escala do Windows. |
| `-IniciarSozinho` | Patch opcional do `XInterface.u`: o dono da sala inicia sem outro jogador pronto, para jogar contra bots. |

Pode rodar de novo quantas vezes quiser. Na primeira vez, os originais ficam salvos como `*.antes-patch`; o `XInterface.u` original fica como `XInterface.u.orig`.

## O que muda

| Arquivo do cliente | Mudança |
|---|---|
| `system\D3D8.dll` | dgVoodoo2. |
| `system\dgVoodoo.conf` | Configuração abaixo. |
| `system\LandMass.ini` | 32 bits, texturas no máximo e resolução widescreen. |
| `system\User.ini` | FOV para a proporção da tela. |
| `system\XInterface.u` | Só com `-IniciarSozinho`. |

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

- `LM_RoomPlayerListPanel.IsReadyToStart` sempre verdadeiro (3 bytes em `0xE70BC`). O botão de iniciar do dono fica ativo sem outro jogador pronto. O servidor ainda recusa o início quando falta alguém pronto e não há bots.

## Remoção

1. Apague `system\D3D8.dll` e `system\dgVoodoo.conf`.
2. Se existirem cópias `*.antes-patch` ou `*.orig`, renomeie-as de volta, tirando o sufixo.

## Observações

- Saia da janela com Alt+Tab ou com a tecla Windows. Evite sair durante o carregamento do mapa.
- O jogo expulsa por inatividade depois de 3 minutos (`GameAfkLimit=3` no `User.ini`). Isso é do jogo original e foi mantido.
- O HUD é desenhado por fração da tela e estica na horizontal em widescreen.
- As opções gráficas do jogo podem regravar o `TextureDetail` e a resolução. Se isso acontecer, rode o `aplicar.ps1` de novo.
