"""
Fonte: Foztrans - Instituto de Transportes e Trânsito de Foz do Iguaçu.

Os veículos guinchados em Foz e não retirados pelos donos vão a leilão
2 a 3 vezes por ano (online, pessoa física pode participar). Muitas motos!

A página https://www.foztrans.pr.gov.br/leilao/ lista os editais. Para cada
um ela mostra: o PDF do edital, a DATA, o site do leiloeiro e o HORÁRIO.
O PDF traz a tabela de lotes, com códigos assim:
    LMC = Moto, Circulação     LMS = Moto, Sucata
    LCC = Carro, Circulação    LCS = Carro, Sucata
Ex.: "LMC03 AKH9543 PR YAMAHA/YBR 125K 2002/ 2002 PRETA ... CIRCULAÇÃO R$ 950,00"
"""

import re

from util import baixar, data_por_extenso, normalizar, texto_html, texto_pdf

PAGINA = "https://www.foztrans.pr.gov.br/leilao/"

TIPOS_LOTE = {
    "LMC": ("Moto", "Circulação"),
    "LMS": ("Moto", "Sucata"),
    "LCC": ("Carro", "Circulação"),
    "LCS": ("Carro", "Sucata"),
}

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
       "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
       "SP", "SE", "TO"}

# Palavras na linha do lote que indicam pendência (vai no aviso de "Obs").
PENDENCIAS = ["ALIENA", "RESTRI", "BLOQUEIO", "JUDICI", "DIVERGENTE", "OUTRO ESTADO",
              "PRIMEIRO EMPLACAMEN"]


def _editais():
    """
    Lê a página de leilões. Devolve uma lista de dicionários:
    {pdf, data (datetime com hora), site}
    """
    html = baixar(PAGINA).decode("utf-8", errors="replace")
    conteudo = html.split("pagina-conteudo", 1)[-1].split("</article>", 1)[0]
    editais = []
    # Cada edital começa num título <h3> com o link do PDF.
    for bloco in re.split(r"<h3", conteudo)[1:]:
        pdf = re.search(r'href="([^"]+\.pdf)"', bloco, re.I)
        if not pdf:
            continue
        texto = texto_html(bloco)
        data = data_por_extenso(texto.split("DATA", 1)[-1])
        if not data:
            continue
        hora = re.search(r"(\d{1,2})h(\d{2})?", texto.split("HOR", 1)[-1])
        if hora:
            data = data.replace(hour=int(hora.group(1)), minute=int(hora.group(2) or 0))
        # Site do leiloeiro: link com "leil" no nome que NÃO seja o PDF.
        site = re.search(r'href="(https?://[^"]*leil[^"]*?)(?<!\.pdf)"', bloco, re.I)
        editais.append({
            "pdf": pdf.group(1),
            "data": data,
            "site": site.group(1).rstrip("/") if site else PAGINA,
        })
    return editais


def _lotes(texto):
    """
    Separa a tabela de lotes do PDF. Devolve dicionários com os campos.

    Cada lote vai do código (ex.: LMC03) até o primeiro "R$ valor" depois
    dele. Usamos o texto normalizado (sem acento) para procurar e o
    original para recortar: os dois têm o mesmo tamanho.
    """
    texto_n = normalizar(texto)
    padrao = re.compile(r"\b(L(?:MC|MS|CC|CS)\d{2,3})\s+(.*?)\s+R\$\s*([\d.]+,\d{2})")
    lotes = []
    for achado in padrao.finditer(texto_n):
        codigo, valor = achado.group(1), achado.group(3)
        linha = texto[achado.start(2):achado.end(2)]
        linha_n = achado.group(2)
        palavras = linha.split()

        # "SEM PLACA PR HONDA/..." ou "AKH9543 PR YAMAHA/..."
        if linha_n.startswith("SEM PLACA"):
            placa, resto = "SEM PLACA", palavras[2:]
        else:
            placa, resto = palavras[0], palavras[1:]
        uf = resto[0] if resto and resto[0] in UFS else None
        if uf:
            resto = resto[1:]

        # O modelo vai até o ano (4 dígitos). Ex.: "HONDA/CG 150 TITAN KS 2006/ 2006"
        modelo, ano = [], None
        for palavra in resto:
            if re.fullmatch(r"(19|20)\d{2}/?", palavra):
                ano = int(palavra[:4])
                break
            modelo.append(palavra)

        categoria, situacao = TIPOS_LOTE[codigo[:3]]
        pendencias = [p for p in PENDENCIAS if p in linha_n]
        lotes.append({
            "codigo": codigo,
            "placa": placa,
            "uf": uf,
            "modelo": " ".join(modelo),
            "ano": ano,
            "categoria": categoria,
            "situacao": situacao,
            "valor": float(valor.replace(".", "").replace(",", ".")),
            "descricao": " ".join(linha.split()),
            "pendencia": bool(pendencias),
        })
    return lotes


def coletar():
    from datetime import datetime

    itens = []
    for edital in _editais():
        if edital["data"] < datetime.now():
            continue  # já aconteceu: nem baixa o PDF (é grande)
        nome_pdf = edital["pdf"].rsplit("/", 1)[-1]
        for lote in _lotes(texto_pdf(baixar(edital["pdf"]))):
            placa_ok = bool(re.fullmatch(r"[A-Z]{3}\d[A-Z0-9]\d{2}", lote["placa"]))
            obs = []
            if lote["situacao"] == "Sucata":
                obs.append("SUCATA: não pode voltar a circular; confira no edital "
                           "se o lote tem mais de um veículo")
            if lote["pendencia"]:
                obs.append("Tem observação/restrição na tabela do edital (alienação, "
                           "bloqueio, outro estado...): leia antes de dar lance")
            if lote["placa"] == "SEM PLACA":
                obs.append("Sem placa (primeiro emplacamento)")
            itens.append({
                "id": f"foztrans:{nome_pdf}:{lote['codigo']}",
                "fonte": "Foztrans",
                "tipo": "lote",
                "categoria": lote["categoria"],
                "titulo": f"{lote['modelo']} {lote['ano'] or ''}".strip(),
                "descricao": lote["descricao"],
                "ano": lote["ano"],
                "placa": lote["placa"],
                # Placa de outro estado ainda é brasileira; só marcamos
                # estrangeira se a placa não tiver o formato brasileiro.
                "estrangeira": not placa_ok and lote["placa"] != "SEM PLACA",
                "situacao": lote["situacao"],
                "cidade": "Foz do Iguaçu",
                "patio": "Pátio Foztrans - Foz do Iguaçu",
                "valor_minimo": lote["valor"],
                "valor_avaliacao": lote["valor"],
                "data_leilao": edital["data"].strftime("%Y-%m-%d %H:%M"),
                "prazo_propostas": None,
                "link": edital["site"],
                "link_edital": edital["pdf"],
                "foto": None,
                "obs": " | ".join(obs),
                "edital": f"Lote {lote['codigo']} (procure este código no site do leilão)",
            })
    return itens
