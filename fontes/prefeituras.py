"""
Fonte: Prefeituras (e outros órgãos), via PNCP - Portal Nacional de
Contratações Públicas.

Pela Lei 14.133/2021, todo órgão público tem que publicar seus leilões no
PNCP. O PNCP tem uma API pública de consulta; usamos o endereço que lista
as contratações com propostas ainda em aberto, filtrando:
  - modalidade 1 = Leilão eletrônico, 13 = Leilão presencial
  - estado = PR
  - município = cidades da região (config.CIDADES)

Além disso, o PNCP tem a LISTA DE ITENS de cada leilão (texto livre que a
prefeitura escreveu, ex.: "Alienação Veículo: HONDA NXR150 BROS ESD Cor:
Preta, Ano: 2007/2008 ... PLACA APS-8171"). Quando achamos veículos nessa
lista, cada um vira um lote separado (moto, carro...), com o lance mínimo.
Se a lista não tiver veículo reconhecível, guardamos o LEILÃO inteiro, como
antes, e o aviso pede para você abrir o edital.
"""

import re
from datetime import datetime, timedelta

import config
from util import baixar_json, categoria_por_modelo, cidade_da_regiao, normalizar

API = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
API_ITENS = "https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
MODALIDADES = {1: "Leilão eletrônico", 13: "Leilão presencial"}

# Palavras que mostram que o item é um veículo (texto sem acento, maiúsculo).
SINAIS_VEICULO = ["VEICULO", "VEIVULO", "PLACA", "RENAVAM", "CHASSI", "MOTOCICLETA",
                  "MOTONETA", "AUTOMOVEL", "CAMINHONETE", "CAMIONETA", "CAMINHAO",
                  "ONIBUS", "AMBULANCIA", "UTILITARIO", "PICK-UP", "PICKUP"]
MARCAS = ["CHEVROLET", "GM", "VW", "VOLKSWAGEN", "FIAT", "FORD", "RENAULT", "TOYOTA",
          "HONDA", "YAMAHA", "SUZUKI", "PEUGEOT", "CITROEN", "HYUNDAI", "MERCEDES",
          "M. BENZ", "M.BENZ", "IVECO", "VOLVO", "SCANIA", "MITSUBISHI", "MMC", "NISSAN",
          "KIA", "JEEP", "AGRALE", "MARCOPOLO", "NAVISTAR", "INTERNATIONAL"]

# Como saber se é MOTO pelo texto livre.
SINAIS_MOTO = ["MOTOCICLETA", "MOTONETA", "CICLOMOTOR", "MOTO", "NXR", "BROS", "XTZ",
               "XRE", "BIZ", "YBR", "FACTOR", "FAZER", "TITAN", "TWISTER", "CROSSER",
               "LANDER", "TENERE", "CG 1", "CG1", "CB 3", "CB3", "POP 1", "POP1", "FAN 1"]
SINAIS_CAMINHONETE = ["CAMINHONETE", "CAMIONETA", "PICK-UP", "PICKUP", "AMBULANCIA",
                      "UTILITARIO", "FURGAO", "VAN"]
SINAIS_CAMINHAO = ["CAMINHAO", "ONIBUS", "MICRO-ONIBUS", "MICROONIBUS", "GRANMINI",
                   "VOLARE", "CITYCLASS"]
SINAIS_MAQUINA = ["TRATOR", "RETROESCAVADEIRA", "PA CARREGADEIRA", "MOTONIVELADORA",
                  "ESCAVADEIRA", "ROLO COMPACTADOR", "REBOQUE", "CARRETA", "IMPLEMENTO",
                  "PULVERIZADOR", "COLHEITADEIRA", "ROCADEIRA"]


def _tem(texto_n, palavras):
    """Alguma das palavras aparece no texto como palavra inteira?"""
    return any(re.search(rf"(?<![A-Z]){re.escape(p)}(?![A-Z])", texto_n) for p in palavras)


