# Server Patch do LandMass

Monta o servidor de partida a partir de uma instalação do cliente. O servidor de partida é o próprio `LandMass.exe` rodando com `-server`. Ele precisa dos mesmos mapas, malhas, morats e sons do cliente; muda só o que vai abaixo. Roda só em Windows.

## Jeito fácil

Dois cliques em `configurar.bat`. Ele pergunta o IP público, a pasta do cliente, se liga as partidas (armas e equipamento), os bots e o Launcher. Depois grava o `config.toml` na raiz do emulador, monta o servidor de partida com o `aplicar.ps1` e cria o `iniciar-servidor.bat`. Rodando de novo, as respostas atuais aparecem como padrão.

Com as partidas ligadas, ele cria a conta `servidor` e guarda o token dela em `data\secrets\match_login_num.txt`: é o `login_num` do `LandMass.exe` servidor. O `iniciar-servidor.bat` passa esse arquivo por `LANDMASS_MATCH_LOGIN_NUM_FILE`.

## Conteúdo

| Arquivo | Para quê |
|---|---|
| `system\LMEmu.u` | Pacote UnrealScript só de servidor do emulador. Põe no jogador o time e o equipamento da conta (morat, armas, booster, gerador, peças, pintura) e escolhe o modo de jogo (DM, TDM, OP, Bombing Run). |
| `aplicar.ps1` | Copia o cliente, aplica os patches e instala o `LMEmu.u`. |
| `configurar.bat` e `configurar.ps1` | Assistente: perguntas, `config.toml`, servidor de partida e `iniciar-servidor.bat`. |

## Patches

| Arquivo | Offset | Antes | Depois | Efeito |
|---|---|---|---|---|
| `system\Core.dll` | `0x3F9C6` | `74 0E` | `90 90` | O cliente descartava a linha de comando. Com o patch, o `-server` chega ao motor, que sobe sem janela e sem renderização. |
| `system\LandMass.exe` | `0x209E4` | `57` | `58` | Sem o patch, um segundo `LandMass.exe` repassava a linha de comando à instância já aberta e fechava. Com ele, cada partida roda no próprio processo, com log próprio. |

O script confere os bytes originais antes de gravar. Se a versão do cliente for outra, ele para sem alterar nada. Os originais ficam salvos como `*.orig`.

## Uso

```
powershell -ExecutionPolicy Bypass -File aplicar.ps1 -Cliente "C:\LandMass" -Destino "D:\servidor-partida"
```

A cópia deixa de fora o que o servidor não usa: `music`, `ScreenShots`, logs, dumps, backups, `Launcher.exe`, `Patcher.exe`, `end.exe` e o dgVoodoo. No emulador, aponte `match_server_dir` para a pasta `system` do destino. O emulador sobe um `LandMass.exe` por sala.

## Atualizar

- **`LMEmu.u`:** compile com `uv run python tools/unreal/build_lmemu.py` na raiz do emulador. O build também atualiza a cópia desta pasta.
- **Conteúdo** (mapas, pacotes `.lm`, `landmass.wdb`): o servidor de partida e os clientes precisam ter os mesmos arquivos. Ao trocar um no cliente, copie o mesmo arquivo para o servidor.

## Rotas dos bots

Os bots andam pela rota do mapa quando não têm inimigo (D225 a D227). A rota sai da geometria do mapa:

1. Suba um servidor sem bots com o bake: `LandMass.exe ONS-Airport?listen?game=LMEmu.LMEmuDeathMatch?lmemubake=1 -server PORT=<porta> LOG=bake.log -log` (com os argumentos de login da sessão de teste). O processo sai sozinho ao fim, com `LMEmuBake fim` no log. No ONS-Airport leva cerca de 30 s de jogo.
2. `uv run python tools/routes/rotas.py --log <pasta>\bake.log --mapa ONS-Airport --ini tools\server-patch\system\LMEmuRoutes.ini` imprime o resumo (contagem por flag e conectividade das bases) e grava só a seção do mapa.
3. `aplicar.ps1` copia `system\LMEmuRoutes.ini` para o servidor quando o arquivo existe. Um arquivo serve a todos os mapas, com uma seção `[<mapa> LMEmuRoutes]` por mapa.

Só o ONS-Airport está gerado nesta fase. Para outro mapa, rode o bake com o nome dele e `--mapa`.

Chaves do `LMEmu.ini` (seção `[LMEmu.LMEmuRecorder]`): `bRecord=True` grava as posições humanas (complemento, `LMEmuRec` no log); `bRecordBots=True` inclui os bots, só para teste. A seção `[LMEmu.LMEmuBake]` aceita `Cell`, `StepH`, `MaxDrop`, `FlyMax`, `Reach`, `NodeCap` e `PerTick`; sem ela valem os padrões do código.

Limites: o bot andando pela rota não foi visto no servidor headless (ver `docs/architecture/08-bots.md`), e pulo e booster não foram verificados em jogo.
