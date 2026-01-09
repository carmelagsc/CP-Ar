                    ┌─────────────────────────────┐
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
        │  Plantillas y estáticos: /templates (HTML), /static (JS,CSS)
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





Diagrama de la válidación de la página y los algoritmos



       ┌──────────────────────────┐
       │  Inicio de la validación │
       └───────────────┬──────────┘
                       │
                       ▼
       ┌────────────────────────────────────────┐
       │ Definir objetivo: validar algoritmo e │
       │ interfaz sin depender de datos reales │
       └─────────────────┬──────────────────────┘
                         │
                         ▼
       ┌─────────────────────────────────────────────┐
       │ Seleccionar método de validación sintético  │
       │ (modelo matemático de la señal de RCP)     │
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
       │ f ∈ [1.6, 2.0] Hz                            │
       │ ϕ ∈ [0.1, 0.4] s                             │
       └──────────────────┬──────────────────────────┘
                          │
                          ▼
       ┌─────────────────────────────────────────────┐
       │ Comparar modelo con señal real (CR3)       │
       │ Calcular correlación de Pearson            │
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
