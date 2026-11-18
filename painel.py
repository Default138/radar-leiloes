"""
Gera o site: docs/index.html.

É uma página só, sem servidor. O visual (HTML/CSS/JavaScript) fica em
modelo_site.html; aqui só colocamos os dados dentro dele como JSON. Funciona de dois jeitos:
  - no GitHub Pages (o GitHub publica a pasta docs/ como site)
  - no seu PC, abrindo docs/index.html com dois cliques
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import config

PASTA = Path(__file__).parent / "docs"
ARQUIVO = PASTA / "index.html"

ORDEM_CATEGORIAS = ["Moto", "Carro", "Caminhonete/Utilitário", "Caminhão/Ônibus",
                    "Reboque/Outros", "Leilão de prefeitura"]

# O visual do site fica num arquivo HTML separado (mais fácil de editar).
MODELO = Path(__file__).parent / "modelo_site.html"


def gerar(linhas):
    # "novo" = apareceu pela primeira vez nos últimos 3 dias.
    limite_novo = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    itens = []
    for linha in linhas:
        item = dict(linha)
        item["estrangeira"] = bool(item["estrangeira"])
        item["novo"] = (item["primeira_vez"] or "") >= limite_novo
        for campo in ("primeira_vez", "ultima_vez", "alertado", "lembrado"):
            item.pop(campo, None)  # o site não precisa disso
        itens.append(item)

    # "</" dentro do JSON poderia fechar a tag <script> antes da hora.
    dados = json.dumps(itens, ensure_ascii=False).replace("</", "<\\/")
    html = (MODELO.read_text(encoding="utf-8")
            .replace("__DADOS__", dados)
            .replace("__CATEGORIAS__", json.dumps(ORDEM_CATEGORIAS, ensure_ascii=False))
            .replace("__MAXIMO__", str(config.VALOR_MAXIMO))
            .replace("__ATUALIZADO__", datetime.now().strftime("%d/%m/%Y %H:%M")))
    PASTA.mkdir(exist_ok=True)
    ARQUIVO.write_text(html, encoding="utf-8")
    return ARQUIVO
