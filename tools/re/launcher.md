# Launcher.exe (2009): atualização e abertura do jogo

Análise estática. O `LandMass.exe` do usuário estava em execução, e a regra de teste não deixou abrir o cliente de teste. Nada aqui foi visto rodando.

## Evidência

| Fato | Fonte |
|---|---|
| Tabela `update_server` em `system\landmass.wdb` (SQLite): `name`, `desc`, `address`, `login_id`, `password`, `remote_path`, `local_path`, `port`, `retry`, `retry_delay`, `use_firewall`, `use_passive_mode`. Três linhas `LM patch 01..03`, com `address` `ftp://201.76.37.107`, `ftp://64.15.158.250` e `ftp://72.55.188.182` (originais, fora do ar), login `landmassbr`, `remote_path` `balance`, porta 21, `retry` 3, `retry_delay` 5, `use_passive_mode` 1. Senhas não reproduzidas aqui. | Consulta de leitura numa cópia do `landmass.wdb` |
| Strings `ftp: retry=%d`, `ftp: login_id=%s`, `Patcher.exe` | `Launcher.exe` (cópia local), função de atualização `FUN_00404180` |
| `Patcher.exe` recebe `mode=landmass version=<int64>` (`%I64d`) | `FUN_00404180`, pseudocódigo local, linhas 847 e 851 |
| Formato do Play: `%s%s?%s%I64d?%s%s` (três pares chave=valor separados por `?`, `version=` no meio) | String UTF-16 no `Launcher.exe` |
| Comando do `LandMass.exe` com `login_server=`, `version=` e `login_num=` | [NOTES.md](NOTES.md), com a ordem a confirmar (ver lacunas) |
| FTP por WinINet (`CFtpConnection`, `FtpFindFirstFileW`); arquivos `.cmp` nomeados `<AAAAMMDDhhmmss>.cmp`; corpo a partir do byte 0x120 | Análise estática de subagente de RE. A saída bruta não foi guardada: confirmar na função de download |

## Fluxo (inferido, não testado)

1. Lê as linhas de `update_server` do `landmass.wdb`.
2. Conecta ao FTP em modo passivo, com `retry` tentativas e `retry_delay` segundos entre elas. Faz login.
3. Entra em `remote_path` (`balance`) e lista os arquivos.
4. Para cada `.cmp` mais novo que a versão local, baixa e roda `Patcher.exe mode=landmass version=<V>`.
5. Sem `.cmp` mais novo, segue para o Play: monta a linha e roda `system\LandMass.exe` por `ShellExecuteExW`.

Resposta mínima de um servidor que deixa o Launcher passar da atualização (inferida): `220`, `230` no login, `250` no `CWD balance`, `227` no PASV, `150`/`226` na listagem, sem `.cmp` novo. É o que `src/landmass_emu/update/ftp.py` responde com `data/update/balance/` vazia (D241).

## Primeiro teste (2026-10-14, D255)

- `report_launcher.log` (`system\`): versão `1245776779`, `ftp: name=LM patch 03`, `remote_path=/`, `file list=0`.
- Comandos WinINet: `USER`, `PASS`, `CWD /`, `TYPE A`, `PASV`, `LIST /`, `PWD`, e `LIST /balance` ao achar a pasta.
- `FUN_00404180`, linha 324 do pseudocódigo: com zero arquivos na lista, mostra "Falha ao conectar o servidor de update". Com algum arquivo, separa como download os `.cmp` de nome com 14 dígitos mais novos que a versão local, `notification.txt` e `Patcher.exe` (este só junto de outro download).

## Lacunas

- Origem da versão `DAT_00433D38` (int64) e a regra exata de comparação com o nome do `.cmp`.
- Ordem dos pares no Play. `NOTES.md` diz `login_server`, `version`, `login_num`; a análise do Play sugeriu `login_num` primeiro. Não resolvido.
- Origem do valor de `login_num` no Play (um GUID salvo pelo Launcher, um token, ou nada). Se for `DEVELOPERGUID` e vier antes de `version=`, o jogo já abre no formulário (ver [authentication.md](../../docs/protocol/authentication.md)).
- O que o `Patcher.exe` faz com o `.cmp` e os argumentos além de `mode` e `version`.
- Endereço da função de Play (`GetCommandLineW` em 0x406836 fica em outro trecho e não foi anotado).
- Teste com o cliente real: não feito.
