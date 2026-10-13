# Registro de decisões (ADR)

Formato: uma linha por decisão. Ao substituir uma decisão, marque a antiga como "substituída por Dn".

| ID | Decisão | Motivo | Status |
|----|---------|--------|--------|
| D1 | Um processo, `asyncio` puro, sem framework de rede. | Poucos jogadores; menos dependências; controle total do framing. | aceita |
| D2 | SQLAlchemy 2 async + Alembic. | Portabilidade SQLite → MySQL/Postgres sem reescrever consultas (R2). | aceita |
| D3 | Login por token em `login_num`. | O cliente força login automático; formulário inalcançável. | aceita |
| D4 | Não implementar Update (7312) nem ServerManager (7310). | Cliente de 2009 não depende deles. | aceita |
| D5 | Codec separado de handlers. | Testar protocolo sem rede nem banco. | aceita |
| D6 | Nomes de tabela/coluna do `LM_account.sql` preservados. | Conferência direta com o comportamento original. | substituída por D11 |
| D7 | Dados estáticos lidos de `landmass.wdb` do cliente, não copiados. | O cliente é a fonte da verdade (R1). | aceita |
| D8 | Tokens com `sha256` + `compare_digest`; senhas com `argon2id`. | Substitui XP Crypt; custo adequado a cada tipo de segredo. | aceita |
| D9 | Handlers devolvem `Sequence[Reply]`; `net/server.py` envia. | Handler testável sem socket; a assinatura `ctx.session.send` do plano inicial foi descartada. | aceita |
| D10 | Contas são criadas só pela CLI (`account create`); o servidor nunca cria conta no login. Token desconhecido → 101 com `result=-160`. | Pedido do usuário; controle de quem joga. | aceita |
| D11 | Nomenclatura Laravel para tabelas/colunas; mapeamento para nomes originais documentado em 04-persistence quando útil. | Regra do usuário; substitui D6. Convenção única para as tabelas atuais e futuras. | aceita |
| D12 | Sem tabelas de log/auditoria/contadores nem cópias `*_del`; usar log estruturado, métricas sob demanda e `deleted_at` quando necessário. | Legado de 2007; reduz escrita e esquema. | aceita |
| D13 | O Channel identifica o cliente pelo `login_num` do pedido 100, validado com `handlers/login.py`. Sem registro de sessões compartilhado entre Message e Channel. | O 100 tem 33 bytes (`char[33]`, como o login do Message) e o servidor original loga `in->guid`. Evita estado compartilhado entre serviços. | substituída por D16 |
| D14 | Cada conexão tem `outbox` e uma única task de escrita (`_pump`). Difusão (lobby) enfileira na `outbox` do destinatário. | Mantém a regra de uma escrita por socket e permite broadcast sem lock. | aceita |
| D15 | Heartbeat do servidor no canal a cada 10 s; o servidor nunca responde ao heartbeat do cliente. | O cliente responde 2 a 2 (dispatch, caso 2); eco do servidor geraria laço. `time_out` de 20 s no cliente. | aceita |
| D16 | O Message emite uma chave de sessão no 111 (`char[33]` @0x25, 32 hex). O Channel a valida no 100 com um registro em memória (`ports/session_keys.py`, `domain/session_keys.py`), criado e injetado por `app.game_servers`. Uma chave por conta. Chave nunca usada expira em 300 s; após o primeiro uso, vale até ser reemitida. O Channel não acessa o banco. | O 111 copia 33 bytes para `DAT_1005AE20` (`re/message_server.md` §4) e o cliente os devolve no 100. Com o 111 zerado, o 100 chegava zerado e era recusado. Substitui D13. | aceita |
| D17 | Contrato com o cliente é fixo (opcodes, layouts, comportamento observável). A arquitetura do servidor é própria: um processo, serviços de domínio, repositório SQLAlchemy e transações curtas. Processos, links, cópias e tabelas auxiliares do legado não são replicados; procedures viram regras de domínio. | Pedido do usuário: só o contrato visto pelo cliente precisa ser idêntico. Detalhes em [07-progression](../architecture/07-progression.md). | aceita |
| D18 | Ranking é consulta sob demanda sobre `accounts`, sem tabela. Empate recebe a menor posição (1, 1, 3). Lista de 100 posições. | Substitui `tbl_ranking` e o job `usp_renew_ranking`: cópia derivada que D12 não admite. O cliente só lê a lista. | aceita |
| D19 | Catálogo estático (`landmass.wdb`) é carregado em memória, somente leitura, no start. Tabelas da conta referenciam itens por `catalog_id` inteiro, sem FK. | Mantém D7 (o cliente é a fonte) e evita cópia no banco. Validação e preço em memória. | aceita |
| D20 | Saldos LD e Cash são colunas de `accounts`. Compra, extensão e presente debitam com `UPDATE` condicional (`saldo >= preço`) na mesma transação que cria o item. Sem tabela de transações. | Atomicidade sem log (D12) e saldo nunca negativo, mesmo com concorrência. | aceita |
| D21 | Patente e abandono são derivados, sem coluna. Patente = maior nível com `total_exp >= LevelList.exp`. Abandono é calculado pelo cliente a partir de partidas, vitórias e derrotas. | Uma única fonte (exp e wdb), sem divergência. O cliente já calcula o abandono (features §12). | aceita |
| D22 | Inventário tem uma linha por unidade, com `item_guid` e `inventory_index` por conta. Quantidade é a contagem de linhas. Destruir apaga a linha (DELETE). | O cliente identifica cada unidade por guid e índice (`LM_ITEM_INFO`). Substitui o contador `item_number` do legado. | aceita |
| D23 | O Channel lê e grava via repositórios compartilhados (ex.: `account_options` no 544); a validação de identidade continua só pela chave de sessão (D16). | F1 precisa persistir opções enviadas ao Channel. | aceita |
