# Autenticação

## Comportamento do cliente

- O `LandMass.exe` exige `version=` e `login_num=` na linha de comando; sem eles encerra.
- O executável converte a linha de comando para minúsculas antes de ler `login_num`.
- Com `login_num` diferente de `DEVELOPERGUID`, o UnrealScript (`XInterface.u`, `NetGuidLogin`) envia o login automaticamente, sem formulário.
- Como a conversão para minúsculas impede `DEVELOPERGUID`, o formulário de usuário/senha é inalcançável.

Evidência: [`../../tools/re/LandMass.exe/main_loop.c`](../../tools/re/LandMass.exe/main_loop.c), [`../../tools/re/NOTES.md`](../../tools/re/NOTES.md).

## Modelo adotado

- `login_num` é a credencial do jogador: token de 32 caracteres hexadecimais minúsculos (`secrets.token_hex(16)`).
- Armazene `sha256(token)`; compare com `hmac.compare_digest`. Token de alta entropia dispensa hash lento.
- Uma conta pode ter um token ativo; regerar o token invalida o anterior.
- O fluxo `id`/`pw` do `MS_LOGIN_IN` permanece no codec. Se usado, armazene senha com `argon2id`.

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

## Distribuição aos jogadores

- Gere um `.bat` por jogador; nunca reutilize token entre jogadores.
- Trate o `.bat` como segredo: quem o possui entra na conta.
