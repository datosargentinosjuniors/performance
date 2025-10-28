# appstreamlit.py
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from io import BytesIO
import matplotlib.pyplot as plt
from matplotlib import patheffects as pe
from matplotlib.ticker import StrMethodFormatter

# =========================
# CONFIG GENERAL
# =========================
st.set_page_config(page_title="Reportes por partido", layout="wide")
st.title("🏃‍♂️ Datos de tracking – Visualización de informes por partido")

COMPETITION_ID = 70
COMP_EDITION_ID = 1073

# Paleta de colores
RED_TOTAL = "#FB0B0E"
BLUE_HSR  = "#0D3E8A"

# Colores para B3/B4/B5 (stacked)
B3_COLOR = "#7FB3FF"  # 15–20 km/h
B4_COLOR = "#0D3E8A"  # 20–25 km/h
B5_COLOR = "#062557"  # >25 km/h

# Colores para Aceleraciones / Desaceleraciones
ACC_MED_COLOR = "#7FB3FF"   # medio (consistente con B3)
ACC_HIGH_COLOR = "#0D3E8A"  # alto  (consistente con B4)
DEC_MED_COLOR = "#FFB3B3"   # medio (rojo claro)
DEC_HIGH_COLOR = "#FB0B0E"  # alto  (rojo AAAJ)

# =========================
# BOTÓN DE ACTUALIZACIÓN
# =========================
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄 Actualizar datos ahora"):
        try:
            fetch_physical.clear()
        except Exception:
            pass
        st.toast("Cache limpiada. Re-descargando…")
        st.rerun()

