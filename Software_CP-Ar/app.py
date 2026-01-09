from flask import Flask, request, render_template, jsonify, send_file
import csv
import os
import io
import filtro3 as ft
import pandas as pd
from datetime import datetime, timezone
import time

from filtro3 import stats_bp
from cpr_metrics import compute_metrics_from_cpm  
import json
from cpr_metrics import write_markdown_summary
from io import BytesIO

app = Flask(__name__)
app.register_blueprint(stats_bp)

FIXED_5CM_BASELINE = 1.7104

datos_z = []
archivo_csv = "datos_CR.csv"
guardando = False 
registro_tiempo_iniciado = False 
comentario_actual = ""
total_muestras_procesadas = 0

# Crear el CSV si no existe 
if not os.path.exists(archivo_csv):
    with open(archivo_csv, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["indice", "timestamp_s", "Aceleración", "cpm", "prof_cm", "no_rcp"])

@app.route("/")
def mostrar_grafico():
    return render_template("index.html")

@app.route("/start", methods=["POST"]) #Esta ruta permite iniciar la grabación de la sesión mediante el boton start
def start():
    global guardando, datos_z, comentario_actual, registro_tiempo_iniciado, total_muestras_procesadas
    datos_z = []
    total_muestras_procesadas = 0
    guardando = True
    #registro_tiempo_iniciado = False

    global state
    state.session_start_ts = None  # <-- Asegura que el timer esté reseteado
    state.session_active = True    # Marcamos que la grabación está 'activa' (esperando datos)
   
    comentario_actual = request.json.get("comentario", "").strip()
    try:
        ft.reset_stream(fixed_baseline_prom=FIXED_5CM_BASELINE)
    except Exception:
        ft.reset_stream()
  
    with open(archivo_csv, mode='w', newline='') as f:   # Reiniciar CSV 
        writer = csv.writer(f)
        writer.writerow(["indice", "timestamp_s", "Aceleración", "cpm", "prof_cm", "no_rcp"])
    
    return "Guardado iniciado"

