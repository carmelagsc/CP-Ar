#!/usr/bin/env python3
import argparse
import json
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np
from pathlib import Path

# --------------------------
# Helpers
# --------------------------

def _detect_time_column(df: pd.DataFrame) -> Tuple[pd.Series, str]:
    """Detecta la columna de tiempo en el DataFrame y la convierte a segundos desde el inicio de la sesión."""
    cols = {c.lower(): c for c in df.columns}

    if "timestamp_s" in cols:
        s = pd.to_numeric(df[cols["timestamp_s"]], errors="coerce")
        if s.isna().any():
            raise ValueError("Found 'timestamp_s' but contains non-numeric values.")
        return s.astype(float), cols["timestamp_s"]

    for cand in ["timestamp", "time"]:
        if cand in cols:
            ts = pd.to_datetime(df[cols[cand]], errors="coerce", utc=True)
            if ts.isna().any():
                raise ValueError(f"Column '{cols[cand]}' has unparsable datetimes.")
            s = (ts - ts.iloc[0]).dt.total_seconds()
            return s.astype(float), cols[cand]

    raise ValueError("No valid time column found. Provide either 'timestamp_s' or 'timestamp'/'time' in CSV.")

def _require_cpm(df: pd.DataFrame) -> pd.Series:
    # Garantiza que exista una columna cpm y la devuelve como numérica.
    cols = {c.lower(): c for c in df.columns}
    if "cpm" not in cols:
        raise ValueError("CSV must contain a 'cpm' column (compressions per minute).")
    s = pd.to_numeric(df[cols["cpm"]], errors="coerce")
    if s.isna().any():
        raise ValueError("Column 'cpm' contains non-numeric values.")
    return s.astype(float)

def _require_depth_cm(df: pd.DataFrame) -> Optional[pd.Series]:
    candidates = ["depth_cm", "profundidad", "profundidad_cm", "depth", "prof_cm"]
    cols = {c.lower(): c for c in df.columns}
    for k in candidates:
        if k in cols:
            s = pd.to_numeric(df[cols[k]], errors="coerce")
            return s
    return None

def _segments_by_condition(times_s: np.ndarray, values: np.ndarray, predicate) -> List[Tuple[float, float]]:
    n = len(values)
    if n < 2:
        return []
    segs = []
    in_seg = False
    seg_start = None
    for i in range(n-1):
        v = values[i]
        dt = times_s[i+1] - times_s[i]
        good = bool(predicate(v)) and dt > 0
        if good and not in_seg:
            in_seg = True
            seg_start = times_s[i]
        if not good and in_seg:
            in_seg = False
            segs.append((seg_start, times_s[i]))
            seg_start = None
    if in_seg:
        segs.append((seg_start, times_s[-1]))
    return segs

