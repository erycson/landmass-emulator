# Riscos

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Executável do game server ausente | Sem partida | confirmado | Construir Game Server Host ([architecture/06-game-server-host.md](architecture/06-game-server-host.md)); avaliar viabilidade no marco 3. |
| Divergência entre structs do servidor de 2007 e do cliente de 2009 | Pacotes mal interpretados | alta | Usar o cliente como referência (R1) e validar com capturas. |
| HShield bloquear execução fora do Launcher ou em modo servidor | Cliente/host não iniciam | média | Testar cedo; documentar comportamento. |
| Render D3D minimizado | Testes de aceitação automatizados falham | média | Janela pequena fora de foco; ver [operations/running-client.md](operations/running-client.md). |
| NAT/firewall dos jogadores | Conexão externa falha | média | Configurar `LANDMASS_PUBLIC_HOST`; documentar portas a abrir. |
| Vazamento de `.bat` com token | Acesso indevido à conta | baixa | Token por jogador; regerar invalida o anterior. |
| Resultado da partida não lido: o bloco `GameEnded` pode não sair no log se o servidor cair antes do `exit` | Histórico sem métricas; F9 sem prova no cliente | mitigado (D153) | Captura pelo console com `LOG=` próprio. Falta testar com dois clientes que o bloco aparece antes do `exit` (`tools/re/game_server_host.md`, §11.7). |
| Presente (615) e extensão (580) cobram o preço do wdb e não leem `shop_items`: item desativado na loja segue vendável por esses caminhos | Venda desativada não é respeitada fora da compra (550) | confirmado | Ligar 615 e 580 a `shop_items` (D191, R-BUY-07). Até lá, não desativar item para barrar venda. |
