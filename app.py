"""
=============================================================
 LOTERIA ENGINE v6 — Análises Avançadas
=============================================================
 Análises:
 - Frequência, atraso, primos
 - Faixas (1-10, 11-20, ...) e colunas
 - Distribuição histórica por faixa
 - 🔗 Coocorrência (números que saem juntos)
 - 🔢 Dezenas finais (0-9)
 - ↗️ Diagonais dominantes
=============================================================
 ⚠️  Loterias são aleatórias. Este app NÃO prevê resultados
     e NÃO aumenta a chance de acertar.
=============================================================
"""

import math
import random
from collections import Counter, defaultdict
from itertools import combinations

import pandas as pd
import requests
import streamlit as st


JANELA_FIXA = 100

LOTERIAS = {
    "Mega-Sena": {
        "min": 1, "max": 60, "qtd": 6,
        "faixas": 6, "tam_faixa": 10,
        "colunas": 6, "linhas": 10,
        "soma_ideal": (150, 220),
        "pares_ideal": (2, 4),
        "max_seq": 3, "repetidas_max": 2,
        "faixa_min": 0, "faixa_max": 3,
        "coluna_min": 0, "coluna_max": 3,
        "diagonal_max": 3, "linha_max": 2,
        "custo_aposta": 6.00,
        "populares_max": 31,
    },
    "Lotofácil": {
        "min": 1, "max": 25, "qtd": 15,
        "faixas": 5, "tam_faixa": 5,
        "colunas": 5, "linhas": 5,
        "soma_ideal": (170, 220),
        "pares_ideal": (6, 9),
        "max_seq": 5, "repetidas_max": 10,
        "faixa_min": 2, "faixa_max": 5,
        "coluna_min": 2, "coluna_max": 5,
        "diagonal_max": 5, "linha_max": 5,
        "custo_aposta": 3.50,
        "populares_max": 25,
    },
    "Quina": {
        "min": 1, "max": 80, "qtd": 5,
        "faixas": 8, "tam_faixa": 10,
        "colunas": 10, "linhas": 8,
        "soma_ideal": (150, 250),
        "pares_ideal": (1, 4),
        "max_seq": 2, "repetidas_max": 2,
        "faixa_min": 0, "faixa_max": 2,
        "coluna_min": 0, "coluna_max": 2,
        "diagonal_max": 2, "linha_max": 2,
        "custo_aposta": 3.00,
        "populares_max": 31,
    },
}

PRIMOS = {2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79}
SLUGS = {"Mega-Sena": "megasena", "Lotofácil": "lotofacil", "Quina": "quina"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LoteriaEngine/6.0)"}


# ---------- PROBABILIDADES ----------
def prob_total(cfg):
    return math.comb(cfg["max"] - cfg["min"] + 1, cfg["qtd"])

def prob_parcial(cfg, acertos):
    N = cfg["max"] - cfg["min"] + 1
    K = cfg["qtd"]
    try:
        return (math.comb(K, acertos) * math.comb(N - K, K - acertos)) / math.comb(N, K)
    except Exception:
        return 0.0


# ---------- POSIÇÃO ----------
def faixa_de(n, cfg):  return (n - cfg["min"]) // cfg["tam_faixa"]
def coluna_de(n, cfg): return (n - cfg["min"]) % cfg["colunas"]
def linha_de(n, cfg):  return (n - cfg["min"]) // cfg["colunas"]

def coord(n, cfg):
    idx = n - cfg["min"]
    return idx // cfg["colunas"], idx % cfg["colunas"]

def nome_faixa(i, cfg):
    lo = cfg["min"] + i * cfg["tam_faixa"]
    hi = min(lo + cfg["tam_faixa"] - 1, cfg["max"])
    return f"{lo}-{hi}"


