# appstreamlit_players_compare_2selectors.py
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from io import BytesIO

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Comparativa física - Tracking", layout="wide")
st.title("🏃‍♂️ Comparador de jugadores")

# =========================
# CATÁLOGO (IDs fijos)
# =========================
COMPETITION_CATALOG = {
    "Argentina": {
        "Primera División (1st Phase)": {
            "competition_id": 70,
            "editions": {
                "2018": 140, "2019": 107, "2020": 157, "2021": 293, "2022": 331,
                "2023": 374, "2024": 767, "2025": 1073, "2026": 1390,
            },
        },
        "Primera División (2nd Phase)": {
            "competition_id": 376,
            "editions": {"2024": 865},
        },
        "Primera Nacional": {
            "competition_id": 412,
            "editions": {"2024": 969, "2025": 1059, "2026": 1419},
        },
    },
    "USA": {
        "MLS": {
            "competition_id": 60,
            "editions": {
                "2017": 89, "2018": 99, "2019": 168, "2020": 198, "2021": 235,
                "2022": 360, "2023": 419, "2024": 798, "2025": 1091, "2026": 1393,
            },
        },
    },
    "México": {
        "Liga MX": {
            "competition_id": 97,
            "editions": {
                "2016/2017": 84, "2019/2020": 290, "2020/2021": 200, "2021/2022": 267,
                "2022/2023": 400, "2023/2024": 558, "2024/2025": 922, "2025/2026": 1169,
            },
        },
    },
    "Uruguay": {
        "Primera División": {
            "competition_id": 95,
            "editions": {
                "2019": 197, "2020": 196, "2021": 312, "2022": 359,
                "2023": 418, "2024": 797, "2025": 1090, "2026": 1400,
            },
        },
    },
    "Paraguay": {
        "División Profesional": {
            "competition_id": 140,
            "editions": {"2021": 315, "2022": 354, "2023": 404, "2024": 793, "2025": 1087, "2026": 1383},
        },
    },
}

# =========================
# ALIASES (solo estas métricas quedan)
# =========================
METRIC_ALIASES_ES = {
    "total_distance_full_all": "Distancia total (m)",
    "total_metersperminute_full_all": "Metros por minuto (m)",
    "running_distance_full_all": "Distancia corriendo (B3) (m)",
    "hsr_distance_full_all": "Distancia en HSR (B4) (m)",
    "hsr_count_full_all": "Cantidad de veces que alcanzó HSR (B4)",
    "sprint_distance_full_all": "Distancia en sprint (B5) (m)",
    "sprint_count_full_all": "Cantidad de veces que realizó un sprint (B5)",
    "hi_count_full_all": "Cantidad de veces que alcanzó una alta intensidad (B4 o B5)",
    "hi_distance_full_all": "Distancia en alta intensidad (B4 + B5) (m)",
    "highaccel_count_full_all": "Aceleraciones altas",
    "highdecel_count_full_all": "Desaceleraciones altas",
    "medaccel_count_full_all": "Aceleraciones medias",
    "meddecel_count_full_all": "Desaceleraciones medias",
    "psv99": "Velocidad máxima (PSV99) (km/h)",
    "explacceltohsr_count_full_all": "Aceleraciones explosivas a HSR (B4)",
    "timetohsr": "Tiempo a un HSR (B4) (segundos)",
    "explacceltosprint_count_full_all": "Aceleraciones explosivas a sprint (B5)",
    "timetosprint": "Tiempo a un sprint (B5) (segundos)",
    "cod_count_full_all": "Cambios de dirección",
    "timetohsrpostcod": "Tiempo a un HSR (B4) post cambio de ritmo (segundos)",
    "timetosprintpostcod": "Tiempo a un sprint (B5) post cambio de ritmo (segundos)",
}

ROW_ORDER_ES = [
    "Distancia total (m)",
    "Metros por minuto (m)",
    "Distancia corriendo (B3) (m)",
    "Distancia en HSR (B4) (m)",
    "Cantidad de veces que alcanzó HSR (B4)",
    "Distancia en sprint (B5) (m)",
    "Cantidad de veces que realizó un sprint (B5)",
    "Cantidad de veces que alcanzó una alta intensidad (B4 o B5)",
    "Distancia en alta intensidad (B4 + B5) (m)",
    "Aceleraciones altas",
    "Desaceleraciones altas",
    "Aceleraciones medias",
    "Desaceleraciones medias",
    "Velocidad máxima (PSV99) (km/h)",
    "Aceleraciones explosivas a HSR (B4)",
    "Tiempo a un HSR (B4) (segundos)",
    "Aceleraciones explosivas a sprint (B5)",
    "Tiempo a un sprint (B5) (segundos)",
    "Cambios de dirección",
    "Tiempo a un HSR (B4) post cambio de ritmo (segundos)",
    "Tiempo a un sprint (B5) post cambio de ritmo (segundos)",
]

