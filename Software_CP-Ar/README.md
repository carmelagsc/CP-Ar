# Software – CP-Ar

Este directorio contiene el firmware del dispositivo CP-Ar y las herramientas de procesamiento, visualización y validación asociadas.  
El software fue diseñado para operar tanto en modo autónomo (embebido) como en modo conectado mediante un servidor externo.

---

## Arquitectura general del sistema

```text
                    ┌──────────────────────────────┐
                    │        Dispositivo ESP32     │
                    │  - Aceleración (muestras)    │
                    │                              │
                    │  - Wi-Fi HTTP POST           │
                    └──────────────┬───────────────┘
                                   │  POST /esp32 (muestras)
                                   │  ← respuesta: "CPM,PROF"
                                   ▼
        ┌──────────────────────────────────────────────────────────┐
        │                   Servidor Flask (PC)                    │
        │──────────────────────────────────────────────────────────│
        │  Rutas:                                                  │
        │   /start(POST)  /stop(POST)  /esp32(POST)                │
        │   /metrics(JSON) /stats(JSON) /datos(JSON)               │
        │   /reporte(HTML) /descargar(CSV) /info /guia             │
        │   /api/device-info (estado equipo)                       │
        │                                                          │
        │  Submódulos internos:                                    │
        │   ┌────────────────────┐   ┌──────────────────────────┐  │
        │   │ Session/State      │   │  Buffer + Almacenamiento │  │
        │   │ - flags de sesión  │   │ - datos_z (cap ~2000)    │  │
        │   │ - duración, cpm    │   │ - fs = 100 Hz            │  │
        │   │ - device info API  │   │ - CSV: indice,t,acc,cpm  │  │
        │   └────────────────────┘   └──────────────────────────┘  │
        │           │                         │                    │
        │           │                         ▼                    │
        │   ┌────────────────────┐   ┌──────────────────────────┐  │
        │   │ Filtro (ft)        │   │ Analyzer (cpr_metrics)   │  │
        │   │ - compute_counts   │   │ - compresiones totales   │  │
        │   │ - compute_depth    │   │ - CPM y PROF medio/      |  |
            |                    |   |      mediana             │  │
        │   │ - robustez errores │   │ - pausas, CCF, % en rango│  │
        │   └────────────────────┘   └──────────────────────────┘  │
        │                                                          │
        │  Plantillas y estáticos: /templates (HTML),              │
        │                           /static (JS,CSS)               │
        └──────────────┬───────────────────────────────────────────┘
                       │
         (HTTP GET / AJAX desde GUI)                               
                       ▼
          ┌────────────────────────────────────────┐
          │        Interfaz Web (Navegador)        │
          │  - (/) Tabs: Data / Reporte / Info     │
          │  - AJAX: /metrics y /stats             │
          │  - Botones: POST /start, POST /stop    │
          │  - Ver /reporte y bajar /descargar     │
          └────────────────────────────────────────┘
```
---

## Validación del algoritmo y la interfaz

La validación del sistema se realizó utilizando señales sintéticas controladas y señales reales obtenidas durante ensayos experimentales, con el objetivo de evaluar el comportamiento del algoritmo sin depender exclusivamente de datos reales.

```text

       ┌──────────────────────────┐
       │  Inicio de la validación │
       └───────────────┬──────────┘
                       │
                       ▼
       ┌────────────────────────────────────────┐
       │ Definir objetivo: validar algoritmo e  │
       │ interfaz sin depender de datos reales  │
       └─────────────────┬──────────────────────┘
                         │
                         ▼
       ┌─────────────────────────────────────────────┐
       │ Seleccionar método de validación sintético  │
       │ (modelo matemático de la señal de RCP)      │
       └─────────────────┬───────────────────────────┘
                         │
                         ▼
       ┌─────────────────────────────────────────────┐
       │ Construir modelo de señal: tren de semisenos│
       │ (parámetros: A, w, b, f, ruido)             │
       └──────────────────┬──────────────────────────┘
                          │
                          ▼
       ┌─────────────────────────────────────────────┐
       │ Generar barrido de parámetros               │
       │ f ∈ [1.6, 2.0] Hz                           │
       │ ϕ ∈ [0.1, 0.4] s                            │
       └──────────────────┬──────────────────────────┘
                          │
                          ▼
       ┌─────────────────────────────────────────────┐
       │ Comparar modelo con señal real (CR3)        │
       │ Calcular correlación de Pearson             │
       └──────────────────┬──────────────────────────┘
                          │
                          ▼
       ┌─────────────────────────────────────────────┐
       │ Seleccionar combinación (f*,ϕ*) con máxima  │
       │ correlación                                 │
       └──────────────────┬──────────────────────────┘
                          │
                          ▼
       ┌─────────────────────────────────────────────┐
       │ Validar algoritmo de detección, gráficos,   │
       │ métricas e interfaz con señal sintética     │
       └──────────────────┬──────────────────────────┘
                          │
                          ▼
       ┌──────────────────────────┐
       │ Validación completada    │
       └──────────────────────────┘
```


