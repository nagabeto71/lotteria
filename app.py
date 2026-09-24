import math
import random
from collections import Counter
from itertools import combinations

import pandas as pd
import requests
import streamlit as st

# =============================================================
# CONFIG
# =============================================================
LOTERIAS = {
    "Mega-Sena": {
        "min": 1, "max": 60, "qtd": 6,
        "faixas": 6, "tam_faixa": 10,
        "colunas": 6, "linhas": 10,
        "soma": (150, 220), "pares": (2, 4),
        "max_seq": 3, "rep_max": 2,
        "custo": 6.00, "pop_max": 31,
    },
    "Lotofácil": {
        "min": 1, "max": 25, "qtd": 15,
        "faixas": 5, "tam_faixa": 5,
        "colunas": 5, "linhas": 5,
        "soma": (170, 220), "pares": (6, 9),
        "max_seq": 5, "rep_max": 10,
        "custo": 3.50, "pop_max": 25,
    },
    "Quina": {
        "min": 1, "max": 80, "qtd": 5,
        "faixas": 8, "tam_faixa": 10,
        "colunas": 10, "linhas": 8,
        "soma": (150, 250), "pares": (1, 4),
        "max_seq": 2, "rep_max": 2,
        "custo": 3.00, "pop_max": 31,
    },
}

SLUGS = {"Mega-Sena": "megasena", "Lotofácil": "lotofacil", "Quina": "quina"}
PRIMOS = {2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79}

# =============================================================
# POSIÇÃO
# =============================================================
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

# =============================================================
# API
# =============================================================
def buscar_ultimo(loteria):
    slug = SLUGS[loteria]
    for url in [
        f"https://loteriascaixa-api.herokuapp.com/api/{slug}/latest",
        f"https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}",
    ]:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                d = r.json()
                if "concurso" in d:
                    return int(d["concurso"]), [int(x) for x in d["dezenas"]]
                if "numero" in d:
                    return int(d["numero"]), [int(x) for x in d["listaDezenas"]]
        except Exception:
            pass
    return None, None

def buscar_concurso(loteria, c):
    slug = SLUGS[loteria]
    for url in [
        f"https://loteriascaixa-api.herokuapp.com/api/{slug}/{c}",
        f"https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}/{c}",
    ]:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                d = r.json()
                if "concurso" in d:
                    return [int(x) for x in d["dezenas"]]
                if "numero" in d:
                    return [int(x) for x in d["listaDezenas"]]
        except Exception:
            pass
    return None

@st.cache_data(ttl=1800, show_spinner=False)
def baixar_100(loteria):
    ult, _ = buscar_ultimo(loteria)
    if not ult:
        return []
    ini = max(1, ult - 99)
    hist = []
    p = st.progress(0, text="Baixando...")
    total = ult - ini + 1
    for i, c in enumerate(range(ini, ult + 1)):
        s = buscar_concurso(loteria, c)
        if s:
            hist.append(s)
        p.progress((i + 1) / total, text=f"{i+1}/{total}")
    p.empty()
    return hist

# =============================================================
# ANÁLISES
# =============================================================
def analisar(hist, cfg):
    freq = Counter(n for s in hist for n in s)
    atraso = {}
    for n in range(cfg["min"], cfg["max"] + 1):
        atraso[n] = len(hist)
        for i, s in enumerate(reversed(hist)):
            if n in s:
                atraso[n] = i
                break
    return freq, atraso

def distrib_faixa(s, cfg):
    cont = [0] * cfg["faixas"]
    for n in s:
        cont[faixa_de(n, cfg)] += 1
    return cont

def analisar_dist(hist, cfg):
    dists = [distrib_faixa(s, cfg) for s in hist]
    n_f = cfg["faixas"]
    media = [sum(d[i] for d in dists)/len(dists) for i in range(n_f)]
    mini = [min(d[i] for d in dists) for i in range(n_f)]
    maxi = [max(d[i] for d in dists) for i in range(n_f)]
    return {"dists": dists, "media": media, "min": mini, "max": maxi}

def analisar_finais(hist):
    return Counter(n % 10 for s in hist for n in s)

