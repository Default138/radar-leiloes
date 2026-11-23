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
import comandos
import config
import painel
import telegram
from fontes import detran, foztrans, pf, prefeituras, prf, receita

FONTES = {
    "Receita Federal": receita.coletar,
    "PRF": prf.coletar,
    "Polícia Federal": pf.coletar,
    "Detran-PR": detran.coletar,
    "Foztrans": foztrans.coletar,
    "Prefeituras (PNCP)": prefeituras.coletar,
}


# Quantos itens no máximo o /lista manda (o resto, veja no site).
LIMITE_LISTA = 30
# Quantos itens no máximo vão num aviso de novidades/lembrete.
LIMITE_AVISO = 20


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
        linhas.append(f"🔖 {e(item['edital'] or '')}")
    linhas.append(f'<a href="{e(item["link"])}">Site do leilão</a> · <a href="{e(item["link_edital"])}">Edital</a>')
    return "\n".join(linhas)


def data_chave(item):
    """A data que importa para o lembrete: prazo das propostas, se houver."""
    iso = item["prazo_propostas"] or item["data_leilao"]
    return datetime.strptime(iso[:16], "%Y-%m-%d %H:%M") if iso else None


def listar(conexao, filtros):
    """Resposta do /lista: tudo à venda agora que passa nos filtros."""
    itens = [i for i in banco.futuros(conexao) if comandos.passa(i, filtros)]
    if not itens:
        return "📋 Nada à venda agora com estes filtros.\n\n" + comandos.resumo(filtros)
    texto = f"📋 <b>{len(itens)} item(ns) à venda com seus filtros</b>"
    if len(itens) > LIMITE_LISTA:
        texto += f" (mostrando os {LIMITE_LISTA} primeiros; o resto está no site)"
    texto += "\n\n" + "\n\n".join(formatar(i) for i in itens[:LIMITE_LISTA])
    return texto + f'\n\n<a href="{config.SITE}">Abrir o site</a>'


def mensagem_resumida(cabecalho, itens):
    """
    Cabeçalho + itens, mas no máximo LIMITE_AVISO (os mais baratos).
    Um leilão grande (ex.: Foztrans, 80+ motos) viraria 8 mensagens seguidas.
    """
    itens = sorted(itens, key=lambda i: (i["valor_minimo"] is None, i["valor_minimo"] or 0))
    texto = cabecalho + "\n\n" + "\n\n".join(formatar(i) for i in itens[:LIMITE_AVISO])
    if len(itens) > LIMITE_AVISO:
        texto += (f"\n\n➕ <b>E mais {len(itens) - LIMITE_AVISO}</b> (acima mostrei os "
                  f"{LIMITE_AVISO} mais baratos). Veja todos no "
                  f'<a href="{config.SITE}">site</a> ou mande /lista.')
    return texto


def avisar(conexao):
    if not telegram.configurado():
        print("Telegram não configurado (.env). Pulando avisos.")
        return

    # 0) Comandos que você mandou no chat desde a última coleta (/tipos, /preco...).
    filtros = comandos.processar(lambda f: listar(conexao, f))

    itens = banco.futuros(conexao)

    # 1) Novidades: tudo que ainda não foi avisado (inclui o que foi
    #    coletado enquanto o Telegram estava desligado).
    novos = [i for i in itens if not i["alertado"]]
    para_avisar = [i for i in novos if comandos.passa(i, filtros)]
    if para_avisar:
        telegram.enviar(mensagem_resumida(f"🔔 <b>{len(para_avisar)} novidade(s)</b>", para_avisar)
                        + "\n\n<i>Filtros: /filtros · Ajuda: /ajuda</i>")
    banco.marcar(conexao, [i["id"] for i in novos], "alertado")

    # 2) Lembretes de véspera
    agora = datetime.now()
    limite = agora + timedelta(days=config.DIAS_LEMBRETE)
    vespera = [i for i in itens
               if not i["lembrado"] and comandos.passa(i, filtros)
               and data_chave(i) and agora < data_chave(i) <= limite]
    if vespera:
        telegram.enviar(mensagem_resumida(f"⏳ <b>Está chegando a hora!</b> ({len(vespera)} item(ns))",
                                          vespera))
        banco.marcar(conexao, [i["id"] for i in vespera], "lembrado")


def main():
    usar_telegram = "--sem-telegram" not in sys.argv
    print(f"=== Coleta {datetime.now():%d/%m/%Y %H:%M} ===")

    conexao = banco.conectar()
    ids_novos = set()
    avisar_erro = []   # fontes que acabaram de completar N falhas seguidas
    voltaram = []      # fontes que tinham sido avisadas e voltaram a funcionar
    for nome, funcao in FONTES.items():
        try:
            itens = funcao()
            novos = banco.salvar(conexao, itens)
            banco.esquecer_ausentes(conexao, itens)
            ids_novos.update(novos)
            print(f"{nome}: {len(itens)} itens ({len(novos)} novos)")
            antes, _ = banco.registrar_falha(conexao, nome, deu_erro=False)
            if antes >= config.FALHAS_PARA_AVISAR:
                voltaram.append(nome)
        except Exception:
            # Se um site mudar ou sair do ar, as outras fontes continuam.
            print(f"{nome}: ERRO")
            traceback.print_exc()
            _, seguidas = banco.registrar_falha(conexao, nome, deu_erro=True)
            # Avisa uma vez só, quando completa N falhas seguidas (não a cada coleta).
            if seguidas == config.FALHAS_PARA_AVISAR:
                avisar_erro.append(nome)

    # O site é gerado ANTES dos avisos: se o Telegram falhar, o site e o
    # banco continuam sendo atualizados.
    arquivo = painel.gerar(banco.futuros(conexao))
    print(f"Painel: {arquivo}")

    if usar_telegram:
        try:
            avisar(conexao)
            if avisar_erro and telegram.configurado():
                telegram.enviar(f"⚠️ Radar de Leilões: {', '.join(avisar_erro)} com erro há "
                                f"{config.FALHAS_PARA_AVISAR} coletas seguidas. Veja o log no "
                                "GitHub (aba Actions). Aviso de novo quando voltar a funcionar.")
            if voltaram and telegram.configurado():
                telegram.enviar(f"✅ Radar de Leilões: {', '.join(voltaram)} voltou a funcionar.")
        except Exception:
            # Os itens não são marcados como avisados, então serão
            # avisados na próxima coleta que funcionar.
            print("Telegram: ERRO ao enviar avisos")
            traceback.print_exc()
            sys.exit(1)  # deixa a execução vermelha no GitHub, para você notar


if __name__ == "__main__":
    main()
