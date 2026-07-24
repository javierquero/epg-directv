import requests
import json
import os

ARCHIVO_JSON = "respuesta_capturada.json"  # cambiá el nombre si tu archivo se llama distinto
CARPETA_DESTINO = "logos_canales"


def cargar_canales(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # A veces la respuesta viene envuelta en la clave "d"
    canales = data.get("d", data) if isinstance(data, dict) else data
    if not isinstance(canales, list):
        raise ValueError(f"No se pudo interpretar el JSON como lista de canales (tipo: {type(canales)})")
    return canales


def descargar_logos():
    canales = cargar_canales(ARCHIVO_JSON)
    print(f"Se encontraron {len(canales)} canales en el archivo.")

    os.makedirs(CARPETA_DESTINO, exist_ok=True)

    vistos = set()
    descargados = 0
    saltados = 0
    fallidos = 0

    for canal in canales:
        numero = str(canal.get("ChannelNumber", "")).strip()
        nombre = canal.get("ChannelName", "").strip()
        url_imagen = canal.get("ImageUrl", "").strip()

        if not url_imagen or not numero:
            continue

        if numero in vistos:
            continue
        vistos.add(numero)

        extension = url_imagen.split(".")[-1].split("?")[0] or "png"
        destino = os.path.join(CARPETA_DESTINO, f"{numero}_{nombre}.{extension}")

        # Evitar re-descargar si ya existe
        if os.path.exists(destino):
            saltados += 1
            continue

        try:
            res = requests.get(url_imagen, timeout=15)
            if res.status_code == 200:
                with open(destino, "wb") as f:
                    f.write(res.content)
                descargados += 1
                if descargados % 20 == 0:
                    print(f"  ... {descargados} descargados hasta ahora")
            else:
                print(f"⚠️ {nombre} ({numero}): status {res.status_code}")
                fallidos += 1
        except Exception as e:
            print(f"❌ Error con {nombre} ({numero}): {e}")
            fallidos += 1

    print(f"\n✅ Listo. Descargados: {descargados} | Ya existían: {saltados} | Fallidos: {fallidos}")
    print(f"Carpeta: {os.path.abspath(CARPETA_DESTINO)}")


if __name__ == "__main__":
    descargar_logos()