def analisar_cooc(hist, top=30):
    pares = Counter()
    for s in hist:
        for a, b in combinations(sorted(s), 2):
            pares[(a, b)] += 1
    return pares.most_common(top)

def analisar_diag(hist, cfg, top=5):
    dp, ds = Counter(), Counter()
    for s in hist:
        for n in s:
            l, c = coord(n, cfg)
            dp[l - c] += 1
            ds[l + c] += 1
    return {"p": dp.most_common(top), "s": ds.most_common(top),
            "p_set": {d for d, _ in dp.most_common(top)},
            "s_set": {d for d, _ in ds.most_common(top)}}

def score_numeros(freq, atraso, finais, diag, cfg, pesos):
    mf = max(freq.values()) or 1
    ma = max(atraso.values()) or 1
    mfin = max(finais.values()) or 1
    scores = {}
    for n in range(cfg["min"], cfg["max"] + 1):
        f = freq.get(n, 0) / mf
        a = atraso[n] / ma
        p = 1 if n in PRIMOS else 0
        fin = finais.get(n % 10, 0) / mfin
        l, c = coord(n, cfg)
        d_score = 1 if (l-c) in diag["p_set"] else (0.7 if (l+c) in diag["s_set"] else 0)
        scores[n] = (pesos["freq"]*f + pesos["atraso"]*a + pesos["primo"]*p
                     + pesos["final"]*fin + pesos["diag"]*d_score)
    return scores

# =============================================================
# FILTROS
# =============================================================
def ok_soma(a, cfg):
    lo, hi = cfg["soma"]
    return lo <= sum(a) <= hi
def ok_pares(a, cfg):
    lo, hi = cfg["pares"]
    p = sum(1 for n in a if n % 2 == 0)
    return lo <= p <= hi
def ok_seq(a, cfg):
    s = sorted(a); seq = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1] + 1:
            seq += 1
            if seq > cfg["max_seq"]: return False
        else:
            seq = 1
    return True
def ok_rep(a, cfg, ult):
    return len(set(a) & set(ult)) <= cfg["rep_max"]
def ok_term(a):
    return all(v <= 2 for v in Counter(n % 10 for n in a).values())
def ok_pop(a, cfg):
    limite = cfg["pop_max"]
    datas = sum(1 for n in a if n <= limite)
    return datas / len(a) <= 0.6
def ok_dist(a, cfg, d, tol=1):
    dist = distrib_faixa(a, cfg)
    for i in range(cfg["faixas"]):
        lo = max(0, d["min"][i] - tol)
        hi = d["max"][i] + tol
        if not (lo <= dist[i] <= hi):
            return False
    return True
def ok_cooc(a, pares, min_ratio=0.2):
    set_p = {p for p, _ in pares}
    t = f = 0
    for x, y in combinations(sorted(a), 2):
        t += 1
        if (x, y) in set_p:
            f += 1
    return t > 0 and f/t >= min_ratio
def ok_finais(a, finais_fortes):
    return sum(1 for n in a if n % 10 in finais_fortes) >= 2
def ok_diag(a, diag, cfg):
    cont = 0
    for n in a:
        l, c = coord(n, cfg)
        if (l-c) in diag["p_set"] or (l+c) in diag["s_set"]:
            cont += 1
    return cont >= 1

def passa(a, cfg, ult, dist, pares, finais_fortes, diag, flags):
    if not ok_soma(a, cfg): return False
    if not ok_pares(a, cfg): return False
    if not ok_seq(a, cfg): return False
    if not ok_rep(a, cfg, ult): return False
    if not ok_term(a): return False
    if flags.get("pop") and not ok_pop(a, cfg): return False
    if flags.get("dist") and not ok_dist(a, cfg, dist, flags.get("tol", 1)): return False
    if flags.get("cooc") and not ok_cooc(a, pares): return False
    if flags.get("finais") and not ok_finais(a, finais_fortes): return False
    if flags.get("diag") and not ok_diag(a, diag, cfg): return False
    return True

