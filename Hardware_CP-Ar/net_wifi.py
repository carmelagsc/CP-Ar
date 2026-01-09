import network
import time
import config as Cfg

def _log(msg):
    if getattr(Cfg, "DEBUG", False):
        print(msg)

def conectar_wifi(ssid=None, password=None, timeout_s=10):
    #Intenta conectar usando la lista de Cfg.WIFI_NETWORKS.
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Si ya está conectado, no reconecta
    if wlan.isconnected():
        return True

    try:
        redes = wlan.scan()
        disponibles = [r[0].decode() for r in redes]
    except Exception as e:
        disponibles = []

    candidatos = [n for n in Cfg.WIFI_NETWORKS if n["ssid"] in disponibles] or Cfg.WIFI_NETWORKS

    # Intentar conexión con cada red
    for net in candidatos:
        ssid = net.get("ssid")
        password = net.get("pass")
        url = net.get("url")
        if not ssid:
            continue

        wlan.connect(ssid, password)
        for _ in range(int(timeout_s * 2)):
            if wlan.isconnected():
                Cfg.WIFI_SSID = ssid
                Cfg.WIFI_PASS = password
                Cfg.SERVER_URL = url
                return True
            time.sleep(0.5)

        _log("Falló WiFi: {}".format(ssid))
    return False

