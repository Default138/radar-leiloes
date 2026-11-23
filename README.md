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
| Polícia Federal | páginas HTML de gov.br/pf (delegacias do PR) + PDF do edital | cada veículo oficial usado: modelo, placa, valor mínimo |
| Detran-PR | página "Leilões públicos" + PDFs de texto e anexo | só leilões de **conservados** (sucata é só para desmontadoras); cada veículo com tipo, placa e lance inicial; leilão presencial |
| Foztrans | página foztrans.pr.gov.br/leilao + PDF do edital | veículos guinchados em Foz: códigos LMC/LMS (moto) e LCC/LCS (carro), circulação ou sucata |
| Prefeituras | API do PNCP (Portal Nacional de Contratações Públicas) + lista de itens de cada leilão | cada veículo achado na lista (modelo, ano, placa, lance mínimo); se não achar veículo, o leilão inteiro |

## Estrutura

```
config.py              <- cidades, valor máximo, tipos que avisam (mexa aqui)
coletar.py             <- programa principal
fontes/receita.py      <- coletor da Receita
fontes/prf.py          <- coletor da PRF (lê PDF)
fontes/pf.py           <- coletor da Polícia Federal (lê PDF)
fontes/detran.py       <- coletor do Detran-PR (lê PDF)
fontes/foztrans.py     <- coletor da Foztrans (lê PDF)
fontes/prefeituras.py  <- coletor do PNCP
util.py                <- funções comuns (download, cidades, categorias)
banco.py               <- banco SQLite (leiloes.db)
telegram.py            <- envio de mensagens
comandos.py            <- filtros pelo chat do Telegram (/tipos, /preco...)
filtros.json           <- filtros atuais (o bot atualiza sozinho)
painel.py              <- gera o site (docs/index.html) a partir do modelo
modelo_site.html       <- visual do site (HTML/CSS/JS) — edite aqui para mudar a aparência
.github/workflows/coletar.yml <- agenda do GitHub Actions
```

## Site

- Filtros: **tipo de veículo** (Moto, Carro, Caminhonete/Utilitário, Caminhão/Ônibus,
  Reboque/Outros, Leilão de prefeitura), **faixa de preço**, fonte, cidade, busca,
  esconder sucata/placa estrangeira, ordenação.
- Os filtros escolhidos ficam salvos no navegador.

## Avisos no Telegram

- **Novidade:** item novo que passa nos seus filtros (tipo, preço, sucata,
  placa estrangeira, cidade).
- **Filtros pelo chat:** mande comandos para o bot. Ele só lê nas coletas
  (08h/18h), então a resposta pode demorar algumas horas.

  | Comando | O que faz |
  |---|---|
  | `/filtros` | mostra os filtros atuais |
  | `/tipos moto carro` | moto, carro, caminhonete, caminhao, reboque, prefeitura ou todos |
  | `/preco 1000 6000` | faixa de preço (ou só o máximo: `/preco 6000`) |
  | `/sucata sim` / `/sucata nao` | incluir sucatas? |
  | `/estrangeira sim` / `/estrangeira nao` | incluir placa estrangeira? |
  | `/cidade foz, cascavel` / `/cidade todas` | cidades (separadas por vírgula) |
  | `/lista` | tudo à venda agora que passa nos filtros |
  | `/padrao` | volta aos valores do `config.py` |
  | `/ajuda` | lista os comandos |

  Os filtros ficam em `filtros.json`. Só mensagens do seu `TELEGRAM_CHAT_ID`
  são obedecidas (o bot é público).
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