# =============================================================
# GERADOR COM FALLBACK
# =============================================================
def gerar_um(scores, cfg, ult, dist, pares, finais_fortes, diag, flags):
    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    corte = max(cfg["qtd"] * 3, int(len(ranking) * 0.7))
    pool = [n for n, _ in ranking[:corte]]
    pesos_pool = [scores[n] for n in pool]
    for _ in range(3000):
        a = sorted(random.choices(pool, weights=pesos_pool, k=cfg["qtd"]))
        if len(set(a)) < cfg["qtd"]: continue
        if passa(a, cfg, ult, dist, pares, finais_fortes, diag, flags):
            return a
    return None

def gerar_muitos(scores, cfg, ult, dist, pares, finais_fortes, diag, n, flags):
    apostas, vistos = [], set()
    falhas = 0
    max_falhas = 500

    for _ in range(n * 100):
        if len(apostas) >= n: break
        a = gerar_um(scores, cfg, ult, dist, pares, finais_fortes, diag, flags)
        if a and tuple(a) not in vistos:
            apostas.append(a); vistos.add(tuple(a)); falhas = 0
        else:
            falhas += 1
            if falhas > max_falhas:
                break

    # fallback 1: sem filtros extras
    if len(apostas) < n:
        flags2 = dict(flags)
        flags2["pop"] = False
        flags2["cooc"] = False
        flags2["finais"] = False
        flags2["diag"] = False
        for _ in range((n - len(apostas)) * 100):
            if len(apostas) >= n: break
            a = gerar_um(scores, cfg, ult, dist, pares, finais_fortes, diag, flags2)
            if a and tuple(a) not in vistos:
                apostas.append(a); vistos.add(tuple(a))

    # fallback 2: sem filtros de distribuição
    if len(apostas) < n:
        flags3 = dict(flags2)
        flags3["dist"] = False
        for _ in range((n - len(apostas)) * 100):
            if len(apostas) >= n: break
            a = gerar_um(scores, cfg, ult, dist, pares, finais_fortes, diag, flags3)
            if a and tuple(a) not in vistos:
                apostas.append(a); vistos.add(tuple(a))

    return apostas

# =============================================================
# INTERFACE
# =============================================================
st.set_page_config(page_title="Loteria Engine v7", page_icon="🎲", layout="wide")
st.title("🎲 Loteria Engine")
st.caption("Análise dos últimos 100 concursos. Loterias são aleatórias — isto não garante prêmios.")

