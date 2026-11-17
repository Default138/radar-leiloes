"""
Gera o site: docs/index.html.

É uma página só, sem servidor. Os dados vão "embutidos" na página como
JSON e um pouco de JavaScript faz os filtros. Funciona de dois jeitos:
  - no GitHub Pages (o GitHub publica a pasta docs/ como site)
  - no seu PC, abrindo docs/index.html com dois cliques
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import config

PASTA = Path(__file__).parent / "docs"
ARQUIVO = PASTA / "index.html"

ORDEM_CATEGORIAS = ["Moto", "Carro", "Caminhonete/Utilitário", "Caminhão/Ônibus",
                    "Reboque/Outros", "Leilão de prefeitura"]

MODELO = r"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Radar de Leilões</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏍️</text></svg>">
<style>
  :root { --fundo:#f3f5f7; --cartao:#fff; --texto:#1b2128; --suave:#5d6975;
          --borda:#d9dee4; --destaque:#0b6e4f; --destaque-fundo:#e3f3ec;
          --alerta:#b42318; --aviso:#8a5a00; }
  @media (prefers-color-scheme: dark) {
    :root { --fundo:#12161a; --cartao:#1c2228; --texto:#e7ebee; --suave:#9aa5b0;
            --borda:#2d353d; --destaque:#4cc38a; --destaque-fundo:#173328;
            --alerta:#ff8a80; --aviso:#e3b341; }
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui, "Segoe UI", Roboto, sans-serif;
         background:var(--fundo); color:var(--texto); }
  .largura { max-width:1200px; margin:auto; padding:0 16px; }
  header { padding-top:20px; }
  h1 { margin:0; font-size:1.5rem; }
  .sub { color:var(--suave); font-size:.9rem; margin-top:4px; }

  .filtros { background:var(--cartao); border:1px solid var(--borda); border-radius:12px;
             padding:14px; margin:14px auto 6px; display:grid; gap:12px; }
  .linha { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
  .rotulo { font-size:.8rem; font-weight:600; color:var(--suave);
            text-transform:uppercase; letter-spacing:.03em; min-width:58px; }
  .chip { border:1px solid var(--borda); background:transparent; color:var(--texto);
          border-radius:99px; padding:6px 12px; font-size:.9rem; cursor:pointer; }
  .chip[aria-pressed="true"] { background:var(--destaque-fundo); border-color:var(--destaque);
          color:var(--destaque); font-weight:600; }
  .chip .n { opacity:.7; font-weight:400; margin-left:4px; }
  input, select { padding:8px 10px; border:1px solid var(--borda); border-radius:8px;
          background:var(--cartao); color:var(--texto); font-size:.95rem; }
  input[type=number] { width:110px; }
  #busca { flex:1 1 220px; }
  label.check { font-size:.9rem; display:flex; gap:6px; align-items:center; }
  .limpar { background:none; border:none; color:var(--destaque); cursor:pointer;
            font-size:.9rem; text-decoration:underline; padding:0; }

  .resumo { color:var(--suave); font-size:.9rem; margin:8px auto; }
  main { display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr));
         gap:14px; padding-bottom:40px; }
  .card { background:var(--cartao); border:1px solid var(--borda); border-radius:12px;
          overflow:hidden; display:flex; flex-direction:column; }
  .card img { width:100%; height:170px; object-fit:cover; background:var(--borda); }
  .corpo { padding:12px 14px; display:flex; flex-direction:column; gap:6px; flex:1; }
  .topo { display:flex; justify-content:space-between; gap:8px; align-items:baseline; }
  .titulo { font-weight:600; }
  .valor { font-weight:700; color:var(--destaque); white-space:nowrap; }
  .meta { color:var(--suave); font-size:.85rem; }
  .tag { display:inline-block; font-size:.75rem; padding:2px 8px; border-radius:99px;
         border:1px solid var(--borda); color:var(--suave); margin:0 4px 2px 0; }
  .tag.novo { border-color:var(--destaque); color:var(--destaque); }
  .alerta { color:var(--alerta); font-size:.85rem; }
  .obs { color:var(--aviso); font-size:.82rem; }
  .links { margin-top:auto; padding-top:6px; display:flex; gap:14px; font-size:.9rem; }
  a { color:var(--destaque); }
  .vazio { color:var(--suave); padding:30px 0; }
  footer { color:var(--suave); font-size:.8rem; padding:0 16px 30px; text-align:center; }
</style>
</head>
<body>
<header class="largura">
  <h1>🏍️ Radar de Leilões</h1>
  <div class="sub">Foz do Iguaçu → Cascavel · Receita Federal, PRF e Prefeituras · atualizado em __ATUALIZADO__</div>
</header>

<section class="largura">
  <div class="filtros">
    <div class="linha"><span class="rotulo">Tipo</span><span id="tipos" class="linha"></span></div>
    <div class="linha">
      <span class="rotulo">Preço</span>
      <span>R$</span><input id="minimo" type="number" min="0" step="500" placeholder="mínimo">
      <span>até R$</span><input id="maximo" type="number" min="0" step="500" placeholder="máximo">
      <button class="chip" data-faixa="0-3000">até 3 mil</button>
      <button class="chip" data-faixa="0-6000">até 6 mil</button>
      <button class="chip" data-faixa="0-15000">até 15 mil</button>
      <button class="chip" data-faixa="-">qualquer</button>
    </div>
    <div class="linha">
      <input id="busca" type="search" placeholder="Buscar modelo (ex.: CG, Biz, Gol, 2015)">
      <select id="fonte"><option value="">Todas as fontes</option></select>
      <select id="cidade"><option value="">Todas as cidades</option></select>
      <select id="ordem">
        <option value="data">Ordenar: leilão mais próximo</option>
        <option value="preco">Ordenar: menor preço</option>
        <option value="ano">Ordenar: mais novo</option>
      </select>
    </div>
    <div class="linha">
      <label class="check"><input id="semSucata" type="checkbox" checked> Esconder sucata</label>
      <label class="check"><input id="soBr" type="checkbox" checked> Esconder placa estrangeira</label>
      <button class="limpar" id="limpar">Limpar filtros</button>
    </div>
  </div>
  <div class="resumo" id="resumo"></div>
</section>

<main class="largura" id="lista"></main>
<footer>Dados públicos dos editais. Sempre leia o edital antes de dar lance.</footer>

<script>
const ITENS = __DADOS__;
const CATEGORIAS = __CATEGORIAS__;
const PADRAO = { tipos: ["Moto"], minimo: "", maximo: "__MAXIMO__", busca: "", fonte: "",
                 cidade: "", ordem: "data", semSucata: true, soBr: true };
const $ = id => document.getElementById(id);
const brl = v => v == null ? "—" : v.toLocaleString("pt-BR", {style:"currency", currency:"BRL", maximumFractionDigits:0});
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const ehSucata = i => (i.situacao || "").startsWith("Sucata");

// Filtros escolhidos ficam salvos no navegador (se o navegador permitir).
let estado = { ...PADRAO };
try { Object.assign(estado, JSON.parse(localStorage.getItem("radar-filtros") || "{}")); } catch (e) {}
const salvar = () => { try { localStorage.setItem("radar-filtros", JSON.stringify(estado)); } catch (e) {} };

function quando(iso) {
  if (!iso) return "";
  const d = new Date(iso.replace(" ", "T"));
  const hoje = new Date(); hoje.setHours(0,0,0,0);
  const dia = new Date(d); dia.setHours(0,0,0,0);
  const faltam = Math.round((dia - hoje) / 86400000);
  const txt = d.toLocaleString("pt-BR", {day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit"});
  return `${txt} (${faltam <= 0 ? "hoje" : faltam === 1 ? "amanhã" : "em " + faltam + " dias"})`;
}

// Monta botões de tipo e listas de fonte/cidade a partir dos dados.
for (const cat of CATEGORIAS) {
  const n = ITENS.filter(i => i.categoria === cat).length;
  if (!n) continue;
  $("tipos").insertAdjacentHTML("beforeend",
    `<button class="chip" data-tipo="${esc(cat)}">${esc(cat)}<span class="n">${n}</span></button>`);
}
for (const [campo, sel] of [["fonte", "fonte"], ["cidade", "cidade"]]) {
  for (const v of [...new Set(ITENS.map(i => i[campo]).filter(Boolean))].sort()) {
    $(sel).insertAdjacentHTML("beforeend", `<option>${esc(v)}</option>`);
  }
}

function lerTela() {
  estado.tipos = [...document.querySelectorAll("[data-tipo]")]
    .filter(b => b.getAttribute("aria-pressed") === "true").map(b => b.dataset.tipo);
  for (const id of ["minimo", "maximo", "busca", "fonte", "cidade", "ordem"]) estado[id] = $(id).value;
  for (const id of ["semSucata", "soBr"]) estado[id] = $(id).checked;
}

function mostrarNaTela() {
  document.querySelectorAll("[data-tipo]").forEach(b =>
    b.setAttribute("aria-pressed", estado.tipos.includes(b.dataset.tipo)));
  for (const id of ["minimo", "maximo", "busca", "fonte", "cidade", "ordem"]) $(id).value = estado[id];
  for (const id of ["semSucata", "soBr"]) $(id).checked = estado[id];
  document.querySelectorAll("[data-faixa]").forEach(b =>
    b.setAttribute("aria-pressed", b.dataset.faixa === `${estado.minimo ? estado.minimo : 0}-${estado.maximo}`
      || (b.dataset.faixa === "-" && !estado.minimo && !estado.maximo)));
}

function desenhar() {
  const min = parseFloat(estado.minimo) || 0;
  const max = parseFloat(estado.maximo) || Infinity;
  const busca = estado.busca.trim().toUpperCase();
  let lista = ITENS.filter(i =>
    estado.tipos.includes(i.categoria) &&
    (i.valor_minimo == null || (i.valor_minimo >= min && i.valor_minimo <= max)) &&
    (!estado.fonte || i.fonte === estado.fonte) &&
    (!estado.cidade || i.cidade === estado.cidade) &&
    (!estado.semSucata || !ehSucata(i)) &&
    (!estado.soBr || !i.estrangeira) &&
    (!busca || `${i.titulo} ${i.descricao} ${i.cidade}`.toUpperCase().includes(busca))
  );
  const ordens = {
    data:  (a, b) => (a.data_leilao || "").localeCompare(b.data_leilao || ""),
    preco: (a, b) => (a.valor_minimo ?? 1e12) - (b.valor_minimo ?? 1e12),
    ano:   (a, b) => (b.ano || 0) - (a.ano || 0),
  };
  lista.sort(ordens[estado.ordem] || ordens.data);

  $("resumo").textContent = estado.tipos.length
    ? `${lista.length} resultado(s) de ${ITENS.length} itens coletados`
    : "Escolha pelo menos um tipo de veículo.";
  $("lista").innerHTML = lista.length ? lista.map(i => `
    <article class="card">
      ${i.foto ? `<img src="${esc(i.foto)}" alt="" loading="lazy">` : ""}
      <div class="corpo">
        <div class="topo"><span class="titulo">${esc(i.titulo)}</span>
          <span class="valor">${i.tipo === "leilao" ? "" : brl(i.valor_minimo)}</span></div>
        <div>
          <span class="tag">${esc(i.categoria)}</span><span class="tag">${esc(i.fonte)}</span>
          ${i.novo ? '<span class="tag novo">novo</span>' : ""}
          ${i.situacao ? `<span class="tag">${esc(i.situacao)}</span>` : ""}
        </div>
        <div class="meta">📅 Leilão: ${esc(quando(i.data_leilao))}</div>
        ${i.prazo_propostas ? `<div class="alerta">⏰ Propostas até ${esc(quando(i.prazo_propostas))}</div>` : ""}
        <div class="meta">📍 ${esc(i.patio || i.cidade)}${i.placa ? " · " + esc(i.placa) : ""}</div>
        ${i.tipo === "lote" ? `<div class="meta">🔖 ${esc(i.edital)}</div>` : ""}
        ${i.tipo === "leilao" ? `<div class="meta">${esc((i.descricao || "").slice(0, 220))}</div>` : ""}
        ${i.valor_avaliacao && i.valor_avaliacao !== i.valor_minimo && i.tipo !== "leilao"
          ? `<div class="meta">Avaliação: ${brl(i.valor_avaliacao)}</div>` : ""}
        ${i.obs ? `<div class="obs">⚠️ ${esc(i.obs)}</div>` : ""}
        <div class="links">
          <a href="${esc(i.link)}" target="_blank" rel="noopener">Site do leilão</a>
          <a href="${esc(i.link_edital)}" target="_blank" rel="noopener">Edital</a>
        </div>
      </div>
    </article>`).join("") : (estado.tipos.length ? '<p class="vazio">Nada encontrado com esses filtros.</p>' : "");
}

function atualizar() { lerTela(); salvar(); mostrarNaTela(); desenhar(); }

document.querySelectorAll("[data-tipo]").forEach(b => b.addEventListener("click", () => {
  b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true"); atualizar();
}));
document.querySelectorAll("[data-faixa]").forEach(b => b.addEventListener("click", () => {
  const [mi, ma] = b.dataset.faixa.split("-");
  $("minimo").value = mi === "0" ? "" : mi; $("maximo").value = ma; atualizar();
}));
for (const id of ["minimo", "maximo", "busca", "fonte", "cidade", "ordem", "semSucata", "soBr"]) {
  $(id).addEventListener("input", atualizar);
}
$("limpar").addEventListener("click", () => { estado = { ...PADRAO }; salvar(); mostrarNaTela(); desenhar(); });

mostrarNaTela();
desenhar();
</script>
</body>
</html>
"""


def gerar(linhas):
    # "novo" = apareceu pela primeira vez nos últimos 3 dias.
    limite_novo = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    itens = []
    for linha in linhas:
        item = dict(linha)
        item["estrangeira"] = bool(item["estrangeira"])
        item["novo"] = (item["primeira_vez"] or "") >= limite_novo
        for campo in ("primeira_vez", "ultima_vez", "alertado", "lembrado"):
            item.pop(campo, None)  # o site não precisa disso
        itens.append(item)

    # "</" dentro do JSON poderia fechar a tag <script> antes da hora.
    dados = json.dumps(itens, ensure_ascii=False).replace("</", "<\\/")
    html = (MODELO
            .replace("__DADOS__", dados)
            .replace("__CATEGORIAS__", json.dumps(ORDEM_CATEGORIAS, ensure_ascii=False))
            .replace("__MAXIMO__", str(config.VALOR_MAXIMO))
            .replace("__ATUALIZADO__", datetime.now().strftime("%d/%m/%Y %H:%M")))
    PASTA.mkdir(exist_ok=True)
    ARQUIVO.write_text(html, encoding="utf-8")
    return ARQUIVO
