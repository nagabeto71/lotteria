import math
import random
from collections import Counter

import pandas as pd
import requests
import streamlit as st

# ---------- CONFIG ----------
LOTERIAS = {
    "Mega-Sena": {"min": 1, "max": 60, "qtd": 6,
                  "soma": (150, 220), "pares": (2, 4),
                  "custo": 6.00},
    "Lotofácil": {"min": 1, "max": 25, "qtd": 15,
                  "soma": (170, 220), "pares": (6, 9),
                  "custo": 3.50},
    "Quina":     {"min": 1, "max": 80, "qtd": 5,
                  "soma": (150, 250), "pares": (1, 4),
                  "custo": 3.00},
}
SLUGS = {"Mega-Sena": "megasena", "Lotofácil": "lotofacil", "Quina": "quina"}
PRIMOS = {2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79}

# ---------- API ----------
def buscar_ultimo(loteria):
    slug = SLUGS[loteria]
    for url in [
        f"https://loteriascaixa-api.herokuapp.com/api/{slug}/latest",
        f"https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}",
    ]:
        try:
            r = requests.get(url, timeout=15,
                             headers={"User-Agent": "Mozilla/5.0"})
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
            r = requests.get(url, timeout=15,
                             headers={"User-Agent": "Mozilla/5.0"})
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

# ---------- ANÁLISE ----------
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

def score_numeros(freq, atraso, cfg):
    mf = max(freq.values()) or 1
    ma = max(atraso.values()) or 1
    scores = {}
    for n in range(cfg["min"], cfg["max"] + 1):
        f = freq.get(n, 0) / mf
        a = atraso[n] / ma
        p = 1 if n in PRIMOS else 0
        scores[n] = 0.4 * f + 0.4 * a + 0.2 * p
    return scores

# ---------- GERAR ----------
def gerar_um(scores, cfg, ultimo):
    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    corte = max(cfg["qtd"] * 3, int(len(ranking) * 0.7))
    pool = [n for n, _ in ranking[:corte]]
    pesos_pool = [scores[n] for n in pool]

    for _ in range(5000):
        a = sorted(random.choices(pool, weights=pesos_pool, k=cfg["qtd"]))
        if len(set(a)) < cfg["qtd"]:
            continue
        # filtros básicos
        lo, hi = cfg["soma"]
        if not (lo <= sum(a) <= hi):
            continue
        lo, hi = cfg["pares"]
        p = sum(1 for n in a if n % 2 == 0)
        if not (lo <= p <= hi):
            continue
        if len(set(a) & set(ultimo)) > 2:
            continue
        # sem 4+ sequência
        s = sorted(a)
        seq = 1
        ok = True
        for i in range(1, len(s)):
            if s[i] == s[i-1] + 1:
                seq += 1
                if seq > 3:
                    ok = False
                    break
            else:
                seq = 1
        if not ok:
            continue
        return a
    return None

def gerar_muitos(scores, cfg, ultimo, n):
    apostas = []
    vistos = set()
    for _ in range(n * 50):
        if len(apostas) >= n:
            break
        a = gerar_um(scores, cfg, ultimo)
        if a and tuple(a) not in vistos:
            apostas.append(a)
            vistos.add(tuple(a))
    return apostas

# =============================================================
# INTERFACE
# =============================================================
st.set_page_config(page_title="Loteria Engine", page_icon="🎲", layout="wide")
st.title("🎲 Loteria Engine")
st.caption("Análise dos últimos 100 concursos. Loterias são aleatórias — isto não garante prêmios.")

with st.sidebar:
    st.header("Configurações")
    loteria = st.selectbox("Loteria", list(LOTERIAS.keys()))
    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

cfg = LOTERIAS[loteria]

st.subheader("📡 Baixando dados oficiais")
hist = baixar_100(loteria)

if not hist:
    st.error("❌ Não foi possível baixar os dados. Tente novamente.")
    st.stop()

st.success(f"✅ {len(hist)} concursos baixados")

freq, atraso = analisar(hist, cfg)
scores = score_numeros(freq, atraso, cfg)

# métricas
c1, c2, c3 = st.columns(3)
c1.metric("Concursos", len(hist))
c2.metric("Último", len(hist))
c3.metric("Combinações", f"{math.comb(cfg['max']-cfg['min']+1, cfg['qtd']):,}".replace(",","."))

st.divider()
st.subheader("🎰 Gerar jogos")

qtd = st.number_input("Quantos jogos?", 1, 1000, 5, 1)

if st.button(f"🎰 GERAR {qtd} JOGOS", type="primary"):
    with st.spinner("Gerando..."):
        apostas = gerar_muitos(scores, cfg, hist[-1], int(qtd))

    if not apostas:
        st.error("❌ Não consegui gerar. Tente outra quantidade.")
    else:
        st.success(f"✅ {len(apostas)} jogos gerados!")
        df = pd.DataFrame({
            "Jogo": range(1, len(apostas) + 1),
            "Dezenas": [" - ".join(f"{n:02d}" for n in a) for a in apostas],
            "Soma": [sum(a) for a in apostas],
            "Pares": [sum(1 for n in a if n % 2 == 0) for a in apostas],
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("📥 CSV",
                           data=df.to_csv(index=False).encode("utf-8"),
                           file_name=f"jogos_{loteria}.csv",
                           mime="text/csv")
