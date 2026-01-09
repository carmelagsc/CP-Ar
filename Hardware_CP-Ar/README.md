                 ┌──────────────────────────────────┐
                 │           CP-Ar (ESP32)          │
                 │──────────────────────────────────│
                 │  Sensores                        │
                 │   • MPU6050 (aceleración Z)      │
                 │   • ADC batería (divisor R)      │
                 │                                  │
                 │  Adquisición                     │
                 │   • fs = 100 Hz                  │
                 │                                  │
                 │  Algoritmos RCP                  │
                 │   • detección de picos - CPM     │
                 │   • Profundidad                  │
                 │                                  │
                 │  Estados iniciales               │
                 │   • Boot                         │
                 │   • Medición de batería (1 vez)  │
                 │                                  │
                 └───────────────┬──────────────────┘
                                 │
                                 ▼
                 ┌──────────────────────────────────┐
                 │    Verificación de conectividad  │
                 │          Wi-Fi disponible ?      │
                 └───────────────┬───────────────┬──┘
                                 │               │
                              SÍ │               │ NO
                                 │               │
                                 ▼               ▼
     ┌──────────────────────────────────┐   ┌──────────────────────────────────┐
     │   Modo conectado (online)        │   │   Modo autónomo (offline)        │
     │──────────────────────────────────│   │──────────────────────────────────│
     │ • Envío de datos por HTTP POST   │   │ • Procesamiento 100% local       │
     │ • Sincronización con servidor    │   │ • Visualización en OLED          │
     │ • Control externo de sesión      │   │ • Grabación de sesión            │
     │                                  │   │   → LittleFS / sesion.csv        │
     └───────────────┬──────────────────┘   └───────────────┬──────────────────┘
                     │                                      │
                     ▼                                      ▼
       ┌─────────────────────────────┐      ┌─────────────────────────────┐
       │   Servidor externo (PC)     │      │   Usuario / extracción USB  │
       │─────────────────────────────│      │─────────────────────────────│
       │ • Recepción de muestras     │      │ • Descarga de sesion.csv    │
       │ • Procesamiento offline     │      │ • Análisis posterior        │
       │ • Visualización avanzada    │      │ • Reproducibilidad          │
       └─────────────────────────────┘      └─────────────────────────────┘
