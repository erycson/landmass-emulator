# Escopo e restrições

## Propósito

Substituir os servidores originais do LandMass (Message, Channel, Update, ServerManager) por um serviço Python
compatível com o cliente de 2009 em `D:\landmass\cliente`, para um grupo pequeno de jogadores.

## Objetivos

- Levar o cliente do login até a partida usando apenas o emulador.
- Persistir contas, personagem, inventário, clã e ranking em banco SQL padrão.
- Manter protocolo, regras e persistência testáveis de forma isolada.

## Fora de escopo

- Escalabilidade horizontal, balanceamento, alta disponibilidade.
- Anti-cheat (HShield) e qualquer bypass dele.
- Gerar pacotes de patch. O FTP de atualização (D241) só serve uma pasta pronta.

## Restrições

| ID | Restrição |
|----|-----------|
| R1 | O cliente é a fonte da verdade. Quando servidor original e cliente divergirem, implemente o que o cliente espera. |
| R2 | Não use SQL Server, procedures T-SQL nem XP Crypt. Use SQL padrão via ORM; SQLite por padrão; MySQL/PostgreSQL por configuração. |
| R3 | Mantenha tudo dentro de `D:\landmass`: código, ferramentas (`tools/`), cache do uv (`.uv-cache/`), bancos e logs. |
| R4 | Não altere `D:\landmass\LandMass_Setup_20090701.exe`. No cliente, crie apenas arquivos novos (ex.: `.bat`) ou altere com backup. |
| R5 | Python 3.14 gerenciado por `uv`. Sem dependências que exijam compilador nativo. |
| R6 | Versione com git. Nunca rode `git clean`; para descartar mudanças use `git checkout`. |
