"""
Filtros dos avisos do Telegram, que você muda pelo próprio chat do bot.

Como funciona:
  - Você manda um comando para o bot (ex.: /tipos moto carro).
  - O bot NÃO fica ligado o tempo todo: ele só lê as mensagens na próxima
    coleta (08h ou 18h). Aí aplica o filtro e responde "✅ Filtros atualizados".
  - Os filtros ficam guardados em filtros.json (o GitHub salva junto com o
    banco). Se o arquivo não existir, valem os valores do config.py.

Segurança: o bot é público (qualquer um pode achar e mandar mensagem), então
só obedecemos mensagens vindas do SEU chat (TELEGRAM_CHAT_ID).
"""

import json
from pathlib import Path

import config
import telegram
from util import normalizar

ARQUIVO = Path(__file__).parent / "filtros.json"

# Como você escreve no chat -> nome da categoria no sistema.
APELIDOS_TIPO = {
    "MOTO": "Moto",
    "CARRO": "Carro",
    "CAMINHONETE": "Caminhonete/Utilitário",
    "UTILITARIO": "Caminhonete/Utilitário",
    "CAMINHAO": "Caminhão/Ônibus",
    "ONIBUS": "Caminhão/Ônibus",
    "REBOQUE": "Reboque/Outros",
    "OUTROS": "Reboque/Outros",
    "PREFEITURA": "Leilão de prefeitura",
}
TODOS_TIPOS = list(dict.fromkeys(APELIDOS_TIPO.values()))  # sem repetir

AJUDA = """🤖 <b>Comandos do Radar de Leilões</b>

/filtros: mostra os filtros atuais
/tipos moto carro: tipos que você quer receber
   (moto, carro, caminhonete, caminhao, reboque, prefeitura ou todos)
/preco 1000 6000: faixa de preço (ou só o máximo: /preco 6000)
/sucata sim ou /sucata nao: incluir sucatas?
/estrangeira sim ou /estrangeira nao: incluir placa estrangeira?
/cidade foz, cascavel: cidades (separe com vírgula) ou /cidade todas
/lista: tudo que está à venda agora e passa nos filtros
/padrao: volta aos filtros do config.py
/ajuda: esta mensagem

⏰ Eu só leio as mensagens nas coletas (08h e 18h), então a resposta
pode demorar algumas horas."""


# ---------- guardar e ler os filtros ----------

def padrao():
    """Filtros iniciais, tirados do config.py."""
    return {
        "tipos": list(config.TIPOS_ALERTA),
        "preco_min": 0,
        "preco_max": config.VALOR_MAXIMO,
        "sucata": False,
        "estrangeira": False,
        "cidades": [],          # lista vazia = todas as cidades do config
    }


def carregar():
    filtros = padrao()
    filtros["ultimo_update"] = 0  # última mensagem já lida (controle interno)
    if ARQUIVO.exists():
        filtros.update(json.loads(ARQUIVO.read_text(encoding="utf-8")))
    return filtros


