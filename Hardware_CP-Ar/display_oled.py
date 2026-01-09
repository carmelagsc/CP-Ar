from machine import I2C, Pin
from ssd1306 import SSD1306_I2C

class DisplayRCP:
    def __init__(self, width, height, i2c, addr=0x3c):
        self.oled = SSD1306_I2C(width, height, i2c, addr=addr)
        self.indicador_encendido = False
        self.cpm = 0
        self.profundidad_cm = 0.0
        self.bat_percent = None

    def set_metrics(self, cpm, profundidad_cm):
        self.cpm = cpm
        self.profundidad_cm = profundidad_cm

    def toggle_indicador(self):
        self.indicador_encendido = not self.indicador_encendido

    def _draw_battery_icon(self, x, y, percent):
        w, h = 18, 8
        self.oled.framebuf.rect(x, y, w, h, 1)
        self.oled.framebuf.fill_rect(x + w, y + 2, 2, h - 4, 1)  # terminal
        fill_w = int((w - 2) * (percent / 100.0))
        if fill_w < 0:
            fill_w = 0
        if fill_w > (w - 2):
            fill_w = w - 2
        if fill_w > 0:
            self.oled.framebuf.fill_rect(x + 1, y + 1, fill_w, h - 2, 1)

    def draw(self):
        # 1. Limpiar pantalla
        self.oled.fill(0)

        # 2. CPM
        self.oled.text('CPM', 4, 4)
        self.oled.text(str(int(self.cpm)), 4, 16) # Convertimos a int para que se vea limpio (ej: "100" y no "100.0")

        # 3. Indicador de Ritmo
        if self.indicador_encendido:
            self.oled.framebuf.fill_rect(90, 4, 30, 30, 1)
        else:
            self.oled.framebuf.rect(90, 4, 30, 30, 1)

        # 4. Barra de Profundidad
        BAR_X, BAR_Y, BAR_W, BAR_H = 4, 46, 120, 14
        self.oled.text("Prof: {:.1f}cm".format(self.profundidad_cm), BAR_X, BAR_Y - 10)
        self.oled.framebuf.rect(BAR_X, BAR_Y, BAR_W, BAR_H, 1)

        ratio = self.profundidad_cm / 5.0
        if ratio < 0: ratio = 0.0
        if ratio > 1: ratio = 1.0
        
        fill_w = int((BAR_W - 2) * ratio)
        if fill_w > 0:
            self.oled.framebuf.fill_rect(BAR_X + 1, BAR_Y + 1, fill_w, BAR_H - 2, 1)
            
        self.oled.show()

def make_i2c_oled(scl_pin, sda_pin, freq=400000):
    return I2C(1, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)