# Client Patch do LandMass

Ajustes do cliente para rodar em PC atual. Não inclui texturas novas.

## Conteúdo

| Arquivo | Para quê |
|---|---|
| `system\D3D8.dll` | dgVoodoo2 2.87.5. Converte o Direct3D 8 do jogo para D3D11 e permite janela sem borda. |
| `system\dgVoodoo.conf` | Configuração do dgVoodoo usada no LandMass. |
| `aplicar.ps1` | Copia os dois arquivos para `system\`, ajusta `LandMass.ini`, `User.ini` e `dgVoodoo.conf` para a tela e faz o patch do `XInterface.u`. |

### Ajustes do `dgVoodoo.conf`

- Janela sem borda do tamanho da tela (`WindowedAttributes = borderless, fullscreensize`) com proporção 4:3 e faixas pretas (`ScalingMode = stretched_ar`).
- Sem marca d'água.
- Alt+Enter alterna para tela cheia.
- `VRAM = 1024`. Com 256, o jogo dava "General protection fault" em `UD3DRenderDevice::Present` ao sair da janela durante o carregamento.
- Resolução `max_qhd` e antialiasing 2x.
- `ExtraEnumeratedResolutions`: a resolução da tela e a 4:3 da mesma altura, gravadas pelo `aplicar.ps1`.

### Ajustes do `LandMass.ini`

- `Use16bit=False` e `Use16bitTextures=False`. Placas atuais não têm modo 16 bits, e o jogo fecha com "No acceptable display modes found".
- `TextureDetail*=UltraHigh`. Com `Normal`, o motor carrega as texturas reduzidas.
- Widescreen: `FullscreenViewportX/Y` na resolução da tela (partida) e `MenuViewportX/Y` em 4:3 da mesma altura. A tela vem do monitor principal; outra com `-Largura` e `-Altura`.

### Ajustes do `User.ini`

- `DesiredFOV`, `DefaultFOV` e `FOVAngle` com a mesma visão vertical do FOV 90 em 4:3 (Hor+). Em 21:9, cerca de 122.

### Patch do `XInterface.u`

- `LM_RoomPlayerListPanel.IsReadyToStart` sempre verdadeiro (3 bytes em `0xE70BC`): o botão de iniciar do dono fica ativo sem outro jogador pronto, para jogar sozinho contra bots. O servidor ainda recusa o início quando falta alguém pronto e não há bots. Original em `XInterface.u.orig`.

## Instalação

```
powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\caminho\do\LandMass"
```

Na primeira aplicação, os originais ficam salvos como `*.antes-patch`.

## Remoção

1. Apague `system\D3D8.dll` e `system\dgVoodoo.conf`.
2. Se existirem cópias `*.antes-patch` ou `*.orig`, renomeie-as de volta, tirando o sufixo.

## Observações

- Saia da janela com Alt+Tab ou com a tecla Windows. Evite sair durante o carregamento do mapa.
- O jogo expulsa por inatividade depois de 3 minutos (`GameAfkLimit=3` no `User.ini`). Isso é do jogo original e foi mantido.
- O HUD é desenhado por fração da tela e estica na horizontal em widescreen.
- As opções gráficas do jogo podem regravar o `TextureDetail` e a resolução. Se isso acontecer, rode o `aplicar.ps1` de novo.
