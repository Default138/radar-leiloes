"""
Programa principal. Rode com:

    python3 coletar.py                 # coleta, atualiza o painel e avisa no Telegram
    python3 coletar.py --sem-telegram  # só coleta e atualiza o painel

Passo a passo do que ele faz:
  1. Busca as motos/leilões em cada fonte (pasta fontes/)
  2. Salva no banco (banco.py) e descobre o que é novo
  3. Manda no Telegram: motos novas até o valor máximo + lembretes de véspera
  4. Gera o painel.html
"""

import html
import sys
import traceback
from datetime import datetime, timedelta

import banco
import config
import painel
import telegram
from fontes import prefeituras, prf, receita

FONTES = {
    "Receita Federal": receita.coletar,
    "PRF": prf.coletar,
    "Prefeituras (PNCP)": prefeituras.coletar,
}


def interessa(item):
    """Este item merece aviso no Telegram?"""
    if item["categoria"] not in config.TIPOS_ALERTA:
        return False
    if item["tipo"] == "leilao":
        return True  # leilão de prefeitura não tem preço por lote
    if item["estrangeira"]:
        return False
    if (item["situacao"] or "").startswith("Sucata"):
        return False
    valor = item["valor_minimo"]
    return valor is not None and valor <= config.VALOR_MAXIMO


def data_br(iso):
    if not iso:
        return ""
    return datetime.strptime(iso[:16], "%Y-%m-%d %H:%M").strftime("%d/%m %H:%M")


def formatar(item):
    """Um item em formato de mensagem do Telegram (HTML simples)."""
    e = html.escape
    if item["tipo"] == "leilao":
        linhas = [f"🏛️ <b>{e(item['titulo'])}</b>",
                  e(item["descricao"][:200]),
                  f"📅 {data_br(item['data_leilao'])} · {e(item['situacao'] or '')}"]
    else:
        valor = f"R$ {item['valor_minimo']:,.0f}".replace(",", ".")
        icone = {"Moto": "🏍️", "Carro": "🚗"}.get(item["categoria"], "🚙")
        linhas = [f"{icone} <b>{e(item['titulo'])}</b> — <b>{valor}</b>",
                  f"📍 {e(item['patio'] or item['cidade'])} · {e(item['fonte'])}",
                  f"📅 Leilão {data_br(item['data_leilao'])}"]
        if item["prazo_propostas"]:
            linhas.append(f"⏰ Propostas até {data_br(item['prazo_propostas'])}")
    linhas.append(f'<a href="{e(item["link"])}">Abrir</a> · <a href="{e(item["link_edital"])}">Edital</a>')
    return "\n".join(linhas)


def data_chave(item):
    """A data que importa para o lembrete: prazo das propostas, se houver."""
    iso = item["prazo_propostas"] or item["data_leilao"]
    return datetime.strptime(iso[:16], "%Y-%m-%d %H:%M") if iso else None


def avisar(conexao):
    if not telegram.configurado():
        print("Telegram não configurado (.env). Pulando avisos.")
        return

    itens = banco.futuros(conexao)

    # 1) Novidades: tudo que ainda não foi avisado (inclui o que foi
    #    coletado enquanto o Telegram estava desligado).
    novos = [i for i in itens if not i["alertado"]]
    para_avisar = [i for i in novos if interessa(i)]
    if para_avisar:
        cabecalho = (f"🔔 <b>{len(para_avisar)} novidade(s)</b> "
                     f"({', '.join(config.TIPOS_ALERTA)} até R$ {config.VALOR_MAXIMO:,})".replace(",", "."))
        telegram.enviar(cabecalho + "\n\n" + "\n\n".join(formatar(i) for i in para_avisar))
    banco.marcar(conexao, [i["id"] for i in novos], "alertado")

    # 2) Lembretes de véspera
    agora = datetime.now()
    limite = agora + timedelta(days=config.DIAS_LEMBRETE)
    vespera = [i for i in itens
               if not i["lembrado"] and interessa(i)
               and data_chave(i) and agora < data_chave(i) <= limite]
    if vespera:
        telegram.enviar("⏳ <b>Está chegando a hora!</b>\n\n"
                        + "\n\n".join(formatar(i) for i in vespera))
        banco.marcar(conexao, [i["id"] for i in vespera], "lembrado")


def main():
    usar_telegram = "--sem-telegram" not in sys.argv
    print(f"=== Coleta {datetime.now():%d/%m/%Y %H:%M} ===")

    conexao = banco.conectar()
    ids_novos = set()
    erros = []
    for nome, funcao in FONTES.items():
        try:
            itens = funcao()
            novos = banco.salvar(conexao, itens)
            ids_novos.update(novos)
            print(f"{nome}: {len(itens)} itens ({len(novos)} novos)")
        except Exception:
            # Se um site mudar ou sair do ar, as outras fontes continuam.
            erros.append(nome)
            print(f"{nome}: ERRO")
            traceback.print_exc()

    if usar_telegram:
        avisar(conexao)
        if erros and telegram.configurado():
            telegram.enviar("⚠️ Radar de Leilões: erro ao coletar " + ", ".join(erros)
                            + ". Veja o coleta.log.")

    arquivo = painel.gerar(banco.futuros(conexao))
    print(f"Painel: {arquivo}")


if __name__ == "__main__":
    main()
