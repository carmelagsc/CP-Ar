# filtro3.py — streaming causal + no RCP + calibración relativa a 5 cm + Ventana Deslizante
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi, find_peaks
import time

# =========================
# Parámetros de procesamiento
# =========================
fs = 100.0                      # Hz
batch_sec = 10.0
n_batch = int(batch_sec * fs)   # 1000 muestras
discard_sec = 0.5
n_discard = int(discard_sec * fs)

# MAD adaptativo (ventana deslizante)
mad_win_sec = 15.0
mad_win_max = int(mad_win_sec * fs)

# Detección de picos (máximos)
min_distance = int(fs * 0.40)                # ~133 cpm
width_minmax = (int(0.04*fs), int(0.25*fs))  # 40–250 ms

# "No RCP" (dispositivo quieto alrededor de g)
G0 = -9.81
G_TOL = 0.6                   # ±0.6 m/s^2
QUIET_MIN_SAMPLES = 100       # >=100 muestras (~1 s)

# Recalibración automática
NORCP_RECAL_S = 3.0           # si hay un segmento de no RCP >= 3 s -> recalibrar
AMP_SHIFT_RECAL = 0.40        # si mediana reciente cambia >40% -> recalibrar

# Calibración 5 cm
CAL_ENABLE = True
CAL_N_INIT = 8                # compresiones "buenas" para fijar baseline
CAL_MIN_PROM_FACTOR = 0.6     # mínima prominencia relativa al cuantil 75% local
CAL_SMOOTH_K = 3              # usar mediana de las últimas k prominencias

# =========================
# Filtros causales (ligeros)
# =========================
_sos_hp = butter(2, 0.25/(fs/2), btype='highpass', output='sos')
_sos_bp = butter(2, [0.6/(fs/2), 10.0/(fs/2)], btype='bandpass', output='sos')

# =========================
# Estados internos (streaming)
# =========================
_zi_hp = sosfilt_zi(_sos_hp) * 0.0
_zi_bp = sosfilt_zi(_sos_bp) * 0.0

_global_idx = 0
_y_filt_stream = [] # Buffer continuo para ventana deslizante
_mad_buffer = np.empty(0)

# resultados del último cálculo
_last_peaks = np.array([], dtype=int)
_last_n = 0
_last_cpm = 0.0

# Profundidad (relativa)
_last_depth_cm = 0.0          
_last_pct_target = 0.0        
_hit_5cm = False

# Estado "no RCP"
_quiet_consec = 0
_no_rcp_active = False
_no_rcp_start_idx = None
_no_rcp_time_s = 0.0
_last_norcp_segment_s = 0.0   

# Calibración
_calibrated = False
_cal_baseline_prom = None      
_cal_prom_buffer = []          
_recent_proms = []             

def reset_stream(fixed_baseline_prom: float = None):
    """Reinicia estados. Acepta baseline fijo opcional."""
    global _zi_hp, _zi_bp, _global_idx, _y_filt_stream
    global _mad_buffer, _last_peaks, _last_n, _last_cpm
    global _last_depth_cm, _last_pct_target, _hit_5cm
    global _quiet_consec, _no_rcp_active, _no_rcp_start_idx, _no_rcp_time_s, _last_norcp_segment_s
    global _calibrated, _cal_baseline_prom, _cal_prom_buffer, _recent_proms
    global CAL_N_INIT

    _zi_hp = sosfilt_zi(_sos_hp) * 0.0
    _zi_bp = sosfilt_zi(_sos_bp) * 0.0

    _global_idx = 0
    _y_filt_stream = []
    _mad_buffer = np.empty(0)

    _last_peaks = np.array([], dtype=int)
    _last_n = 0
    _last_cpm = 0.0

    _last_depth_cm = 0.0
    _last_pct_target = 0.0
    _hit_5cm = False

    _quiet_consec = 0
    _no_rcp_active = False
    _no_rcp_start_idx = None
    _no_rcp_time_s = 0.0
    _last_norcp_segment_s = 0.0

    _calibrated = False
    _cal_baseline_prom = None
    _cal_prom_buffer = []
    _recent_proms = []

    # Aplicar baseline fijo si existe
    if fixed_baseline_prom is not None and fixed_baseline_prom > 0:
        _cal_baseline_prom = fixed_baseline_prom
        _calibrated = True
        _cal_prom_buffer = [fixed_baseline_prom] * CAL_N_INIT
        _recent_proms = [fixed_baseline_prom] * 5

