"""
Fonte: Prefeituras (e outros órgãos), via PNCP - Portal Nacional de
Contratações Públicas.

Pela Lei 14.133/2021, todo órgão público tem que publicar seus leilões no
PNCP. O PNCP tem uma API pública de consulta; usamos o endereço que lista
as contratações com propostas ainda em aberto, filtrando:
  - modalidade 1 = Leilão eletrônico, 13 = Leilão presencial
  - estado = PR
  - município = cidades da região (config.CIDADES)

Aqui não dá para saber os lotes (cada prefeitura usa um site de leiloeiro
diferente), então cada item é o LEILÃO inteiro. O alerta avisa para você
abrir o edital e ver se tem moto.
"""

from datetime import datetime, timedelta

import config
from util import baixar_json, cidade_da_regiao, normalizar

API = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
MODALIDADES = {1: "Leilão eletrônico", 13: "Leilão presencial"}


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

                itens.append({
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
                })
            if pagina >= (dados.get("totalPaginas") or 1):
                break
            pagina += 1
    return itens
