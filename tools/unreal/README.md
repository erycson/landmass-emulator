# Unreal: pacote LMEmu e texturas

Fontes UnrealScript e ferramentas para o motor do LandMass (Unreal Engine 2, licença 30).

| Arquivo | Para quê |
|---|---|
| `LMEmu/Classes/*.uc` | Pacote `LMEmu`, que roda só no servidor de partida. Ele põe no jogador o time e o equipamento da conta, escolhe o modo de jogo e controla os bots (rotas e comandos `/bot`). |
| `build_lmemu.py` | Compila o `LMEmu.u` e o instala no servidor de partida, nos clientes e em `tools/server-patch/system`. |
| `patch_ucc.py` | Ajusta o `UCC.exe` do UT2004 ao layout de objeto do LandMass, que o `LandMass.exe` não traz. |
| `transplant_texture.py` | Troca uma textura dentro de um pacote `.lm` sem regravar o pacote. |
| `LMTexImport/Classes/LMTexImport.uc` | Modelo do pacote usado para importar a textura nova. |

## Compilar o LMEmu

É preciso o `UCC.exe` do **UT2004 patch 3369**, que é o compilador, não incluído aqui.

1. Crie `D:\landmass\build\System` com uma cópia do `system` do servidor de partida e o `UCC.exe` do UT2004 3369.
2. Corrija o compilador uma vez:

   ```
   uv run python tools/unreal/patch_ucc.py D:\landmass\build\System\UCC.exe
   ```

3. Compile e instale:

   ```
   uv run python tools/unreal/build_lmemu.py --landmass D:/landmass
   ```

O script cria as junctions `Etc`, `Static`, `Unit` e `Map`, copia as fontes e apaga o `LMEmu.u` antigo, porque o make só compila pacote ausente. A saída tem de terminar em `Success - 0 error(s)`.

Detalhes do ambiente: [`docs/operations/game-server.md`](../../docs/operations/game-server.md).

## Trocar uma textura

Passo a passo em [`docs/operations/textures.md`](../../docs/operations/textures.md). Resumo:

```
uv run python tools/unreal/transplant_texture.py <pacote.lm> <LMTexImport.u> <Grupo>.<Nome> <saída.lm>
```

O script confere que reproduz byte a byte a export original antes de gravar.
