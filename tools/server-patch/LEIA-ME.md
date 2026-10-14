# Server Patch do LandMass

Monta o servidor de partida a partir de uma instalação do cliente. O servidor de partida é o próprio `LandMass.exe` rodando com `-server`. Ele precisa dos mesmos mapas, malhas, morats e sons do cliente; muda só o que vai abaixo. Roda só em Windows.

## Conteúdo

| Arquivo | Para quê |
|---|---|
| `system\LMEmu.u` | Pacote UnrealScript só de servidor do emulador. Põe no jogador o time e o equipamento da conta (morat, armas, booster, gerador, peças, pintura) e escolhe o modo de jogo (DM, TDM, OP, Bombing Run). |
| `aplicar.ps1` | Copia o cliente, aplica os patches e instala o `LMEmu.u`. |

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