# ---------- API ----------
def _get_json(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def buscar_ultimo(loteria):
    slug = SLUGS[loteria]
    for url in [
        f"https://loteriascaixa-api.herokuapp.com/api/{slug}/latest",
        f"https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}",
    ]:
        d = _get_json(url)
        if not d: continue
        if "concurso" in d:
            return {"concurso": int(d["concurso"]), "dezenas": [int(x) for x in d["dezenas"]]}
        if "numero" in d:
            return {"concurso": int(d["numero"]), "dezenas": [int(x) for x in d.get("listaDezenas", [])]}
    return None

def buscar_concurso(loteria, concurso):
    slug = SLUGS[loteria]
    for url in [
        f"https://loteriascaixa-api.herokuapp.com/api/{slug}/{concurso}",
        f"https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}/{concurso}",
    ]:
        d = _get_json(url)
        if not d: continue
        if "concurso" in d:
            return {"concurso": int(d["concurso"]), "dezenas": [int(x) for x in d["dezenas"]]}
        if "numero" in d:
            return {"concurso": int(d["numero"]), "dezenas": [int(x) for x in d.get("listaDezenas", [])]}
    return None

def buscar_ultimos_100(loteria):
    ultimo = buscar_ultimo(loteria)
    if not ultimo:
        return [], None, None
    fim = ultimo["concurso"]
    inicio = max(1, fim - JANELA_FIXA + 1)
    historico = []
    progresso = st.progress(0, text=f"Baixando concursos {inicio} a {fim}...")
    total = fim - inicio + 1
    for i, c in enumerate(range(inicio, fim + 1)):
        s = buscar_concurso(loteria, c)
        if s and s["dezenas"]:
            historico.append(s["dezenas"])
        progresso.progress((i + 1) / total, text=f"Concurso {c} ({i+1}/{total})")
    progresso.empty()
    return historico, inicio, fim


# =============================================================
# ANÁLISES
# =============================================================
def analisar_numeros(historico, cfg):
    freq = Counter(n for s in historico for n in s)
    atraso = {}
    for n in range(cfg["min"], cfg["max"] + 1):
        atraso[n] = len(historico)
        for i, s in enumerate(reversed(historico)):
            if n in s:
                atraso[n] = i
                break
    return freq, atraso


def distrib_faixa(sorteio, cfg):
    cont = [0] * cfg["faixas"]
    for n in sorteio:
        cont[faixa_de(n, cfg)] += 1
    return cont


def analisar_distribuicoes(historico, cfg):
    dists = [distrib_faixa(s, cfg) for s in historico]
    assinaturas = Counter(tuple(d) for d in dists)
    n_faixas = cfg["faixas"]
    media = [sum(d[i] for d in dists) / len(dists) for i in range(n_faixas)]
    minimo = [min(d[i] for d in dists) for i in range(n_faixas)]
    maximo = [max(d[i] for d in dists) for i in range(n_faixas)]
    return {
        "por_sorteio": dists,
        "assinaturas": assinaturas,
        "media": media, "min": minimo, "max": maximo,
        "top_assinaturas": assinaturas.most_common(10),
    }


def assinatura_bate(aposta, cfg, dist_stats, tolerancia=1):
    dist = distrib_faixa(aposta, cfg)
    for i in range(cfg["faixas"]):
        lo = max(0, dist_stats["min"][i] - tolerancia)
        hi = dist_stats["max"][i] + tolerancia
        if not (lo <= dist[i] <= hi):
            return False
    return True


# ---------- 🔗 COOCORRÊNCIA ----------
def analisar_coocorrencia(historico, top_n=30):
    """
    Retorna os top N pares de números que mais saíram juntos.
    """
    pares = Counter()
    for s in historico:
        for a, b in combinations(sorted(s), 2):
            pares[(a, b)] += 1
    return pares.most_common(top_n)


def score_coocorrencia(aposta, pares_fortes, set_pares=None):
    """
    Para cada par da aposta, verifica se é um par "forte" (coocorrente).
    Retorna a proporção de pares fortes dentro da aposta.
    """
    if set_pares is None:
        set_pares = {p for p, _ in pares_fortes}
    total_pares = 0
    fortes = 0
    for a, b in combinations(sorted(aposta), 2):
        total_pares += 1
        if (a, b) in set_pares:
            fortes += 1
    return fortes / total_pares if total_pares > 0 else 0


# ---------- 🔢 DEZENAS FINAIS ----------
def final_de(n):
    return n % 10


def analisar_finais(historico, cfg):
    """Frequência de cada final (0-9)."""
    finais = Counter(final_de(n) for s in historico for n in s)
    return finais


def filtro_finais(aposta, finais_fortes, min_fortes=2):
    """
    Exige que pelo menos min_fortes dezenas da aposta terminem em finais quentes.
    """
    qtd = sum(1 for n in aposta if final_de(n) in finais_fortes)
    return qtd >= min_fortes


# ---------- ↗️ DIAGONAIS DOMINANTES ----------
def diagonal_principal(n, cfg):
    """Retorna índice da diagonal principal (linha - coluna)."""
    l, c = coord(n, cfg)
    return l - c


def diagonal_secundaria(n, cfg):
    l, c = coord(n, cfg)
    return l + c


def analisar_diagonais(historico, cfg, top_n=5):
    """Descobre as diagonais principais e secundárias mais frequentes."""
    diag_p = Counter()
    diag_s = Counter()
    for s in historico:
        for n in s:
            diag_p[diagonal_principal(n, cfg)] += 1
            diag_s[diagonal_secundaria(n, cfg)] += 1
    return {
        "principal": diag_p.most_common(top_n),
        "secundaria": diag_s.most_common(top_n),
        "diag_p_full": diag_p,
        "diag_s_full": diag_s,
    }


def filtro_diagonais_fortes(aposta, diag_stats, cfg, min_numeros=1):
    """
    Exige que ao menos N números estejam nas diagonais mais frequentes.
    """
    diag_p_top = {d for d, _ in diag_stats["principal"]}
    diag_s_top = {d for d, _ in diag_stats["secundaria"]}

    cont = 0
    for n in aposta:
        if diagonal_principal(n, cfg) in diag_p_top:
            cont += 1
        elif diagonal_secundaria(n, cfg) in diag_s_top:
            cont += 1
    return cont >= min_numeros


# ---------- DEMAIS ANÁLISES ----------
def analisar_dimensao(historico, cfg, n_setores, func):
    freq = [0] * n_setores
    recente = [0] * n_setores
    atraso = [len(historico)] * n_setores
    media = cfg["qtd"] / n_setores
    for s in historico:
        for n in s:
            freq[func(n, cfg)] += 1
    for s in historico[-10:]:
        for n in s:
            recente[func(n, cfg)] += 1
    for i in range(n_setores):
        for j, s in enumerate(reversed(historico)):
            if sum(1 for n in s if func(n, cfg) == i) >= media:
                atraso[i] = j
                break
    return {"freq": freq, "recente": recente, "atraso": atraso}


def detectar_padroes(aposta, cfg):
    dp, ds, linhas, colunas = Counter(), Counter(), Counter(), Counter()
    for n in aposta:
        l, c = coord(n, cfg)
        dp[l - c] += 1; ds[l + c] += 1
        linhas[l] += 1; colunas[c] += 1
    total = cfg["max"] + cfg["min"]
    s = set(aposta)
    sim = sum(1 for n in aposta if (total - n) in s and n < total - n)
    return {
        "diag_p": max(dp.values()) if dp else 0,
        "diag_s": max(ds.values()) if ds else 0,
        "linha": max(linhas.values()) if linhas else 0,
        "coluna": max(colunas.values()) if colunas else 0,
        "simetrias": sim,
    }


# ---------- SCORES ----------
def calcular_scores(historico, cfg, pesos, finais_stats=None, diag_stats=None):
    freq, atraso = analisar_numeros(historico, cfg)
    m_fx = analisar_dimensao(historico, cfg, cfg["faixas"], faixa_de)
    m_col = analisar_dimensao(historico, cfg, cfg["colunas"], coluna_de)
    max_f = max(freq.values()) or 1
    max_a = max(atraso.values()) or 1
    max_fx = max(m_fx["freq"]) or 1
    max_col = max(m_col["freq"]) or 1

    # final mais frequente (se disponível)
    if finais_stats:
        max_fin = max(finais_stats.values()) or 1
    else:
        max_fin = 1

    # diagonais fortes
    diag_p_top = set()
    diag_s_top = set()
    if diag_stats:
        diag_p_top = {d for d, _ in diag_stats["principal"]}
        diag_s_top = {d for d, _ in diag_stats["secundaria"]}

    scores = {}
    for n in range(cfg["min"], cfg["max"] + 1):
        f  = freq.get(n, 0) / max_f
        a  = atraso[n] / max_a
        p  = 1 if n in PRIMOS else 0
        fx = m_fx["freq"][faixa_de(n, cfg)] / max_fx
        c  = m_col["freq"][coluna_de(n, cfg)] / max_col

        # final
        fin_score = 0
        if finais_stats:
            fin_score = finais_stats.get(final_de(n), 0) / max_fin

        # diagonal
        diag_score = 0
        if diag_stats:
            if diagonal_principal(n, cfg) in diag_p_top:
                diag_score = 1
            elif diagonal_secundaria(n, cfg) in diag_s_top:
                diag_score = 0.7

        scores[n] = (
            pesos.get("freq", 0) * f
            + pesos.get("atraso", 0) * a
            + pesos.get("primo", 0) * p
            + pesos.get("faixa", 0) * fx
            + pesos.get("coluna", 0) * c
            + pesos.get("final", 0) * fin_score
            + pesos.get("diagonal", 0) * diag_score
        )
    return scores


def score_impopular(aposta, cfg):
    limite = cfg.get("populares_max", 31)
    datas = sum(1 for n in aposta if n <= limite)
    s = sorted(aposta)
    seq = sum(1 for i in range(1, len(s)) if s[i] == s[i-1] + 1)
    penal_d = datas / len(aposta)
    penal_s = min(seq / max(len(aposta) - 1, 1), 1)
    return max(0.0, 1 - 0.7 * penal_d - 0.3 * penal_s)


# ---------- FILTROS BÁSICOS ----------
def f_soma(a, cfg):
    lo, hi = cfg["soma_ideal"]
    return lo <= sum(a) <= hi
def f_pares(a, cfg):
    lo, hi = cfg["pares_ideal"]
    p = sum(1 for n in a if n % 2 == 0)
    return lo <= p <= hi
def f_seq(a, cfg):
    s = sorted(a); seq = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1] + 1:
            seq += 1
            if seq > cfg["max_seq"]: return False
        else: seq = 1
    return True