# =========================
# FUNCIÓN DE DESCARGA (CACHE DIARIO)
# =========================
@st.cache_data(show_spinner=True)
def fetch_physical(competition: int, competition_edition: int, cache_date: str) -> pd.DataFrame:
    from skillcorner.client import SkillcornerClient

    client = SkillcornerClient(
        username=st.secrets["SKILLCORNER_USERNAME"],
        password=st.secrets["SKILLCORNER_PASSWORD"],
    )

    params = {"competition": [competition], "competition_edition": [competition_edition]}
    resp = client.get_physical(params=params, raise_for_status=True)

    if isinstance(resp, list):
        df = pd.DataFrame(resp)
    elif isinstance(resp, dict):
        df = pd.json_normalize(resp)
    else:
        df = pd.read_csv(BytesIO(resp))

    if "match_date" in df.columns:
        df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce").dt.date
    for c in ["match_id", "team_id", "player_id"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


today_key = date.today().isoformat()
with st.spinner("Descargando datos físicos desde SkillCorner…"):
    df = fetch_physical(COMPETITION_ID, COMP_EDITION_ID, cache_date=today_key)

if df.empty:
    st.error("No se recibieron datos del endpoint /api/physical.")
    st.stop()

# =========================
# FILTROS EN PÁGINA
# =========================
st.subheader("Filtros")

colA, colB, colC = st.columns([1.2, 1, 3], vertical_alignment="bottom")

with colA:
    if "match_date" not in df.columns or df["match_date"].isna().all():
        st.error("La columna 'match_date' no está disponible o no tiene datos válidos.")
        st.stop()

    max_date = df["match_date"].max()
    data_year = int(max_date.year)

    sem1_start = date(data_year, 1, 1)
    sem1_end = date(data_year, 6, 2)
    sem2_start = date(data_year, 6, 4)
    sem2_end = max_date

    semestre = st.radio("Semestre", ["Semestre 1", "Semestre 2"], horizontal=True, index=0)

if semestre == "Semestre 1":
    df_sem = df[(df["match_date"] >= sem1_start) & (df["match_date"] <= sem1_end)].copy()
    min_d, max_d = sem1_start, sem1_end
else:
    df_sem = df[(df["match_date"] >= sem2_start) & (df["match_date"] <= sem2_end)].copy()
    min_d, max_d = sem2_start, sem2_end

with colB:
    if df_sem.empty:
        st.warning("No hay datos para el semestre seleccionado.")
        st.stop()
    fechas_disponibles = sorted(df_sem["match_date"].dropna().unique().tolist())
    default_fecha = fechas_disponibles[-1]
    fecha_elegida = st.date_input("Fecha", value=default_fecha, min_value=min_d, max_value=max_d)
    if isinstance(fecha_elegida, list):
        fecha_elegida = fecha_elegida[0]

with colC:
    df_dia = df_sem[df_sem["match_date"] == fecha_elegida].copy()
    if df_dia.empty:
        st.warning("No hay partidos en esa fecha.")
        st.stop()
    df_dia["match_label"] = df_dia["match_name"].astype(str) + "  ·  ID " + df_dia["match_id"].astype(int).astype(str)
    partidos_opts = df_dia[["match_id", "match_label"]].drop_duplicates().sort_values("match_label")
    match_label = st.selectbox("Partido", partidos_opts["match_label"].tolist())
    match_id_sel = int(partidos_opts.loc[partidos_opts["match_label"] == match_label, "match_id"].iloc[0])

df_match = df_dia[df_dia["match_id"] == match_id_sel].copy()
if df_match.empty:
    st.warning("No se encontraron datos para el partido seleccionado.")
    st.stop()

st.divider()
st.subheader(f"Partido: {match_label}")


# =========================
# FUNCIONES DE VISUALIZACIÓN
# =========================
def _set_font_family():
    plt.rcParams['font.family'] = ['Proxima Nova', 'DejaVu Sans', 'Arial', 'Helvetica']


def render_team_vis1_total_vs_mpm(df_team, team_name):
    need = ['player_short_name', 'total_distance_full_all', 'total_metersperminute_full_all']
    if not all(c in df_team.columns for c in need):
        return

    d = df_team[need].copy()
    # Orden: mayor total arriba
    d = d.sort_values('total_distance_full_all', ascending=False).reset_index(drop=True)

    players = d['player_short_name'].tolist()
    totals = pd.to_numeric(d['total_distance_full_all'], errors='coerce').fillna(0).to_numpy()
    mpm = pd.to_numeric(d['total_metersperminute_full_all'], errors='coerce').fillna(0).to_numpy()
    y = np.arange(len(players))

    height = max(6, len(players) * 0.05)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120)
    _set_font_family()

    ax.barh(y, totals, color=RED_TOTAL, alpha=0.9, edgecolor='none')
    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_yticks(y)
    ax.set_yticklabels(players)
    ax.set_xlabel("Distancia total (m)")
    ax.set_title(f"{team_name} — Distancia total (m) + m/min", fontsize=14, pad=12, fontweight='bold')
    # Poner mayor arriba
    ax.invert_yaxis()

    # m/min al inicio de la barra
    for yi, val in zip(y, mpm):
        ax.text(100, yi, f"{val:.1f} m/min",
                va='center', ha='left', color='white', fontweight='bold',
                fontsize=10, path_effects=[pe.withStroke(linewidth=1, foreground="black")])

    # Metros al final (adentro o afuera)
    for yi, t in zip(y, totals):
        if t > 0:
            if t >= 1500:
                ax.text(t * 0.98, yi, f"{t:,.0f} m",
                        va='center', ha='right', color='white', fontweight='bold',
                        fontsize=10, path_effects=[pe.withStroke(linewidth=1, foreground="black")])
            else:
                ax.text(t + 100, yi, f"{t:,.0f} m",
                        va='center', ha='left', color='white', fontweight='bold', fontsize=10,
                        path_effects=[pe.withStroke(linewidth=1.5, foreground="black")])

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def _prep_b345(df_team: pd.DataFrame):
    need = [
        'player_short_name', 'total_distance_full_all',
        'running_distance_full_all', 'hsr_distance_full_all', 'sprint_distance_full_all'
    ]
    if not all(c in df_team.columns for c in need):
        return None

    d = df_team[need].copy()
    for c in [
        'total_distance_full_all', 'running_distance_full_all',
        'hsr_distance_full_all', 'sprint_distance_full_all'
    ]:
        d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)

    d["sum_b345"] = d["running_distance_full_all"] + d["hsr_distance_full_all"] + d["sprint_distance_full_all"]
    d["pct_b345"] = np.where(d["total_distance_full_all"] > 0, (d["sum_b345"] / d["total_distance_full_all"]) * 100.0, 0.0)
    return d


