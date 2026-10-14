# Widescreen e menu responsivo (estudo)

Estado: estudo, nada aplicado. Fonte: `XInterface.src.txt` (UnrealScript extraído de `XInterface.u`, scratchpad `src\`).

## 1. Como a UI posiciona

- Posições e tamanhos são **frações da tela** (`WinLeft`, `WinTop`, `WinWidth`, `WinHeight` em 0..1). Ex.: `WinLeft = 0.5 - (WinWidth * 0.5)` centraliza a página (L4925, L5856, L6387).
- Desenho direto no `Canvas` (HUD, alertas, painéis animados) usa `Canvas.ClipX/ClipY` ou `SizeX` vezes uma fração derivada de 800x600. Ex.: `fAltLeft = Canvas.ClipX * 0.7225 // 578 / 800.0` (L2053) e `pt.X += 315 / 800.f * Canvas.SizeX` (L7076).
- Contagem: cerca de 180 atribuições relativas de `Win*`, 636 usos de `ClipX/ClipY`, 77 constantes derivadas de 800/600, 514 chamadas de desenho (`DrawTile`, `SetPos`).
- Não há posições absolutas em pixels nos `Win*` amostrados.

## 2. Consequência

- A UI já acompanha qualquer resolução, mas **escala X e Y de forma independente**. Em 16:9 nada quebra nem desalinha, mas tudo fica esticado na horizontal (≈ 33%).
- Para não esticar, a UI tem de ser desenhada numa área 4:3 centralizada, com o cenário 3D ocupando a tela toda.

## 3. Caminhos

| Caminho | Como | Custo | Risco |
|---|---|---|---|
| A. Letterbox (atual) | dgVoodoo `ScalingMode = stretched_ar`: render 800x600, faixas pretas | nenhum | nenhum; imagem menos nítida |
| B. Área 4:3 no Canvas | Patch único no desenho de menus (`GUIController` / `UCanvas` nativo): deslocar `OrgX` e reduzir `ClipX` para `ClipY*4/3` antes de desenhar a UI | médio (RE em Engine.dll/XInterface) | baixo: a UI só usa frações do Clip, então se ajusta sozinha |
| C. Página a página | Reescrever `Win*` e constantes de 800/600 | alto (centenas de pontos) | alto; exige recompilar `XInterface.u` |
| D. Partida em 16:9 | Resolução 16:9 + FOV corrigido (padrão dos fixes de UT2004) só durante a partida; HUD também é por fração e estica | médio | HUD esticado sem o caminho B |

Recomendação: B, se o RE confirmar um ponto único onde a UI recebe o `Canvas`; ele resolve menus e HUD sem tocar em cada página. D vem junto para a partida.

## 4. Resolução e upscaling

O jogo renderiza em 800x600 (`[WinDrv.WindowsClient] MenuViewportX/Y`, `FullscreenViewportX/Y`). O dgVoodoo amplia para a tela. Opções, da mais simples à mais elaborada:

| Opção | Onde | Efeito | Observação |
|---|---|---|---|
| Resolução interna forçada | `dgVoodoo.conf` `[DirectX] Resolution` (`max_isf`, `2x`, `desktop`, `1600x1200`) | 3D renderizado na resolução real da tela, sem o jogo saber | Principal ganho de nitidez. A UI usa frações e acompanha; texturas 2D da UI continuam na resolução original |
| Antialiasing | `[DirectX] Antialiasing = 4x/8x` | MSAA no 3D | Custo baixo em GPU atual |
| Filtragem anisotrópica | `[DirectX] Filtering` | Texturas nítidas em ângulo | Sem risco |
| Resampling da saída | `[General] Resampling` (`bilinear`, `lanczos-2/3`, `pointsampled`) | Qualidade da ampliação final | `pointsampled` com fator inteiro = pixels nítidos |
| Resolução nativa maior em 4:3 | `LandMass.ini` `FullscreenViewportX/Y` e `MenuViewportX/Y` (ex.: 1600x1200) | O próprio motor renderiza maior | UI por frações deve se ajustar; testar se o cliente força 800x600 nos menus |
| ReShade | por cima da saída D3D11 do dgVoodoo | SMAA, CAS (nitidez), cor | Pós-processo; não aumenta detalhe real |
| Magpie (código aberto) ou Lossless Scaling | upscaler de janela externo | FSR 1 / Anime4K / geração de quadro | Funciona em janela; latência extra; Lossless Scaling é pago |
| DLSS, FSR 2/3, XeSS | — | Inviável | Exigem vetores de movimento e integração no motor |

Recomendação para testar: `Resolution = max_isf` + `Antialiasing = 4x` + `Filtering` anisotrópico no dgVoodoo, mantendo `ScalingMode = stretched_ar`. Se a UI ficar borrada, testar resolução nativa maior no `LandMass.ini`.

## 5. Abertos

- Ponto exato onde `GUIController` recebe o `Canvas` (nativo em `Engine.dll`/`XInterface`) e se o clique do mouse usa o mesmo `OrgX` (coordenadas de entrada também precisam do deslocamento).
- Projetos de referência para UT2004: Widescreen Fixes Pack e "UT2004 widescreen fix" (FOV e resoluções); PCGamingWiki, página Unreal Tournament 2004.
