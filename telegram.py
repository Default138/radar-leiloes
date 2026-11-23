"""
Envio de mensagens pelo Telegram.

O token do bot e o seu chat_id ficam no arquivo .env (que NÃO vai para o
GitHub; veja o .gitignore). Formato do .env:

    TELEGRAM_TOKEN=123456:ABC...
    TELEGRAM_CHAT_ID=987654321

Para descobrir o chat_id: mande qualquer mensagem para o seu bot e rode
    python3 telegram.py
que ele encontra o número e grava no .env sozinho.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ARQUIVO_ENV = Path(__file__).parent / ".env"
LIMITE_MENSAGEM = 4000  # o Telegram aceita até 4096 caracteres


def ler_env():
    """
    Lê TELEGRAM_TOKEN e TELEGRAM_CHAT_ID. No GitHub Actions eles vêm das
    variáveis de ambiente (Secrets); no seu PC, do arquivo .env.
    """
    valores = {}
    if ARQUIVO_ENV.exists():
        for linha in ARQUIVO_ENV.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.strip().startswith("#"):
                chave, valor = linha.split("=", 1)
                valores[chave.strip()] = valor.strip()
    for chave in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"):
        if os.environ.get(chave):
            valores[chave] = os.environ[chave]
    # Tira espaços/quebras de linha colados sem querer (ex.: no Secret do
    # GitHub). Um espaço no token quebra o endereço da API do Telegram.
    return {chave: valor.strip() for chave, valor in valores.items()}


def _chamar(token, metodo, parametros):
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    dados = urllib.parse.urlencode(parametros).encode()
    with urllib.request.urlopen(url, data=dados, timeout=30) as resposta:
        return json.load(resposta)


def configurado():
    env = ler_env()
    return bool(env.get("TELEGRAM_TOKEN") and env.get("TELEGRAM_CHAT_ID"))


def enviar(texto):
    """Envia uma mensagem (em HTML simples). Quebra em partes se for grande."""
    env = ler_env()
    token, chat = env.get("TELEGRAM_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("[telegram] .env sem TELEGRAM_TOKEN/TELEGRAM_CHAT_ID: mensagem não enviada")
        return False

    partes, atual = [], ""
    for bloco in texto.split("\n\n"):
        if len(atual) + len(bloco) + 2 > LIMITE_MENSAGEM:
            partes.append(atual)
            atual = ""
        atual += bloco + "\n\n"
    if atual.strip():
        partes.append(atual)

    for parte in partes:
        _chamar(token, "sendMessage", {
            "chat_id": chat,
            "text": parte,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        })
    return True


def descobrir_chat_id():
    env = ler_env()
    token = env.get("TELEGRAM_TOKEN")
    if not token:
        sys.exit("Coloque TELEGRAM_TOKEN=... no arquivo .env primeiro.")
    atualizacoes = _chamar(token, "getUpdates", {})["result"]
    if not atualizacoes:
        sys.exit("Nenhuma mensagem encontrada. Mande um 'oi' para o seu bot e rode de novo.")
    ultima = atualizacoes[-1]
    mensagem = ultima.get("message") or ultima.get("edited_message") or {}
    chat_id = mensagem.get("chat", {}).get("id")
    if not chat_id:
        sys.exit("Não achei o chat_id. Mande uma mensagem de texto para o bot e rode de novo.")

    linhas = [l for l in ARQUIVO_ENV.read_text(encoding="utf-8").splitlines()
              if not l.startswith("TELEGRAM_CHAT_ID")]
    linhas.append(f"TELEGRAM_CHAT_ID={chat_id}")
    ARQUIVO_ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"chat_id {chat_id} salvo no .env")
    enviar("✅ Radar de Leilões conectado! Você vai receber os avisos aqui.")


if __name__ == "__main__":
    descobrir_chat_id()
