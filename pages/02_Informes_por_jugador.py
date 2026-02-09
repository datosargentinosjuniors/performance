# appstreamlit_players_compare.py
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from io import BytesIO

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="SkillCorner — Comparativa física", layout="wide")
st.title("🏃‍♂️ Comparador de futbolistas")

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
    "total_distance_full_all": "Distancia total",
    "total_metersperminute_full_all": "Metros por minuto",
    "running_distance_full_all": "Distancia corriendo (B3)",
    "hsr_distance_full_all": "Distancia en HSR",
    "hsr_count_full_all": "Cantidad de veces que alcanzó HSR (B4)",
    "sprint_distance_full_all": "Distancia en sprint (B5)",
    "sprint_count_full_all": "Cantidad de veces que realizó un sprint (B5)",
    "hi_count_full_all": "Cantidad de veces que alcanzó una alta intensidad (B4 o B5)",
    "hi_distance_full_all": "Distancia en alta intensidad (B4 + B5)",
    "highaccel_count_full_all": "Aceleraciones altas",
    "highdecel_count_full_all": "Desaceleraciones altas",
    "medaccel_count_full_all": "Aceleraciones medias",
    "meddecel_count_full_all": "Desaceleraciones medias",
    "psv99": "Velocidad máxima (PSV99)",
    "explacceltohsr_count_full_all": "Aceleraciones explosivas a HSR (B4)",
    "timetohsr": "Tiempo a un HSR (B4)",
    "explacceltosprint_count_full_all": "Aceleraciones explosivas a sprint (B5)",
    "timetosprint": "Tiempo a un sprint (B5)",
    "cod_count_full_all": "Cambios de dirección",
    "timetohsrpostcod": "Tiempo a un HSR (B4) post cambio de ritmo",
    "timetosprintpostcod": "Tiempo a un sprint (B5) post cambio de ritmo",
}

# Orden EXACTO como tu captura 2 (por alias en español)
ROW_ORDER_ES = [
    "Distancia total",
    "Metros por minuto",
    "Distancia corriendo (B3)",
    "Distancia en HSR",
    "Cantidad de veces que alcanzó HSR (B4)",
    "Distancia en sprint (B5)",
    "Cantidad de veces que realizó un sprint (B5)",
    "Cantidad de veces que alcanzó una alta intensidad (B4 o B5)",
    "Distancia en alta intensidad (B4 + B5)",
    "Aceleraciones altas",
    "Desaceleraciones altas",
    "Aceleraciones medias",
    "Desaceleraciones medias",
    "Velocidad máxima (PSV99)",
    "Aceleraciones explosivas a HSR (B4)",
    "Tiempo a un HSR (B4)",
    "Aceleraciones explosivas a sprint (B5)",
    "Tiempo a un sprint (B5)",
    "Cambios de dirección",
    "Tiempo a un HSR (B4) post cambio de ritmo",
    "Tiempo a un sprint (B5) post cambio de ritmo",
]

# =========================
# HELPERS: resp -> DataFrame
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

# =========================
# FETCH: 1 edición (cache diario)
# =========================
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

    # metadata útil
    df["competition_id"] = competition_id
    df["competition_edition_id"] = competition_edition_id

    return df

