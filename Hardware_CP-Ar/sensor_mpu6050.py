from machine import I2C, Pin

class MPU6050:
    def __init__(self, i2c, addr=0x68, acc_scale=16384.0):
        self.i2c = i2c
        self.addr = addr
        self.acc_scale = acc_scale
        # Wake up
        self.i2c.writeto_mem(self.addr, 0x6B, b'\x00')

    def _read_word(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 2)
        hi = data[0]
        lo = data[1]
        val = (hi << 8) | lo
        if val & 0x8000:
            val -= 65536
        return val

    def accel_ms2(self):
        # Devuelve (ax, ay, az) en m/s^2
        ax = self._read_word(0x3B) / self.acc_scale * 9.80665
        ay = self._read_word(0x3D) / self.acc_scale * 9.80665
        az = self._read_word(0x3F) / self.acc_scale * 9.80665
        return ax, ay, az

def make_i2c_mpu(scl_pin, sda_pin, freq=400000):
    return I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