def _mad_adaptive_threshold(y: np.ndarray) -> float:
    """Calcula umbral adaptativo (sin piso de ruido hardcodeado)."""
    global _mad_buffer
    if y.size == 0:
        return 0.0
    _mad_buffer = np.concatenate((_mad_buffer, y))
    if _mad_buffer.size > mad_win_max:
        _mad_buffer = _mad_buffer[-mad_win_max:]
    med = np.median(_mad_buffer)
    mad = np.median(np.abs(_mad_buffer - med))
    prom = 1.0 * 1.4826 * mad
    return prom

def _update_quiet_counter(raw_samples: np.ndarray):
    """Actualiza contador 'no RCP'."""
    global _quiet_consec, _no_rcp_active, _no_rcp_start_idx, _no_rcp_time_s
    global _global_idx, _last_norcp_segment_s
    for v in raw_samples:
        if abs(v - G0) <= G_TOL:
            _quiet_consec += 1
            if (not _no_rcp_active) and _quiet_consec >= QUIET_MIN_SAMPLES:
                _no_rcp_active = True
                _no_rcp_start_idx = _global_idx - QUIET_MIN_SAMPLES + 1
        else:
            if _no_rcp_active and _no_rcp_start_idx is not None:
                seg_s = (_global_idx - _no_rcp_start_idx + 1) / fs
                _last_norcp_segment_s = seg_s
                _no_rcp_time_s += seg_s
            _no_rcp_active = False
            _no_rcp_start_idx = None
            _quiet_consec = 0
        _global_idx += 1

def _maybe_trigger_recalibration():
    global _calibrated, _cal_baseline_prom, _cal_prom_buffer, _recent_proms, _last_norcp_segment_s
    if _last_norcp_segment_s >= NORCP_RECAL_S:
        _calibrated = False
        _cal_baseline_prom = None
        _cal_prom_buffer = []
        _recent_proms = []
        _last_norcp_segment_s = 0.0
        return

    if _calibrated and len(_recent_proms) >= max(CAL_SMOOTH_K, 5):
        med_recent = float(np.median(_recent_proms[-5:]))
        if _cal_baseline_prom > 0:
            shift = abs(med_recent - _cal_baseline_prom) / _cal_baseline_prom
            if shift > AMP_SHIFT_RECAL:
                _calibrated = False
                _cal_baseline_prom = None
                _cal_prom_buffer = []
                _recent_proms = []

def _accept_for_calibration(proms: np.ndarray) -> np.ndarray:
    if proms.size == 0: return proms
    q3 = np.percentile(proms, 75)
    th = CAL_MIN_PROM_FACTOR * q3
    return proms[proms >= th]

def _update_calibration_and_metrics(props):
    """Actualiza métricas relativas (5 cm)."""
    global _calibrated, _cal_baseline_prom, _cal_prom_buffer
    global _last_depth_cm, _last_pct_target, _hit_5cm, _recent_proms

    proms = np.asarray(props.get("prominences", []), dtype=float)
    
    # Si no hay picos (no hay compresiones), la profundidad es 0
    if proms.size == 0:
        _last_depth_cm = 0.0
        _last_pct_target = 0.0
        _hit_5cm = False
        return

    _recent_proms.extend(proms.tolist())
    if len(_recent_proms) > 50:
        _recent_proms = _recent_proms[-50:]

    if CAL_ENABLE and (not _calibrated):
        good = _accept_for_calibration(proms)
        if good.size > 0:
            _cal_prom_buffer.extend(good.tolist())
            if len(_cal_prom_buffer) >= CAL_N_INIT:
                base = float(np.median(_cal_prom_buffer[:CAL_N_INIT]))
                if base > 0:
                    _calibrated = True
                    _cal_baseline_prom = base
                    _cal_prom_buffer = _cal_prom_buffer[:CAL_N_INIT]

    if _calibrated and (_cal_baseline_prom is not None) and (_cal_baseline_prom > 0):
        k = min(CAL_SMOOTH_K, proms.size)
        prom_smooth = float(np.median(proms[-k:])) if k > 0 else float(np.median(proms))
        pct = 100.0 * (prom_smooth / _cal_baseline_prom)
        _last_pct_target = pct
        _hit_5cm = bool(pct >= 100.0)
        _last_depth_cm = 5.0 * (prom_smooth / _cal_baseline_prom)
    else:
        _last_pct_target = 0.0
        _hit_5cm = False
        _last_depth_cm = 0.0