def f_rep(a, cfg, ultimo):
    return len(set(a) & set(ultimo)) <= cfg["repetidas_max"]
def f_term(a):
    return all(v <= 2 for v in Counter(n % 10 for n in a).values())
def f_faixas(a, cfg):
    cont = [0] * cfg["faixas"]
    for n in a: cont[faixa_de(n, cfg)] += 1
    return all(cfg["faixa_min"] <= c <= cfg["faixa_max"] for c in cont)
def f_colunas(a, cfg):
    cont = [0] * cfg["colunas"]
    for n in a: cont[coluna_de(n, cfg)] += 1
    return all(cfg["coluna_min"] <= c <= cfg["coluna_max"] for c in cont)
def f_diag(a, cfg):
    dp, ds = Counter(), Counter()
    for n in a:
        l, c = coord(n, cfg)
        dp[l - c] += 1; ds[l + c] += 1
    return max(dp.values()) <= cfg["diagonal_max"] and max(ds.values()) <= cfg["diagonal_max"]
def f_linhas(a, cfg):
    return max(Counter(linha_de(n, cfg) for n in a).values()) <= cfg["linha_max"]
def f_sim(a, cfg):
    total = cfg["max"] + cfg["min"]; s = set(a)
    return sum(1 for n in a if (total - n) in s and n < total - n) <= 1
