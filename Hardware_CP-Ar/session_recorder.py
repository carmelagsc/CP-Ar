from array import array
import time
import config as Cfg

class SessionRecorder:
    #Graba aceleración filtrada a un buffer en RAM y luego vuelca a CSV en /flash.

    def __init__(self, fs_hz=Cfg.LOCAL_FS_HZ, seconds=Cfg.LOCAL_SESSION_SECONDS, path=Cfg.LOCAL_FILE_PATH):
        self.fs_hz = int(fs_hz)
        self.seconds = int(seconds)
        self.path = path
        self.max_samples = self.fs_hz * self.seconds
        self.data = array("f", [0.0] * self.max_samples)
        self.i = 0
        self.active = True
        self.t0 = time.ticks_ms()
        self.last_sample = self.t0

    def push(self, value):
        if not self.active:
            return False
        now = time.ticks_ms()
        period = int(1000 / self.fs_hz)
        if time.ticks_diff(now, self.last_sample) < period:
            return True
        self.last_sample = now

        if self.i < self.max_samples:
            self.data[self.i] = float(value)
            self.i += 1
            if self.i >= self.max_samples:
                self.active = False
            return True

        self.active = False
        return False

    def save_csv(self):
        # Escribe CSV simple: tiempo_ms,aceleracion_z
        # (tiempo aproximado por índice)
        period = int(1000 / self.fs_hz)
        with open(self.path, "w") as f:
            f.write("tiempo_ms,aceleracion_z\n")
            for idx in range(self.i):
                t = idx * period
                f.write("{},{}\n".format(t, self.data[idx]))