def update_stream(raw_samples):
    """
    Procesa muestras entrantes con lógica de VENTANA DESLIZANTE.
    Analiza siempre los últimos 10 segundos disponibles.
    """
    global _zi_hp, _zi_bp, _y_filt_stream
    global _last_peaks, _last_n, _last_cpm, _last_depth_cm

    if raw_samples is None or len(raw_samples) == 0:
        return get_last_metrics()

    raw_samples = np.asarray(raw_samples, dtype=float)

    # 1) Detectar "No RCP"
    _update_quiet_counter(raw_samples)

    # 2) Filtrado causal
    y1, _zi_hp = sosfilt(_sos_hp, raw_samples, zi=_zi_hp)
    y2, _zi_bp = sosfilt(_sos_bp, y1, zi=_zi_bp)

    # 3) Acumular en buffer continuo (Ventana Deslizante)
    if isinstance(_y_filt_stream, list):
        _y_filt_stream.extend(y2.tolist())
    else:
        _y_filt_stream = _y_filt_stream + y2.tolist() 

    # Mantener buffer limitado (ej. 15 segundos) para no desbordar memoria
    max_buff_len = int(n_batch * 1.5)
    if len(_y_filt_stream) > max_buff_len:
        _y_filt_stream = _y_filt_stream[-max_buff_len:]

    # 4) Analizar SOLO si tenemos al menos 10 segundos llenos
    if len(_y_filt_stream) >= n_batch:
        
        # Tomar los últimos 10 segundos exactos
        y_det = np.asarray(_y_filt_stream[-n_batch:], dtype=float)

        prom_th = _mad_adaptive_threshold(y_det)

        peaks_local, props = find_peaks(
            y_det,
            distance=min_distance,
            prominence=prom_th,
            width=width_minmax
        )
        
        # Calcular CPM
        _last_n = int(peaks_local.size)
        _last_cpm = float((_last_n / batch_sec) * 60.0)

        # 🟢 Lógica para eliminar profundidad fantasma:
        # Si la CPM es muy baja (< 30), asumimos que no hay RCP activa 
        # y forzamos profundidad a 0.
        if _last_cpm < 30:
            _last_cpm = 0.0
            _last_n = 0
            # Vaciamos props para que _update_calibration ponga depth=0
            props = {"prominences": np.array([])}

        _maybe_trigger_recalibration()
        _update_calibration_and_metrics(props)

    return get_last_metrics()

def get_last_metrics():
    return {
        "n_comp": int(_last_n),
        "cpm": round(float(_last_cpm), 1),
        "depth_cm": round(float(_last_depth_cm), 1),
        "pct_target": round(float(_last_pct_target), 1),
        "hit_5cm": bool(_hit_5cm),
        "calibrated": bool(_calibrated),
        "no_rcp_active": bool(_no_rcp_active),
        "no_rcp_time_s": float(_no_rcp_time_s),
    }

# =========================
# Back-compat API
# =========================
def compute_counts(arr):
    update_stream(arr if isinstance(arr, (list, np.ndarray)) else [])
    m = get_last_metrics()
    return m["n_comp"], m["cpm"]

def compute_counts_depth(arr):
    update_stream(arr if isinstance(arr, (list, np.ndarray)) else [])
    m = get_last_metrics()
    return m["n_comp"], m["cpm"], m["depth_cm"]

# Blueprint dummy
try:
    from flask import Blueprint
    stats_bp = Blueprint('stats_bp', __name__)
except Exception:
    stats_bp = None