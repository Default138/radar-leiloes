"""
Banco de dados local (SQLite: um arquivo só, leiloes.db, sem instalar nada).

Guardamos cada lote/leilão encontrado. Assim o sistema sabe:
  - o que é NOVO (para avisar no Telegram só uma vez)
  - se o lembrete de "falta 1 dia" já foi enviado
"""

import sqlite3
from datetime import datetime, timedelta
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


def registrar_falha(conexao, fonte, deu_erro):
    """
    Conta quantas coletas SEGUIDAS a fonte deu erro. Devolve (antes, agora).
    Ex.: falhou de novo -> (1, 2); voltou a funcionar -> (2, 0).
    """
    conexao.execute("CREATE TABLE IF NOT EXISTS falhas (fonte TEXT PRIMARY KEY, "
                    "seguidas INTEGER DEFAULT 0)")
    linha = conexao.execute("SELECT seguidas FROM falhas WHERE fonte = ?", (fonte,)).fetchone()
    antes = linha["seguidas"] if linha else 0
    agora = antes + 1 if deu_erro else 0
    conexao.execute("INSERT OR REPLACE INTO falhas (fonte, seguidas) VALUES (?, ?)",
                    (fonte, agora))
    conexao.commit()
    return antes, agora


def esquecer_ausentes(conexao, itens):
    """
    A fonte funcionou e devolveu estes itens: o que ela devolvia antes e não
    devolve mais (lote retirado, leilão trocado por lotes...) sai do site já.
    Se a fonte não devolveu nada, não mexe (pode ter sido erro do site).
    """
    vistos = {item["id"] for item in itens}
    for fonte in {item["fonte"] for item in itens}:
        antigos = [linha["id"] for linha in conexao.execute(
            "SELECT id FROM itens WHERE fonte = ? AND ultima_vez >= ?",
            (fonte, "2000-01-02"))]
        sumidos = [i for i in antigos if i not in vistos]
        conexao.executemany("UPDATE itens SET ultima_vez = '2000-01-01 00:00' WHERE id = ?",
                            [(i,) for i in sumidos])
    conexao.commit()


# Item que nenhuma coleta encontrou nesses dias é considerado removido da fonte
# (ex.: lote retirado do leilão) e some do site e dos avisos.
DIAS_SEM_VER = 3


def futuros(conexao):
    """Itens cujo leilão ainda não passou, do mais próximo ao mais distante."""
    # Compara data E hora: um leilão de hoje às 10h já some às 10h01.
    agora = datetime.now()
    visto_desde = (agora - timedelta(days=DIAS_SEM_VER)).strftime("%Y-%m-%d %H:%M")
    return conexao.execute(
        "SELECT * FROM itens WHERE data_leilao >= ? AND ultima_vez >= ? "
        "ORDER BY data_leilao, valor_minimo",
        (agora.strftime("%Y-%m-%d %H:%M"), visto_desde)).fetchall()


def marcar(conexao, ids, campo):
    """Marca ids como alertado=1 ou lembrado=1."""
    assert campo in ("alertado", "lembrado")
    conexao.executemany(f"UPDATE itens SET {campo} = 1 WHERE id = ?",
                        [(i,) for i in ids])
    conexao.commit()