def salvar(filtros):
    ARQUIVO.write_text(json.dumps(filtros, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")


def reais(valor):
    return f"R$ {valor:,.0f}".replace(",", ".")


def resumo(filtros):
    """Os filtros em texto, para mostrar no chat."""
    cidades = ", ".join(filtros["cidades"]) if filtros["cidades"] else "todas da região"
    preco = (f"até {reais(filtros['preco_max'])}" if not filtros["preco_min"]
             else f"{reais(filtros['preco_min'])} a {reais(filtros['preco_max'])}")
    return "\n".join([
        f"🚘 Tipos: {', '.join(filtros['tipos']) or 'nenhum'}",
        f"💰 Preço: {preco}",
        f"🔧 Sucata: {'sim' if filtros['sucata'] else 'não'}",
        f"🌎 Placa estrangeira: {'sim' if filtros['estrangeira'] else 'não'}",
        f"📍 Cidades: {cidades}",
    ])


# ---------- o item passa nos filtros? ----------

def passa(item, filtros):
    """Este item merece aviso no Telegram, com estes filtros?"""
    if item["categoria"] not in filtros["tipos"]:
        return False
    if filtros["cidades"] and item["cidade"] not in filtros["cidades"]:
        return False
    if item["tipo"] == "leilao":
        return True  # leilão de prefeitura não tem preço por lote
    if item["estrangeira"] and not filtros["estrangeira"]:
        return False
    if (item["situacao"] or "").startswith("Sucata") and not filtros["sucata"]:
        return False
    valor = item["valor_minimo"]
    return valor is not None and filtros["preco_min"] <= valor <= filtros["preco_max"]


# ---------- entender cada comando ----------
# Cada função recebe os filtros e o texto depois do comando.
# Devolve a resposta (texto) ou levanta ValueError com a explicação do erro.

def _tipos(filtros, argumento):
    palavras = normalizar(argumento).replace(",", " ").split()
    if not palavras:
        raise ValueError("Diga os tipos. Ex.: /tipos moto carro")
    if palavras == ["TODOS"]:
        filtros["tipos"] = list(TODOS_TIPOS)
        return "Tipos: todos"
    escolhidos = []
    for palavra in palavras:
        # "motos" ou "carros" também valem (tira o S do plural).
        nome = APELIDOS_TIPO.get(palavra) or APELIDOS_TIPO.get(palavra.rstrip("S"))
        if not nome:
            raise ValueError(f"Não conheço o tipo “{palavra.lower()}”. Use: "
                             "moto, carro, caminhonete, caminhao, reboque, prefeitura ou todos")
        if nome not in escolhidos:
            escolhidos.append(nome)
    filtros["tipos"] = escolhidos
    return "Tipos: " + ", ".join(escolhidos)


def _numero(texto):
    """'6.000' ou '6000' ou 'R$6000' -> 6000"""
    limpo = texto.upper().replace("R$", "").replace(".", "").split(",")[0]
    if not limpo.isdigit():
        raise ValueError(f"“{texto}” não é um valor. Ex.: /preco 1000 6000")
    return int(limpo)


def _preco(filtros, argumento):
    valores = [_numero(v) for v in argumento.replace("-", " ").replace(" a ", " ").split()]
    if len(valores) == 1:
        minimo, maximo = 0, valores[0]
    elif len(valores) == 2:
        minimo, maximo = sorted(valores)
    else:
        raise ValueError("Use /preco 6000 (só o máximo) ou /preco 1000 6000")
    filtros["preco_min"], filtros["preco_max"] = minimo, maximo
    return f"Preço: {reais(minimo)} a {reais(maximo)}"


def _sim_nao(argumento, comando):
    resposta = normalizar(argumento).strip()
    if resposta in ("SIM", "S"):
        return True
    if resposta in ("NAO", "N"):
        return False
    raise ValueError(f"Use /{comando} sim ou /{comando} nao")


def _sucata(filtros, argumento):
    filtros["sucata"] = _sim_nao(argumento, "sucata")
    return "Sucata: " + ("incluir" if filtros["sucata"] else "esconder")


def _estrangeira(filtros, argumento):
    filtros["estrangeira"] = _sim_nao(argumento, "estrangeira")
    return "Placa estrangeira: " + ("incluir" if filtros["estrangeira"] else "esconder")


def _cidade(filtros, argumento):
    pedacos = [p.strip() for p in normalizar(argumento).split(",") if p.strip()]
    if not pedacos:
        raise ValueError("Diga as cidades. Ex.: /cidade foz, cascavel  ou  /cidade todas")
    if pedacos == ["TODAS"]:
        filtros["cidades"] = []
        return "Cidades: todas da região"
    escolhidas = []
    for pedaco in pedacos:
        # "foz" acha "Foz do Iguaçu"; "santa" acha as três "Santa ...".
        achadas = [c for c in config.CIDADES if pedaco in normalizar(c)]
        if not achadas:
            raise ValueError(f"Não achei a cidade “{pedaco.lower()}” na lista do config.py")
        escolhidas += [c for c in achadas if c not in escolhidas]
    filtros["cidades"] = escolhidas
    return "Cidades: " + ", ".join(escolhidas)


def _padrao(filtros, argumento):
    filtros.update(padrao())
    return "Filtros voltaram ao padrão do config.py"


ALTERAM_FILTRO = {
    "tipos": _tipos, "tipo": _tipos,
    "preco": _preco,
    "sucata": _sucata,
    "estrangeira": _estrangeira,
    "cidade": _cidade, "cidades": _cidade,
    "padrao": _padrao,
}


# ---------- ler as mensagens do Telegram ----------

def _mensagens_novas(filtros):
    """Mensagens recebidas desde a última coleta (só as do seu chat)."""
    env = telegram.ler_env()
    resposta = telegram._chamar(env["TELEGRAM_TOKEN"], "getUpdates", {
        "offset": filtros["ultimo_update"] + 1,
        "allowed_updates": '["message"]',
    })
    for update in resposta.get("result", []):
        # Guardar o número faz o Telegram "esquecer" esta mensagem: ela não
        # é lida de novo na próxima coleta.
        filtros["ultimo_update"] = max(filtros["ultimo_update"], update["update_id"])
        mensagem = update.get("message") or {}
        if str(mensagem.get("chat", {}).get("id")) != env["TELEGRAM_CHAT_ID"]:
            continue  # alguém que não é você: ignora
        texto = (mensagem.get("text") or "").strip()
        if texto.startswith("/"):
            yield texto


def processar(listar):
    """
    Lê os comandos novos, aplica nos filtros, responde no chat e devolve os
    filtros atualizados. "listar" é a função que monta a resposta do /lista.
    """
    filtros = carregar()
    antes = json.dumps(filtros, sort_keys=True)
    respostas, pediu_lista = [], False

    for texto in _mensagens_novas(filtros):
        # "/tipos@radar_bot moto carro" -> comando "tipos", argumento "moto carro"
        primeira, _, argumento = texto[1:].partition(" ")
        comando = normalizar(primeira.split("@")[0]).lower()
        if comando in ALTERAM_FILTRO:
            try:
                respostas.append("✅ " + ALTERAM_FILTRO[comando](filtros, argumento))
            except ValueError as erro:
                respostas.append(f"❌ {erro}")
        elif comando == "filtros":
            respostas.append("")  # o resumo já vai no fim da resposta
        elif comando == "lista":
            pediu_lista = True
        else:  # /ajuda, /start ou qualquer coisa desconhecida
            telegram.enviar(AJUDA)

    if respostas:
        texto = "\n".join(r for r in respostas if r)
        telegram.enviar((texto + "\n\n<b>Filtros atuais:</b>\n" + resumo(filtros)).strip())
    if pediu_lista:
        telegram.enviar(listar(filtros))

    # Grava se algo mudou (inclusive o número da última mensagem lida).
    if json.dumps(filtros, sort_keys=True) != antes:
        salvar(filtros)
    return filtros
