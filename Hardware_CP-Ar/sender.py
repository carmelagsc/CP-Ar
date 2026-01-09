import urequests
import config as Cfg

def _log(msg):
    if getattr(Cfg, "DEBUG", False):
        print(msg)

def enviar_buffer(url, buffer_datos):
    # Convierte una lista de floats a CSV (una por línea)
    csv_data = "\n".join([str(d) for d in buffer_datos])
    resp = None
    try:
        resp = urequests.post(url, data=csv_data)
        if resp.status_code == 200:
            texto = resp.text.strip()
            cpm = 0
            prof = 0.0
            partes = texto.split(',')
            for p in partes:
                if 'CPM:' in p:
                    try:
                        cpm = int(p.split(':')[1])
                    except:
                        try:
                            cpm = int(float(p.split(':')[1]))
                        except:
                            cpm = 0
                elif 'PROF:' in p:
                    try:
                        prof = float(p.split(':')[1])
                    except:
                        prof = 0.0
            return True, cpm, prof
        return False, 0, 0.0
    except Exception as e:
        _log("Error enviando datos:", e)
        return False, 0, 0.0
    finally:
        try:
            if resp and hasattr(resp, "close"):
                resp.close()
        except:
            pass
