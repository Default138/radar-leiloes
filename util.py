"""Funções pequenas usadas por várias partes do sistema."""

import json
import re
import time
import unicodedata
import urllib.request

import config

USER_AGENT = "Mozilla/5.0 (radar-leiloes; uso pessoal)"


def baixar(url, tentativas=3):
    """
    Baixa uma URL e devolve os bytes. Tenta de novo se der erro de rede,
    esperando cada vez mais (15s, 30s): alguns sites do governo derrubam a
    conexão por um tempo quando recebem muitos acessos.
    """
    import urllib.error
    for tentativa in range(1, tentativas + 1):
        try:
            pedido = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, */*",
            })
            with urllib.request.urlopen(pedido, timeout=60) as resposta:
                dados = resposta.read()
            time.sleep(config.PAUSA_ENTRE_REQUISICOES)
            return dados
        except urllib.error.HTTPError as erro:
            # O site respondeu "proibido"/"não existe" (4xx): tentar de novo
            # não muda nada. Só insiste em erro do servidor (5xx).
            if erro.code < 500 or tentativa == tentativas:
                raise
            time.sleep(15 * tentativa)
        except Exception:
            if tentativa == tentativas:
                raise
            time.sleep(15 * tentativa)


def baixar_json(url):
    """Baixa uma URL e já converte o JSON em dicionário/lista do Python."""
    return json.loads(baixar(url).decode("utf-8"))


def normalizar(texto):
    """
    Deixa o texto em MAIÚSCULAS e sem acento, para comparar nomes.
    Ex.: "Foz do Iguaçu" -> "FOZ DO IGUACU"

    Cada letra vira exatamente uma letra, então o texto mantém o mesmo
    tamanho (isso é usado no leitor do PDF da PRF).
    """
    resultado = []
    for letra in texto or "":
        base = unicodedata.normalize("NFKD", letra)[:1] or letra
        resultado.append(base.upper())
    return "".join(resultado)


CIDADES_NORMALIZADAS = [normalizar(c) for c in config.CIDADES]


def cidade_da_regiao(texto):
    """Devolve o nome da cidade da região que aparece no texto, ou None."""
    texto_n = normalizar(texto)
    for original, normalizada in zip(config.CIDADES, CIDADES_NORMALIZADAS):
        if normalizada in texto_n:
            return original
    return None


def patio_da_regiao(texto):
    """Como cidade_da_regiao, mas também aceita apelidos de pátio."""
    cidade = cidade_da_regiao(texto)
    if cidade:
        return cidade
    texto_n = normalizar(texto)
    for apelido, cidade in config.APELIDOS_PATIO.items():
        if normalizar(apelido) in texto_n:
            return cidade
    return None


# ---------------------------------------------------------------------------
# Categorias de veículo (usadas no filtro do site e nos avisos do Telegram)
# ---------------------------------------------------------------------------
# Cada palavra (sem acento, maiúscula) aponta para uma categoria.
# A ordem importa: "CAMINHONETE" precisa vir antes de "CAMINHAO".
CATEGORIAS = [
    ("MOTOCICLETA", "Moto"), ("MOTONETA", "Moto"), ("CICLOMOTOR", "Moto"),
    ("TRICICLO", "Moto"), ("QUADRICICLO", "Moto"),
    ("AUTOMOVEL", "Carro"),
    ("CAMINHONETE", "Caminhonete/Utilitário"), ("CAMIONETA", "Caminhonete/Utilitário"),
    ("UTILITARIO", "Caminhonete/Utilitário"), ("FURGAO", "Caminhonete/Utilitário"),
    ("CAMINHAO", "Caminhão/Ônibus"), ("CAVALO-MECANICO", "Caminhão/Ônibus"),
    ("CAVALO MECANICO", "Caminhão/Ônibus"), ("ONIBUS", "Caminhão/Ônibus"),
    ("MICRO-ONIBUS", "Caminhão/Ônibus"), ("MICROONIBUS", "Caminhão/Ônibus"),
    ("MICRO ONIBUS", "Caminhão/Ônibus"), ("MICRO", "Caminhão/Ônibus"),
    ("SEMI-REBOQUE", "Reboque/Outros"), ("SEMIRREBOQUE", "Reboque/Outros"),
    ("REBOQUE", "Reboque/Outros"), ("CARRETA", "Reboque/Outros"),
    ("TRATOR", "Reboque/Outros"),
]


def categoria(tipo):
    """
    Categoria a partir do TIPO do veículo, que é o começo do texto.
    Ex.: "MOTOCICLETA HONDA CG..." -> "Moto"; "Automóvel" -> "Carro"
    (Olhamos só o começo para "MOTOR" no meio da descrição não virar moto.)
    """
    tipo_n = normalizar(tipo).strip()
    for palavra, nome in CATEGORIAS:
        if tipo_n.startswith(palavra):
            return nome
    return "Reboque/Outros"


# ---------------------------------------------------------------------------
# Ajudantes para os coletores que leem PDF e HTML
# ---------------------------------------------------------------------------

def paginas_pdf(conteudo):
    """Texto de cada página de um PDF (lista), já sem quebras de linha."""
    import io
    from pypdf import PdfReader
    leitor = PdfReader(io.BytesIO(conteudo))
    return [" ".join((pagina.extract_text() or "").split()) for pagina in leitor.pages]


def texto_pdf(conteudo):
    """Texto do PDF inteiro, numa linha só."""
    return " ".join(paginas_pdf(conteudo))


def texto_html(conteudo):
    """Tira as tags de uma página HTML e devolve só o texto."""
    import html
    import re
    if isinstance(conteudo, bytes):
        conteudo = conteudo.decode("utf-8", errors="replace")
    conteudo = re.sub(r"<(script|style)\b.*?</\1>", " ", conteudo, flags=re.S | re.I)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", conteudo)).split())


MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6,
         "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11,
         "DEZEMBRO": 12}


def data_por_extenso(texto):
    """
    Primeira data escrita por extenso no texto, ex.: "04 de dezembro de 2026".
    Devolve datetime (sem hora) ou None.
    """
    import re
    from datetime import datetime
    for dia, mes, ano in re.findall(r"(\d{1,2})\s*DE\s+([A-Z]+)\s+DE\s+(\d{4})", normalizar(texto)):
        if mes in MESES:
            try:
                return datetime(int(ano), MESES[mes], int(dia))
            except ValueError:
                continue
    return None


# Quando o PDF não diz o TIPO do veículo, tentamos adivinhar pela marca/modelo.
MARCAS_SO_DE_MOTO = ["YAMAHA", "KAWASAKI", "HARLEY", "TRIUMPH", "DUCATI", "DAFRA",
                     "SHINERAY", "KASINSKI", "SUNDOWN", "TRAXX", "HAOJUE", "BUELL",
                     "MOTTU", "AVELLOZ", "BULL", "JTA/SUZUKI", "J.TOLEDO", "ROYAL ENFIELD"]
MODELOS_DE_MOTO = ["HONDA/CG", "HONDA/CB", "HONDA/XRE", "HONDA/NXR", "HONDA/BIZ",
                   "HONDA/POP", "HONDA/PCX", "HONDA/ELITE", "HONDA/NX", "HONDA/XR",
                   "HONDA/CRF", "HONDA/LEAD", "HONDA/ADV", "HONDA/FAN", "HONDA/TITAN",
                   "HONDA/NC", "HONDA/SH", "SUZUKI/EN", "SUZUKI/YES", "SUZUKI/GS",
                   "SUZUKI/INTRUDER", "SUZUKI/BURGMAN", "SUZUKI/DL", "BMW/G ", "BMW/F ",
                   "BMW/R ", "BMW/S "]


# Palavras do modelo que indicam caminhonete/utilitário ou caminhão/ônibus.
MODELOS_CAMINHONETE = ["HILUX", "AMAROK", "L200", "F250", "F-250", "F1000", "RAM ",
                       "S10", "RANGER", "FRONTIER", "SAVEIRO", "STRADA", "TORO",
                       "MONTANA", "OROCH", "KOMBI", "SPRINTER", "MASTER", "DUCATO",
                       "BESTA", "BOXER", "JUMPER", "DAILY", "TRANSIT", "HR ", "BONGO"]
MODELOS_CAMINHAO = ["SCANIA", "VOLVO/FH", "VOLVO/VM", "IVECO", "CARGO", "ATEGO",
                    "ACCELO", "AXOR", "CONSTELLATION", "WORKER", "DELIVERY"]


def categoria_por_modelo(modelo):
    """Ex.: "HONDA/CG 160 FAN" -> "Moto"; "REBOQUE/..." -> "Reboque/Outros"."""
    m = normalizar(modelo).strip()
    m = m[2:] if m.startswith("I/") else m  # "I/" = importado
    if m.startswith(("R/", "SR/", "REB", "SEMI", "CARRETA")):
        return "Reboque/Outros"
    if any(m.startswith(marca) for marca in MARCAS_SO_DE_MOTO) or \
       any(m.startswith(modelo_moto) for modelo_moto in MODELOS_DE_MOTO):
        return "Moto"
    # Caminhão/ônibus: marcas de caminhão, ou M.BENZ/VW com número (ex.: "M.BENZ/1720",
    # "VW/24.250") ou ônibus "O 400".
    if any(p in m for p in MODELOS_CAMINHAO) or \
       re.match(r"(M\.?BENZ|MERCEDES|VW|VOLKSWAGEN)\s*/\s*(\d|O\s?\d)", m) or "ONIBUS" in m:
        return "Caminhão/Ônibus"
    if any(p in f"{m} " for p in MODELOS_CAMINHONETE):
        return "Caminhonete/Utilitário"
    return "Carro"