def _veiculo(descricao):
    """
    Tenta ler um veículo do texto livre de um item. Devolve dicionário com
    titulo/ano/placa/categoria/sucata, ou None se não parecer veículo.
    """
    texto = " ".join((descricao or "").split())
    texto_n = normalizar(texto)
    if not (_tem(texto_n, SINAIS_VEICULO) or _tem(texto_n, MARCAS)):
        return None

    if _tem(texto_n, SINAIS_MOTO):
        categoria = "Moto"
    elif _tem(texto_n, SINAIS_CAMINHAO):
        categoria = "Caminhão/Ônibus"
    elif _tem(texto_n, SINAIS_MAQUINA):
        categoria = "Reboque/Outros"
    elif _tem(texto_n, SINAIS_CAMINHONETE):
        categoria = "Caminhonete/Utilitário"
    else:
        categoria = None  # decide pelo modelo, mais abaixo

    # Título: tira os prefixos comuns ("CATSER: 21946.", "LOTE 03 - TIPO / DESCRIÇÃO:",
    # "Alienação Veículo:") e corta antes de "Cor", "Ano", "Placa", vírgula...
    titulo = re.sub(r"^CATSER:?\s*\d+\s*[.:]?\s*", "", texto, flags=re.I)
    titulo = re.sub(r"^LOTE\s*\d+\s*[-–]\s*(TIPO\s*/\s*DESCRI\w+:)?\s*", "", titulo, flags=re.I)
    # (aceita erro de digitação, ex.: "VEÍVULO")
    titulo = re.sub(r"^(ALIENA\w+\s+(D[EOA]S?\s+)?)?VE[IÍ]\w+:?\s*", "", titulo, flags=re.I)
    titulo = re.split(r",|•|;|\s+(?:COR|ANO|PLACA|RENAVAM|COMBUST\w*|MARCA|CHASSI)\b",
                      titulo, maxsplit=1, flags=re.I)[0].strip(" .:-")[:60]

    ano = None
    achado = re.search(r"ANO(?:\s*/\s*MODELO)?\s*:?\s*((?:19|20)\d{2})(?:\s*/\s*((?:19|20)\d{2}))?", texto_n)
    if not achado:
        achado = re.search(r"\b((?:19|20)\d{2})\s*/\s*((?:19|20)\d{2})\b", texto_n)
    if achado:
        ano = int(achado.group(2) or achado.group(1))

    placa = re.search(r"PLACA\s*:?\s*([A-Z]{3})\s*-?\s*(\d[A-Z0-9]\d{2})", texto_n)

    if categoria is None:
        categoria = categoria_por_modelo(titulo)
        # "Carro" é o palpite padrão, então exigimos uma prova: placa/RENAVAM ou
        # o título começar com uma marca. Evita equipamento escrito como
        # "Alienação Veículo: ROMPEDOR HIDRÁULICO" ou "triturador... chassi".
        comeca_com_marca = _tem(normalizar(titulo)[:15], MARCAS)
        if categoria == "Carro" and not (placa or "RENAVAM" in texto_n or comeca_com_marca):
            return None
    return {
        "titulo": f"{titulo} {ano or ''}".strip(),
        "ano": ano,
        "placa": placa.group(1) + placa.group(2) if placa else None,
        "categoria": categoria,
        "sucata": "SUCATA" in texto_n,
        "descricao": texto,
    }


def _itens_do_leilao(cnpj, ano, seq):
    """Lista de itens do leilão no PNCP (todas as páginas)."""
    itens, pagina = [], 1
    while True:
        url = API_ITENS.format(cnpj=cnpj, ano=ano, seq=seq) + f"?pagina={pagina}&tamanhoPagina=100"
        lote = baixar_json(url) or []
        itens += lote
        if len(lote) < 100:
            return itens
        pagina += 1


