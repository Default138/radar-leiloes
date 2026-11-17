# 🏍️ Radar de Leilões

Sistema pessoal que procura **veículos em leilão entre Foz do Iguaçu e Cascavel**,
publica um site com filtros e avisa no **Telegram**. Roda sozinho no GitHub,
sem precisar do PC ligado.

## Como funciona

```
GitHub Actions (2x por dia: 08h e 18h)
   └─ coletar.py → busca nas fontes → salva leiloes.db → avisa no Telegram
                 → gera docs/index.html → commit no repositório
GitHub Pages
   └─ publica a pasta docs/ como site
```

## Fontes

| Fonte | De onde vem | O que traz |
|---|---|---|
| Receita Federal | API pública do Sistema de Leilão Eletrônico (SLE) | cada veículo: descrição, pátio, lance mínimo, foto, prazo |
| PRF | API do site gov.br (Plone) + planilha PDF "Anexo II" | cada veículo: modelo, placa, situação (circulação/sucata), valor |
| Prefeituras | API do PNCP (Portal Nacional de Contratações Públicas) | o leilão inteiro (abrir o edital para ver os lotes) |

## Estrutura

```
config.py              <- cidades, valor máximo, tipos que avisam (mexa aqui)
coletar.py             <- programa principal
fontes/receita.py      <- coletor da Receita
fontes/prf.py          <- coletor da PRF (lê PDF)
fontes/prefeituras.py  <- coletor do PNCP
util.py                <- funções comuns (download, cidades, categorias)
banco.py               <- banco SQLite (leiloes.db)
telegram.py            <- envio de mensagens
painel.py              <- gera o site (docs/index.html)
.github/workflows/coletar.yml <- agenda do GitHub Actions
```

## Site

- Filtros: **tipo de veículo** (Moto, Carro, Caminhonete/Utilitário, Caminhão/Ônibus,
  Reboque/Outros, Leilão de prefeitura), **faixa de preço**, fonte, cidade, busca,
  esconder sucata/placa estrangeira, ordenação.
- Os filtros escolhidos ficam salvos no navegador.

## Avisos no Telegram

- **Novidade:** item novo cuja categoria está em `TIPOS_ALERTA`, com valor ≤
  `VALOR_MAXIMO`, placa brasileira e que não seja sucata.
- **Lembrete:** `DIAS_LEMBRETE` dia(s) antes do fim das propostas (Receita) ou do leilão.
- Se um site der erro, as outras fontes continuam e chega um aviso de erro.

## Configuração no GitHub (uma vez só)

1. **Secrets** (Settings → Secrets and variables → Actions → New repository secret):
   `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` (os mesmos valores do `.env`).
2. **Pages** (Settings → Pages): Source = *Deploy from a branch*, Branch = `main`, pasta `/docs`.
3. **Rodar na hora:** aba Actions → *Coletar leilões* → *Run workflow*.

Para mudar o valor máximo ou os tipos: edite o `config.py` direto no GitHub
(ícone de lápis) e salve. A próxima coleta já usa o valor novo.

## Rodar no PC (opcional, para testar)

No WSL, dentro desta pasta:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python coletar.py --sem-telegram   # coleta sem mandar mensagem
```

O `.env` (token) está no `.gitignore`: **nunca** suba ele para o GitHub.

## ⚠️ Antes de dar lance

- Leia o **edital** inteiro: comissão do leiloeiro (geralmente 5%), taxas,
  prazo de retirada, se o débito (IPVA/multas) fica com você.
- **Sucata** não pode voltar a circular. **Placa estrangeira** dificilmente é
  regularizada no Brasil.
- Receita: precisa de conta **gov.br** e a proposta é feita **antes** da disputa.
- Visite o pátio nos dias de visitação.
