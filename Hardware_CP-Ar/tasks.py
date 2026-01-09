import time
import uasyncio as asyncio
import config as Cfg
from sender import enviar_buffer

def _log(msg):
    if getattr(Cfg, "DEBUG", False):
        print(msg)

class Estado:
    def __init__(self):
        self.buffer = []
        self.cpm = 0
        self.profundidad = 0.0
        self.ultimo_envio_ms = time.ticks_ms()
        self.ultimo_blink_ms = time.ticks_ms()
        self.wifi_ok = False
        self.envio_iniciado = False   
        self.display = None
        self.bat_percent = None
        self.bat_mv = None
        self.rec_active = False
        self.rec_saved = False

async def tarea_bateria(batmon, estado, update_ms=Cfg.BAT_UPDATE_PERIOD_MS):
    while True:
        try:
            p, mv = batmon.read_percent()
            estado.bat_percent = p
            estado.bat_mv = mv
        except Exception as e:
            _log("Battery err: {}".format(e))
        await asyncio.sleep_ms(int(update_ms))

async def tarea_sensado(mpu, estado, buffer_size, sample_period_ms):
    #Modo online
    while True:
        try:
            ax, ay, az = mpu.accel_ms2()
            estado.buffer.append(az)
            if len(estado.buffer) > buffer_size:
                estado.buffer = estado.buffer[-buffer_size:]
        except Exception as e:
            _log("MPU err: {}".format(e))
        await asyncio.sleep_ms(sample_period_ms)

async def tarea_envio(estado, server_url, envio_ms, control_period_ms):
    while True:
        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, estado.ultimo_envio_ms) >= envio_ms:
            if estado.wifi_ok and server_url and len(estado.buffer) > 0:
                ok, cpm, prof = enviar_buffer(server_url, estado.buffer)
                if ok:
                    estado.cpm = cpm
                    estado.profundidad = prof
                    estado.buffer = []
                    estado.ultimo_envio_ms = ahora
        await asyncio.sleep_ms(int(control_period_ms))

async def tarea_display(display, estado, ritmo_ideal_ms, display_period_ms):
    while True:
        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, estado.ultimo_blink_ms) >= (ritmo_ideal_ms // 2):
            display.toggle_indicador()
            estado.ultimo_blink_ms = ahora

        display.set_metrics(estado.cpm, estado.profundidad)
        display.draw()
        await asyncio.sleep_ms(display_period_ms)

# Modo local (sin WiFi)
def _abs(x):
    return x if x >= 0 else -x

async def tarea_rcp_local(mpu, estado, recorder=None):
    acc_f = 0.0
    alpha = float(Cfg.LOCAL_ALPHA)
    umbral = float(Cfg.LOCAL_UMBRAL_MIN)
    base_5cm = float(Cfg.LOCAL_BASELINE_5CM_ACCEL)
    g = float(Cfg.LOCAL_GRAVITY)

    en_comp = False
    max_acc = 0.0
    ultimo_pico = time.ticks_ms()

    while True:
        now = time.ticks_ms()

        try:
            _, _, az = mpu.accel_ms2()
            raw = _abs(az) - g
            acc_f = (alpha * raw) + ((1.0 - alpha) * acc_f)
        except Exception as e:
            _log("MPU err: {}".format(e))
            await asyncio.sleep_ms(int(Cfg.SAMPLE_PERIOD_MS))
            continue

        # grabación
        if recorder is not None and recorder.active:
            recorder.push(acc_f)
            estado.rec_active = True
        elif recorder is not None and (not recorder.active) and (not estado.rec_saved):
            try:
                recorder.save_csv()
                estado.rec_saved = True
            except Exception as e:
                _log("Save CSV err: {}".format(e))

        # detección
        if (acc_f > umbral) and (not en_comp):
            en_comp = True
            max_acc = acc_f
        elif en_comp:
            if acc_f > max_acc:
                max_acc = acc_f
            if acc_f < umbral:
                en_comp = False
                dt = time.ticks_diff(now, ultimo_pico)
                ultimo_pico = now

                if dt > 200:
                    cpm_inst = 60000.0 / float(dt)
                    if estado.cpm == 0:
                        estado.cpm = int(cpm_inst)
                    else:
                        estado.cpm = int((0.7 * estado.cpm) + (0.3 * cpm_inst))

                ratio = max_acc / base_5cm if base_5cm > 0 else 0.0
                profundidad = ratio * 5.0
                if profundidad > float(Cfg.LOCAL_MAX_DEPTH_CM):
                    profundidad = float(Cfg.LOCAL_MAX_DEPTH_CM)
                if profundidad < 0:
                    profundidad = 0.0
                estado.profundidad = float(profundidad)

        if time.ticks_diff(now, ultimo_pico) > int(Cfg.LOCAL_TIMEOUT_RESET_MS):
            estado.cpm = 0
            estado.profundidad = 0.0

        await asyncio.sleep_ms(int(Cfg.SAMPLE_PERIOD_MS))
