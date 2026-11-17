"""
Fonte: PRF - Polícia Rodoviária Federal (Superintendência do Paraná).

O site gov.br da PRF é feito em Plone, que tem uma API REST: basta colocar
"++api++" no endereço para receber JSON em vez de HTML.

Cada leilão é uma "notícia" com o texto (datas, site do leiloeiro) e
anexos em PDF. O "ANEXO II" é a planilha com todos os lotes, que lemos
com a biblioteca pypdf.
"""

import io
import re
from datetime import datetime

from pypdf import PdfReader

from util import baixar, baixar_json, categoria, cidade_da_regiao, normalizar

SITE = "https://www.gov.br/prf/pt-br/assuntos/leiloes-prf/parana"
API = "https://www.gov.br/prf/++api++/pt-br/assuntos/leiloes-prf/parana"

# Tipos de veículo como aparecem na coluna "TipoVeiculo" do PDF.
# São escritos com só a 1ª letra maiúscula, o que diferencia de modelos
# (que vêm em MAIÚSCULAS, ex.: "HONDA/CG 125").
TIPOS = ["Motocicleta", "Motoneta", "Ciclomotor", "Triciclo", "Quadriciclo",
         "Automóvel", "Caminhonete", "Camioneta", "Utilitário",
         "Caminhão Trator", "Caminhão", "Micro-ônibus", "Microônibus", "Ônibus",
         "Semi-reboque", "Semirreboque", "Reboque", "Trator", "Motor-casa"]

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
       "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
       "SP", "SE", "TO"}


def _para_api(url):
    """Converte um endereço normal do site no endereço da API."""
    return url.replace("/prf/pt-br/", "/prf/++api++/pt-br/")


def _texto_dos_blocos(noticia):
    """Junta todos os textos da notícia (o Plone guarda em 'blocks')."""
    textos = []

    def percorrer(valor):
        if isinstance(valor, dict):
            for chave, filho in valor.items():
                if chave == "text" and isinstance(filho, str):
                    textos.append(filho)
                else:
                    percorrer(filho)
        elif isinstance(valor, list):
            for filho in valor:
                percorrer(filho)

    percorrer(noticia.get("blocks", {}))
    texto_html = (noticia.get("text") or {}).get("data", "")
    textos.append(re.sub(r"<[^>]+>", " ", texto_html))
    return " ".join(textos)


def _datas_futuras(texto):
    """Todas as datas dd/mm/aaaa do texto que ainda não passaram, em ordem."""
    hoje = datetime.now().date()
    datas = set()
    # O texto às vezes vem quebrado: "25/11/ 2026"
    for dia, mes, ano in re.findall(r"(\d{2})/(\d{2})/\s*(\d{4})", texto):
        try:
            data = datetime(int(ano), int(mes), int(dia)).date()
        except ValueError:
            continue
        if data >= hoje:
            datas.add(data)
    return sorted(datas)


def _site_leiloeiro(texto_edital, texto_noticia):
    """
    Site onde os LANCES acontecem.

    Cuidado: o leiloeiro (a pessoa) às vezes usa uma plataforma com outro
    nome. Ex.: o leiloeiro é Helcio Kronberg, mas os lances são no site
    vipleiloes.com.br. Por isso procuramos primeiro, no PDF do edital, um
    endereço perto das palavras "lance" ou "cadastro".
    """
    for texto in (texto_edital, texto_noticia):
        achado = re.search(
            r"(?:lance|cadastr)[^.]{0,250}?(https?://(?:www\.)?[a-z0-9.-]+\.com\.br)",
            texto, re.I)
        if achado:
            return achado.group(1).lower().rstrip("/")
    # Plano B: qualquer site "...leiloes.com.br" citado.
    for texto in (texto_edital, texto_noticia):
        achado = re.search(r"([a-z0-9-]+leil(?:oes|ao)\.com\.br)", texto, re.I)
        if achado:
            return f"https://www.{achado.group(1).lower()}"
    return None


