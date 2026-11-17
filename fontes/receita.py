"""
Fonte: Receita Federal (Sistema de Leilão Eletrônico - SLE).

O site da Receita é montado por JavaScript, mas por trás ele usa uma API
pública que devolve JSON. Usamos 3 endereços dela:

  1. api/editais-disponiveis           -> lista de todos os editais
  2. api/edital/<un>/<num>/<ano>       -> lotes do edital (tipo, valores, fotos)
  3. api/lote/<un>/<num>/<ano>/<lote>  -> detalhes de um lote (descrição, pátio)

O passo 2 não diz onde o lote está, então abrimos (passo 3) todo lote de
veículo para ver o pátio. Por isso a Receita é a fonte mais demorada.
"""

import re
from datetime import datetime

from util import baixar_json, categoria, patio_da_regiao

API = "https://www25.receita.fazenda.gov.br/sle-sociedade/api"
PORTAL = "https://www25.receita.fazenda.gov.br/sle-sociedade/portal"

# Os lotes de Foz e Cascavel entram nos editais da 9ª Região Fiscal (PR e SC).
# O código da unidade desses editais começa com 9 (ex.: 900100 = Curitiba).
PREFIXO_9A_REGIAO = "9"

# Tipos de lote (campo "tipo" da API) que são veículos.
TIPOS_VEICULO = {"VEÍCULO", "VEÍCULO PARA DESMONTAGEM", "MOTOCICLETA/ACESSÓRIO"}


def _editais_futuros():
    """Editais da 9ª Região cuja disputa de lances ainda não aconteceu."""
    dados = baixar_json(f"{API}/editais-disponiveis")
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    editais = []
    for situacao in dados["situacoes"]:
        for edital in situacao["lista"]:
            unidade = edital["edle"].split("/")[0]
            if not unidade.startswith(PREFIXO_9A_REGIAO):
                continue
            if edital["dataAberturaLances"] < agora:
                continue  # já passou
            editais.append(edital)
    return editais


def _extrair_ano(descricao):
    """Primeiro ano (1950-2099) que aparece na descrição."""
    achado = re.search(r"\b(19[5-9]\d|20\d\d)\b", descricao)
    return int(achado.group(1)) if achado else None


def _extrair_placa(descricao):
    """Placa brasileira (antiga ABC1234 ou Mercosul ABC1D23)."""
    achado = re.search(r"\b([A-Z]{3}\d[A-Z0-9]\d{2})\b", descricao)
    return achado.group(1) if achado else None


# Primeiras palavras da descrição que são só o "tipo" e saem do título.
PREFIXOS_TIPO = r"^(MOTOCICLETA|MOTONETA|CICLOMOTOR|AUTOMOVEL DE PASSEIO|AUTOMOVEL|AUTOMÓVEL)\s+"


def _titulo(descricao):
    """
    Deixa só a parte "MARCA MODELO ANO" da descrição.
    Ex.: "MOTOCICLETA HONDA CG 125 FAN 2008 APR8381,PRETA,CHASSI ..."
      -> "HONDA CG 125 FAN 2008"
    """
    texto = descricao.split(",")[0].split("////")[0].split(" CHASSI")[0]
    texto = re.sub(PREFIXOS_TIPO, "", texto)
    # Corta logo depois do ano (o que vem depois é placa e cor).
    achado = re.search(r"^(.*?\b(?:19[5-9]\d|20\d\d)\b)", texto)
    if achado:
        texto = achado.group(1)
    # Às vezes a marca vem repetida: "HONDA HONDA/XRE 300"
    texto = re.sub(r"^(\w+) \1/", r"\1/", texto)
    return " ".join(texto.split())


def coletar():
    """Devolve todos os veículos em pátios da região, nos editais futuros."""
    itens = []
    for edital in _editais_futuros():
        un, num, ano = edital["edle"].split("/")
        lotes = baixar_json(f"{API}/edital/{un}/{num}/{ano}")["listaLotes"]

        for resumo in lotes:
            if resumo.get("tipo") not in TIPOS_VEICULO:
                continue
            numero = resumo["nrAtribuido"]
            lote = baixar_json(f"{API}/lote/{un}/{num}/{ano}/{numero}")
            itens_lote = lote.get("itensDetalhesLote") or []
            if not itens_lote:
                continue
            primeiro = itens_lote[0]
            descricao = (primeiro.get("descricao") or "").strip()
            patio = primeiro.get("recintoArmazenador") or ""
            cidade = patio_da_regiao(patio)
            if not cidade:
                continue

            fotos = resumo.get("imagens") or []
            avisos = [a["texto"] for a in lote.get("avisosErratas") or []]
            if len(itens_lote) > 1:
                avisos.insert(0, f"Lote com {len(itens_lote)} itens")
            if resumo["tipo"] == "VEÍCULO PARA DESMONTAGEM":
                situacao = "Sucata (para desmontagem)"
                avisos.insert(0, "SUCATA: só para desmontagem, não circula")
            else:
                situacao = "Apreendido (Receita)"

            itens.append({
                "id": f"receita:{edital['edle']}:{numero}",
                "fonte": "Receita Federal",
                "tipo": "lote",
                "categoria": categoria(descricao),
                "titulo": _titulo(descricao),
                "descricao": descricao,
                "ano": _extrair_ano(descricao),
                "placa": _extrair_placa(descricao),
                "estrangeira": False,
                "situacao": situacao,
                "cidade": cidade,
                "patio": patio,
                "valor_minimo": lote.get("valorMinimo"),
                "valor_avaliacao": resumo.get("valorAvaliacao"),
                "data_leilao": edital["dataAberturaLances"],
                "prazo_propostas": edital["dataFimPropostas"],
                "link": f"{PORTAL}/edital/{un}/{num}/{ano}/lote/{numero}",
                "link_edital": f"{PORTAL}/edital/{un}/{num}/{ano}",
                "foto": fotos[0]["min"] if fotos else None,
                "obs": " | ".join(avisos),
                "edital": f"Receita {edital['edle']} (lote {numero})",
            })
    return itens