def render_team_vis2_b345_stacked_simple(df_team, team_name):
    """Visualización 2 — HID (B3/B4/B5) apilado, orden por suma, sin % ni suma"""
    d = _prep_b345(df_team)
    if d is None:
        return

    d = d.sort_values("sum_b345", ascending=False).reset_index(drop=True)

    players = d['player_short_name'].tolist()
    b3 = d['running_distance_full_all'].to_numpy()
    b4 = d['hsr_distance_full_all'].to_numpy()
    b5 = d['sprint_distance_full_all'].to_numpy()

    y = np.arange(len(players))
    height = max(6, len(players) * 0.08)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120)
    _set_font_family()

    left = np.zeros_like(b3, dtype=float)
    bars = []
    bars.append(ax.barh(y, b3, left=left, color=B3_COLOR, alpha=0.95, edgecolor='none', label="B3: 15–20 km/h"))
    left = left + b3
    bars.append(ax.barh(y, b4, left=left, color=B4_COLOR, alpha=0.95, edgecolor='none', label="B4: 20–25 km/h"))
    left = left + b4
    b5_bars = ax.barh(y, b5, left=left, color=B5_COLOR, alpha=0.95, edgecolor='none', label="B5: > 25 km/h")

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_yticks(y)
    ax.set_yticklabels(players)
    ax.set_xlabel("Distancia (m)")
    ax.set_title(f"{team_name} — HID (B3/B4/B5)", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()  # mayor arriba

    # Etiquetas: B3/B4 al centro
    for arr, container in zip([b3, b4], bars):
        for rect, width in zip(container.patches, arr):
            if width <= 0:
                continue
            yi = rect.get_y() + rect.get_height() / 2.0
            xm = rect.get_x() + width / 2.0
            ax.text(xm, yi, f"{width:,.0f} m", va='center', ha='center',
                    color='white', fontweight='bold', fontsize=9,
                    path_effects=[pe.withStroke(linewidth=1, foreground="black")])

    # Etiquetas: B5 afuera a la derecha
    for rect, width in zip(b5_bars.patches, b5):
        if width <= 0:
            continue
        yi = rect.get_y() + rect.get_height() / 2.0
        x1 = rect.get_x() + rect.get_width()
        ax.text(x1 + 15, yi, f"{width:,.0f} m", va='center', ha='left',
                color=B5_COLOR, fontweight='bold', fontsize=9)

    ax.legend(loc="lower right", ncols=3, frameon=False)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def render_team_vis3_b345_sum_pct(df_team, team_name):
    """Visualización 3 — Barra con suma HID y % del total, orden por suma"""
    d = _prep_b345(df_team)
    if d is None:
        return

    d = d.sort_values("sum_b345", ascending=False).reset_index(drop=True)

    players = d['player_short_name'].tolist()
    total = d['total_distance_full_all'].to_numpy()
    sum_b = d['sum_b345'].to_numpy()
    pct_b = np.where(total > 0, (sum_b / total) * 100.0, 0.0)

    y = np.arange(len(players))
    height = max(6, len(players) * 0.08)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120)
    _set_font_family()

    ax.barh(y, sum_b, color=BLUE_HSR, alpha=0.95, edgecolor='none')

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_yticks(y)
    ax.set_yticklabels(players)
    ax.set_xlabel("Distancia (m)")
    ax.set_title(f"{team_name} — Suma de HID (B3+B4+B5) y % del total", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()  # mayor arriba

    # % a la izquierda
    for yi, p in enumerate(pct_b):
        ax.text(20, yi, f"{p:.0f}%", va='center', ha='left',
                color='white', fontsize=10, fontweight='bold',
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])

    # suma al final (dentro si larga, fuera si corta)
    for yi, sb in enumerate(sum_b):
        if sb > 0:
            if sb >= 1200:
                ax.text(sb * 0.98, yi, f"{sb:,.0f} m",
                        va='center', ha='right', color='white', fontweight='bold', fontsize=10,
                        path_effects=[pe.withStroke(linewidth=1, foreground="black")])
            else:
                ax.text(sb + 15, yi, f"{sb:,.0f} m",
                        va='center', ha='left', color='black', fontweight='bold', fontsize=10)

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ==== Aceleraciones / Desaceleraciones ====
def _prep_counts(df_team: pd.DataFrame, cols: list, sum_col_name: str) -> pd.DataFrame:
    """
    Prepara dataframe numérico y agrega suma de columnas de conteo.
    cols: lista de columnas a sumar (2 elementos).
    sum_col_name: nombre para la columna suma.
    """
    need = ['player_short_name'] + cols
    if not all(c in df_team.columns for c in need):
        return None

    d = df_team[need].copy()
    for c in cols:
        d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
    d[sum_col_name] = d[cols[0]] + d[cols[1]]
    # Orden de mayor a menor por la suma
    d = d.sort_values(sum_col_name, ascending=False).reset_index(drop=True)
    return d


