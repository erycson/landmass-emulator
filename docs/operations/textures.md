# Troca de textura nos pacotes do cliente

Substitui uma textura de um pacote `.lm` (por exemplo, a pele de um morat) por outra de resolução maior. O pacote mantém malhas, animações e GUID.

## Ferramentas

- umodel: `D:\landmass\tools\umodel\umodel.exe`, para exportar e conferir.
- UCC do LandMass corrigido, no ambiente `D:\landmass\build` (ver [game-server.md](game-server.md), `build_lmemu.py`).
- `tools/unreal/transplant_texture.py`, para gravar a textura no pacote do jogo.

## Limites

- **Formato:** peles de morat são DXT5 com mipmaps. O alfa é a máscara do env map, usada pelo `Combiner`. Uma imagem gerada por IA chega sem alfa, e é preciso reaplicar o alfa original ampliado.
- **Tamanho:** use até 2048×2048. 4096 carrega em alguns casos, mas consome a memória de um processo de 32 bits: são cerca de 22 MB em DXT5 por textura, com cópia na RAM e no vídeo.
- **Desenho:** a imagem nova precisa manter o layout UV da original. Confira reduzindo a nova ao tamanho da original e misturando as duas: não pode haver contorno duplicado.

## Passos

1. Exporte a original com o umodel. Gere a versão ampliada em TGA RGBA, com o alfa da original redimensionado.
2. Copie `tools/unreal/LMTexImport` para `D:\landmass\build\LMTexImport` e, no `Classes\LMTexImport.uc`, coloque a linha abaixo. `NAME` e `GROUP` são os da textura no pacote de destino.

   ```
   #exec TEXTURE IMPORT NAME=<Nome> FILE=<tga> GROUP=<Grupo> MIPS=1 DXT=5 LODSET=2
   ```

   Em `build\System\LandMass.ini`, deixe `EditPackages=LMTexImport` logo depois de `EditPackages=LMEmu`.
3. Apague `build\System\LMTexImport.u` e compile. No PowerShell, use `Start-Process -ArgumentList`, porque `-ini=LandMass.ini` passado direto vira dois argumentos:

   ```
   Start-Process D:\landmass\build\System\ucc.exe -ArgumentList 'Editor.MakeCommandlet','-ini=LandMass.ini','-userini=User.ini' -WorkingDirectory D:\landmass\build\System -NoNewWindow -Wait
   ```

   O `ucc.log` deve ter `Imported Texture LMTexImport.<Grupo>.<Nome>`.
4. Rode o transplante:

   ```
   uv run python tools/unreal/transplant_texture.py <pacote.lm> D:\landmass\build\System\LMTexImport.u <Grupo>.<Nome> <saída.lm>
   ```

   O script confere que reproduz byte a byte a export original e a nova antes de gravar.
5. Confira com `umodel -export -png <saída.lm> <Nome>`: o tamanho e o alfa têm de estar certos.
6. Faça backup do original como `<pacote>.lm.bak-orig`. Copie o novo para `cliente\unit`, `cliente2\unit` e `servidor-partida\Unit`, mesmo com o GUID igual, para as três cópias ficarem idênticas.

## Por que não regravar o pacote no editor

O `OBJ SAVEPACKAGE` do editor do LandMass não grava e também não avisa.

O UnrealEd do UT2004 grava no formato da sua própria versão. Os pacotes do LandMass com licença 30 podem ter malhas serializadas de outro jeito, e uma regravação inteira arrisca corromper o pacote.

O transplante evita isso: mexe só na entrada de export da textura e acrescenta os dados novos no fim do arquivo.

## Aplicado

| Pacote | Textura | Origem |
|---|---|---|
| `A_Mo_Rats.lm` | `Skin.A01_1_S` (AU-TP02), 512 → 1024 | `texturas\export\A_Mo_Rats\Texture\A01_1_S.1k.tga` com alfa da original; DXT5 |
