"""
Fonte: Polícia Federal - leilões de veículos (delegacias do Paraná).

O site da PF é gov.br, mas numa versão antiga do Plone que NÃO libera a
API (diferente da PRF). Então lemos o HTML:
  1. https://www.gov.br/pf/pt-br/assuntos/leiloes  -> pastas por ano (2025, 2026-1...)
  2. pasta do ano -> uma página por leilão; ficamos só com as do Paraná
     (o nome termina em "-pr", ex.: "edital-no-01-2026-dpf-fig-pr" = Foz)
  3. página do leilão -> PDF do edital, que tem a data e os lotes:
     "LOTE Nº 3 01 veículo GM/MERIVA MAXX, Ano 2005/2005, Placa DRE3534/PR,
      ... Valor mínimo de arrematação: R$ 7.500,00"
"""

import re
from datetime import datetime

from util import (baixar, categoria_por_modelo, cidade_da_regiao, data_por_extenso,
                  normalizar, texto_pdf)

INICIO = "https://www.gov.br/pf/pt-br/assuntos/leiloes"


def _links(url, padrao):
    """Endereços da página que casam com o padrão (sem repetir, em ordem)."""
    html = baixar(url).decode("utf-8", errors="replace")
    return list(dict.fromkeys(re.findall(padrao, html)))


def _paginas_do_parana():
    """Páginas de leilão do Paraná nas pastas deste ano e do ano passado."""
    ano = datetime.now().year
    pastas = _links(INICIO, rf'href="({re.escape(INICIO)}/(?:{ano}|{ano - 1})[^"/]*)/?"')
    for pasta in pastas:
        for pagina in _links(pasta, rf'href="({re.escape(pasta)}/[^"/]+)/?"'):
            nome = pagina.rsplit("/", 1)[-1]
            if re.search(r"(^|-)pr($|-)", nome):
                yield pagina


def _pdf_do_edital(pagina):
    """O PDF do edital (ignora aviso de licitação, publicação no DOU etc.)."""
    for pdf in _links(pagina, r'href="([^"]+\.pdf)(?:/view)?"'):
        nome = normalizar(pdf.rsplit("/", 1)[-1])
        if "EDITAL" in nome and "AVISO" not in nome and "PUBLICACAO" not in nome:
            return pdf + "/@@download/file"
    return None


def _data_do_leilao(texto):
    """'O leilão será realizado ... no dia 04 de dezembro de 2026, às 09:00 horas'"""
    trecho = texto.split("será realizado", 1)[-1][:300]
    data = data_por_extenso(trecho)
    if not data:
        return None
    hora = re.search(r"às (\d{1,2})[:h](\d{2})", trecho)
    if hora:
        data = data.replace(hour=int(hora.group(1)), minute=int(hora.group(2)))
    return data


def _lotes(texto):
    # Tira o rodapé do SEI que aparece no meio do texto, ex.:
    # "Edital 01 (148694744) SEI 08389.004071/2026-23 / pg. 2"
    texto = re.sub(r"Edital \d+ \(\d+\) SEI [\d./-]+ / pg\. \d+", " ", texto)
    partes = re.split(r"LOTE N[º°o]\s*(\d+)\b", texto)
    lotes = []
    for i in range(1, len(partes) - 1, 2):
        numero, corpo = partes[i], partes[i + 1]
        valor = re.search(r"Valor m[íi]nimo de arremata[çc][ãa]o:\s*R\$\s*([\d.]+,\d{2})", corpo)
        modelo = re.search(r"ve[íi]culo\s+(.*?),\s*Ano\s+(\d{4})", corpo)
        if not (valor and modelo):
            continue
        placa = re.search(r"Placa\s+([A-Z0-9]+)/([A-Z]{2})", corpo)
        descricao = corpo[:valor.end()]
        lotes.append({
            "lote": numero,
            "modelo": " ".join(modelo.group(1).split()),
            "ano": int(modelo.group(2)),
            "placa": placa.group(1) if placa else "",
            "valor": float(valor.group(1).replace(".", "").replace(",", ".")),
            "sucata": "SUCATA" in normalizar(descricao),
            "descricao": " ".join(descricao.split()),
        })
    return lotes


def coletar():
    itens = []
    for pagina in _paginas_do_parana():
        pdf = _pdf_do_edital(pagina)
        if not pdf:
            continue
        texto = texto_pdf(baixar(pdf))
        data = _data_do_leilao(texto)
        if not data or data < datetime.now():
            continue  # sem data ou já aconteceu

        # Onde os veículos estão: "...local onde os bens encontram-se depositados: Pátio ..."
        local = texto.split("depositados", 1)[-1][:300] if "depositados" in texto else texto[:3000]
        cidade = cidade_da_regiao(local)
        if not cidade:
            continue  # leilão do Paraná, mas longe da região

        site = re.search(r"(?:https?://)?(www\.[a-z0-9.-]*leil[a-z0-9.-]*\.com\.br)", texto, re.I)
        link = f"https://{site.group(1).lower()}" if site else pagina
        nome = pagina.rsplit("/", 1)[-1]

        for lote in _lotes(texto):
            obs = ["Veículo oficial usado: entregue sem placas (precisa emplacar)"]
            if lote["sucata"]:
                obs.insert(0, "SUCATA: não pode voltar a circular")
            itens.append({
                "id": f"pf:{nome}:{lote['lote']}",
                "fonte": "Polícia Federal",
                "tipo": "lote",
                "categoria": categoria_por_modelo(lote["modelo"]),
                "titulo": f"{lote['modelo']} {lote['ano']}",
                "descricao": lote["descricao"],
                "ano": lote["ano"],
                "placa": lote["placa"],
                "estrangeira": False,
                "situacao": "Sucata" if lote["sucata"] else "Conservado",
                "cidade": cidade,
                "patio": f"Pátio PF - {cidade}",
                "valor_minimo": lote["valor"],
                "valor_avaliacao": lote["valor"],
                "data_leilao": data.strftime("%Y-%m-%d %H:%M"),
                "prazo_propostas": None,
                "link": link,
                "link_edital": pdf,
                "foto": None,
                "obs": " | ".join(obs),
                "edital": f"Lote {lote['lote']} (procure este número no site do leilão)",
            })
    return itens