def f_impop(a, cfg, minimo=0.4):
    return score_impopular(a, cfg) >= minimo


def passa_todos(a, cfg, ultimo, dist_stats=None, tolerancia=1,
                usar_dist=True, usar_pop=True,
                pares_fortes=None, usar_cooc=False,
                finais_fortes=None, usar_finais=False,
                diag_stats=None, usar_diag=False):
    conds = [
        f_soma(a, cfg), f_pares(a, cfg), f_seq(a, cfg),
        f_rep(a, cfg, ultimo), f_term(a), f_faixas(a, cfg),
        f_colunas(a, cfg), f_diag(a, cfg), f_linhas(a, cfg), f_sim(a, cfg),
    ]
    if usar_pop:
        conds.append(f_impop(a, cfg))
    if usar_dist and dist_stats:
        conds.append(assinatura_bate(a, cfg, dist_stats, tolerancia))
    if usar_cooc and pares_fortes:
        conds.append(score_coocorrencia(a, pares_fortes) >= 0.3)
    if usar_finais and finais_fortes:
        conds.append(filtro_finais(a, finais_fortes, min_fortes=2))
    if usar_diag and diag_stats:
        conds.append(filtro_diagonais_fortes(a, diag_stats, cfg, min_numeros=1))
    return all(conds)


