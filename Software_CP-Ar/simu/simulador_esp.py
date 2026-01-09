import time
import argparse
import requests
import pandas as pd
from pathlib import Path

def load_series(csv_path, value_col=None, fs_fallback=100.0):
    """
    Devuelve (times_s, values) listas sincronizadas.
    Si el CSV tiene 'timestamp_s', usa esos tiempos.
    Si no, asume muestreo uniforme con fs_fallback.
    value_col: si None, intenta detectar ('Aceleracion','Aceleración','acc','acc_z','az').
    """
    df = pd.read_csv(csv_path)
    # tiempo
    if "tiempo_s" in df.columns:
        t = df["tiempo_s"].astype(float).tolist()
    else:
        n = len(df)
        dt = 1.0 / fs_fallback
        t = [i * dt for i in range(n)]

    # valor
    candidates = [value_col] if value_col else ["Aceleracion_Z", "Aceleración", "acc", "acc_z", "az", "aceleracion_z"]
    col = None
    for c in candidates:
        if c and c in df.columns:
            col = c
            break
    if col is None:
        # si solo hay una o dos columnas, tomamos una que no sea timestamp_s
        non_time_cols = [c for c in df.columns if c != "tiempo_s"]
        if not non_time_cols:
            raise ValueError("No se encontró columna de valores.")
        col = non_time_cols[0]

    v = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float).tolist()
    return t, v

def iter_blocks(times, values, block_samples):
    """Genera bloques consecutivos de tamaño block_samples (último bloque puede ser menor)."""
    n = len(values)
    i = 0
    while i < n:
        j = min(i + block_samples, n)
        yield times[i:j], values[i:j]
        i = j

def main():
    p = argparse.ArgumentParser(description="Feed CSV to Flask /esp32 like an ESP32 would.")
    p.add_argument("--csv", required=True, help="Ruta al CSV.")
    p.add_argument("--url", required=True, help="URL del endpoint /esp32 (ej: http://192.168.0.10:5000/esp32)")
    p.add_argument("--fs", type=float, default=100.0, help="FS si no hay timestamp_s en el CSV (Hz).")
    p.add_argument("--block", type=int, default=50, help="Muestras por POST (p.ej. 50 a 100 Hz = 0.5 s por request).")
    p.add_argument("--loop", action="store_true", help="Repetir al terminar.")
    p.add_argument("--dry", action="store_true", help="No hace POST; solo imprime tiempos.")
    p.add_argument("--show-replies", action="store_true", help="Imprimir respuestas del servidor.")
    args = p.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"No existe: {csv_path}")

    while True:
        times, values = load_series(csv_path, value_col=None, fs_fallback=args.fs)
        if len(times) != len(values) or not times:
            raise SystemExit("CSV vacío o mal formado.")

        # Envío en tiempo real
        t0 = times[0]
        start_monotonic = time.monotonic()

        sent_samples = 0
        for blk_t, blk_v in iter_blocks(times, values, args.block):
            # Calcular cuánto esperar para respetar el tiempo del último sample del bloque
            # tiempo "ideal" transcurrido desde t0 hasta el final del bloque:
            t_last = blk_t[-1]
            ideal_elapsed = (t_last - t0)
            now_elapsed = time.monotonic() - start_monotonic
            delay = ideal_elapsed - now_elapsed
            if delay > 0:
                time.sleep(delay)

            # Payload: líneas con un valor por muestra (como envía la ESP)
            payload = "\n".join(f"{x:.6f}" for x in blk_v)

            if args.dry:
                print(f"[DRY] POST {len(blk_v)} muestras; t_last={t_last:.3f}s (ideal_elapsed={ideal_elapsed:.3f})")
            else:
                try:
                    r = requests.post(args.url, data=payload.encode("utf-8"), timeout=5)
                    if args.show_replies:
                        print(f"[{len(blk_v)}] -> {r.text.strip()}")
                except Exception as e:
                    print("Error POST:", e)
                    # opcional: backoff
                    time.sleep(0.5)

            sent_samples += len(blk_v)

        if not args.loop:
            break
        # reinicia loop respetando continuidad (arranca nuevo start_monotonic)
        print("Reiniciando simulación…")

if __name__ == "__main__":
    main()