def _texto_pdf(conteudo):
    """Texto corrido de um PDF (todas as páginas, sem quebras de linha)."""
    leitor = PdfReader(io.BytesIO(conteudo))
    return " ".join(" ".join((p.extract_text() or "") for p in leitor.pages).split())


def _leiloes_recentes():
    """Últimas notícias de LEILÃO (ignora as de 'notificação de retirada')."""
    busca = (f"{API}/@search?portal_type=News%20Item&sort_on=effective"
             f"&sort_order=descending&b_size=15")
    for noticia in baixar_json(busca)["items"]:
        titulo = normalizar(noticia["title"])
        if "LEILAO" in titulo and "NOTIFICA" not in titulo:
            yield noticia["@id"]


def _arquivos_pdf(url_noticia):
    """
    PDFs dentro da notícia, separados em dois grupos:
      - editais: o texto com as regras (onde dar lance, prazos...)
      - anexos:  as planilhas com os lotes ("ANEXO")
    """
    busca = f"{_para_api(url_noticia)}/@search?portal_type=File&b_size=50"
    editais, anexos = [], []
    for arquivo in baixar_json(busca)["items"]:
        url = arquivo["@id"] + "/@@download/file"
        if "ANEXO" in normalizar(arquivo["title"]):
            anexos.append(url)
        else:
            editais.append(url)
    return editais, anexos


def _registros_do_pdf(conteudo):
    """
    Quebra o texto do PDF em um registro por lote.

    No PDF, cada lote começa com o número do lote seguido de "DEL ..."
    (delegacia). Às vezes o número vem numa linha própria, às vezes colado
    no fim da linha anterior; por isso juntamos tudo num texto só e
    separamos pelo padrão "<número> DEL".
    """
    leitor = PdfReader(io.BytesIO(conteudo))
    texto = " ".join((pagina.extract_text() or "") for pagina in leitor.pages)
    texto = " ".join(texto.split())  # quebras de linha viram espaço

    # Tira o rodapé que o sistema SEI imprime em cada página, ex.:
    # "29/10/2026, 15:33 SEI/PRF - 76530946 - Anexo https://sei... 8/18"
    texto = re.sub(r"\d{2}/\d{2}/\d{4}, \d{2}:\d{2} SEI/\S+.*?\s\d{1,3}/\d{1,3}(?=\s|$)", " ", texto)

    # re.split com grupo devolve: [antes, lote1, texto1, lote2, texto2, ...]
    partes = re.split(r"(?:^|\s)(\d{1,5})\s+(?=DEL\s)", texto)
    registros = []
    for i in range(1, len(partes) - 1, 2):
        registros.append({"lote": partes[i], "texto": partes[i + 1]})
    return registros