@app.route("/stop", methods=["POST"]) # Esta ruta permite frenar el guardado y la sesión para el análisis de métricas
def stop_recording():
    global guardando, registro_tiempo_iniciado
    guardando = False
    registro_tiempo_iniciado = False # <-- Reinicia el flag

    # Resetea el estado para /api/device-info
    global state
    state.session_active = False
    state.session_start_ts = None
    state.session_compressions = 0
    state.session_cpm = None
    try:
        results = compute_metrics_from_cpm( df = pd.read_csv( archivo_csv, encoding="latin1"), pause_threshold_s=10.0,
                                           sustained_high_thr=130.0,
                                           sustained_high_min_s=20.0, depth_low_cm = 4.8,
                                           depth_high_cm = 6.0,
                                           depth_alarm_low_cm = 4.5,
                                           depth_alarm_min_s= 10.0,)

        return jsonify({"ok": True, "samples": results["session"]["samples"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/datos") #ruta para ordenar los datos en json
def datos_json():
    return jsonify({
        "valores": datos_z,
        "indices": list(range(len(datos_z)))
    })

@app.route("/esp32", methods=["POST"])  #ruta para recibir las muestras desde la esp32
def recibir_datos():
    global datos_z, guardando, comentario_actual, state, total_muestras_procesadas

    contenido = request.data.decode("utf-8").strip()
    try:
        nuevas_medidas = [float(linea) for linea in contenido.splitlines() if linea]
    except ValueError:
        return "CPM:0,PROF:0.0"
    
    #start_index = len(datos_z) #Buffer en memoria 
    datos_z.extend(nuevas_medidas)


    if guardando and state.session_start_ts is None:
        state.session_start_ts = time.time()  # <-- Inicia el timer AQUI solo si es None
     # Marca que el timer ya se ha iniciado
     
        print(f"Timer de sesión iniciado a las: {state.session_start_ts}")
    n_comp, cpm, prof_cm, no_rcp = 0, 0.0, 0.0, 0
    try:
        m = ft.update_stream(nuevas_medidas)
        n_comp = m["n_comp"]
        cpm    = m["cpm"]
        prof_cm= m["depth_cm"]
        no_rcp = 1 if m.get("no_rcp_active", False) else 0
        
    except Exception:
        n_comp, cpm, prof_cm = 0, 0.0, 0.0

    if guardando: 
        fs_local = getattr(ft, "fs", 100.0)
        with open(archivo_csv, mode='a', newline='') as f:
            writer = csv.writer(f)
            # Usamos el contador global para mantener la continuidad del tiempo
            start_absolute_index = total_muestras_procesadas 
            
            for i, valor in enumerate(nuevas_medidas):
                indice = start_absolute_index + i
                timestamp_s = indice / fs_local # Tiempo absoluto y continuo
                
                writer.writerow([indice, f"{timestamp_s:.2f}", valor, f"{cpm:.1f}", f"{prof_cm:.1f}", no_rcp])

    # Actualizamos contadores
    total_muestras_procesadas += len(nuevas_medidas)
    
    if len(datos_z) > 2000:  
        datos_z = datos_z[-2000:]
        
    return f"CPM:{int(round(cpm))},PROF:{prof_cm:.1f}"

@app.route("/descargar") #ruta par descargar el csv
def descargar_csv():
    global datos_z
    global guardando
    guardando = False
    with open(archivo_csv, "r") as f:
        contenido = f.read()
    datos_z = []
    with open(archivo_csv, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["indice", "timestamp_s", "Aceleración", "cpm", "prof_cm", "no_rcp"])

    return send_file(
        io.BytesIO(contenido.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="datos_pruebasCR.csv"
    )

@app.route("/cal_status") #calculos para la profundidad
def cal_status():
    try:
        m = ft.get_last_metrics()
        return jsonify({
            "calibrated": m.get("calibrated", False),
            "pct_target": m.get("pct_target", 0.0),     # 100% == 5 cm
            "hit_5cm":    m.get("hit_5cm", False),
            "depth_cm_rel": m.get("depth_cm", 0.0),     # relativo al baseline
            "no_rcp_active": m.get("no_rcp_active", False),
            "no_rcp_time_s": round(m.get("no_rcp_time_s", 0.0), 1),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/stats')
def stats():
    arr = datos_z
    m = ft.get_last_metrics()   # ya está procesando en /esp32
    return jsonify({'n_comp': m["n_comp"], 'cpm': m["cpm"],'prof_cm':m["depth_cm"] })


@app.route("/metrics") #calculo de metricas
def metrics_json():
    """Devuelve el JSON de métricas CPM-only computado desde datos.csv (salta 9 s iniciales)."""
    try:
        results = compute_metrics_from_cpm(df = pd.read_csv( archivo_csv, encoding="latin1"), pause_threshold_s=10.0,
                                           sustained_high_thr=130.0,
                                           sustained_high_min_s=20.0, depth_low_cm = 4.8,
                                           depth_high_cm = 6.0,
                                           depth_alarm_low_cm = 4.5,
                                           depth_alarm_min_s= 10.0)
        
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/reporte")
def reporte_html():
    try:
        results = compute_metrics_from_cpm(df = pd.read_csv( archivo_csv, encoding="latin1"), pause_threshold_s=10.0,
                                           sustained_high_thr=130.0,
                                           sustained_high_min_s=20.0, depth_low_cm = 4.8,
                                           depth_high_cm = 6.0,
                                           depth_alarm_low_cm = 4.5,
                                           depth_alarm_min_s= 10.0)
        print(results)
        return render_template("reporte.html", metrics=results)
       

    except Exception as e:
        return render_template("reporte.html", metrics=None, error=str(e))

class State:
    device_name = "CP.Ar– v1.0"
    serial = "CP.Ar-00001"
    firmware = "1.3.2"

    # Sensores
    acc_ok = True

    # Sesión
    session_active = False
    session_start_ts = None
    session_compressions = 0
    session_cpm = None

    # Conexión/sync
    last_sync_ts = None

state = State()

def iso_utc(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()

def mmss_from_seconds(seconds):
    if seconds is None:
        return "—"
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


@app.route("/info") #info del equipo
def info_equipo():
    return render_template("info_equipo.html")

@app.route("/api/device-info")
def api_device_info():
    if state.session_active and state.session_start_ts:
        elapsed = time.time() - state.session_start_ts
        sess_status = "Grabando"
    else:
        elapsed = None
        sess_status = "Detenido"

    server_ip = request.host.split(":")[0] if request.host else "—"

    payload = {
        "device_name": state.device_name,
        "serial": state.serial,
        "firmware": state.firmware,
        "sensors": [
            {"name": "Acelerómetro", "status": "OK" if state.acc_ok else "Error"}
        ],
        "session": {
            "status": sess_status,
            "duration": mmss_from_seconds(elapsed),
            "compressions": state.session_compressions,
            "cpm": state.session_cpm if state.session_cpm is not None else "—"
        },
        "connection": {
            "connected": True,   # si el server responde, mostrá conectado
            "ip": server_ip
        },
        "contact": "cp_ar@itba.edu"
    }
    return jsonify(payload)


@app.route("/guia")
def guia_html():
      return render_template("guia.html")

@app.route('/descargar-md')
def descargar_markdown():
    metrics = compute_metrics_from_cpm(df = pd.read_csv( archivo_csv, encoding="latin1"), pause_threshold_s=10.0,
                                           sustained_high_thr=130.0,
                                           sustained_high_min_s=20.0, depth_low_cm = 4.8,
                                           depth_high_cm = 6.0,
                                           depth_alarm_low_cm = 4.5,
                                           depth_alarm_min_s= 10.0)
    
    if not metrics:
        return "No hay datos de métricas para exportar.", 404

    # 1. Generar el resumen de Markdown
    markdown_text = write_markdown_summary(metrics)
    
    # 2. Convertir la cadena de texto a un buffer de bytes
    buffer = BytesIO(markdown_text.encode('utf-8'))
    
    # 3. Enviar el archivo
    return send_file(
        buffer,
        as_attachment=True,
        download_name='informe_rcp_resumen.md', # Nombre del archivo
        mimetype='text/markdown' # MIME-type para Markdown
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)