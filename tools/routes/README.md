# Rotas dos bots

Os mapas do LandMass não têm caminhos para a IA, e as bases são ilhas desconectadas. Por isso as rotas são geradas pelo servidor de partida, lendo a geometria do mapa, sem editar o mapa (D225 a D227, [`docs/architecture/08-bots.md`](../../docs/architecture/08-bots.md)).

O resultado é o `tools/server-patch/system/LMEmuRoutes.ini`, com uma seção por mapa. Hoje só tem o `ONS-AirPort`.

## Gerar as rotas de um mapa

1. Rode o bake no servidor de partida, já com o `LMEmu.u` instalado. O processo sai sozinho e grava `LMEmuBake fim` no log. Inicie pelo `subprocess` do Python, porque iniciado pelo `Start-Process` do PowerShell o `LandMass.exe` sai na hora.

   ```
   LandMass.exe <Mapa>?listen?game=LMEmu.LMEmuDeathMatch?lmemubake=1 -server PORT=7897 LOG=bake.log -log login_server=127.0.0.1:7313?version=1245776779?login_num=<token>
   ```

2. Gere a seção do mapa:

   ```
   uv run python tools/routes/rotas.py --log <pasta do servidor>\system\bake.log --mapa <Mapa> --ini tools\server-patch\system\LMEmuRoutes.ini
   ```

   Use em `--mapa` o nome exato da URL da partida (por exemplo `ONS-AirPort`). As seções de outros mapas ficam intactas.

3. Confira o resumo: número de pontos e ligações por tipo (`w` andar, `f` queda, `j` pulo, `b` booster) e se as duas bases se alcançam nos dois sentidos.
4. Copie o `.ini` para o `system` do servidor de partida, ou rode o `aplicar.ps1` do Server Patch.

## Gravação de jogadores (opcional)

Para completar trechos que o bake não pegou, ligue `bRecord=True` em `[LMEmu.LMEmuRecorder]` no `LMEmu.ini` do servidor. Cada jogador humano gera uma linha `LMEmuRec` no log a cada 0,5 s. O `rotas.py` usa essas linhas quando o log não tem bake.