def build_players_from_df_all(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    1 fila por player_id + team_id (para evitar mezclar traspasos dentro de la edición).
    """
    if df_all.empty or "player_id" not in df_all.columns:
        return pd.DataFrame()

    keep = [c for c in [
        "player_id", "player_short_name", "player_name",
        "team_id", "team_name",
        "minutes_full_all"
    ] if c in df_all.columns]

    d = df_all[keep].copy()

    if "minutes_full_all" in d.columns:
        d["minutes_full_all"] = pd.to_numeric(d["minutes_full_all"], errors="coerce").fillna(0)
    else:
        d["minutes_full_all"] = 0

    gcols = [c for c in ["player_id", "team_id"] if c in d.columns]
    players = (
        d.groupby(gcols, as_index=False)
         .agg({
             "player_short_name": "first" if "player_short_name" in d.columns else "first",
             "player_name": "first" if "player_name" in d.columns else "first",
             "team_name": "first" if "team_name" in d.columns else "first",
             "minutes_full_all": "sum",
         })
    )

    players = players.sort_values(
        ["minutes_full_all", "team_name", "player_short_name"],
        ascending=[False, True, True]
    ).reset_index(drop=True)

    # etiqueta linda para selectbox
    players["label"] = (
        players["player_short_name"].fillna(players["player_name"]).fillna("—").astype(str)
        + " — " + players["team_name"].fillna("—").astype(str)
        + "  |  " + players["minutes_full_all"].round(0).astype(int).astype(str) + " min"
    )
    return players

def _filter_player_rows(df_all: pd.DataFrame, player_id: int, team_id: int, min_mp: float, max_mp: float) -> pd.DataFrame:
    d = df_all.copy()
    if "minutes_full_all" in d.columns:
        d["minutes_full_all"] = pd.to_numeric(d["minutes_full_all"], errors="coerce")
    else:
        d["minutes_full_all"] = np.nan

    d = d[(d["player_id"] == player_id) & (d["team_id"] == team_id)].copy()
    d = d[d["minutes_full_all"].between(min_mp, max_mp, inclusive="both")].copy()
    return d

def _compute_means_for_player(d: pd.DataFrame) -> dict:
    """
    Promedia SOLO métricas con alias. Si la métrica no existe, queda NaN.
    """
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
        rows.append({
            "Métrica": alias_es,
            label_a: means_a.get(metric_key, np.nan),
            label_b: means_b.get(metric_key, np.nan),
        })
    df_cmp = pd.DataFrame(rows)

    # redondeo a 2 decimales
    for c in [label_a, label_b]:
        df_cmp[c] = pd.to_numeric(df_cmp[c], errors="coerce").round(2)

    # orden por tu lista
    order_map = {name: i for i, name in enumerate(ROW_ORDER_ES)}
    df_cmp["_ord"] = df_cmp["Métrica"].map(order_map).fillna(9999).astype(int)
    df_cmp = df_cmp.sort_values("_ord").drop(columns=["_ord"]).reset_index(drop=True)

    # (extra) si por alguna razón aparece algo fuera del orden, lo deja al final
    return df_cmp

def _styler_bold_max(df_cmp: pd.DataFrame, col_a: str, col_b: str):
    """
    Sin colores de fondo. Solo deja en negrita el mayor por fila.
    """
    def bold_row(row):
        a = row[col_a]
        b = row[col_b]
        styles = [""] * len(row)

        try:
            a_num = float(a) if pd.notna(a) else np.nan
        except Exception:
            a_num = np.nan
        try:
            b_num = float(b) if pd.notna(b) else np.nan
        except Exception:
            b_num = np.nan

        # índices
        idx_a = row.index.get_loc(col_a)
        idx_b = row.index.get_loc(col_b)

        if pd.notna(a_num) and pd.notna(b_num):
            if a_num > b_num:
                styles[idx_a] = "font-weight: 700;"
            elif b_num > a_num:
                styles[idx_b] = "font-weight: 700;"
            # empate: nada
        elif pd.notna(a_num) and pd.isna(b_num):
            styles[idx_a] = "font-weight: 700;"
        elif pd.isna(a_num) and pd.notna(b_num):
            styles[idx_b] = "font-weight: 700;"
        return styles

    sty = df_cmp.style.apply(bold_row, axis=1)
    sty = sty.format({col_a: "{:.2f}", col_b: "{:.2f}"}, na_rep="—")
    return sty

# =========================
# BOTÓN: limpiar cache
# =========================
c1, c2 = st.columns([6, 1])
with c2:
    if st.button("🔄 Actualizar datos"):
        try:
            fetch_physical_one.clear()
        except Exception:
            pass
        st.toast("Cache limpiada. Re-descargando…")
        st.rerun()

# =========================
# UI: selects (competición + edición)
# =========================
col1, col2, col3, col4 = st.columns([1.2, 1.8, 1.2, 1], vertical_alignment="bottom")

with col1:
    country = st.selectbox("País/Liga", list(COMPETITION_CATALOG.keys()), index=0)

with col2:
    comp_label = st.selectbox("Competencia", list(COMPETITION_CATALOG[country].keys()), index=0)

info = COMPETITION_CATALOG[country][comp_label]
competition_id = info["competition_id"]

with col3:
    edition_label = st.selectbox("Edición", list(info["editions"].keys()), index=0)

competition_edition_id = info["editions"][edition_label]

with col4:
    do_fetch = st.button("📥 Descargar")

st.caption(f"Seleccionado: competition_id={competition_id} | competition_edition_id={competition_edition_id}")

# =========================
# EXEC: download + select players + filters + compare
# =========================
if do_fetch:
    today_key = date.today().isoformat()
    with st.spinner("Descargando /physical…"):
        df_all = fetch_physical_one(competition_id, competition_edition_id, cache_date=today_key)

    if df_all.empty:
        st.error("La API devolvió vacío para esta edición.")
        st.stop()

    df_players = build_players_from_df_all(df_all)
    if df_players.empty:
        st.error("No pude construir el listado de jugadores (faltan columnas clave).")
        st.stop()

    st.success(f"Listo ✅ Entradas: {len(df_all):,} | Jugadores únicos (player+team): {len(df_players):,}")

    st.divider()
    st.subheader("Elegí 2 jugadores (sin filtrar por puesto)")

    # Selects: 2 jugadores (player_id + team_id)
    p1_label = st.selectbox("Jugador A", df_players["label"].tolist(), index=0)
    p2_label = st.selectbox("Jugador B", df_players["label"].tolist(), index=min(1, len(df_players)-1))

    p1_row = df_players.loc[df_players["label"] == p1_label].iloc[0]
    p2_row = df_players.loc[df_players["label"] == p2_label].iloc[0]

    player_a_id, team_a_id = int(p1_row["player_id"]), int(p1_row["team_id"])
    player_b_id, team_b_id = int(p2_row["player_id"]), int(p2_row["team_id"])

    # Rangos de minutos por partido (independientes por jugador)
    st.divider()
    st.subheader("Filtro por minutos por partido (rango)")

    # límites sugeridos
    min_lim = 0
    max_lim = 130

    colA, colB = st.columns(2)
    with colA:
        minA, maxA = st.slider("Jugador A — Min/Max minutos por partido",
                               min_value=min_lim, max_value=max_lim, value=(60, 130), step=1)
    with colB:
        minB, maxB = st.slider("Jugador B — Min/Max minutos por partido",
                               min_value=min_lim, max_value=max_lim, value=(60, 130), step=1)

    # Filtrar filas
    dA = _filter_player_rows(df_all, player_a_id, team_a_id, minA, maxA)
    dB = _filter_player_rows(df_all, player_b_id, team_b_id, minB, maxB)

    if dA.empty:
        st.warning("Jugador A: no hay filas que cumplan el rango de minutos elegido.")
    if dB.empty:
        st.warning("Jugador B: no hay filas que cumplan el rango de minutos elegido.")

    # Calcular promedios (solo métricas con alias)
    meansA = _compute_means_for_player(dA)
    meansB = _compute_means_for_player(dB)

    # Etiquetas columnas (cortas)
    col_name_a = f"A: {p1_row['player_short_name']} ({p1_row['team_name']})"
    col_name_b = f"B: {p2_row['player_short_name']} ({p2_row['team_name']})"

    # Tabla comparativa
    df_cmp = _build_comparison_table(meansA, meansB, col_name_a, col_name_b)

    st.divider()
    st.subheader("Tabla comparativa (promedios)")

    sty = _styler_bold_max(df_cmp, col_name_a, col_name_b)
    st.dataframe(sty, use_container_width=True, height=720)

    # Resumen abajo (mins totales + partidos)
    st.divider()
    st.subheader("Resumen de la muestra")

    def _mins_sum(d):
        if d.empty or "minutes_full_all" not in d.columns:
            return 0.0
        return float(pd.to_numeric(d["minutes_full_all"], errors="coerce").fillna(0).sum())

    sumA = round(_mins_sum(dA), 0)
    sumB = round(_mins_sum(dB), 0)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Jugador A:** {p1_label}")
        st.write(f"Partidos que cumplieron el rango: **{len(dA):,}**")
        st.write(f"Minutos totales (muestra): **{int(sumA):,}**")
    with c2:
        st.markdown(f"**Jugador B:** {p2_label}")
        st.write(f"Partidos que cumplieron el rango: **{len(dB):,}**")
        st.write(f"Minutos totales (muestra): **{int(sumB):,}**")

    # (Opcional) debug raw
    with st.expander("Ver filas raw filtradas (debug)", expanded=False):
        st.write("Jugador A — filas filtradas")
        st.dataframe(dA, use_container_width=True, height=260)
        st.write("Jugador B — filas filtradas")
        st.dataframe(dB, use_container_width=True, height=260)
