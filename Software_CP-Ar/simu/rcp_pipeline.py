import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Parámetros
fs = 100.0  # (Hz)
file = "Software_CP-Ar/simu/modelo.csv" 

# Cargar el CSV
df = pd.read_csv(file)


if "timestamp_s" not in df.columns:
    n = len(df)
    df["timestamp_s"] = np.arange(n) / fs

df = df[df["timestamp_s"] <= 14.0]
plt.figure(figsize=(12, 5))
plt.plot(df["timestamp_s"], df["Aceleracion_Z"], color='tab:blue')
plt.title("Aceleración Z - Señal CR3 (100 Hz)")
plt.xlabel("Tiempo [s]")
plt.ylabel("Aceleración Z [m/s²]")
plt.grid(True)
plt.tight_layout()
plt.show()
