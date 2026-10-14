# Client Patch do LandMass

Ajustes do cliente para rodar em PC atual. Não inclui texturas novas.

## Conteúdo

| Arquivo | Para quê |
|---|---|
| `system\D3D8.dll` | dgVoodoo2 2.87.5. Converte o Direct3D 8 do jogo para D3D11 e permite janela sem borda. |
| `system\dgVoodoo.conf` | Configuração do dgVoodoo usada no LandMass. |
| `aplicar.ps1` | Copia os dois arquivos para `system\` e ajusta o `LandMass.ini`. |

### Ajustes do `dgVoodoo.conf`

- Janela sem borda do tamanho da tela (`WindowedAttributes = borderless, fullscreensize`) com proporção 4:3 e faixas pretas (`ScalingMode = stretched_ar`).
- Sem marca d'água.
- Alt+Enter alterna para tela cheia.
- `VRAM = 1024`. Com 256, o jogo dava "General protection fault" em `UD3DRenderDevice::Present` ao sair da janela durante o carregamento.
- Resolução `max_qhd` e antialiasing 2x.

### Ajustes do `LandMass.ini`

- `Use16bit=False` e `Use16bitTextures=False`. Placas atuais não têm modo 16 bits, e o jogo fecha com "No acceptable display modes found".
- `TextureDetail*=UltraHigh`. Com `Normal`, o motor carrega as texturas reduzidas.

## Instalação

```
powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\caminho\do\LandMass"
```

Na primeira aplicação, os originais ficam salvos como `*.antes-patch`.

## Remoção

1. Apague `system\D3D8.dll` e `system\dgVoodoo.conf`.
2. Se existirem cópias `*.antes-patch`, renomeie-as de volta, tirando o sufixo.

## Observações

- Saia da janela com Alt+Tab ou com a tecla Windows. Evite sair durante o carregamento do mapa.
- O jogo expulsa por inatividade depois de 3 minutos (`GameAfkLimit=3` no `User.ini`). Isso é do jogo original e foi mantido.
- As opções gráficas do jogo podem regravar o `TextureDetail`. Se isso acontecer, rode o `aplicar.ps1` de novo.
