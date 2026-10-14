# Autenticação

## Comportamento do cliente

- O `LandMass.exe` exige `version=` e `login_num=` na linha de comando; sem eles encerra (`main_loop.c`, `Parse` falha e vai para `LAB_109111e2`).
- A linha de comando é reescrita a cada chave lida (`version=`, `login_server=`, `login_num=`). O texto antes da chave mantém a caixa original. O texto depois dela vem da cópia em minúsculas (`main_loop.c`, linhas 76-92 e 124-134; a mesma regra está em [game_server_host.md](../../tools/re/game_server_host.md) §2).
- Por isso, `login_num` escrito antes de `version=` chega com a caixa original. Depois de `version=` ou `login_server=`, chega em minúsculas.
- Com `login_num` diferente de `DEVELOPERGUID`, a tela de login (`LM_LoginPage`, `XInterface.u`) envia o login automaticamente por `NetGuidLogin`, sem formulário.
- Com `login_num=DEVELOPERGUID` (a constante `DEVELOPER_GUID` de `Core.u`), a tela mostra o formulário de usuário e senha e chama `NetLogin(id, senha)`. O valor precisa vir antes de `version=`. Não testado no cliente real (D240).

Evidência: `tools/re/LandMass.exe/main_loop.c` (pseudocódigo local, fora do git), [`tools/re/NOTES.md`](../../tools/re/NOTES.md), [`tools/re/message_server.md`](../../tools/re/message_server.md) §5.1.

## Modelo adotado

- Token (`login_num` do `.bat`): 32 caracteres hexadecimais minúsculos (`secrets.token_hex(16)`). Armazene `sha256(token)` e compare com `hmac.compare_digest`. Token de alta entropia dispensa hash lento. Uma conta tem um token ativo; regerar o token invalida o anterior.
- Senha do formulário (D240): `hashlib.scrypt` (n=2^14, r=8, p=1, sal de 16 bytes), na coluna `accounts.password_hash`. Até 32 bytes em cp1252. Substitui o argon2id que D8 previa para senhas.
- Com conta já logada no Message, um novo login sem confirmação recebe -607 (`ACCOUNT_IS_LOGIN`). O cliente pergunta; se o jogador confirmar, entra com `forced_login = 1`.

## Login por formulário (usuário e senha)

Linha de comando para o formulário (não testada no cliente real). Note a ordem: `login_num=` antes de `version=`.

```
LandMass.exe login_num=DEVELOPERGUID?version=1245776779?login_server=<ip>:7313
```

- O `MS_LOGIN_IN` (opcode 100) vem com `id_len` e `pw_len` maiores que zero. O cliente não preenche o campo `login_num` (sobra lixo da pilha) e o servidor não o lê. O byte 41 é 0 e `forced_login` fica no byte 42.
- `id` e senha vão codificados pelo alfabeto próprio de `FUN_10028120` (`LM_Engine.dll`), com pad `9`. Implementação em `src/landmass_emu/protocol/form_codec.py`.
- Códigos devolvidos (`Core.u`): -602 usuário vazio, -603 senha vazia, -501 senha errada ou conta inexistente, -607 conta já logada, -160 conta banida. O formulário só tem texto próprio para -602, -603, -605, -607 e -600 a -610. Qualquer outro código, incluindo -501, mostra a mensagem 112000901 e desconecta (`NetOutAllServer`), sem fechar o jogo.
- Não verificado: se o formulário volta a aparecer depois de um login recusado (o `NetOutAllServer` pode desligar a tela), e se `DEVELOPERGUID` passa pelo `Parse` como valor.

## Chave de sessão (Message → Channel)

O `login_num` só entra no Message. O Channel recebe uma chave de sessão, emitida pelo Message:

- O `110` (Register) emite a chave da conta logada. Ela vai no `111` @0x25, `char[33]` (32 hexadecimais minúsculos e NUL; [message-server.md](message-server.md)).
- O cliente envia esses 33 bytes no `100` do Channel. O Channel resolve a chave em um registro de sessões em memória (`ports/session_keys.py`, implementado em `domain/session_keys.py`). Para validar a chave, não acessa o banco; a única escrita do Channel é a das opções (544, `account_options`).
- Um único registro, criado por `app.game_servers` e injetado nos dois servidores. Sem variável global.
- Uma conta tem uma chave viva: um novo `110` invalida a anterior.
- Expiração: chave que nunca foi usada no Channel expira 300 s após a emissão. Depois do primeiro uso bem-sucedido, a chave vale até ser reemitida; não há prazo ocioso. A expiração é checada no `resolve`, sem tarefa de fundo. Na emissão seguinte, o registro descarta chaves expiradas e a chave anterior da conta.
- A chave não é persistida. Reiniciar o emulador invalida todas as chaves, e o cliente precisa refazer o `110`.
- Chave zerada, desconhecida, expirada ou de conta reemitida: o Channel responde `101` com `result = -160` e não coloca o jogador no lobby.

Evidência: layout de 111 em `tools/re/message_server.md` §4 (33 bytes copiados para `DAT_1005AE20`). No teste com o cliente real, o `100` chegou com 33 bytes zerados depois de um `111` zerado. Não testado: o cliente aceitar uma chave não zerada, e a regra de expiração escolhida.

## Sequência

```mermaid
sequenceDiagram
  participant A as Admin (CLI)
  participant DB as Banco
  participant B as .bat do jogador
  participant C as Cliente
  participant M as Message (7313)
  participant R as Registro de chaves (memória)
  participant Ch as Channel (7314)
  A->>DB: account create --user <u> --nickname <n> → grava sha256(token)
  A->>B: gera login_server=..?version=..?login_num=<token>
  C->>M: MS_LOGIN_IN {id_len=0, pw_len=0, login_num=<token>}
  M->>DB: busca conta por sha256(token(lower))
  alt token válido
    M-->>C: 101 com result = 0; conexão fica autenticada
    C->>M: Register (110)
    M->>R: issue(conta)
    M-->>C: 111 com session_key @0x25
  else inválido
    M-->>C: 101 com result = -160 (senha inválida)
  end
  C->>Ch: IN_CHANNEL_SERVER (100) com session_key
  Ch->>R: resolve(session_key)
  alt chave válida
    Ch-->>C: 101 com result = 0
  else zerada, desconhecida ou expirada
    Ch-->>C: 101 com result = -160
  end
```

No formulário (D240), o `MS_LOGIN_IN` vem com `id` e senha codificados em vez do token, e o servidor confere a senha com scrypt. Presumido, não observado: depois do `101` com `result = 0`, o cliente segue com `110` e `111` como no token.

## Distribuição aos jogadores

- Por token: gere um `.bat` por jogador; nunca reutilize token entre jogadores. Trate o `.bat` como segredo: quem o possui entra na conta.
- Por senha: `account create --password` ou `account password --user <u> --password <p>`. A senha não vai para o `.bat`; o jogador digita no formulário.
