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