def render_team_vis4_accels(df_team, team_name):
    """Visualización 4 — Aceleraciones (medias + altas) apiladas, orden por suma"""
    cols = ['medaccel_count_full_all', 'highaccel_count_full_all']
    d = _prep_counts(df_team, cols, 'sum_acc')
    if d is None:
        return

    players = d['player_short_name'].tolist()
    med = d[cols[0]].to_numpy()
    high = d[cols[1]].to_numpy()

    y = np.arange(len(players))
    height = max(5.5, len(players) * 0.06)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120)
    _set_font_family()

    left = np.zeros_like(med, dtype=float)
    b_med  = ax.barh(y, med,  left=left, color=ACC_MED_COLOR,  alpha=0.95, edgecolor='none', label="Aceleraciones medias")
    left   = left + med
    b_high = ax.barh(y, high, left=left, color=ACC_HIGH_COLOR, alpha=0.95, edgecolor='none', label="Aceleraciones altas")

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_yticks(y)
    ax.set_yticklabels(players)
    ax.set_xlabel("Cantidad")
    ax.set_title(f"{team_name} — Aceleraciones (medias + altas)", fontsize=14, pad=20, fontweight='bold')
    ax.text(0.5, 1.03,
            "Medias: 1.5–3.0 m/s² (≥0.7 s)   •   Altas: >3.0 m/s² (≥0.7 s)",
            transform=ax.transAxes, ha='center', va='center', fontsize=10, color='black')
    ax.invert_yaxis()

    # Etiquetas
    for rect, width in zip(b_med.patches, med):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        xm = rect.get_x() + width/2.0
        ax.text(xm, yi, f"{int(width)}", va='center', ha='center',
                color='white', fontweight='bold', fontsize=9,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    for rect, width in zip(b_high.patches, high):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        xm = rect.get_x() + rect.get_width() - (width/2.0)
        ax.text(xm, yi, f"{int(width)}", va='center', ha='center',
                color='white', fontweight='bold', fontsize=9,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])

    ax.legend(loc="lower right", frameon=False)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def render_team_vis5_decels(df_team, team_name):
    """Visualización 5 — Desaceleraciones (medias + altas) apiladas, orden por suma"""
    cols = ['meddecel_count_full_all', 'highdecel_count_full_all']
    d = _prep_counts(df_team, cols, 'sum_dec')
    if d is None:
        return

    players = d['player_short_name'].tolist()
    med = d[cols[0]].to_numpy()
    high = d[cols[1]].to_numpy()

    y = np.arange(len(players))
    height = max(5.5, len(players) * 0.06)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120)
    _set_font_family()

    left = np.zeros_like(med, dtype=float)
    b_med  = ax.barh(y, med,  left=left, color=DEC_MED_COLOR,  alpha=0.95, edgecolor='none', label="Desaceleraciones medias")
    left   = left + med
    b_high = ax.barh(y, high, left=left, color=DEC_HIGH_COLOR, alpha=0.95, edgecolor='none', label="Desaceleraciones altas")

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_yticks(y)
    ax.set_yticklabels(players)
    ax.set_xlabel("Cantidad")
    ax.set_title(f"{team_name} — Desaceleraciones (medias + altas)", fontsize=14, pad=20, fontweight='bold')
    ax.text(0.5, 1.03,
            "Medias: −1.5 a −3.0 m/s² (≥0.7 s)   •   Altas: < −3.0 m/s² (≥0.7 s)",
            transform=ax.transAxes, ha='center', va='center', fontsize=10, color='black')
    ax.invert_yaxis()

    # Etiquetas
    for rect, width in zip(b_med.patches, med):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        xm = rect.get_x() + width/2.0
        ax.text(xm, yi, f"{int(width)}", va='center', ha='center',
                color='black', fontweight='bold', fontsize=9)
    for rect, width in zip(b_high.patches, high):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        xm = rect.get_x() + rect.get_width() - (width/2.0)
        ax.text(xm, yi, f"{int(width)}", va='center', ha='center',
                color='white', fontweight='bold', fontsize=9,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])

    ax.legend(loc="lower right", frameon=False)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ==== Visualización 6 y 7: Explosive Accels a HSR / Sprint (barra = conteo, base = tiempo) ====
