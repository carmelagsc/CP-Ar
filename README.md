<img width="942" height="401" alt="logo, CP-Ar-Photoroom" src="https://github.com/user-attachments/assets/142e2913-e89e-48c7-beb9-0b20c266a5ee" />

# CP-Ar
Dispositivo de Retroalimentación para RCP de Alta Calidad - códigos 

**CP-Ar** es un prototipo portátil de bajo costo destinado a monitorear y mejorar la calidad de la Reanimación Cardiopulmonar (RCP) mediante retroalimentación en tiempo real.  
Este repositorio acompaña y documenta el desarrollo realizado en el marco de un trabajo final de grado, integrando el diseño de hardware, el firmware embebido y las herramientas de validación.

---

## Contexto y motivación

La calidad de las compresiones torácicas es un factor determinante en la supervivencia ante un paro cardíaco. Sin embargo, en contextos de entrenamiento y en escenarios con recursos limitados, el acceso a dispositivos de retroalimentación suele verse restringido por costos de adquisición, importación y disponibilidad.

CP-Ar surge como una alternativa tecnológica accesible, que busca ofrecer métricas objetivas de desempeño sin depender de equipamiento de alto costo, manteniendo criterios de simplicidad, portabilidad y robustez.

---

## Descripción general del sistema

El sistema integra:

- Un microcontrolador **ESP32**
- Un sensor inercial **MPU6050** para la adquisición de aceleración
- Una pantalla **OLED** para visualización local
- Comunicación **Wi-Fi** para visualización y análisis externo

A partir de la señal de aceleración asociada a las compresiones torácicas, el firmware implementa procesamiento embebido en **MicroPython** que permite estimar métricas clave de desempeño, principalmente:

- Frecuencia de compresiones (CPM)
- Profundidad de compresión (estimada a partir de la aceleración)

---

## Organización del repositorio

```text
CP-Ar/
├── hardware/        # Diseño electrónico y documentación del prototipo
│   ├── Códigos correspientes al funcionamiento del dispositivo físico
│   └── README.md
├── software/        # Firmware ESP32 y herramientas asociadas
│   ├── Códigos correspientes al funcionamiento del servidor local y el procesamiento de la señal proveniente del MPU6050
│   └── README.md
└── README.md        # Documentación general del proyecto

