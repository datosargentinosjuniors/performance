# app_player_semestre.py
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
st.set_page_config(page_title="Reportes por jugador", layout="wide")
st.title("🏃‍♂️ Tracking por jugador — Informes por torneo")

# IDs por defecto (ajustá si hace falta)
COMPETITION_ID = 70
COMP_EDITION_ID = 1073

# Paleta de colores (coherente con tu app)
RED_TOTAL = "#FB0B0E"
BLUE_HSR  = "#0D3E8A"

B3_COLOR = "#7FB3FF"  # 15–20 km/h
B4_COLOR = "#0D3E8A"  # 20–25 km/h
B5_COLOR = "#062557"  # >25 km/h

ACC_MED_COLOR = "#7FB3FF"   # medio
ACC_HIGH_COLOR = "#0D3E8A"  # alto
DEC_MED_COLOR = "#FFB3B3"   # medio
DEC_HIGH_COLOR = "#FB0B0E"  # alto

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

    # Tipos básicos
    if "match_date" in df.columns:
        df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce").dt.date
    for c in ["match_id", "team_id", "player_id"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Normalizaciones útiles
    if "player_short_name" in df.columns:
        df["player_short_name"] = df["player_short_name"].fillna(df.get("player_name", ""))
    if "match_name" in df.columns:
        df["match_name"] = df["match_name"].astype(str)

    return df

today_key = date.today().isoformat()
with st.spinner("Descargando datos físicos desde SkillCorner…"):
    df = fetch_physical(COMPETITION_ID, COMP_EDITION_ID, cache_date=today_key)

if df.empty:
    st.error("No se recibieron datos del endpoint /api/physical.")
    st.stop()

# =========================
# UTILIDADES
# =========================
def _set_font_family():
    plt.rcParams['font.family'] = ['Proxima Nova', 'DejaVu Sans', 'Arial', 'Helvetica']

def map_opponent_from_match(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada match_id, mapeamos los dos team_name.
    Luego, para cada fila, opponent_name = el otro team_name del mismo partido.
    """
    if not set(["match_id", "team_name"]).issubset(df_all.columns):
        return df_all.copy()

    teams_by_match = (
        df_all[["match_id", "team_name"]]
        .dropna()
        .drop_duplicates()
        .groupby("match_id")["team_name"]
        .apply(list)
        .to_dict()
    )

    def _opp(row):
        mids = row["match_id"]
        my_team = row["team_name"]
        names = teams_by_match.get(mids, [])
        if names and my_team in names and len(names) >= 2:
            return [n for n in names if n != my_team][0]
        # fallback: intentar parsear match_name si vino como "A - B"
        mn = str(row.get("match_name", ""))
        if " - " in mn:
            a, b = [x.strip() for x in mn.split(" - ", 1)]
            return b if a == my_team else a if b == my_team else b
        return np.nan

    out = df_all.copy()
    out["opponent_name"] = out.apply(_opp, axis=1)
    return out

def build_row_label(opponent: str, position: str, minutes) -> str:
    """
    Etiqueta compacta para el eje Y: 'Rival | position | minutes min'
    Sin fecha (por pedido), pero la ordenación se hace por fecha desc.
    """
    pos_txt = "-" if pd.isna(position) or position == "" else str(position)
    try:
        mins_val = pd.to_numeric(minutes, errors="coerce")
    except Exception:
        mins_val = np.nan
    mins_txt = "-" if pd.isna(mins_val) else f"{int(round(float(mins_val)))}"
    opp_txt = "" if pd.isna(opponent) else str(opponent)
    label = f"{opp_txt} | {pos_txt} | {mins_txt} min"
    return label.strip()

def xlim_with_margin(values, right_pct: float = 0.25):
    """
    Devuelve (0, vmax*(1+right_pct)) garantizando rango > 0.
    """
    vmax = float(np.nanmax(values)) if len(values) else 0.0
    vmax = max(vmax, 1.0)  # evita rango 0
    return (0.0, vmax * (1.0 + right_pct))

# =========================
# FILTROS EN PÁGINA
# =========================
st.subheader("Filtros")

colA, colB = st.columns([1.2, 2], vertical_alignment="bottom")

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
else:
    df_sem = df[(df["match_date"] >= sem2_start) & (df["match_date"] <= sem2_end)].copy()

if df_sem.empty:
    st.warning("No hay datos para el semestre seleccionado.")
    st.stop()

with colB:
    # Selector de jugador directo (incluye equipo entre paréntesis antes del ID)
    if "player_short_name" not in df_sem.columns or df_sem["player_short_name"].isna().all():
        st.error("No hay identificadores de jugador válidos.")
        st.stop()

    jugadores = (
        df_sem[["player_id", "player_short_name", "team_name"]]
        .dropna(subset=["player_id"])
        .drop_duplicates()
        .sort_values(["player_short_name", "team_name"])
        .to_dict("records")
    )
    if not jugadores:
        st.warning("No se encontraron jugadores para ese filtro.")
        st.stop()

    def _label(j):
        name = str(j.get("player_short_name", ""))
        team = str(j.get("team_name", ""))
        pid  = int(j["player_id"])
        team_txt = f" ({team})" if team else ""
        return f"{name}{team_txt} · ID {pid}"

    player_label_opts = [_label(j) for j in jugadores]
    player_label = st.selectbox("Jugador", player_label_opts)
    player_id_sel = int(player_label.split("· ID")[-1].strip())

# Subconjunto por jugador, mapeo de rival y label por partido
df_sem = map_opponent_from_match(df_sem)
df_player = df_sem[df_sem["player_id"] == player_id_sel].copy()

if df_player.empty:
    st.warning("No hay datos del jugador en el semestre elegido.")
    st.stop()

player_name = str(df_player["player_short_name"].iloc[0])
team_name_own = str(df_player["team_name"].value_counts().index[0]) if "team_name" in df_player else ""

# Orden cronológico: más nuevo primero
if "match_date" in df_player.columns:
    df_player["_match_order"] = pd.to_datetime(df_player["match_date"], errors="coerce")
    df_player = df_player.sort_values("_match_order", ascending=False).copy()
else:
    df_player["_match_order"] = np.arange(len(df_player))[::-1]

# Etiqueta (sin fecha) para cada partido: "Rival | position | minutes min"
df_player["row_label"] = df_player.apply(
    lambda r: build_row_label(r.get("opponent_name", np.nan), r.get("position", np.nan), r.get("minutes_full_all", np.nan)),
    axis=1
)

st.divider()
st.subheader(f"Jugador: {player_name}  | Equipo: {team_name_own}")

# =========================
# VISUALIZACIONES (orden: el más reciente arriba) — con margen derecho 10% para la leyenda
# =========================
def vis1_player_total_vs_mpm(df_player, player_name):
    need = ['row_label', 'total_distance_full_all', 'total_metersperminute_full_all', '_match_order']
    if not all(c in df_player.columns for c in need): return
    d = df_player[need].copy().sort_values("_match_order", ascending=False)

    d["total_distance_full_all"] = pd.to_numeric(d["total_distance_full_all"], errors="coerce").fillna(0)
    d["total_metersperminute_full_all"] = pd.to_numeric(d["total_metersperminute_full_all"], errors="coerce").fillna(0)

    ylabels = d['row_label'].tolist()
    totals = d['total_distance_full_all'].to_numpy()
    mpm = d['total_metersperminute_full_all'].to_numpy()
    y = np.arange(len(ylabels))

    height = max(6, len(ylabels) * 0.5)
    fig, ax = plt.subplots(figsize=(13, height), dpi=170); _set_font_family()

    ax.barh(y, totals, color=RED_TOTAL, alpha=0.9, edgecolor='none')
    ax.set_xlim(*xlim_with_margin(totals, right_pct=0.10))

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3)
    ax.set_yticks(y); ax.set_yticklabels(ylabels)
    ax.set_xlabel("Distancia total (m)")
    ax.set_title(f"{player_name} — Distancia por partido + m/min", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()

    for yi, val in zip(y, mpm):
        ax.text(100, yi, f"{val:.1f} m/min",
                va='center', ha='left', color='white', fontweight='bold',
                fontsize=10, path_effects=[pe.withStroke(linewidth=1, foreground="black")])

    for yi, t in zip(y, totals):
        if t > 0:
            if t >= 1500:
                ax.text(t * 0.98, yi, f"{t:,.0f} m",
                        va='center', ha='right', color='white', fontweight='bold',
                        fontsize=10, path_effects=[pe.withStroke(linewidth=1, foreground="black")])
            else:
                ax.text(t + 10, yi, f"{t:,.0f} m",
                        va='center', ha='left', color='black', fontweight='bold', fontsize=10)

    plt.tight_layout(); st.pyplot(fig); plt.close(fig)

def _prep_b345_player(df_player: pd.DataFrame):
    need = ['row_label', '_match_order', 'total_distance_full_all',
            'running_distance_full_all','hsr_distance_full_all','sprint_distance_full_all']
    if not all(c in df_player.columns for c in need): return None
    d = df_player[need].copy().sort_values("_match_order", ascending=False)
    for c in ['total_distance_full_all','running_distance_full_all','hsr_distance_full_all','sprint_distance_full_all']:
        d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
    d["sum_b345"] = d["running_distance_full_all"] + d["hsr_distance_full_all"] + d["sprint_distance_full_all"]
    d["pct_b345"] = np.where(d["total_distance_full_all"] > 0,
                             (d["sum_b345"] / d["total_distance_full_all"]) * 100.0, 0.0)
    return d

def vis2_player_b345_stacked(df_player, player_name):
    d = _prep_b345_player(df_player)
    if d is None: return

    labels = d['row_label'].tolist()
    b3 = d['running_distance_full_all'].to_numpy()
    b4 = d['hsr_distance_full_all'].to_numpy()
    b5 = d['sprint_distance_full_all'].to_numpy()
    total_stack = b3 + b4 + b5
    y = np.arange(len(labels))

    height = max(6, len(labels) * 0.5)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120); _set_font_family()

    left = np.zeros_like(b3, dtype=float)
    b3b = ax.barh(y, b3, left=left, color=B3_COLOR, alpha=0.95, edgecolor='none', label="B3: 15–20 km/h")
    left = left + b3
    b4b = ax.barh(y, b4, left=left, color=B4_COLOR, alpha=0.95, edgecolor='none', label="B4: 20–25 km/h")
    left = left + b4
    b5b = ax.barh(y, b5, left=left, color=B5_COLOR, alpha=0.95, edgecolor='none', label="B5: >25 km/h")

    ax.set_xlim(*xlim_with_margin(total_stack, right_pct=0.30))

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3); ax.set_axisbelow(True)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("Distancia (m)")
    ax.set_title(f"{player_name} — HID (B3/B4/B5) por partido", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()

    for arr, cont in [(b3, b3b), (b4, b4b)]:
        for rect, width in zip(cont.patches, arr):
            if width <= 0: continue
            yi = rect.get_y() + rect.get_height()/2.0
            xm = rect.get_x() + width/2.0
            ax.text(xm, yi, f"{width:,.0f} m", va='center', ha='center',
                    color='white', fontweight='bold', fontsize=9,
                    path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    for rect, width in zip(b5b.patches, b5):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        x1 = rect.get_x() + rect.get_width()
        ax.text(x1 + 10, yi, f"{width:,.0f} m", va='center', ha='left',
                color=B5_COLOR, fontweight='bold', fontsize=9)

    ax.legend(loc="lower right", ncols=1, frameon=False)
    plt.tight_layout(); st.pyplot(fig); plt.close(fig)

def vis3_player_b345_sum_pct(df_player, player_name):
    d = _prep_b345_player(df_player)
    if d is None: return

    labels = d['row_label'].tolist()
    total = d['total_distance_full_all'].to_numpy()
    sum_b = d['sum_b345'].to_numpy()
    pct_b = np.where(total > 0, (sum_b / total) * 100.0, 0.0)

    y = np.arange(len(labels))
    height = max(6, len(labels) * 0.5)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120); _set_font_family()

    ax.barh(y, sum_b, color=BLUE_HSR, alpha=0.95, edgecolor='none')
    ax.set_xlim(*xlim_with_margin(sum_b, right_pct=0.10))

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3); ax.set_axisbelow(True)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("Distancia (m)")
    ax.set_title(f"{player_name} — HID (B3+B4+B5) y % del total por partido", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()

    for yi, p in enumerate(pct_b):
        ax.text(25, yi, f"{p:.0f}%", va='center', ha='left',
                color='white', fontsize=10, fontweight='bold',
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    for yi, sb in enumerate(sum_b):
        if sb > 0:
            if sb >= 1200:
                ax.text(sb * 0.98, yi, f"{sb:,.0f} m",
                        va='center', ha='right', color='white', fontweight='bold', fontsize=10,
                        path_effects=[pe.withStroke(linewidth=1, foreground="black")])
            else:
                ax.text(sb + 10, yi, f"{sb:,.0f} m",
                        va='center', ha='left', color='black', fontweight='bold', fontsize=10)
    plt.tight_layout(); st.pyplot(fig); plt.close(fig)

def _prep_counts_player(df_player: pd.DataFrame, cols: list, sum_col_name: str) -> pd.DataFrame:
    need = ['row_label', '_match_order'] + cols
    if not all(c in df_player.columns for c in need): return None
    d = df_player[need].copy().sort_values("_match_order", ascending=False)
    for c in cols:
        d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
    d[sum_col_name] = d[cols[0]] + d[cols[1]]
    return d

def vis4_player_accels(df_player, player_name):
    cols = ['medaccel_count_full_all', 'highaccel_count_full_all']
    d = _prep_counts_player(df_player, cols, 'sum_acc')
    if d is None: return
    labels = d['row_label'].tolist()
    med = d[cols[0]].to_numpy(); high = d[cols[1]].to_numpy()
    sums = med + high
    y = np.arange(len(labels))

    height = max(6, len(labels) * 0.45)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120); _set_font_family()

    ax.set_xlim(*xlim_with_margin(sums, right_pct=0.10))

    left = np.zeros_like(med, dtype=float)
    bmed  = ax.barh(y, med,  left=left, color=ACC_MED_COLOR,  alpha=0.95, edgecolor='none', label="Acel. medias")
    left  = left + med
    bhigh = ax.barh(y, high, left=left, color=ACC_HIGH_COLOR, alpha=0.95, edgecolor='none', label="Acel. altas")

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3); ax.set_axisbelow(True)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("Cantidad")
    ax.set_title(f"{player_name} — Aceleraciones por partido", fontsize=14, pad=20, fontweight='bold')
    ax.text(0.5, 1.03,
            "Medias: 1.5–3.0 m/s² (≥0.7 s)   •   Altas: >3.0 m/s² (≥0.7 s)",
            transform=ax.transAxes, ha='center', va='center', fontsize=10, color='black')
    ax.invert_yaxis()

    for rect, width in zip(bmed.patches, med):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        xm = rect.get_x() + width/2.0
        ax.text(xm, yi, f"{int(width)}", va='center', ha='center',
                color='white', fontweight='bold', fontsize=9,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    for rect, width in zip(bhigh.patches, high):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        xm = rect.get_x() + rect.get_width() - (width/2.0)
        ax.text(xm, yi, f"{int(width)}", va='center', ha='center',
                color='white', fontweight='bold', fontsize=9,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    ax.legend(loc="lower right", frameon=False)
    plt.tight_layout(); st.pyplot(fig); plt.close(fig)

def vis5_player_decels(df_player, player_name):
    cols = ['meddecel_count_full_all', 'highdecel_count_full_all']
    d = _prep_counts_player(df_player, cols, 'sum_dec')
    if d is None: return
    labels = d['row_label'].tolist()
    med = d[cols[0]].to_numpy(); high = d[cols[1]].to_numpy()
    sums = med + high
    y = np.arange(len(labels))

    height = max(6, len(labels) * 0.45)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120); _set_font_family()

    ax.set_xlim(*xlim_with_margin(sums, right_pct=0.10))

    left = np.zeros_like(med, dtype=float)
    bmed  = ax.barh(y, med,  left=left, color=DEC_MED_COLOR,  alpha=0.95, edgecolor='none', label="Desacel. medias")
    left  = left + med
    bhigh = ax.barh(y, high, left=left, color=DEC_HIGH_COLOR, alpha=0.95, edgecolor='none', label="Desacel. altas")

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3); ax.set_axisbelow(True)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("Cantidad")
    ax.set_title(f"{player_name} — Desaceleraciones por partido", fontsize=14, pad=20, fontweight='bold')
    ax.text(0.5, 1.03,
            "Medias: −1.5 a −3.0 m/s² (≥0.7 s)   •   Altas: < −3.0 m/s² (≥0.7 s)",
            transform=ax.transAxes, ha='center', va='center', fontsize=10, color='black')
    ax.invert_yaxis()

    for rect, width in zip(bmed.patches, med):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        xm = rect.get_x() + width/2.0
        ax.text(xm, yi, f"{int(width)}", va='center', ha='center',
                color='black', fontweight='bold', fontsize=9)
    for rect, width in zip(bhigh.patches, high):
        if width <= 0: continue
        yi = rect.get_y() + rect.get_height()/2.0
        xm = rect.get_x() + rect.get_width() - (width/2.0)
        ax.text(xm, yi, f"{int(width)}", va='center', ha='center',
                color='white', fontweight='bold', fontsize=9,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    ax.legend(loc="lower right", frameon=False)
    plt.tight_layout(); st.pyplot(fig); plt.close(fig)

def vis6_player_expl_to_hsr(df_player, player_name):
    COUNT_COL, TIME_COL = 'explacceltohsr_count_full_all', 'timetohsr'
    need = ['row_label', COUNT_COL, TIME_COL, '_match_order']
    if not all(c in df_player.columns for c in need): return
    d = df_player[need].copy().sort_values("_match_order", ascending=False)
    d[COUNT_COL] = pd.to_numeric(d[COUNT_COL], errors='coerce').fillna(0)
    d[TIME_COL]  = pd.to_numeric(d[TIME_COL],  errors='coerce')

    labels = d['row_label'].tolist()
    counts = d[COUNT_COL].to_numpy()
    times  = d[TIME_COL].to_numpy()
    y = np.arange(len(labels))

    height = max(6, len(labels) * 0.5)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120); _set_font_family()

    ax.set_xlim(*xlim_with_margin(counts, right_pct=0.10))

    bars = ax.barh(y, counts, color=B4_COLOR, alpha=0.95, edgecolor='none')

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3); ax.set_axisbelow(True)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("Cantidad")
    ax.set_title(f"{player_name} — Explosive accel → HSR (B4)", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()

    x0, x1 = ax.get_xlim()
    base_x = x0 + 0.02*(x1 - x0)
    for yi, t in enumerate(times):
        txt = "–" if pd.isna(t) else f"{t:.1f} s"
        ax.text(base_x, yi, txt, va='center', ha='left',
                color='white', fontsize=10, fontweight='bold',
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    for rect, c in zip(bars.patches, counts):
        if c <= 0: continue
        yi = rect.get_y() + rect.get_height() / 2.0
        x_end = rect.get_x() + rect.get_width()
        ax.text(x_end + 0.01*(x1-x0), yi, f"{int(c)}",
                va='center', ha='left', color='black', fontweight='bold', fontsize=10)
    plt.tight_layout(); st.pyplot(fig); plt.close(fig)

def vis7_player_expl_to_sprint(df_player, player_name):
    COUNT_COL, TIME_COL = 'explacceltosprint_count_full_all', 'timetosprint'
    need = ['row_label', COUNT_COL, TIME_COL, '_match_order']
    if not all(c in df_player.columns for c in need): return
    d = df_player[need].copy().sort_values("_match_order", ascending=False)
    d[COUNT_COL] = pd.to_numeric(d[COUNT_COL], errors='coerce').fillna(0)
    d[TIME_COL]  = pd.to_numeric(d[TIME_COL],  errors='coerce')

    labels = d['row_label'].tolist()
    counts = d[COUNT_COL].to_numpy()
    times  = d[TIME_COL].to_numpy()
    y = np.arange(len(labels))

    height = max(6, len(labels) * 0.5)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120); _set_font_family()

    ax.set_xlim(*xlim_with_margin(counts, right_pct=0.10))

    bars = ax.barh(y, counts, color=B5_COLOR, alpha=0.95, edgecolor='none')

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3); ax.set_axisbelow(True)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("Cantidad")
    ax.set_title(f"{player_name} — Explosive accel → Sprint (B5)", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()

    x0, x1 = ax.get_xlim()
    base_x = x0 + 0.02*(x1 - x0)
    for yi, t in enumerate(times):
        txt = "–" if pd.isna(t) else f"{t:.1f} s"
        ax.text(base_x, yi, txt, va='center', ha='left',
                color='white', fontsize=10, fontweight='bold',
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    for rect, c in zip(bars.patches, counts):
        if c <= 0: continue
        yi = rect.get_y() + rect.get_height() / 2.0
        x_end = rect.get_x() + rect.get_width()
        ax.text(x_end + 0.01*(x1-x0), yi, f"{int(c)}",
                va='center', ha='left', color='black', fontweight='bold', fontsize=10)
    plt.tight_layout(); st.pyplot(fig); plt.close(fig)

def vis8_player_psv99(df_player, player_name):
    COL = 'psv99'
    need = ['row_label', COL, '_match_order']
    if not all(c in df_player.columns for c in need): return
    d = df_player[need].copy().sort_values("_match_order", ascending=False)
    d[COL] = pd.to_numeric(d[COL], errors='coerce').fillna(0)

    labels = d['row_label'].tolist()
    speeds  = d[COL].to_numpy()
    y = np.arange(len(labels))
    height = max(6, len(labels) * 0.5)
    fig, ax = plt.subplots(figsize=(13, height), dpi=120); _set_font_family()

    bars = ax.barh(y, speeds, color=B5_COLOR, alpha=0.95, edgecolor='none')
    ax.set_xlim(*xlim_with_margin(speeds, right_pct=0.10))

    ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.1f}'))
    ax.grid(axis='x', linestyle=':', alpha=0.3); ax.set_axisbelow(True)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("Velocidad (km/h)")
    ax.set_title(f"{player_name} — PSV99 por partido", fontsize=14, pad=12, fontweight='bold')
    ax.invert_yaxis()

    for rect, v in zip(bars.patches, speeds):
        if v <= 0: continue
        yi = rect.get_y() + rect.get_height() / 2.0
        x_end = rect.get_x() + rect.get_width()
        x_label = x_end - 0.02 * (ax.get_xlim()[1] - ax.get_xlim()[0])
        ax.text(x_label, yi, f"{v:.1f} km/h",
                va='center', ha='right',
                color='white', fontweight='bold', fontsize=10,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")])
    plt.tight_layout(); st.pyplot(fig); plt.close(fig)

# =========================
# RENDER
# =========================
st.subheader("Reportes por partido")

vis1_player_total_vs_mpm(df_player, player_name)
vis2_player_b345_stacked(df_player, player_name)
vis3_player_b345_sum_pct(df_player, player_name)
vis4_player_accels(df_player, player_name)
vis5_player_decels(df_player, player_name)
vis6_player_expl_to_hsr(df_player, player_name)
vis7_player_expl_to_sprint(df_player, player_name)
vis8_player_psv99(df_player, player_name)
