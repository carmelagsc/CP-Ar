from machine import I2C, Pin
import uasyncio as asyncio
import time

import config as Cfg
from sensor_mpu6050 import MPU6050
from display_oled import DisplayRCP
from net_wifi import conectar_wifi
from tasks import Estado, tarea_sensado, tarea_envio, tarea_display, tarea_bateria, tarea_rcp_local
from battery_monitor import BatteryMonitor
from session_recorder import SessionRecorder

def _log(msg):
    if getattr(Cfg, "DEBUG", False):
        print(msg)

def inicializar_i2c():
    return I2C(1, scl=Pin(Cfg.I2C_SCL), sda=Pin(Cfg.I2C_SDA), freq=400000)

def inicializar_mpu(i2c):
    dispositivos = i2c.scan()
    mpu_addr = Cfg.MPU_ADDR
    if mpu_addr not in dispositivos:
        if 0x69 in dispositivos:
            mpu_addr = 0x69
        else:
            raise Exception("MPU6050 no encontrado en I2C")
    return MPU6050(i2c, addr=mpu_addr, acc_scale=Cfg.ACC_SCALE), dispositivos

def inicializar_oled(i2c, dispositivos):
    if Cfg.OLED_ADDR in dispositivos:
        return DisplayRCP(Cfg.OLED_WIDTH, Cfg.OLED_HEIGHT, i2c, addr=Cfg.OLED_ADDR)
    return None

def mostrar_boot(display):
    if not display:
        return
    oled = display.oled
    oled.fill(0)
    oled.text("CP-Ar", 0, 0)
    oled.text("Iniciando...", 0, 16)
    oled.show()

def mostrar_wifi(display, ok):
    if not display:
        return
    oled = display.oled
    oled.fill(0)
    oled.text("RCP listo", 0, 0)
    oled.text("WiFi: " + ("OK" if ok else "NO"), 0, 16)
    if not ok:
        oled.text("Modo local", 0, 32)
    oled.show()

def main():
    # I2C + Periféricos
    i2c = inicializar_i2c()
    mpu, dispositivos = inicializar_mpu(i2c)
    display = inicializar_oled(i2c, dispositivos)

    mostrar_boot(display)

    # Estado
    estado = Estado()
    estado.display = display

    # Batería
    batmon = BatteryMonitor()

    # WiFi
    wifi_ok = conectar_wifi(timeout_s=10)
    estado.wifi_ok = wifi_ok
    mostrar_wifi(display, wifi_ok)

    # Loop / tareas
    loop = asyncio.get_event_loop()

    # Tarea batería (siempre)
    loop.create_task(tarea_bateria(batmon, estado, Cfg.BAT_UPDATE_PERIOD_MS))

    if wifi_ok:
        # Online: sensado -> buffer -> envío -> display
        loop.create_task(tarea_sensado(mpu, estado, Cfg.BUFFER_SIZE, Cfg.SAMPLE_PERIOD_MS))
        loop.create_task(tarea_envio(estado, Cfg.SERVER_URL, Cfg.ENVIO_MS, Cfg.CONTROL_ENVIO_PERIOD_MS))
    else:
        # Offline: algoritmo local + grabación en /flash
        recorder = SessionRecorder(fs_hz=Cfg.LOCAL_FS_HZ, seconds=Cfg.LOCAL_SESSION_SECONDS, path=Cfg.LOCAL_FILE_PATH)
        loop.create_task(tarea_rcp_local(mpu, estado, recorder=recorder))

    if display is not None:
        loop.create_task(tarea_display(display, estado, Cfg.RITMO_IDEAL_MS, Cfg.DISPLAY_PERIOD_MS))

    loop.run_forever()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        _log("Fatal: {}".format(e))