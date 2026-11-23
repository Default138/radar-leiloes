"""
Fonte: Detran-PR - veículos apreendidos e não retirados pelos donos.

A página https://www.detran.pr.gov.br/Pagina/Leiloes-publicos lista os
editais, cada um com dois PDFs:
  - texto (ex.: 2026lel005_texto_ok.pdf): regras, data, cidade do leilão
  - anexo (ex.: 2026lel005_anexo.pdf): tabela com os lotes

Só pegamos os leilões de CONSERVADOS (veículos que podem voltar a rodar).
Os de SUCATA só aceitam empresas de desmontagem (Lei 12.977/2014) e cada
lote é um pacote com vários veículos, então não servem para pessoa física.

No anexo, cada página tem um rodapé com a cidade do pátio, ex.:
"EDITAL DE LEILÃO Nº 2026LEL005 - CURITIBA - ANEXO 001". Usamos isso para
ficar só com os veículos da região. Cada lote é uma linha assim:
"LANCE INICIAL R$ 4.400,00 002 4.400,00R$ 256082 SFI9G80 HONDA/CG 160 START
 2023 MOTOCICLETA GAS VERMELHA PAS KC25E0R016352"

Os leilões do Detran são PRESENCIAIS e exigem cadastro por e-mail antes.
"""

import re
from datetime import datetime, timedelta

from util import baixar, categoria, cidade_da_regiao, normalizar, paginas_pdf, texto_pdf

PAGINA = "https://www.detran.pr.gov.br/Pagina/Leiloes-publicos"

# Só olhamos editais publicados nos últimos meses (os antigos já aconteceram).
MESES_PARA_TRAS = 6

LINHA_LOTE = re.compile(
    r"LANCE INICIAL R\$ ?([\d.]+,\d{2}) (\d{3}) [\d.]+,\d{2} ?R\$ (\d+) (\S+) "
    r"(.+?) ((?:19|20)\d{2}) ([A-Z][A-Z-]+) ")


def _editais():
    """Pares {texto, anexo} dos editais recentes, do mais novo ao mais antigo."""
    html = baixar(PAGINA).decode("utf-8", errors="replace")
    limite = (datetime.now() - timedelta(days=30 * MESES_PARA_TRAS)).strftime("%Y-%m")
    editais = {}
    padrao = (r'href="(https://www\.detran\.pr\.gov\.br/sites/default/arquivos_restritos/'
              r'files/documento/(\d{4}-\d{2})/(\d{4}lel\d{3})_(texto|anexo)[^"]*\.pdf)"')
    for url, mes, codigo, parte in re.findall(padrao, html, re.I):
        if mes < limite:
            continue
        editais.setdefault(codigo.lower(), {}).setdefault(parte.lower(), url)
    return [{"codigo": c, **e} for c, e in sorted(editais.items(), reverse=True)
            if "texto" in e and "anexo" in e]


def _dados_do_texto(texto):
    """Do PDF de texto: é de conservados? quando? onde? até quando se cadastrar?"""
    texto_n = normalizar(texto)
    conservados = "CATEGORIA CONSERVADOS" in texto_n
    quando = re.search(r"realizado em (\d{2}/\d{2}/\d{4}) a partir das (\d{1,2})h(\d{2})?", texto)
    data = None
    if quando:
        data = datetime.strptime(quando.group(1), "%d/%m/%Y").replace(
            hour=int(quando.group(2)), minute=int(quando.group(3) or 0))
    onde = re.search(r"na cidade de ([^/,]+)", texto)
    cadastro = re.search(r"documentos .{0,80}?até o dia (\d{2}/\d{2}/\d{4})", texto)
    return {
        "conservados": conservados,
        "data": data,
        "cidade_leilao": onde.group(1).strip() if onde else "?",
        "cadastro_ate": cadastro.group(1) if cadastro else None,
    }


def _lotes_do_anexo(conteudo, regiao=cidade_da_regiao):
    """
    Lotes do anexo cujo pátio é da região.

    O rodapé com a cidade só aparece na 1ª página de cada pátio; as páginas
    sem rodapé continuam o pátio anterior. Uma página pode ter vários
    rodapés (pátios pequenos juntos): aí basta um deles ser da região.
    """
    lotes = []
    cidade_anterior = None
    for pagina in paginas_pdf(conteudo):
        rodapes = re.findall(r"EDITAL DE LEIL[ÃA]O N[º°] ?\w+ - (.+?) - ANEXO", pagina)
        if rodapes:
            da_regiao = [regiao(r) for r in rodapes if regiao(r)]
            cidade = da_regiao[0] if da_regiao else None
            cidade_anterior = regiao(rodapes[-1])
        else:
            cidade = cidade_anterior
        if not cidade:
            continue
        pagina_n = normalizar(pagina)
        for achado in LINHA_LOTE.finditer(pagina_n):
            valor, lote, _registro, placa, _modelo, ano, tipo = achado.groups()
            modelo = pagina[achado.start(5):achado.end(5)]  # com acentos originais
            lotes.append({
                "lote": lote,
                "placa": placa,
                "modelo": " ".join(modelo.split()),
                "ano": int(ano),
                "tipo": tipo,
                "valor": float(valor.replace(".", "").replace(",", ".")),
                "cidade": cidade,
                "descricao": " ".join(pagina[achado.start():achado.end() + 40].split()),
            })
    return lotes


def coletar():
    itens = []
    for edital in _editais():
        dados = _dados_do_texto(texto_pdf(baixar(edital["texto"])))
        if not dados["conservados"]:
            continue  # sucata: só empresas de desmontagem podem comprar
        if not dados["data"] or dados["data"] < datetime.now():
            continue
        for lote in _lotes_do_anexo(baixar(edital["anexo"])):
            obs = [f"Leilão PRESENCIAL em {dados['cidade_leilao']}"]
            if dados["cadastro_ate"]:
                obs.append(f"Mande os documentos por e-mail até {dados['cadastro_ate']} "
                           "(veja o edital)")
            placa_ok = bool(re.fullmatch(r"[A-Z]{3}\d[A-Z0-9]\d{2}", lote["placa"]))
            itens.append({
                "id": f"detran:{edital['codigo']}:{lote['lote']}",
                "fonte": "Detran-PR",
                "tipo": "lote",
                "categoria": categoria(lote["tipo"]),
                "titulo": f"{lote['modelo']} {lote['ano']}",
                "descricao": lote["descricao"],
                "ano": lote["ano"],
                "placa": lote["placa"],
                "estrangeira": not placa_ok,
                "situacao": "Circulação",
                "cidade": lote["cidade"],
                "patio": f"Pátio Detran - {lote['cidade']}",
                "valor_minimo": lote["valor"],
                "valor_avaliacao": lote["valor"],
                "data_leilao": dados["data"].strftime("%Y-%m-%d %H:%M"),
                "prazo_propostas": None,
                "link": PAGINA,
                "link_edital": edital["texto"],
                "foto": None,
                "obs": " | ".join(obs),
                "edital": f"Lote {lote['lote']} (edital {edital['codigo'].upper()}, anexo)",
            })
    return itens
