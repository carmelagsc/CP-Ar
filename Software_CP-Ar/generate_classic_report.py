#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

CSS = """
body { font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #222; }
h1, h2, h3 { margin: 0.4em 0; }
h1 { font-size: 1.8rem; }
h2 { font-size: 1.4rem; margin-top: 1.2rem; }
h3 { font-size: 1.1rem; margin-top: 1rem; }
.section { margin: 1rem 0 1.2rem 0; padding: 0.8rem 1rem; background: #fafafa; border: 1px solid #eee; border-radius: 8px; }
small, .muted { color: #666; }
table { width: 100%; border-collapse: collapse; margin-top: 0.6rem; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; }
.bad { color: #a40000; font-weight: bold; }
.good { color: #0b6; font-weight: bold; }
.kpi { font-weight: bold; }
.code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
.highlight { background: #fff4cc; border-radius: 4px; padding: 0 4px; }
.header { display:flex; justify-content: space-between; align-items: baseline; }
"""

def pct(v):
    if v is None: return "N/D"
    return f"{v:.1f}%"

def fmt(v, nd=2):
    if v is None: return "N/D"
    return f"{v:.{nd}f}"

def badge(value, lo, hi):
    if value is None:
        return '<span class="muted">N/D</span>'
    if lo <= value <= hi:
        return f'<span class="good">{value:.2f}</span>'
    return f'<span class="bad">{value:.2f}</span>'

def render_table_rows(rows):
    return "\n".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows])

def render_report(metrics: dict) -> str:
    s = metrics.get("session", {})
    q = metrics.get("cpr_quality", {})
    rbpm = q.get("rate_bpm", {})

    # KPI checks (solo los que tenemos con CPM)
    mean_rate = rbpm.get("mean")
    in_target = rbpm.get("in_target_pct_100_120")
    comp_frac = q.get("compression_fraction_pct")
    hands_off = q.get("hands_off_time_s")

    # Simple quality highlights
    mean_rate_html = badge(mean_rate if mean_rate is not None else None, 100, 120)
    comp_frac_html = f'<span class="kpi">{fmt(comp_frac,1)}%</span>' if comp_frac is not None else "N/D"
    if comp_frac is not None and comp_frac < 60:
        comp_frac_html = f'<span class="bad">{fmt(comp_frac,1)}%</span>'
    elif comp_frac is not None:
        comp_frac_html = f'<span class="good">{fmt(comp_frac,1)}%</span>'

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    html = [f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe sesión RCP</title>
<style>{CSS}</style>
</head>
<body>
<div class="header">
  <h1>Informe sesión RCP</h1>
  <small class="muted">Generado: {now}</small>
</div>

<div class="section">
  <h2>Resumen</h2>
  <p>
    Duración de sesión: <span class="kpi">{fmt(s.get('duration_s'),1)} s</span>
  </p>
  <p>
    Muestras: <span class="kpi">{s.get('samples','N/D')}</span>
  </p>
  <p>
    Franja objetivo adulto (frecuencia): <span class="kpi">100–120/min</span> ·
    Objetivo de <em>Compression Fraction</em>: <span class="kpi">&gt; 60%</span>
  </p>
  <p>
    Frecuencia media: {mean_rate_html} cpm ·
    % en 100–120: <span class="kpi">{pct(in_target)}</span> ·
    Compression Fraction: {comp_frac_html} ·
    Hands-off total: <span class="kpi">{fmt(hands_off,1)} s</span>
  </p>
</div>

<div class="section">
  <h2>Métricas de frecuencia</h2>
  <table>
    <thead><tr><th>Métrica</th><th>Valor</th></tr></thead>
    <tbody>
      {render_table_rows([
        ("Media (cpm)", fmt(rbpm.get("mean"))),
        ("Mediana (cpm)", fmt(rbpm.get("median"))),
        ("Desvío (cpm)", fmt(rbpm.get("std"))),
        ("% dentro de 100–120", pct(rbpm.get("in_target_pct_100_120"))),
      ])}
    </tbody>
  </table>
</div>

<div class="section">
  <h2>Pausas y fracciones</h2>
  <table>
    <thead><tr><th>Métrica</th><th>Valor</th></tr></thead>
    <tbody>
      {render_table_rows([
        ("Compression Fraction", pct(q.get("compression_fraction_pct"))),
        ("Hands-off time (s)", fmt(q.get("hands_off_time_s"),1)),
        ("Tiempo a primera compresión (s)", fmt(q.get("time_to_first_compression_s"),1))
      ])}
    </tbody>
  </table>
</div>
"""]

    # Pausas top-3
    pauses = (q.get("pauses_over_threshold_s") or {}).get("top3_by_duration", [])
    if pauses:
        rows = []
        for p in pauses:
            rows.append((
                f"Inicio–Fin (s)",
                f"{fmt(p.get('start_s'),1)}–{fmt(p.get('end_s'),1)} (dur {fmt(p.get('duration_s'),1)} s)"
            ))
        html.append(f"""
<div class="section">
  <h2>Top-3 pausas prolongadas</h2>
  <p class="muted">Umbral: {(q.get("pauses_over_threshold_s") or {}).get("threshold_s","N/D")} s · Conteo total: {(q.get("pauses_over_threshold_s") or {}).get("count","N/D")}</p>
  <table>
    <thead><tr><th>Detalle</th><th>Valor</th></tr></thead>
    <tbody>
      {render_table_rows(rows)}
    </tbody>
  </table>
</div>
""")

    # Alarmas: frecuencia sostenida alta
    alarms = metrics.get("alarms", {})
    segs = (alarms.get("sustained_high_rate") or {}).get("segments", [])
    thr = (alarms.get("sustained_high_rate") or {}).get("threshold_cpm", "N/D")
    min_s = (alarms.get("sustained_high_rate") or {}).get("min_duration_s", "N/D")
    if segs:
        rows = []
        for sseg in segs:
            rows.append((
                "Segmento",
                f"{fmt(sseg.get('start_s'),1)}–{fmt(sseg.get('end_s'),1)} (dur {fmt(sseg.get('duration_s'),1)} s)"
            ))
        html.append(f"""
<div class="section">
  <h2>Alarmas</h2>
  <p>Frecuencia sostenida &gt; <span class="highlight">{thr} cpm</span> por ≥ <span class="highlight">{min_s} s</span>:</p>
  <table>
    <thead><tr><th>Tipo</th><th>Detalle</th></tr></thead>
    <tbody>
      {render_table_rows(rows)}
    </tbody>
  </table>
</div>
""")
    else:
        html.append(f"""
<div class="section">
  <h2>Alarmas</h2>
  <p class="muted">Sin segmentos de frecuencia sostenida alta detectados (umbral {thr} cpm, duración mínima {min_s} s).</p>
</div>
""")




    return "".join(html)

def main(in_path="C:/Users/Equipo/Documents/Proyecto_Final/Datos/metrics.json", out_path="C:/Users/Equipo/Documents/Proyecto_Final/Datos/reporte_clasico.html"):
    with open(in_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)
    html = render_report(metrics)
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"Reporte HTML generado en {out_path}")

if __name__ == "__main__":
    main()
