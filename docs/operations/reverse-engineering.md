# Engenharia reversa

## Ferramentas

| Ferramenta | Local | Uso |
|------------|-------|-----|
| REA (MCP `rea`) | global (Node 24) | Decompilação, strings, xrefs via Ghidra. |
| Ghidra 12.1.4 | `D:\landmass\tools\ghidra_12.1.4_PUBLIC` | Provider do REA (`GHIDRA_INSTALL_DIR`). |
| JDK 21 | `D:\landmass\tools\jdk-21.0.12.1+1` | Runtime do Ghidra (`JAVA_HOME`). |
| Sniffer | `uv run landmass-emu sniff` | Captura bytes enviados pelo cliente. |

O REA mantém um único binário ativo. Não paralelize análises que troquem de alvo.

## Fontes de verdade (ordem de confiança)

1. Comportamento do cliente: capturas, `cliente\system\LandMass.log`.
2. Código do cliente: `+server_interface.dll` (montagem dos pedidos), `LM_Engine.dll` (tratamento das respostas, game server), UnrealScript embutido nos `.u` (fonte legível).
3. Servidores de 2006-07: `ChannelServer.map`, `.ilk`, executáveis — apenas como pista (R1).

## Binários-chave

| Binário | O que contém |
|---------|--------------|
| `cliente\system\+server_interface.dll` | `Cmessage_interface`, `Cchannel_interface`: um método por pedido, com opcode e tamanho. |
| `cliente\system\_core_network.dll` | Transporte: framing, IO overlapped. |
| `cliente\system\LM_Engine.dll` | Dispatch de respostas (`Recived from ... %d`), motor de game server, `InitServer`. |
| `cliente\system\LandMass.exe` | Parsing da linha de comando, inicialização UE2. |
| `cliente\system\XInterface.u`, `Core.u` | UnrealScript da UI e constantes. |

## Registro de achados

- Grave em `re/` com evidência: binário, endereço ou função, ou linha de script.
- Marque inferências com "(inferido)".
- Salve pseudocódigo relevante em `re/<binário>/<função>.c`.
- Promova para `docs/protocol/` somente o que estiver confirmado.