def _interpretar(registro):
    """
    Tira os campos de um registro de lote. Exemplo de texto:
      "... SERRA (F540) Foz do Iguaçu AQN4G74 PR JTA/SUZUKI EN125 YES
       Motocicleta 00982910967 9CDN... 2008 PRETA Circulação R$ 800,00"
    Devolve None se não achar o tipo do veículo ou se não for da região.
    """
    texto = " ".join(registro["texto"].split())
    texto_n = normalizar(texto)

    # Acha o tipo que aparece primeiro no texto (como palavra inteira).
    achados = []
    for nome in TIPOS:
        m = re.search(rf"\s{re.escape(nome)}\s", f" {texto} ")
        if m:
            achados.append((m.start(), nome))
    if not achados:
        return None
    tipo = min(achados)[1]
    pos_tipo = f" {texto} ".find(f" {tipo} ") - 1  # posição no texto original

    cidade = cidade_da_regiao(texto)
    if not cidade:
        return None

    # Pedaço entre o nome da cidade e o tipo: "PLACA [UF] MARCA/MODELO"
    pos_cidade = texto_n.rfind(normalizar(cidade), 0, pos_tipo)
    meio = texto[pos_cidade + len(cidade):pos_tipo].split()
    placa = meio[0] if meio else ""
    uf = meio[1] if len(meio) > 1 and meio[1] in UFS else None
    modelo = " ".join(meio[2:] if uf else meio[1:])

    placa_brasileira = bool(re.fullmatch(r"[A-Z]{3}\d[A-Z0-9]\d{2}", placa))
    estrangeira = not (uf and placa_brasileira)

    depois = texto[pos_tipo + len(tipo) + 1:]
    achado = re.search(r"\s(\d{1,4})\s+([A-ZÀ-Ú]+)\s+(Circula|Sucata|$)", depois)
    ano = int(achado.group(1)) if achado and 1950 <= int(achado.group(1)) <= 2100 else None

    # Situação = do "Circulação"/"Sucata" até o valor (R$) ou o fim do texto.
    # Ex.: "Circulação", "Circulação sem Motor", "Sucata aproveitável"
    situacao = None
    achado_sit = re.search(r"((?:Circula|Sucata).*?)\s*(?:R\$|$)", texto)
    if achado_sit:
        situacao = achado_sit.group(1).strip()

    valor = None
    achado_valor = re.search(r"R\$\s*([\d.]+,\d{2})", texto)
    if achado_valor:
        valor = float(achado_valor.group(1).replace(".", "").replace(",", "."))

    return {
        "lote": registro["lote"],
        "titulo": f"{modelo} {ano or ''}".strip(),
        "descricao": texto,
        "ano": ano,
        "placa": placa,
        "uf": uf,
        "estrangeira": estrangeira,
        "situacao": situacao,
        "cidade": cidade,
        "valor": valor,
        "categoria": categoria(tipo),
    }


def coletar():
    itens = []
    for url_noticia in _leiloes_recentes():
        noticia = baixar_json(_para_api(url_noticia))
        texto = _texto_dos_blocos(noticia)
        datas = _datas_futuras(texto)
        if not datas:
            continue  # leilão já aconteceu
        editais, anexos = _arquivos_pdf(url_noticia)
        texto_edital = " ".join(_texto_pdf(baixar(u)) for u in editais)
        leiloeiro = _site_leiloeiro(texto_edital, texto)
        resumo_datas = ", ".join(d.strftime("%d/%m") for d in datas)

        for url_pdf in anexos:
            for registro in _registros_do_pdf(baixar(url_pdf)):
                moto = _interpretar(registro)
                if not moto:
                    continue

                # O edital da PRF costuma ter um dia para veículos de
                # circulação e o dia seguinte para sucatas.
                if moto["situacao"] and moto["situacao"].startswith("Sucata") and len(datas) > 1:
                    data = datas[1]
                else:
                    data = datas[0]

                obs = [f"Datas do edital: {resumo_datas}"]
                if moto["estrangeira"]:
                    obs.insert(0, "Placa estrangeira/sem placa BR: regularização difícil")
                if moto["situacao"] and moto["situacao"].startswith("Sucata"):
                    obs.insert(0, "SUCATA: não pode voltar a circular")

                itens.append({
                    "id": f"prf:{url_noticia.rsplit('/', 1)[-1]}:{moto['lote']}",
                    "fonte": "PRF",
                    "tipo": "lote",
                    "categoria": moto["categoria"],
                    "titulo": moto["titulo"],
                    "descricao": moto["descricao"],
                    "ano": moto["ano"],
                    "placa": moto["placa"],
                    "estrangeira": moto["estrangeira"],
                    "situacao": moto["situacao"],
                    "cidade": moto["cidade"],
                    "patio": f"Pátio PRF - {moto['cidade']}",
                    "valor_minimo": moto["valor"],
                    "valor_avaliacao": moto["valor"],
                    "data_leilao": data.strftime("%Y-%m-%d 09:00"),
                    "prazo_propostas": None,
                    "link": leiloeiro or url_noticia,
                    "link_edital": editais[0] if editais else url_noticia,
                    "foto": None,
                    "obs": " | ".join(obs),
                    "edital": f"Lote {moto['lote']} (procure este número no site do leilão)",
                })
    return itens