def render_team_vis6_expl_to_hsr(df_team, team_name):
    """
    Visualización 6 — Aceleración explosiva a HSR (B4)
    - Barra por jugador: explacceltohsr_count_full_all (conteo)
    - En la base (inicio de barra): timetohsr (s)
    - Orden: mayor conteo arriba
    """
    COUNT_COL = 'explacceltohsr_count_full_all'
    TIME_COL  = 'timetohsr'
    need = ['player_short_name', COUNT_COL, TIME_COL]
    if not all(c in df_team.columns for c in need):
        return

    d = df_team[need].copy()
    d[COUNT_COL] = pd.to_numeric(d[COUNT_COL], errors='coerce').fillna(0)
    d[TIME_COL]  = pd.to_numeric(d[TIME_COL],  errors='coerce')

    # Orden por conteo (mayor arriba)
    d = d.sort_values(COUNT_COL, ascending=False).reset_index(drop=True)

    players = d['player_short_name'].tolist()
    counts  = d[COUNT_COL].to_numpy()
    times   = d[TIME_COL].to_numpy()

    y = np.arange(len(players))
    height = max(6, len(players) * 0.08)  # mismo alto que otras vis
    fig, ax = plt.subplots(figsize=(13, height), dpi=120)
    _set_font_family()

    bars = ax.barh(y, counts, color=B4_COLOR, alpha=0.95, edgecolor='none')

    # --- Escala y ejes ---
    max_c = float(np.nanmax(counts)) if len(counts) else 0.0
    right_pad = max(2.0, max_c * 0.12)   # margen para el número al final
    ax.set_xlim(0, max_c + right_pad)

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_yticks(y)
    ax.set_yticklabels(players)
    ax.set_xlabel("Cantidad")
    ax.set_title(f"{team_name} — Aceleraciones explosivas a HSR (B4)", fontsize=14, pad=14, fontweight='bold')
    ax.invert_yaxis()

    # --- Segundos en la base (inicio de barra) ---
    # offset proporcional al ancho del eje para que no “salte” ni se repita visualmente
    x0, x1 = ax.get_xlim()
    base_x = x0 + 0.015 * (x1 - x0)  # 1.5% del ancho del eje
    for yi, t in enumerate(times):
        if pd.isna(t):
            txt = "–"
        else:
            txt = f"{t:.1f} s"
        ax.text(base_x, yi, txt, va='center', ha='left',
                color='white', fontsize=10, fontweight='bold',
                path_effects=[pe.withStroke(linewidth=1, foreground="black")], zorder=3)

    # --- Conteo pegado al final (siempre afuera) ---
    for rect, c in zip(bars.patches, counts):
        if c <= 0:
            continue
        yi = rect.get_y() + rect.get_height() / 2.0
        x_end = rect.get_x() + rect.get_width()
        ax.text(x_end + 0.01 * (x1 - x0), yi, f"{int(c)}",  # 3% del ancho del eje
                va='center', ha='left', color='black', fontweight='bold', fontsize=10)

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def render_team_vis7_expl_to_sprint(df_team, team_name):
    """
    Visualización 7 — Aceleración explosiva a sprint (B5)
    - Barra por jugador: explacceltosprint_count_full_all (conteo)
    - En la base (inicio de barra): timetosprint (s)
    - Orden: mayor conteo arriba
    """
    COUNT_COL = 'explacceltosprint_count_full_all'
    TIME_COL  = 'timetosprint'
    need = ['player_short_name', COUNT_COL, TIME_COL]
    if not all(c in df_team.columns for c in need):
        return

    d = df_team[need].copy()
    d[COUNT_COL] = pd.to_numeric(d[COUNT_COL], errors='coerce').fillna(0)
    d[TIME_COL]  = pd.to_numeric(d[TIME_COL],  errors='coerce')

    d = d.sort_values(COUNT_COL, ascending=False).reset_index(drop=True)

    players = d['player_short_name'].tolist()
    counts  = d[COUNT_COL].to_numpy()
    times   = d[TIME_COL].to_numpy()

    y = np.arange(len(players))
    height = max(6, len(players) * 0.08)  # mismo alto que otras vis
    fig, ax = plt.subplots(figsize=(13, height), dpi=120)
    _set_font_family()

    bars = ax.barh(y, counts, color=B5_COLOR, alpha=0.95, edgecolor='none')

    # --- Escala y ejes ---
    max_c = float(np.nanmax(counts)) if len(counts) else 0.0
    right_pad = max(2.0, max_c * 0.12)
    ax.set_xlim(0, max_c + right_pad)

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_yticks(y)
    ax.set_yticklabels(players)
    ax.set_xlabel("Cantidad")
    ax.set_title(f"{team_name} — Aceleración explosiva a sprint (B5)", fontsize=14, pad=14, fontweight='bold')
    ax.invert_yaxis()

    # --- Segundos en la base (inicio de barra) ---
    x0, x1 = ax.get_xlim()
    base_x = x0 + 0.015 * (x1 - x0)  # 1.5% del ancho del eje
    for yi, t in enumerate(times):
        if pd.isna(t):
            txt = "–"
        else:
            txt = f"{t:.1f} s"
        ax.text(base_x, yi, txt, va='center', ha='left',
                color='white', fontsize=10, fontweight='bold',
                path_effects=[pe.withStroke(linewidth=1, foreground="black")], zorder=3)

    # --- Conteo pegado al final (siempre afuera) ---
    for rect, c in zip(bars.patches, counts):
        if c <= 0:
            continue
        yi = rect.get_y() + rect.get_height() / 2.0
        x_end = rect.get_x() + rect.get_width()
        ax.text(x_end + 0.01 * (x1 - x0), yi, f"{int(c)}",
                va='center', ha='left', color='black', fontweight='bold', fontsize=10)

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