with st.sidebar:
    st.header("⚙️ Configurações")
    loteria = st.selectbox("Loteria", list(LOTERIAS.keys()))
    if st.button("🔄 Atualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("Pesos dos scores")
    pesos = {
        "freq":   st.slider("Frequência", 0.0, 1.0, 0.30, 0.05),
        "atraso": st.slider("Atraso",     0.0, 1.0, 0.30, 0.05),
        "primo":  st.slider("Primos",     0.0, 1.0, 0.05, 0.05),
        "final":  st.slider("Finais",     0.0, 1.0, 0.15, 0.05),
        "diag":   st.slider("Diagonais",  0.0, 1.0, 0.20, 0.05),
    }

    st.divider()
    st.subheader("Filtros")
    fl_dist   = st.checkbox("Seguir distribuição por faixa", value=True)
    fl_tol    = st.slider("Tolerância por faixa", 0, 2, 2, 1, disabled=not fl_dist)
    fl_pop    = st.checkbox("Evitar populares (≤31)", value=True)
    fl_cooc   = st.checkbox("🔗 Pares que saem juntos", value=False)
    fl_finais = st.checkbox("🔢 Finais quentes", value=False)
    fl_diag   = st.checkbox("↗️ Diagonais dominantes", value=False)

cfg = LOTERIAS[loteria]

st.subheader("📡 Baixando dados oficiais")
hist = baixar_100(loteria)

if not hist:
    st.error("❌ Não foi possível baixar. Tente novamente.")
    st.stop()

st.success(f"✅ {len(hist)} concursos baixados")

# análises
freq, atraso = analisar(hist, cfg)
dist_stats = analisar_dist(hist, cfg)
finais_stats = analisar_finais(hist)
finais_fortes = {f for f, _ in finais_stats.most_common(5)}
pares_fortes = analisar_cooc(hist, 30)
diag_stats = analisar_diag(hist, cfg)

scores = score_numeros(freq, atraso, finais_stats, diag_stats, cfg, pesos)

# métricas topo
c1, c2, c3, c4 = st.columns(4)
c1.metric("Concursos", len(hist))
c2.metric("Faixa", f"{cfg['min']}–{cfg['max']}")
c3.metric("Dezenas", cfg["qtd"])
c4.metric("Chance tudo", f"1 em {math.comb(cfg['max']-cfg['min']+1, cfg['qtd']):,}".replace(",","."))

# abas
tab_gerar, tab_analises = st.tabs(["🎰 Gerar", "📊 Análises"])

with tab_gerar:
    qtd = st.number_input("Quantos jogos?", 1, 1000, 5, 1)

    if st.button(f"🎰 GERAR {qtd} JOGOS", type="primary"):
        flags = {
            "pop": fl_pop, "dist": fl_dist, "tol": fl_tol,
            "cooc": fl_cooc, "finais": fl_finais, "diag": fl_diag,
        }
        with st.spinner("Gerando..."):
            apostas = gerar_muitos(
                scores, cfg, hist[-1], dist_stats, pares_fortes,
                finais_fortes, diag_stats, int(qtd), flags,
            )

        if not apostas:
            st.error("❌ Nenhum jogo gerado. Desative alguns filtros e tente de novo.")
        else:
            if len(apostas) < qtd:
                st.warning(f"⚠️ Filtros restritivos: {len(apostas)} de {qtd} jogos gerados (relaxados automaticamente).")
            else:
                st.success(f"✅ {len(apostas)} jogos gerados!")

            df = pd.DataFrame({
                "Jogo": range(1, len(apostas) + 1),
                "Dezenas": [" - ".join(f"{n:02d}" for n in a) for a in apostas],
                "Distrib.": ["-".join(str(x) for x in distrib_faixa(a, cfg)) for a in apostas],
                "Soma": [sum(a) for a in apostas],
                "Pares": [sum(1 for n in a if n % 2 == 0) for a in apostas],
                "Primos": [sum(1 for n in a if n in PRIMOS) for a in apostas],
                "≤31": [sum(1 for n in a if n <= 31) for a in apostas],
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("📥 CSV",
                               data=df.to_csv(index=False).encode("utf-8"),
                               file_name=f"jogos_{loteria}_{len(apostas)}.csv",
                               mime="text/csv")
            custo = len(apostas) * cfg.get("custo", 5)
            st.info(f"💰 Custo estimado: R$ {custo:.2f}")

with tab_analises:
    st.subheader("📊 Distribuição por faixa")
    labels = [nome_faixa(i, cfg) for i in range(cfg["faixas"])]
    st.dataframe(pd.DataFrame({
        "Faixa": labels,
        "Média": [round(x, 2) for x in dist_stats["media"]],
        "Mín": dist_stats["min"], "Máx": dist_stats["max"],
    }), use_container_width=True, hide_index=True)

    st.subheader("🔢 Finais (0-9)")
    st.dataframe(pd.DataFrame([
        {"Final": f, "Freq": finais_stats.get(f, 0),
         "🔥": "sim" if f in finais_fortes else ""}
        for f in range(10)
    ]), use_container_width=True, hide_index=True)

    st.subheader("🔗 Top 15 pares que saem juntos")
    st.dataframe(pd.DataFrame([
        {"Par": f"{a:02d} + {b:02d}", "Vezes": n}
        for (a, b), n in pares_fortes[:15]
    ]), use_container_width=True, hide_index=True)

    st.subheader("🔥 Quentes e ❄️ Frios")
    dfq = pd.DataFrame({
        "Número": list(range(cfg["min"], cfg["max"]+1)),
        "Freq": [freq.get(n, 0) for n in range(cfg["min"], cfg["max"]+1)],
        "Atraso": [atraso[n] for n in range(cfg["min"], cfg["max"]+1)],
    })
    st.dataframe(dfq, use_container_width=True, hide_index=True)

st.divider()
st.caption("⚠️ Este app NÃO prevê resultados e NÃO aumenta suas chances. Loterias são aleatórias.")
