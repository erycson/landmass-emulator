"""Aponta o cliente para este servidor (D242): `update_server` e `message_server` de `landmass.wdb`.

O Launcher lê o endereço e as credenciais do FTP de patch dessa tabela. O original fica em
`landmass.wdb.antes-patch`, gravado uma vez: reaplicar não troca o backup.
"""

import shutil
import sqlite3
from pathlib import Path

# login_id e password são varchar(20) no wdb; o Launcher lê com buffer desse tamanho.
WDB_FIELD_BYTES = 20


def point_client(
    wdb: Path,
    update_dir: Path,
    *,
    message_host: str,
    message_port: int,
    update_host: str,
    update_port: int,
    user: str,
    password: str,
) -> None:
    if not wdb.is_file():
        raise ValueError(f"landmass.wdb não encontrado em {wdb}")
    for campo in (user, password):
        if len(campo.encode("cp1252", errors="replace")) > WDB_FIELD_BYTES:
            raise ValueError(f"usuário e senha do FTP passam de {WDB_FIELD_BYTES} bytes no wdb")
    backup = wdb.with_name(wdb.name + ".antes-patch")
    if not backup.exists():
        shutil.copy2(wdb, backup)
    con = sqlite3.connect(wdb)
    try:
        remotos: list[str | None] = [
            linha[0] for linha in con.execute("SELECT remote_path FROM update_server")
        ]
        with con:
            con.execute(
                "UPDATE message_server SET address = ?, port = ?", (message_host, message_port)
            )
            con.execute(
                "UPDATE update_server SET address = ?, port = ?, login_id = ?, password = ?, "
                "use_passive_mode = 1",
                (f"ftp://{update_host}", update_port, user, password),
            )
    finally:
        con.close()
    # O Launcher faz CWD no remote_path: a pasta precisa existir, mesmo vazia (sem .cmp, sem patch).
    for remoto in remotos:
        if remoto and remoto.strip("/"):
            (update_dir / remoto.strip("/")).mkdir(parents=True, exist_ok=True)
