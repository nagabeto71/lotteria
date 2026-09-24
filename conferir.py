import requests
import pandas as pd
import streamlit as st

SLUGS = {"Mega-Sena": "megasena", "Lotofácil": "lotofacil", "Quina": "quina"}

st.set_page_config(page_title="Conferência de Jogos", page_icon="✅", layout="wide")
st.title("✅ Conferir Jogos")
st.caption("Compara seus jogos com o resultado oficial mais recente.")

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("⚙️ Configurações")
    loteria = st.selectbox("Loteria", list(SLUGS.keys()))
    st.divider()
    st.caption("Cole seus jogos abaixo, um por linha.")
    st.caption("Ex: `05 12 23 34 45 56` ou `05,12,23,34,45,56`")

# ---------- API ----------
@st.cache_data(ttl=600, show_spinner=False)
def buscar_resultado(loteria):
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
                    return {
                        "concurso": int(d["concurso"]),
                        "data": d.get("data", ""),
                        "dezenas": sorted(int(x) for x in d["dezenas"]),
                    }
                if "numero" in d:
                    return {
                        "concurso": int(d["numero"]),
                        "data": d.get("dataApuracao", ""),
                        "dezenas": sorted(int(x) for x in d["listaDezenas"]),
                    }
        except Exception:
            pass
    return None

# ---------- RESULTADO ----------
resultado = buscar_resultado(loteria)

if not resultado:
    st.error("❌ Não foi possível baixar o resultado oficial. Tente novamente em alguns minutos.")
    st.stop()

st.subheader(f"🎯 Resultado do concurso {resultado['concurso']}")
st.caption(f"Data: {resultado['data']}")

st.markdown(
    " ".join(
        f"<span style='background:#2c3e50;color:#fff;padding:8px 14px;"
        f"border-radius:8px;font-size:22px;font-weight:bold;margin-right:6px;"
        f"display:inline-block;margin-bottom:6px'>{n:02d}</span>"
        for n in resultado["dezenas"]
    ),
    unsafe_allow_html=True,
)

st.divider()

# ---------- ENTRADA DE JOGOS ----------
st.subheader("📝 Cole seus jogos")
st.caption("Um jogo por linha. Aceita vírgula, espaço ou ponto como separador.")

exemplo = "05 12 23 34 45 56\n01 14 22 33 44 55\n07 18 25 36 47 58"
texto = st.text_area("Seus jogos", value="", height=200, placeholder=exemplo)

if st.button("🔍 Conferir", type="primary"):
    if not texto.strip():
        st.warning("Cole pelo menos um jogo.")
        st.stop()

    # parsing
    jogos = []
    for linha in texto.strip().splitlines():
        linha = linha.strip()
        if not linha:
            continue
        # aceita vírgula, ponto, espaço, tab
        nums_str = (
    linha.replace(",", " ")
         .replace(".", " ")
         .replace("-", " ")
         .replace("\t", " ")
         .split()
)
        try:
            jogo = sorted(int(x) for x in nums_str)
            if len(jogo) < 2:
                continue
            jogos.append(jogo)
        except ValueError:
            st.warning(f"⚠️ Linha ignorada (não numérica): {linha}")
            continue

    if not jogos:
        st.error("Nenhum jogo válido encontrado.")
        st.stop()

    # conferência
    ganhadores = set(resultado["dezenas"])
    linhas = []
    total_acertos = 0

    for i, jogo in enumerate(jogos, 1):
        acertos = sorted(set(jogo) & ganhadores)
        linhas.append({
            "Jogo": i,
            "Dezenas": " - ".join(f"{n:02d}" for n in jogo),
            "Acertos": len(acertos),
            "Números acertados": " ".join(f"{n:02d}" for n in acertos) if acertos else "—",
        })
        total_acertos += len(acertos)

    df = pd.DataFrame(linhas)
    df = df.sort_values("Acertos", ascending=False).reset_index(drop=True)

    st.success(f"✅ {len(jogos)} jogos conferidos")

    # distribuição de acertos
    dist = df["Acertos"].value_counts().sort_index(ascending=False)
    st.subheader("📊 Distribuição de acertos")

    cols = st.columns(len(dist)) if len(dist) <= 6 else st.columns(6)
    for idx, (acertos, qtd) in enumerate(dist.items()):
        with cols[idx % 6]:
            st.metric(f"{acertos} acertos", f"{qtd} jogo(s)")

    # tabela completa
    st.subheader("🎟️ Detalhes por jogo")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # download
    st.download_button(
        "📥 Baixar conferência (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"conferencia_{loteria}_{resultado['concurso']}.csv",
        mime="text/csv",
    )

    # resumo
    st.divider()
    st.subheader("💰 Resumo financeiro")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de jogos", len(jogos))
    c2.metric("Total de acertos", total_acertos)
    c3.metric("Média acertos/jogo", f"{total_acertos/len(jogos):.2f}")

st.divider()
st.caption("⚠️ Conferência manual baseada no resultado oficial. Sempre confira também no site da Caixa.")
