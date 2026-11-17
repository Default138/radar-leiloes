"""
Banco de dados local (SQLite: um arquivo só, leiloes.db, sem instalar nada).

Guardamos cada lote/leilão encontrado. Assim o sistema sabe:
  - o que é NOVO (para avisar no Telegram só uma vez)
  - se o lembrete de "falta 1 dia" já foi enviado
"""

import sqlite3
from datetime import datetime
from pathlib import Path

ARQUIVO = Path(__file__).parent / "leiloes.db"

CAMPOS = ["id", "fonte", "tipo", "categoria", "titulo", "descricao", "ano", "placa",
          "estrangeira", "situacao", "cidade", "patio", "valor_minimo",
          "valor_avaliacao", "data_leilao", "prazo_propostas", "link",
          "link_edital", "foto", "obs", "edital"]


def conectar():
    conexao = sqlite3.connect(ARQUIVO)
    conexao.row_factory = sqlite3.Row  # permite usar linha["titulo"]
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS itens (
            id TEXT PRIMARY KEY,
            fonte TEXT, tipo TEXT, categoria TEXT, titulo TEXT, descricao TEXT,
            ano INTEGER, placa TEXT, estrangeira INTEGER, situacao TEXT,
            cidade TEXT, patio TEXT,
            valor_minimo REAL, valor_avaliacao REAL,
            data_leilao TEXT, prazo_propostas TEXT,
            link TEXT, link_edital TEXT, foto TEXT, obs TEXT, edital TEXT,
            primeira_vez TEXT,          -- quando o sistema viu pela 1ª vez
            ultima_vez TEXT,            -- última coleta em que apareceu
            alertado INTEGER DEFAULT 0, -- já avisou no Telegram que é novo?
            lembrado INTEGER DEFAULT 0  -- já mandou o lembrete de véspera?
        )
    """)
    # Bancos criados antes do filtro por tipo não têm a coluna "categoria".
    colunas = [linha["name"] for linha in conexao.execute("PRAGMA table_info(itens)")]
    if "categoria" not in colunas:
        conexao.execute("ALTER TABLE itens ADD COLUMN categoria TEXT")
    return conexao


def salvar(conexao, itens):
    """Insere itens novos e atualiza os existentes. Devolve os ids novos."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    novos = []
    for item in itens:
        existe = conexao.execute("SELECT 1 FROM itens WHERE id = ?",
                                 (item["id"],)).fetchone()
        valores = [item.get(c) for c in CAMPOS]
        if existe:
            colunas = ", ".join(f"{c} = ?" for c in CAMPOS[1:])
            conexao.execute(
                f"UPDATE itens SET {colunas}, ultima_vez = ? WHERE id = ?",
                valores[1:] + [agora, item["id"]])
        else:
            colunas = ", ".join(CAMPOS)
            marcadores = ", ".join("?" for _ in CAMPOS)
            conexao.execute(
                f"INSERT INTO itens ({colunas}, primeira_vez, ultima_vez) "
                f"VALUES ({marcadores}, ?, ?)",
                valores + [agora, agora])
            novos.append(item["id"])
    conexao.commit()
    return novos


def futuros(conexao):
    """Itens cujo leilão ainda não passou, do mais próximo ao mais distante."""
    # Compara data E hora: um leilão de hoje às 10h já some às 10h01.
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    return conexao.execute(
        "SELECT * FROM itens WHERE data_leilao >= ? ORDER BY data_leilao, valor_minimo",
        (agora,)).fetchall()


def marcar(conexao, ids, campo):
    """Marca ids como alertado=1 ou lembrado=1."""
    assert campo in ("alertado", "lembrado")
    conexao.executemany(f"UPDATE itens SET {campo} = 1 WHERE id = ?",
                        [(i,) for i in ids])
    conexao.commit()
