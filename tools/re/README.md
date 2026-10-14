# Engenharia reversa

Notas do que se sabe do cliente e do servidor original do LandMass. É daqui que vêm os formatos de mensagem e as regras do emulador. Comece por [`NOTES.md`](NOTES.md).

| Nota | Assunto |
|---|---|
| [`NOTES.md`](NOTES.md) | Índice e linha de comando do `LandMass.exe`. |
| [`protocol_full.md`](protocol_full.md) | Todos os opcodes, layouts e lacunas. |
| [`message_server.md`](message_server.md) | Porta 7313: login, canais, amigos, clã, ranking. |
| [`channel_server.md`](channel_server.md) | Porta 7314: lobby, chat, loja, inventário. |
| [`layouts_f0.md`](layouts_f0.md) | Registros de jogador, sala e códigos de erro. |
| [`rooms.md`](rooms.md) | Salas: slots, times, pronto, convite. |
| [`features.md`](features.md) | Mapa das funções do jogo. |
| [`game_server_host.md`](game_server_host.md) | Servidor de partida: linha de comando, patches, fim de partida. |
| [`launcher.md`](launcher.md) | `Launcher.exe`: FTP de atualização (`update_server` do wdb), `Patcher.exe` e abertura do jogo. |
| [`game_movement.md`](game_movement.md) | Movimento, pulo e booster. |
| [`cmdline.md`](cmdline.md), [`fullscreen.md`](fullscreen.md), [`windowed.md`](windowed.md), [`widescreen.md`](widescreen.md) | Linha de comando e vídeo. |

## O que não está no repositório

O pseudocódigo descompilado (`<binário>/all/*.c`), os índices `_index.tsv` e os logs de prova ficam só na cópia local, porque são derivados dos binários do jogo. As notas citam esses arquivos pelo caminho e pelo endereço da função. Para gerar de novo, abra o binário do cliente no REA ou no Ghidra ([`docs/operations/reverse-engineering.md`](../../docs/operations/reverse-engineering.md)).
