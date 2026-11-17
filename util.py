"""Funções pequenas usadas por várias partes do sistema."""

import json
import time
import unicodedata
import urllib.request

import config

USER_AGENT = "Mozilla/5.0 (radar-leiloes; uso pessoal)"


def baixar(url, tentativas=3):
    """Baixa uma URL e devolve os bytes. Tenta de novo se der erro de rede."""
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
        except Exception:
            if tentativa == tentativas:
                raise
            time.sleep(3 * tentativa)


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
