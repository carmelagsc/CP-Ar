from machine import ADC, Pin
import time

try:
    import esp32  # type: ignore
except Exception:
    esp32 = None

import config as Cfg

def _clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x

class BatteryMonitor:
    #Lee tensión de batería vía ADC y devuelve mV y porcentaje.

    def __init__(self, pin=Cfg.BAT_ADC_PIN, vdiv_ratio=Cfg.BAT_VDIV_RATIO):
        self.adc = ADC(Pin(pin))
        try:
            self.adc.atten(ADC.ATTN_11DB)
        except Exception:
            pass
        try:
            self.adc.width(ADC.WIDTH_12BIT)
        except Exception:
            pass
        self.vdiv_ratio = float(vdiv_ratio)

    def read_vadc_mv(self, samples=Cfg.BAT_SAMPLES, delay_ms=Cfg.BAT_SAMPLE_DELAY_MS):
        total_uv = 0
        ok_uv = False

        for _ in range(int(samples)):
            # Preferir lectura calibrada en uV si está disponible
            if hasattr(self.adc, "read_uv"):
                try:
                    total_uv += int(self.adc.read_uv())
                    ok_uv = True
                except Exception:
                    ok_uv = False
            if not ok_uv:
                # Fallback: ADC.read() 0..4095 aprox. ref ~3.3V
                try:
                    raw = int(self.adc.read())
                except Exception:
                    raw = int(self.adc.read_u16()) >> 4  # 16->12 bits
                # 12-bit: 0..4095
                total_uv += int(raw * 3300000 // 4095)
            time.sleep_ms(int(delay_ms))

        avg_uv = total_uv // int(samples)
        return int(avg_uv // 1000)  # mV

    def read_vbat_mv(self, samples=Cfg.BAT_SAMPLES, delay_ms=Cfg.BAT_SAMPLE_DELAY_MS):
        vadc_mv = self.read_vadc_mv(samples=samples, delay_ms=delay_ms)
        vbat_mv = int(vadc_mv * self.vdiv_ratio)
        return vbat_mv

    def read_percent(self, vbat_mv=None):
        if vbat_mv is None:
            vbat_mv = self.read_vbat_mv()

        v = vbat_mv / 1000.0
        p = (v - Cfg.BAT_VMIN) / (Cfg.BAT_VMAX - Cfg.BAT_VMIN)
        p = _clamp(p, 0.0, 1.0)
        return int(p * 100), int(vbat_mv)
