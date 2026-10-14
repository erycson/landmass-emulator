# Scripts de teste com o cliente

Automação para testar o emulador com o cliente real na mesma máquina. Não é necessária para jogar nem para rodar o servidor.

| Script | Para quê |
|---|---|
| `launch.ps1` | Fecha os clientes abertos e abre um por pasta, pelo `jogar_<usuário>.bat` de cada uma. |
| `gui.py` | Clica, digita e tira screenshot da janela do jogo, em coordenadas de 800x600. |

## `launch.ps1`

```
powershell -ExecutionPolicy Bypass -File tools\scripts\launch.ps1 cliente:teste cliente2:teste2
```

Cada argumento é `<pasta em D:\landmass>:<usuário>`. A segunda instância precisa do `LandMass.exe` com o patch `WLog` → `XLog` ([`docs/operations/running-client.md`](../../docs/operations/running-client.md)).

## `gui.py`

```
uv run --no-project --with pillow python -I tools/scripts/gui.py shot saida.png [--pid N]
uv run --no-project --with pillow python -I tools/scripts/gui.py click <x> <y> [--double] [--pid N]
uv run --no-project --with pillow python -I tools/scripts/gui.py type <texto> [--pid N]
uv run --no-project --with pillow python -I tools/scripts/gui.py key 0x0D [--pid N]
```

- O cursor do jogo é movido por deltas (DirectInput), em malha fechada: screenshot, localiza o cursor, move.
- O script aborta se o jogo não estiver em primeiro plano, para não clicar em outra janela.
- `key` recebe o virtual-key code.
