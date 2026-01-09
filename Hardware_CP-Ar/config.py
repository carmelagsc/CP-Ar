# CP-Ar | Configuración general

# I2C - Pines y direcciones
I2C_SCL = 25   
I2C_SDA = 15   

OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_ADDR = 0x3c

MPU_ADDR = 0x68
ACC_SCALE = 16384.0  # ±2g -> 16384 LSB/g

# WiFi y servidor
WIFI_NETWORKS = [
    {"ssid": "Nombre_Wifi1",    "pass": "contraseña1",    "url": "http://mi_servidor_remoto.com/esp32"}, 
    {"ssid": "Nombre_Wifi2",    "pass": "contraseña2",    "url": "http://mi_servidor_remoto.com/esp32"}, 
]
#Se debe completar con las credenciales de las redes WiFi a las que CP-Ar podrá conectarse.
# Variables que se completan al conectarse
WIFI_SSID = None
WIFI_PASS = None
SERVER_URL = None

# Buffers y tiempos
BUFFER_SIZE = 100         
ENVIO_MS = 1000           
RITMO_IDEAL_MS = 600      
SAMPLE_PERIOD_MS = 10     
DISPLAY_PERIOD_MS = 50     
CONTROL_ENVIO_PERIOD_MS = 100

# Batería (ADC)
BAT_ADC_PIN = 27

# Divisor resistivo:
BAT_VDIV_RATIO = 10.8

BAT_VMIN = 6.6    
BAT_VMAX = 8.4 

BAT_SAMPLES = 20
BAT_SAMPLE_DELAY_MS = 10
BAT_UPDATE_PERIOD_MS = 2000

# Modo local (sin WiFi): algoritmo + grabación
LOCAL_FS_HZ = 50                 # 50 Hz alcanza para RCP
LOCAL_SESSION_SECONDS = 60       # duración sesión
LOCAL_FILE_PATH = "sesion.csv"   # en /flash

# Algoritmo (simple) basado en umbral + max en ciclo
LOCAL_GRAVITY = 9.80665
LOCAL_ALPHA = 0.20
LOCAL_UMBRAL_MIN = 0.30
LOCAL_BASELINE_5CM_ACCEL = 1.7104
LOCAL_MAX_DEPTH_CM = 8.0
LOCAL_TIMEOUT_RESET_MS = 2000
