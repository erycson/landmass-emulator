# Executar o cliente contra o emulador

## Linha de comando

```
LandMass.exe login_server=<ip>:7313?version=<versão>?login_num=<token>
```

| Parâmetro | Obrigatório | Efeito |
|-----------|:-----------:|--------|
| `version=` | sim | Versão local (`LocalVersion`). Sem ele o executável encerra. |
| `login_num=` | sim | Token de login (minúsculo). Sem ele o executável encerra. |
| `login_server=` | não | Sobrepõe o Message Server de `landmass.wdb` (`message_server`). |
| `SERVER` | não | Liga modo servidor (`GIsClient=0`); ver [../architecture/06-game-server-host.md](../architecture/06-game-server-host.md). |

## Scripts

| Arquivo | Uso |
|---------|-----|
| `cliente\system\jogar_local.bat` | Desenvolvimento: aponta para `127.0.0.1:7313`. |
| `.bat` por jogador | Gerado pela CLI `account`; contém o token do jogador. |

## Launcher

Não use `Launcher.exe`: ele tenta FTP de patch inexistente. Inicie `LandMass.exe` diretamente.

## Modo janela e testes automatizados

Receita em investigação: [`../../re/windowed.md`](../../re/windowed.md). Requisitos:

- Não alterar `LandMass.ini`/`User.ini` originais; usar cópias via `INI=`/`USERINI=`.
- Iniciar fora de foco/minimizado para não atrapalhar o usuário.
- Validar resultado lendo `cliente\system\LandMass.log` (linhas `Recived from Message Server N`).