def _pagina(modalidade, data_final, pagina):
    url = (f"{API}?dataFinal={data_final}&codigoModalidadeContratacao={modalidade}"
           f"&uf=PR&pagina={pagina}&tamanhoPagina=50")
    return baixar_json(url)


def coletar():
    # "Propostas abertas até daqui a 6 meses"
    data_final = (datetime.now() + timedelta(days=180)).strftime("%Y%m%d")
    itens = []
    for modalidade, nome_modalidade in MODALIDADES.items():
        pagina = 1
        while True:
            try:
                dados = _pagina(modalidade, data_final, pagina)
            except Exception:
                # A API devolve erro/vazio quando não há resultados.
                break
            for compra in dados.get("data") or []:
                municipio = compra["unidadeOrgao"]["municipioNome"]
                cidade = cidade_da_regiao(municipio)
                if not cidade:
                    continue
                objeto = " ".join((compra.get("objetoCompra") or "").split())
                if not any(p in normalizar(objeto) for p in config.PALAVRAS_PREFEITURA):
                    continue

                cnpj = compra["orgaoEntidade"]["cnpj"]
                ano = compra["anoCompra"]
                seq = compra["sequencialCompra"]
                link_pncp = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"
                data = (compra.get("dataEncerramentoProposta")
                        or compra.get("dataAberturaProposta") or "")

                leilao = {
                    "id": f"pncp:{compra['numeroControlePNCP']}",
                    "fonte": "Prefeitura",
                    "tipo": "leilao",
                    "categoria": "Leilão de prefeitura",
                    "titulo": compra["orgaoEntidade"]["razaoSocial"].title(),
                    "descricao": objeto,
                    "ano": None,
                    "placa": None,
                    "estrangeira": False,
                    "situacao": nome_modalidade,
                    "cidade": cidade,
                    "patio": municipio,
                    "valor_minimo": None,
                    "valor_avaliacao": compra.get("valorTotalEstimado"),
                    "data_leilao": data.replace("T", " ")[:16],
                    "prazo_propostas": None,
                    "link": compra.get("linkSistemaOrigem") or link_pncp,
                    "link_edital": link_pncp,
                    "foto": None,
                    "obs": "Abra o edital para ver se há motos",
                    "edital": f"PNCP {compra['numeroControlePNCP']}",
                }

                # Tenta abrir a lista de itens e achar os veículos.
                try:
                    lista = _itens_do_leilao(cnpj, ano, seq)
                except Exception:
                    lista = []  # sem a lista, fica só o leilão inteiro
                veiculos = []
                for item in lista:
                    veiculo = _veiculo(item.get("descricao"))
                    if not veiculo:
                        continue
                    numero = item.get("numeroItem")
                    obs = [f"Leilão da prefeitura ({nome_modalidade.lower()}): "
                           "leia o edital (comissão, retirada, débitos)"]
                    if veiculo["sucata"]:
                        obs.insert(0, "SUCATA: não pode voltar a circular")
                    veiculos.append({
                        **leilao,
                        "id": f"pncp:{compra['numeroControlePNCP']}:{numero}",
                        "tipo": "lote",
                        "categoria": veiculo["categoria"],
                        "titulo": veiculo["titulo"],
                        "descricao": veiculo["descricao"],
                        "ano": veiculo["ano"],
                        "placa": veiculo["placa"],
                        "situacao": "Sucata" if veiculo["sucata"] else "Usado (frota pública)",
                        "patio": f"Prefeitura de {cidade}",
                        "valor_minimo": item.get("valorUnitarioEstimado") or None,
                        "valor_avaliacao": item.get("valorUnitarioEstimado") or None,
                        "obs": " | ".join(obs),
                        "edital": f"Item {numero} do leilão (procure este número no site do leilão)",
                    })
                itens.extend(veiculos or [leilao])
            if pagina >= (dados.get("totalPaginas") or 1):
                break
            pagina += 1
    return itens