# ---------- GERADOR ----------
def gerar_aposta(scores, cfg, ultimo, dist_stats, tent=20000,
                 usar_dist=True, usar_pop=True, tolerancia=1,
                 pares_fortes=None, usar_cooc=False,
                 finais_fortes=None, usar_finais=False,
                 diag_stats=None, usar_diag=False):
    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    corte = max(cfg["qtd"] * 3, int(len(ranking) * 0.7))
    pool = [n for n, _ in ranking[:corte]]
    pesos_pool = [scores[n] for n in pool]

    for _ in range(tent):
        a = sorted(random.choices(pool, weights=pesos_pool, k=cfg["qtd"]))
        if len(set(a)) < cfg["qtd"]: continue
        if passa_todos(a, cfg, ultimo, dist_stats, tolerancia,
                       usar_dist, usar_pop,
                       pares_fortes, usar_cooc,
                       finais_fortes, usar_finais,
                       diag_stats, usar_diag):
            return a
    return None


def gerar_massa(scores, cfg, ultimo, dist_stats, n_total,
                usar_dist=True, usar_pop=True, tolerancia=1,
                pares_fortes=None, usar_cooc=False,
                finais_fortes=None, usar_finais=False,
                diag_stats=None, usar_diag=False,
                max_tentativas=None):
    if max_tentativas is None:
        max_tentativas = n_total * 100

    apostas, vistos = [], set()
    tentativas = 0
    falhas = 0
    barra = st.progress(0, text=f"Gerando 0/{n_total}...")

    while len(apostas) < n_total and tentativas < max_tentativas:
        tentativas += 1
        a = gerar_aposta(scores, cfg, ultimo, dist_stats, tent=400,
                         usar_dist=usar_dist, usar_pop=usar_pop,
                         tolerancia=tolerancia,
                         pares_fortes=pares_fortes, usar_cooc=usar_cooc,
                         finais_fortes=finais_fortes, usar_finais=usar_finais,
                         diag_stats=diag_stats, usar_diag=usar_diag)
        if a and tuple(a) not in vistos:
            apostas.append(a); vistos.add(tuple(a)); falhas = 0
            if len(apostas) % 10 == 0 or len(apostas) == n_total:
                barra.progress(len(apostas) / n_total,
                               text=f"Gerando {len(apostas)}/{n_total}...")
        else:
            falhas += 1
            if falhas > 1000:
                break

    barra.empty()
    return apostas, {"solicitados": n_total, "gerados": len(apostas),
                     "tentativas": tentativas}