def _time_weighted_percent(times_s: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    total = float(times_s[-1] - times_s[0])
    if total <= 0:
        return 0.0
    acc = 0.0
    for i in range(n-1):
        dt = times_s[i+1] - times_s[i]
        if dt <= 0:
            continue
        v = values[i]
        if lo <= v <= hi:
            acc += dt
    return 100.0 * acc / total

def _time_weighted_mean(times_s: np.ndarray, values) -> float:
    t = np.asarray(times_s, dtype=float)
    v = np.asarray(values,  dtype=float)
    n = v.shape[0]
    if n < 2:
        return float(v[0]) if n == 1 else float("nan")
    total = float(t[-1] - t[0])
    if total <= 0:
        return float("nan")
    acc = 0.0
    for i in range(n - 1):
        dt = t[i+1] - t[i]
        if dt > 0:
            acc += v[i] * dt
    return acc / total

def _time_weighted_std(times_s: np.ndarray, values) -> float:
    t = np.asarray(times_s, dtype=float)
    v = np.asarray(values,  dtype=float)
    n = v.shape[0]
    mu = _time_weighted_mean(t, v)
    if n < 2 or not np.isfinite(mu):
        return float("nan")
    total = float(t[-1] - t[0])
    if total <= 0:
        return float("nan")
    var_acc = 0.0
    for i in range(n - 1):
        dt = t[i+1] - t[i]
        if dt > 0:
            diff = v[i] - mu
            var_acc += (diff * diff) * dt
    var = var_acc / total
    return float(np.sqrt(var))

def _contiguous_zero_pauses(times_s: np.ndarray, values: np.ndarray, min_pause_s: float) -> List[Tuple[float,float]]:
    segs = _segments_by_condition(times_s, values, predicate=lambda v: v == 0)
    long_segs = [(a,b) for (a,b) in segs if (b-a) >= min_pause_s]
    return long_segs

def _first_time_condition(times_s: np.ndarray, values: np.ndarray, predicate) -> Optional[float]:
    n = len(values)
    if n < 2:
        return None
    for i in range(n-1):
        if predicate(values[i]):
            return float(times_s[i] - times_s[0])
    return None

def _sustained_over_threshold(times_s: np.ndarray, values: np.ndarray, thr: float, min_duration_s: float) -> List[Tuple[float,float]]:
    segs = _segments_by_condition(times_s, values, predicate=lambda v: v > thr)
    long = [(a,b) for (a,b) in segs if (b-a) >= min_duration_s]
    return long

# --------------------------
# Main computation
# --------------------------

def compute_metrics_from_cpm(df: pd.DataFrame,
                             pause_threshold_s: float = 10.0,
                             sustained_high_thr: float = 130.0,
                             sustained_high_min_s: float = 10.0,
                             depth_low_cm: float = 5.0,
                             depth_high_cm: float = 6.0,
                             depth_alarm_low_cm: float = 4.5,
                             depth_alarm_min_s: float = 10.0) -> Dict[str, Any]:
    
    # 1. Detectar Tiempo y Columnas
    ts_s, detected_time_col = _detect_time_column(df)
    cpm = _require_cpm(df)
    depth_cm = _require_depth_cm(df) 
    
    # 2. Ignorar los primeros 10s (warm-up)
    mask = ts_s - ts_s.iloc[0] >= 10.0
    ts_s = ts_s[mask].reset_index(drop=True)
    cpm = cpm[mask].reset_index(drop=True)
    
    # 3. Reconstrucción de tiempo si está roto
    n = len(cpm)
    if n >= 2:
        dt = np.diff(ts_s.values.astype(float))
        total_duration = float(ts_s.iloc[-1] - ts_s.iloc[0])
        if (dt <= 0).any() or total_duration <= 0:
            fs_assumed = 100.0  
            ts_s = pd.Series(np.arange(n, dtype=float) / fs_assumed)
    else:
        fs_assumed = 100.0
        ts_s = pd.Series(np.arange(n, dtype=float) / fs_assumed)

    # 4. ORDENAMIENTO
    order = np.argsort(ts_s.values)
    ts_s = ts_s.iloc[order].reset_index(drop=True)
    cpm = cpm.iloc[order].reset_index(drop=True)
    if depth_cm is not None:
        depth_cm = depth_cm.iloc[order].reset_index(drop=True)

    n = len(cpm)
    duration_s = float(ts_s.iloc[-1]) if n >= 2 else 0.0

    # 5. CÁLCULO DE HANDS-OFF
    cols = {c.lower(): c for c in df.columns}
    col_no_rcp = cols.get("no_rcp") or cols.get("no_rcp_active")
    
    hands_off_time_s = 0.0
    time_with_comp_s = 0.0 

    if col_no_rcp:
        no_rcp_vals = pd.to_numeric(df[col_no_rcp], errors='coerce').fillna(0).astype(int)
        no_rcp_vals = no_rcp_vals[mask].reset_index(drop=True) 
        no_rcp_vals = no_rcp_vals.iloc[order].reset_index(drop=True)

        if n >= 2:
            dt_arr = np.diff(ts_s.values)
            flags = no_rcp_vals.values[:-1]
            hands_off_time_s = np.sum(dt_arr[flags == 1])
            
        time_with_comp_s = duration_s - hands_off_time_s
    else:
        if n >= 2:
            for i in range(n-1):
                dt = ts_s.iloc[i+1] - ts_s.iloc[i]
                if dt > 0 and cpm.iloc[i] > 0:
                    time_with_comp_s += dt
        hands_off_time_s = duration_s - time_with_comp_s
    
    compression_fraction_pct = 100.0 * time_with_comp_s / duration_s if duration_s > 0 else 0.0

    # Estadísticas básicas
    mean_cpm = _time_weighted_mean(ts_s.values, cpm)
    std_cpm = _time_weighted_std(ts_s.values, cpm)
    median_cpm = float(np.median(cpm.values)) if n > 0 else float("nan")
    in_target_pct = _time_weighted_percent(ts_s.values, cpm.values, 100.0, 120.0)

    long_pauses = _contiguous_zero_pauses(ts_s.values, cpm.values, min_pause_s=pause_threshold_s)
    topk = sorted(long_pauses, key=lambda ab: (ab[1]-ab[0]), reverse=True)[:3]
    topk_list = [{"start_s": round(a - ts_s.iloc[0], 3), "end_s": round(b - ts_s.iloc[0], 3), "duration_s": round(b-a, 3)} for (a,b) in topk]

    t_first_comp = _first_time_condition(ts_s.values, cpm.values, predicate=lambda v: v > 0)
    high_rate_segs = _sustained_over_threshold(ts_s.values, cpm.values, thr=sustained_high_thr, min_duration_s=sustained_high_min_s)
    high_rate_list = [{"start_s": round(a - ts_s.iloc[0], 3), "end_s": round(b - ts_s.iloc[0], 3), "duration_s": round(b-a, 3)} for (a,b) in high_rate_segs]
    
    # --- LOGICA DE PROFUNDIDAD CORREGIDA ---
    depth_block = None
    shallow_segments_list = [] # Siempre iniciamos la lista vacía
    
    if depth_cm is not None and len(depth_cm) >= 2:
        mean_depth = _time_weighted_mean(ts_s.values, depth_cm.values)
        std_depth  = _time_weighted_std(ts_s.values, depth_cm.values)
        median_depth = float(np.median(depth_cm.values))

        in_5_6_pct = _time_weighted_percent(ts_s.values, depth_cm.values, depth_low_cm, depth_high_cm)
        below_5_pct = _time_weighted_percent(ts_s.values, depth_cm.values, -1e9, depth_low_cm - 1e-9)
        above_6_pct = _time_weighted_percent(ts_s.values, depth_cm.values, depth_high_cm + 1e-9, 1e9)
        
        depth_block = {
                "mean_cm": mean_depth,
                "median_cm": median_depth,
                "std_cm": std_depth,
                "in_target_pct_5_6": in_5_6_pct,
                "below_5_pct": below_5_pct,
                "above_6_pct": above_6_pct,
        }

        # Calculamos segmentos SIEMPRE que haya datos de profundidad
        # Ignoramos valores < 0.5 cm (hands-off) para no generar falsa alarma
        shallow_segs = _segments_by_condition(
            ts_s.values, 
            depth_cm.values, 
            predicate=lambda v: (0.5 < v < depth_alarm_low_cm)
        )
        shallow_segs = [(a, b) for (a, b) in shallow_segs if (b - a) >= depth_alarm_min_s]
        
        # Llenamos la lista (quedará vacía [] si no hubo alarmas, que es lo correcto)
        shallow_segments_list = [
            {"start_s": round(a - ts_s.iloc[0], 3),
             "end_s": round(b - ts_s.iloc[0], 3),
             "duration_s": round(b-a, 3)} for (a,b) in shallow_segs
        ]

    # Armado del Resultado
    results = {
            "session": {
                "samples": int(n),
                "time_column": detected_time_col,
                "duration_s": round(duration_s, 3),
            },
            "cpr_quality": {
                "rate_bpm": {
                    "mean": round(mean_cpm, 3) if np.isfinite(mean_cpm) else None,
                    "median": round(median_cpm, 3) if np.isfinite(median_cpm) else None,
                    "std": round(std_cpm, 3) if np.isfinite(std_cpm) else None,
                    "in_target_pct_100_120": round(in_target_pct, 3)
                },
                "compression_fraction_pct": round(compression_fraction_pct, 3),
                "hands_off_time_s": round(hands_off_time_s, 3),
                "pauses_over_threshold_s": {
                    "threshold_s": pause_threshold_s,
                    "count": len(long_pauses),
                    "top3_by_duration": topk_list
                },
                "time_to_first_compression_s": t_first_comp,
                "depth_cm": {
                    "mean_cm": round(depth_block["mean_cm"], 3) if depth_block and np.isfinite(depth_block["mean_cm"]) else None,
                    "median_cm": round(depth_block["median_cm"], 3) if depth_block and np.isfinite(depth_block["median_cm"]) else None,
                    "std_cm": round(depth_block["std_cm"], 3) if depth_block and np.isfinite(depth_block["std_cm"]) else None,
                    "in_target_pct_5_6": round(depth_block["in_target_pct_5_6"], 3) if depth_block else None,
                    "below_5_pct": round(depth_block["below_5_pct"], 3) if depth_block else None,
                    "above_6_pct": round(depth_block["above_6_pct"], 3) if depth_block else None
                } if depth_block else None,
            
                "alarms": {
                    "sustained_high_rate": {
                        "threshold_cpm": sustained_high_thr,
                        "min_duration_s": sustained_high_min_s,
                        "segments": high_rate_list
                    },
                    "sustained_shallow_depth": {
                        "threshold_cm": depth_alarm_low_cm,
                        "min_duration_s": depth_alarm_min_s,
                        "segments": shallow_segments_list # Ahora siempre es una lista (puede ser [])
                    } if depth_block else None, # Solo es None si NO hay sensor de profundidad
                },

                "not_computable_from_cpm_only": [
                    *([] if depth_block is not None else ["depth_metrics"]),
                    "recoil_complete_pct",
                    "ventilation_rate_or_ratio",
                    "time_to_first_shock"
                ],
                "reference_ranges_adult": {
                    "rate_bpm_target": "100-120/min",
                    "compression_fraction_target_pct": "> 60% (orientativo)",
                    "depth_cm_target": "5-6 cm"
                },
            },
    }
    return results

def _fmt(v, ndigits=1, suf=""):
    """Formatea números; si es None, devuelve 'N/D'."""
    if v is None:
        return "N/D"
    try:
        return f"{round(float(v), ndigits)}{suf}"
    except Exception:
        return str(v)

def write_markdown_summary(results: Dict[str, Any]) -> str:
    s = results.get("session", {})
    q = results.get("cpr_quality", {}) or {}
    # Helper seguro para extraer alarms
    alarms = q.get("alarms", {}) or {} 

    rbpm = q.get("rate_bpm", {}) or {}
    depth = q.get("depth_cm")  

    md = []
    md.append("# Resumen de calidad de RCP")
    md.append("")
    md.append(f"- Duración: **{_fmt(s.get('duration_s'), 1, ' s')}** (muestras: {s.get('samples', 'N/D')})")
    md.append(f"- Franjas objetivo adulto: **Frecuencia 100–120/min**, **Profundidad 5–6 cm**")
    md.append("")

    # Frecuencia
    md.append("## Frecuencia de compresiones (bpm)")
    md.append(f"- Media: **{_fmt(rbpm.get('mean'), 1)}**")
    md.append(f"- Mediana: **{_fmt(rbpm.get('median'), 1)}**")
    md.append(f"- Desvío: **{_fmt(rbpm.get('std'), 1)}**")
    md.append(f"- % dentro de 100–120: **{_fmt(rbpm.get('in_target_pct_100_120'), 1, '%')}**")
    md.append("")

    # Profundidad (opcional)
    if isinstance(depth, dict):
        md.append("## Profundidad (cm)")
        md.append(f"- Media: **{_fmt(depth.get('mean_cm'), 2)}** cm")
        md.append(f"- Mediana: **{_fmt(depth.get('median_cm'), 2)}** cm")
        md.append(f"- Desvío: **{_fmt(depth.get('std_cm'), 2)}** cm")
        md.append(f"- % dentro de 5–6 cm: **{_fmt(depth.get('in_target_pct_5_6'), 1, '%')}**")
        md.append(f"- % insuficiente (< 5 cm): **{_fmt(depth.get('below_5_pct'), 1, '%')}**")
        md.append(f"- % excesiva (> 6 cm): **{_fmt(depth.get('above_6_pct'), 1, '%')}**")
        md.append("")

    # Fractions & Pausas
    md.append("## Fracciones & Pausas")
    md.append(f"- Compression Fraction: **{_fmt(q.get('compression_fraction_pct'), 1, '%')}** (objetivo > 60%)")
    md.append(f"- Hands-off total: **{_fmt(q.get('hands_off_time_s'), 1, ' s')}**")
    pauses = (q.get("pauses_over_threshold_s") or {})
    md.append(f"- Pausas ≥ {pauses.get('threshold_s', 'N/D')} s: **{pauses.get('count', 0)}**")
    top3 = pauses.get("top3_by_duration") or []
    if top3:
        md.append("  - Top 3 pausas (inicio–fin, duración):")
        for p in top3:
            md.append(
                f"    - {_fmt(p.get('start_s'),1,' s')}–{_fmt(p.get('end_s'),1,' s')}, "
                f"dur **{_fmt(p.get('duration_s'),1,' s')}**"
            )
    md.append("")

    # Hitos
    md.append("## Hitos")
    t1 = q.get("time_to_first_compression_s")
    md.append(f"- Tiempo a primera compresión: **{_fmt(t1, 1, ' s')}**")
    md.append("")

    # Alarmas
    md.append("## Alarmas")
    # Frecuencia sostenida alta
    a_rate = alarms.get("sustained_high_rate") or {}
    segs = a_rate.get("segments") or []
    if segs:
        md.append(
            f"- Frecuencia sostenida > {a_rate.get('threshold_cpm','N/D')} cpm por ≥ "
            f"{a_rate.get('min_duration_s','N/D')} s: **{len(segs)} segmentos**"
        )
        for seg in segs:
            md.append(
                f"  - {_fmt(seg.get('start_s'),1,' s')}–{_fmt(seg.get('end_s'),1,' s')}, "
                f"dur **{_fmt(seg.get('duration_s'),1,' s')}**"
            )
    else:
        md.append("- Sin segmentos de frecuencia sostenida alta detectados.")

    # Profundidad sostenida baja
    a_depth = alarms.get("sustained_shallow_depth")
    if isinstance(a_depth, dict) and a_depth.get("segments"):
        md.append(
            f"- Profundidad sostenida < {a_depth.get('threshold_cm','N/D')} cm por ≥ "
            f"{a_depth.get('min_duration_s','N/D')} s: **{len(a_depth['segments'])} segmentos**"
        )
        for seg in a_depth["segments"]:
            md.append(
                f"  - {_fmt(seg.get('start_s'),1,' s')}–{_fmt(seg.get('end_s'),1,' s')}, "
                f"dur **{_fmt(seg.get('duration_s'),1,' s')}**"
            )
    md.append("")

    # No calculable
    md.append("## No calculable con CPM solamente")
    extras = []
    if not isinstance(depth, dict):
        extras.append("profundidad")
    extras += ["recoil", "ventilaciones", "primer choque"]
    md.append("- " + ", ".join(extras) + ": **no disponibles** en este flujo.")
    return "\n".join(md)

def main():
    parser = argparse.ArgumentParser(description="Compute CPR metrics from CPM-only CSV.")
    parser.add_argument("--csv", required=True, help="Ruta al CSV con columnas: cpm y timestamp_s OR timestamp/time.")
    parser.add_argument("--out", required=False, default="/mnt/data/metrics.json", help="Ruta de salida del JSON.")
    parser.add_argument("--md", required=False, default="/mnt/data/metrics_summary.md", help="Ruta de salida del resumen Markdown.")
    parser.add_argument("--pause_threshold_s", type=float, default=10.0, help="Umbral de pausa (s) para conteo/top-k.")
    parser.add_argument("--sustained_high_thr", type=float, default=130.0, help="CPM para alarma de sostenido alto.")
    parser.add_argument("--sustained_high_min_s", type=float, default=10.0, help="Duración mínima (s) de sostenido alto.")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    results = compute_metrics_from_cpm(
        df,
        pause_threshold_s=args.pause_threshold_s,
        sustained_high_thr=args.sustained_high_thr,
        sustained_high_min_s=args.sustained_high_min_s,
    )
    # Write JSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Write Markdown summary
    md_path = Path(args.md)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(write_markdown_summary(results))

    print(f"Wrote JSON to: {out_path}")
    print(f"Wrote Markdown to: {md_path}")

if __name__ == "__main__":
    main()