def render_team_vis8_psv99(df_team, team_name):
    """
    Visualización 8 — PSV99 | Velocidad máxima
    - Una barra por jugador con psv99 (km/h)
    - Etiqueta al final de la barra (adentro), con sufijo ' km/h'
    - Orden: mayor velocidad arriba
    """
    COL = 'psv99'
    need = ['player_short_name', COL]
    if not all(c in df_team.columns for c in need):
        return

    d = df_team[need].copy()
    d[COL] = pd.to_numeric(d[COL], errors='coerce')
    d = d.fillna({COL: 0})

    # Orden por velocidad (mayor arriba)
    d = d.sort_values(COL, ascending=False).reset_index(drop=True)

    players = d['player_short_name'].tolist()
    speeds  = d[COL].to_numpy()

    y = np.arange(len(players))
    height = max(6, len(players) * 0.08)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120)
    _set_font_family()

    bars = ax.barh(y, speeds, color=B5_COLOR, alpha=0.95, edgecolor='none')

    # Escala con pequeño margen a la derecha
    vmax = float(np.nanmax(speeds)) if len(speeds) else 0.0
    right_pad = max(0.5, vmax * 0.05)
    ax.set_xlim(0, vmax + right_pad)

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.1f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_yticks(y)
    ax.set_yticklabels(players)
    ax.set_xlabel("Velocidad (km/h)")
    ax.set_title(f"{team_name} — PSV99 | Velocidad máxima", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()  # mayor arriba

    # Etiquetas: al final de la barra, adentro
    for rect, v in zip(bars.patches, speeds):
        if v <= 0:
            continue
        yi = rect.get_y() + rect.get_height() / 2.0
        x_end = rect.get_x() + rect.get_width()
        # un pequeño offset hacia adentro para que quede "pegado" al final pero dentro
        x_label = x_end - 0.02 * (ax.get_xlim()[1] - ax.get_xlim()[0])
        ax.text(x_label, yi, f"{v:.1f} km/h",
                va='center', ha='right',
                color='white', fontweight='bold', fontsize=10,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# =========================
# TABLAS POR EQUIPO
# =========================
phys_cols = [
    'player_short_name', 'position', 'position_group',
    'minutes_full_all', 'physical_check_passed', 'total_distance_full_all',
    'total_metersperminute_full_all', 'running_distance_full_all',
    'hsr_distance_full_all', 'hsr_count_full_all',
    'sprint_distance_full_all', 'sprint_count_full_all',
    'hi_distance_full_all', 'hi_count_full_all', 'medaccel_count_full_all',
    'highaccel_count_full_all', 'meddecel_count_full_all',
    'highdecel_count_full_all', 'explacceltohsr_count_full_all',
    'timetohsr', 'explacceltosprint_count_full_all', 'timetosprint',
    'psv99'
]
phys_cols = [c for c in phys_cols if c in df_match.columns]

def order_team_table(df_team: pd.DataFrame) -> pd.DataFrame:
    if "position_group" in df_team.columns:
        order_map = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
        df_team["_pg_order"] = df_team["position_group"].map(order_map).fillna(99)
        df_team = df_team.sort_values(["_pg_order", "position", "player_short_name"]).drop(columns=["_pg_order"])
    else:
        df_team = df_team.sort_values(["position", "player_short_name"])
    return df_team


# =========================
# RENDER FINAL POR EQUIPO
# =========================
teams = df_match[["team_id", "team_name"]].drop_duplicates().sort_values("team_id").to_dict("records")

for t in teams:
    t_id, t_name = t["team_id"], t["team_name"]
    df_team = df_match[df_match["team_id"] == t_id].copy()

    # Vis 1: total + m/min (mayor total arriba)
    render_team_vis1_total_vs_mpm(df_team, t_name)

    # Vis 2: stacked simple B3/B4/B5 (orden por suma, B5 etiqueta a la derecha)
    render_team_vis2_b345_stacked_simple(df_team, t_name)

    # Vis 3: suma B3+B4+B5 y % del total (orden por suma)
    render_team_vis3_b345_sum_pct(df_team, t_name)

    # Vis 4: Aceleraciones (medias + altas) con subtítulo
    render_team_vis4_accels(df_team, t_name)

    # Vis 5: Desaceleraciones (medias + altas) con subtítulo
    render_team_vis5_decels(df_team, t_name)

    # Vis 6: Explosive accel -> HSR (B4): barra = conteo, base = tiempo
    render_team_vis6_expl_to_hsr(df_team, t_name)

    # Vis 7: Explosive accel -> Sprint (B5): barra = conteo, base = tiempo
    render_team_vis7_expl_to_sprint(df_team, t_name)

    # Vis 8: PSV99 | Velocidad máxima
    render_team_vis8_psv99(df_team, t_name)


    # Tabla
    st.markdown(f"### {t_name}")
    df_team_table = order_team_table(df_team[phys_cols].copy())
    st.dataframe(df_team_table, use_container_width=True)