# =============================================================
# INTERFACE
# =============================================================
st.set_page_config(page_title="Loteria Engine — v6", page_icon="🎲", layout="wide")

st.title("🎲 Loteria Engine — v6")
st.markdown(
    "**Análises avançadas + geração em massa.** "
    "⚠️ *NÃO prevê resultados e NÃO aumenta a chance real de ganhar.*"
)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("⚙️ Configurações")
    loteria = st.selectbox("Loteria", list(LOTERIAS.keys()))

    if st.button("🔄 Atualizar dados", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"📌 Analisando últimos **{JANELA_FIXA}** concursos")

    st.divider()
    st.subheader("Pesos dos scores")
    pesos = {
        "freq":     st.slider("Frequência", 0.0, 1.0, 0.20, 0.05),
        "atraso":   st.slider("Atraso",     0.0, 1.0, 0.20, 0.05),
        "primo":    st.slider("Primos",     0.0, 1.0, 0.05, 0.05),
        "faixa":    st.slider("Faixa",      0.0, 1.0, 0.15, 0.05),
        "coluna":   st.slider("Coluna",     0.0, 1.0, 0.10, 0.05),
        "final":    st.slider("Dezenas finais", 0.0, 1.0, 0.15, 0.05),
        "diagonal": st.slider("Diagonais",  0.0, 1.0, 0.15, 0.05),
    }

    st.divider()
    st.subheader("Filtros de geração")
    usar_dist = st.checkbox("Seguir distribuição por faixa", value=True)
    tolerancia = st.slider("Tolerância por faixa", 0, 2, 1, 1, disabled=not usar_dist)
    usar_pop = st.checkbox("Evitar populares (≤31)", value=True)
    usar_cooc = st.checkbox("🔗 Só pares que costumam sair juntos", value=False)
    usar_finais = st.checkbox("🔢 Priorizar finais quentes", value=False)
    usar_diag = st.checkbox("↗️ Priorizar diagonais dominantes", value=False)

cfg = LOTERIAS[loteria]

# ---------- CARREGAR DADOS ----------
st.subheader("📡 Coleta de dados oficiais")
historico, c_ini, c_fim = buscar_ultimos_100(loteria)

if not historico:
    st.error("❌ Não foi possível baixar o histórico. Tente novamente.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Concursos baixados", len(historico))
c2.metric("Intervalo", f"{c_ini} → {c_fim}")
c3.metric("Última atualização", pd.Timestamp.now().strftime("%d/%m %H:%M"))

# ---------- ANÁLISES ----------
st.divider()
dist_stats = analisar_distribuicoes(historico, cfg)
pares_fortes = analisar_coocorrencia(historico, top_n=30)
finais_stats = analisar_finais(historico, cfg)
diag_stats = analisar_diagonais(historico, cfg, top_n=5)

# finais quentes (top 5)
finais_fortes = set([f for f, _ in finais_stats.most_common(5)])

aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "📊 Distribuição por Faixa",
    "🔗 Coocorrência",
    "🔢 Finais",
    "↗️ Diagonais",
    "🎰 Gerar",
])

# ---------- ABA 1 ----------
with aba1:
    labels = [nome_faixa(i, cfg) for i in range(cfg["faixas"])]
    st.subheader("Média por faixa (últimos 100)")
    st.dataframe(pd.DataFrame({
        "Faixa": labels,
        "Média": [round(x, 2) for x in dist_stats["media"]],
        "Mín": dist_stats["min"], "Máx": dist_stats["max"],
    }), use_container_width=True, hide_index=True)

    st.subheader("Assinaturas mais frequentes")
    st.dataframe(pd.DataFrame([
        {"Assinatura": "-".join(str(x) for x in a), "Ocorrências": n,
         "%": f"{n/len(historico)*100:.1f}%"}
        for a, n in dist_stats["top_assinaturas"]
    ]), use_container_width=True, hide_index=True)

