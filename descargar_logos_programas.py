import requests
import json
import os

ARCHIVO_JSON = "respuesta_capturada.json"  # cambiá el nombre si tu archivo se llama distinto
CARPETA_DESTINO = "logos_programas"


def cargar_canales(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    canales = data.get("d", data) if isinstance(data, dict) else data
    if not isinstance(canales, list):
        raise ValueError(f"No se pudo interpretar el JSON como lista de canales (tipo: {type(canales)})")
    return canales


def descargar_logos_programas():
    canales = cargar_canales(ARCHIVO_JSON)
    print(f"Se encontraron {len(canales)} canales en el archivo.")

    os.makedirs(CARPETA_DESTINO, exist_ok=True)

    vistos = set()
    descargados = 0
    saltados = 0
    fallidos = 0
    sin_imagen = 0

    for canal in canales:
        programas = canal.get("ProgramList", []) or []

        for programa in programas:
            event_id = str(programa.get("eventId", "")).strip()
            titulo = programa.get("title", "").strip()
            url_imagen = (programa.get("imageUrl") or "").strip()

            if not url_imagen:
                sin_imagen += 1
                continue

            if event_id in vistos:
                continue
            vistos.add(event_id)

            # Nombre de archivo seguro: solo letras, números, espacios y guiones
            titulo_seguro = "".join(c for c in titulo if c.isalnum() or c in " -_").strip()[:60]
            extension = url_imagen.split(".")[-1].split("?")[0] or "jpg"
            destino = os.path.join(CARPETA_DESTINO, f"{event_id}_{titulo_seguro}.{extension}")

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
                    fallidos += 1
            except Exception as e:
                print(f"❌ Error con '{titulo}' ({event_id}): {e}")
                fallidos += 1

    print(f"\n✅ Listo.")
    print(f"   Descargados: {descargados}")
    print(f"   Ya existían: {saltados}")
    print(f"   Fallidos: {fallidos}")
    print(f"   Sin imagen disponible: {sin_imagen}")
    print(f"   Carpeta: {os.path.abspath(CARPETA_DESTINO)}")


if __name__ == "__main__":
    descargar_logos_programas()