# =========================
# SESSION STATE INIT
# =========================
for k in ["df_all_a", "df_all_b", "df_players_a", "df_players_b", "meta_a", "meta_b"]:
    if k not in st.session_state:
        st.session_state[k] = None

# =========================
# HELPERS
# =========================
def _resp_to_df(resp) -> pd.DataFrame:
    if isinstance(resp, list):
        return pd.DataFrame(resp)
    if isinstance(resp, dict):
        return pd.json_normalize(resp)
    return pd.read_csv(BytesIO(resp))

def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "match_date" in df.columns:
        df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce").dt.date
    for c in ["match_id", "team_id", "player_id"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "minutes_full_all" in df.columns:
        df["minutes_full_all"] = pd.to_numeric(df["minutes_full_all"], errors="coerce")
    if "player_short_name" in df.columns and "player_name" in df.columns:
        df["player_short_name"] = df["player_short_name"].fillna(df["player_name"])
    return df

@st.cache_data(show_spinner=True)
def fetch_physical_one(competition_id: int, competition_edition_id: int, cache_date: str) -> pd.DataFrame:
    from skillcorner.client import SkillcornerClient
    client = SkillcornerClient(
        username=st.secrets["SKILLCORNER_USERNAME"],
        password=st.secrets["SKILLCORNER_PASSWORD"],
    )
    params = {"competition": [competition_id], "competition_edition": [competition_edition_id]}
    resp = client.get_physical(params=params, raise_for_status=True)
    df = _resp_to_df(resp)
    df = _coerce_types(df)
    df["competition_id"] = competition_id
    df["competition_edition_id"] = competition_edition_id
    return df

def build_players_from_df_all(df_all: pd.DataFrame) -> pd.DataFrame:
    if df_all is None or df_all.empty or "player_id" not in df_all.columns:
        return pd.DataFrame()

    keep = [c for c in ["player_id", "player_short_name", "player_name", "team_id", "team_name", "minutes_full_all"] if c in df_all.columns]
    d = df_all[keep].copy()

    if "minutes_full_all" in d.columns:
        d["minutes_full_all"] = pd.to_numeric(d["minutes_full_all"], errors="coerce").fillna(0)
    else:
        d["minutes_full_all"] = 0

    players = (
        d.groupby(["player_id", "team_id"], as_index=False)
         .agg({
             "player_short_name": "first" if "player_short_name" in d.columns else "first",
             "player_name": "first" if "player_name" in d.columns else "first",
             "team_name": "first" if "team_name" in d.columns else "first",
             "minutes_full_all": "sum",
         })
    )

    players = players.sort_values(["minutes_full_all", "team_name", "player_short_name"], ascending=[False, True, True]).reset_index(drop=True)
    players["label"] = (
        players["player_short_name"].fillna(players["player_name"]).fillna("—").astype(str)
        + " — " + players["team_name"].fillna("—").astype(str)
        + "  |  " + players["minutes_full_all"].round(0).astype(int).astype(str) + " min"
    )
    return players

def _filter_player_rows(df_all: pd.DataFrame, player_id: int, team_id: int, min_mp: float, max_mp: float) -> pd.DataFrame:
    d = df_all.copy()
    d["minutes_full_all"] = pd.to_numeric(d.get("minutes_full_all"), errors="coerce")
    d = d[(d["player_id"] == player_id) & (d["team_id"] == team_id)].copy()
    d = d[d["minutes_full_all"].between(min_mp, max_mp, inclusive="both")].copy()
    return d

def _compute_means_for_player(d: pd.DataFrame) -> dict:
    out = {}
    for metric_key in METRIC_ALIASES_ES.keys():
        if metric_key in d.columns:
            out[metric_key] = pd.to_numeric(d[metric_key], errors="coerce").mean()
        else:
            out[metric_key] = np.nan
    return out

def _build_comparison_table(means_a: dict, means_b: dict, label_a: str, label_b: str) -> pd.DataFrame:
    rows = []
    for metric_key, alias_es in METRIC_ALIASES_ES.items():
        rows.append({"Métrica": alias_es, label_a: means_a.get(metric_key, np.nan), label_b: means_b.get(metric_key, np.nan)})
    df_cmp = pd.DataFrame(rows)
    for c in [label_a, label_b]:
        df_cmp[c] = pd.to_numeric(df_cmp[c], errors="coerce").round(2)

    order_map = {name: i for i, name in enumerate(ROW_ORDER_ES)}
    df_cmp["_ord"] = df_cmp["Métrica"].map(order_map).fillna(9999).astype(int)
    df_cmp = df_cmp.sort_values("_ord").drop(columns=["_ord"]).reset_index(drop=True)
    return df_cmp

def _styler_bold_max(df_cmp: pd.DataFrame, col_a: str, col_b: str):
    def bold_row(row):
        styles = [""] * len(row)
        a = pd.to_numeric(row[col_a], errors="coerce")
        b = pd.to_numeric(row[col_b], errors="coerce")
        idx_a = row.index.get_loc(col_a)
        idx_b = row.index.get_loc(col_b)
        if pd.notna(a) and pd.notna(b):
            if a > b:
                styles[idx_a] = "font-weight: 700;"
            elif b > a:
                styles[idx_b] = "font-weight: 700;"
        elif pd.notna(a) and pd.isna(b):
            styles[idx_a] = "font-weight: 700;"
        elif pd.isna(a) and pd.notna(b):
            styles[idx_b] = "font-weight: 700;"
        return styles

    sty = df_cmp.style.apply(bold_row, axis=1)
    sty = sty.format({col_a: "{:.2f}", col_b: "{:.2f}"}, na_rep="—")
    return sty

def _mins_sum(d: pd.DataFrame) -> float:
    if d is None or d.empty:
        return 0.0
    return float(pd.to_numeric(d.get("minutes_full_all"), errors="coerce").fillna(0).sum())

# =========================
# TOP BUTTONS
# =========================
b1, b2, b3 = st.columns([5, 1, 1])
with b2:
    if st.button("🔄 Limpiar consulta"):
        try:
            fetch_physical_one.clear()
        except Exception:
            pass
        st.toast("Cache limpiada.")
with b3:
    if st.button("🧹 Reset selección"):
        for k in ["df_all_a", "df_all_b", "df_players_a", "df_players_b", "meta_a", "meta_b"]:
            st.session_state[k] = None
        st.rerun()

today_key = date.today().isoformat()

# =========================
# UI: SELECTORES A/B (siempre visibles)
# =========================
st.subheader("Seleccione competición para cada jugador (A y B)")

left, right = st.columns(2, vertical_alignment="top")

with left:
    st.markdown("### Jugador A — Competición")
    a_country = st.selectbox("A - País/Liga", list(COMPETITION_CATALOG.keys()), index=0, key="a_country")
    a_comp_label = st.selectbox("A - Competencia", list(COMPETITION_CATALOG[a_country].keys()), index=0, key="a_comp")
    a_info = COMPETITION_CATALOG[a_country][a_comp_label]
    a_competition_id = a_info["competition_id"]
    a_edition_label = st.selectbox("A - Edición", list(a_info["editions"].keys()), index=0, key="a_edition")
    a_competition_edition_id = a_info["editions"][a_edition_label]
    st.caption(f"A: competition_id={a_competition_id} | competition_edition_id={a_competition_edition_id}")

with right:
    st.markdown("### Jugador B — Competición")
    b_country = st.selectbox("B - País/Liga", list(COMPETITION_CATALOG.keys()), index=0, key="b_country")
    b_comp_label = st.selectbox("B - Competencia", list(COMPETITION_CATALOG[b_country].keys()), index=0, key="b_comp")
    b_info = COMPETITION_CATALOG[b_country][b_comp_label]
    b_competition_id = b_info["competition_id"]
    b_edition_label = st.selectbox("B - Edición", list(b_info["editions"].keys()), index=0, key="b_edition")
    b_competition_edition_id = b_info["editions"][b_edition_label]
    st.caption(f"B: competition_id={b_competition_id} | competition_edition_id={b_competition_edition_id}")

# Botón descarga: guarda en session_state (clave para que NO "vuelva arriba")
do_fetch = st.button("📥 Traer información")

if do_fetch:
    with st.spinner("Descargando para A…"):
        df_all_a = fetch_physical_one(a_competition_id, a_competition_edition_id, cache_date=today_key)
    with st.spinner("Descargando para B…"):
        df_all_b = fetch_physical_one(b_competition_id, b_competition_edition_id, cache_date=today_key)

    if df_all_a.empty:
        st.error("A: La API devolvió vacío para esta edición.")
        st.stop()
    if df_all_b.empty:
        st.error("B: La API devolvió vacío para esta edición.")
        st.stop()

    st.session_state["df_all_a"] = df_all_a
    st.session_state["df_all_b"] = df_all_b
    st.session_state["df_players_a"] = build_players_from_df_all(df_all_a)
    st.session_state["df_players_b"] = build_players_from_df_all(df_all_b)

    st.session_state["meta_a"] = {"country": a_country, "comp": a_comp_label, "edition": a_edition_label}
    st.session_state["meta_b"] = {"country": b_country, "comp": b_comp_label, "edition": b_edition_label}

# =========================
# SI YA HAY DATA EN SESSION_STATE => MOSTRAR SELECTORES DE JUGADORES
# =========================
df_all_a = st.session_state["df_all_a"]
df_all_b = st.session_state["df_all_b"]
df_players_a = st.session_state["df_players_a"]
df_players_b = st.session_state["df_players_b"]

if df_all_a is not None and df_all_b is not None and df_players_a is not None and df_players_b is not None:
    st.success(
        f"Listo ✅ "
        f"Consulta A: Entradas {len(df_all_a):,} | Jugadores {len(df_players_a):,}   -   "
        f"Consulta B: Entradas {len(df_all_b):,} | Jugadores {len(df_players_b):,}"
    )

    st.divider()
    st.subheader("Elegí a los dos jugadores (A y B) y sus respectivos rangos de minutos por partido")

    colL, colR = st.columns(2, vertical_alignment="top")

    with colL:
        p1_label = st.selectbox("Jugador A", df_players_a["label"].tolist(), index=0, key="p1_label")
        p1_row = df_players_a.loc[df_players_a["label"] == p1_label].iloc[0]
        player_a_id, team_a_id = int(p1_row["player_id"]), int(p1_row["team_id"])
        minA, maxA = st.slider("Jugador A — Min/Max minutos por partido", 0, 130, (60, 130), 1, key="mins_a")

    with colR:
        p2_label = st.selectbox("Jugador B", df_players_b["label"].tolist(), index=0, key="p2_label")
        p2_row = df_players_b.loc[df_players_b["label"] == p2_label].iloc[0]
        player_b_id, team_b_id = int(p2_row["player_id"]), int(p2_row["team_id"])
        minB, maxB = st.slider("Jugador B — Min/Max minutos por partido", 0, 130, (60, 130), 1, key="mins_b")

    dA = _filter_player_rows(df_all_a, player_a_id, team_a_id, minA, maxA)
    dB = _filter_player_rows(df_all_b, player_b_id, team_b_id, minB, maxB)

    meansA = _compute_means_for_player(dA)
    meansB = _compute_means_for_player(dB)

    col_name_a = f"A: {p1_row['player_short_name']} ({p1_row['team_name']})"
    col_name_b = f"B: {p2_row['player_short_name']} ({p2_row['team_name']})"

    df_cmp = _build_comparison_table(meansA, meansB, col_name_a, col_name_b)

    st.divider()
    st.subheader("Tabla comparativa (promedios) | El valor mayor está en negrita")

    st.dataframe(_styler_bold_max(df_cmp, col_name_a, col_name_b), use_container_width=True, height=720)

    st.divider()
    st.subheader("Resumen de la muestra")

    sumA = int(round(_mins_sum(dA), 0))
    sumB = int(round(_mins_sum(dB), 0))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Jugador A:** {p1_label}")
        st.write(f"Partidos que cumplieron el rango: **{len(dA):,}**")
        st.write(f"Minutos totales (muestra): **{sumA:,}**")
        meta_a = st.session_state.get("meta_a") or {}
        st.caption(f"A: {meta_a.get('country','')} · {meta_a.get('comp','')} · {meta_a.get('edition','')}")
    with c2:
        st.markdown(f"**Jugador B:** {p2_label}")
        st.write(f"Partidos que cumplieron el rango: **{len(dB):,}**")
        st.write(f"Minutos totales (muestra): **{sumB:,}**")
        meta_b = st.session_state.get("meta_b") or {}
        st.caption(f"B: {meta_b.get('country','')} · {meta_b.get('comp','')} · {meta_b.get('edition','')}")

    with st.expander("Ver filas raw filtradas (debug)", expanded=False):
        st.write("Jugador A — filas filtradas")
        st.dataframe(dA, use_container_width=True, height=260)
        st.write("Jugador B — filas filtradas")
        st.dataframe(dB, use_container_width=True, height=260)
else:
    st.info("Elegí competiciones/ediciones y tocá **📥 Traer información** para cargar el listado de jugadores.")