# ---------- ABA 2 ----------
with aba2:
    st.subheader("🔗 Pares que mais saem juntos")
    st.caption("Top 30 pares mais coocorrentes nos últimos 100 sorteios.")
    st.dataframe(pd.DataFrame([
        {"Par": f"{a:02d} + {b:02d}", "Vezes juntos": n,
         "% dos sorteios": f"{n/len(historico)*100:.0f}%"}
        for (a, b), n in pares_fortes
    ]), use_container_width=True, hide_index=True)

    st.info(
        "💡 Coocorrência é apenas uma medida de **frequência histórica**. "
        "Não significa que esses pares **vão** sair juntos."
    )

# ---------- ABA 3 ----------
with aba3:
    st.subheader("🔢 Dezenas finais (0-9)")
    st.caption("Frequência das terminações nos últimos 100 sorteios.")

    df_fin = pd.DataFrame([
        {"Final": f, "Frequência": finais_stats.get(f, 0),
         "É quente?": "🔥" if f in finais_fortes else ""}
        for f in range(10)
    ])
    st.dataframe(df_fin, use_container_width=True, hide_index=True)
    st.bar_chart(df_fin.set_index("Final")["Frequência"])

# ---------- ABA 4 ----------
with aba4:
    st.subheader("↗️ Diagonais dominantes")
    st.caption(
        "Diagonal principal: l - c (↘). Secundária: l + c (↙). "
        "Índice 0 = diagonal do canto."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.write("**Principal (↘)**")
        st.dataframe(pd.DataFrame([
            {"Diagonal": d, "Frequência": n, "Dezenas":
             ", ".join(str(cfg["min"] + d + k*cfg["colunas"])
                       for k in range(cfg["linhas"])
                       if cfg["min"] + d + k*cfg["colunas"] in range(cfg["min"], cfg["max"]+1))[:60]}
            for d, n in diag_stats["principal"]
        ]), use_container_width=True, hide_index=True)
    with c2:
        st.write("**Secundária (↙)**")
        st.dataframe(pd.DataFrame([
            {"Diagonal": d, "Frequência": n}
            for d, n in diag_stats["secundaria"]
        ]), use_container_width=True, hide_index=True)


# ---------- ABA 5 — GERAR ----------
with aba5:
    st.subheader("🎰 Gerar jogos para o próximo concurso")

    col_qtd, col_btn = st.columns([1, 2])
    with col_qtd:
        qtd_jogos = st.number_input("Quantos jogos?", 1, 5000, 10, 1)
    with col_btn:
        st.write(""); st.write("")
        gerar_click = st.button(
            f"🎰 GERAR {qtd_jogos} JOGOS",
            type="primary", use_container_width=True,
        )

    if gerar_click:
        st.session_state.pop("apostas_v6", None)
        with st.spinner(f"Gerando {qtd_jogos} jogos..."):
            scores = calcular_scores(historico, cfg, pesos, finais_stats, diag_stats)
            apostas, info = gerar_massa(
                scores, cfg, historico[-1], dist_stats,
                n_total=int(qtd_jogos),
                usar_dist=usar_dist, usar_pop=usar_pop, tolerancia=tolerancia,
                pares_fortes=pares_fortes, usar_cooc=usar_cooc,
                finais_fortes=finais_fortes, usar_finais=usar_finais,
                diag_stats=diag_stats, usar_diag=usar_diag,
            )
        st.session_state["apostas_v6"] = apostas
        st.session_state["info_v6"] = info

    if "apostas_v6" in st.session_state:
        apostas = st.session_state["apostas_v6"]
        info = st.session_state["info_v6"]

        if not apostas:
            st.warning(
                "❌ Nenhum jogo com os filtros atuais. "
                "Desative filtros extras ou aumente a tolerância.")
           
