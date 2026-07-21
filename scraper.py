import requests
import gzip
import io
import xml.etree.ElementTree as ET

# Fuentes de epgshare01 que contienen la grilla de DirecTV y DSports Latam/AR
FUENTES_EPG = [
    "https://epgshare01.online/epgshare01/epg_ripper_DTV1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CL1.xml.gz"
]

KEYWORDS = ["DSPORTS", "DIRECTV SPORTS", "DS SPORTS", "DS-PORTS"]

def descargar_y_descomprimir(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        print(f"Descargando fuente: {url}...")
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as gz:
                return gz.read()
        else:
            print(f"⚠️ Error {resp.status_code} al acceder a {url}")
    except Exception as e:
        print(f"⚠️ Excepción descargando {url}: {e}")
    return None

def extraer_dsports():
    tv_dsports = ET.Element("tv")
    dsports_channel_ids = set()

    for url in FUENTES_EPG:
        xml_bytes = descargar_y_descomprimir(url)
        if not xml_bytes:
            continue

        print("Procesando estructura XMLTV...")
        try:
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            print(f"❌ Error al parsear XML de {url}: {e}")
            continue

        # 1. Buscar canales de DSports
        for channel in root.findall("channel"):
            ch_id = channel.get("id", "")
            display_names = [dn.text.upper() for dn in channel.findall("display-name") if dn.text]
            texto_busqueda = (ch_id.upper() + " " + " ".join(display_names))

            if any(kw in texto_busqueda for kw in KEYWORDS):
                if ch_id not in dsports_channel_ids:
                    tv_dsports.append(channel)
                    dsports_channel_ids.add(ch_id)
                    print(f"  [+] Canal encontrado: ID='{ch_id}' | Nombres={display_names}")

        # 2. Agregar los eventos correspondientes a esos canales
        eventos_agregados = 0
        for prog in root.findall("programme"):
            if prog.get("channel") in dsports_channel_ids:
                tv_dsports.append(prog)
                eventos_agregados += 1

        print(f"  -> Eventos procesados para esta fuente: {eventos_agregados}")

    print(f"\nTotal final de canales DSports identificados: {len(dsports_channel_ids)}")

    # Guardar el archivo final
    tree = ET.ElementTree(tv_dsports)
    tree.write("epg-dsports.xml", encoding="utf-8", xml_declaration=True)
    print("✅ Archivo 'epg-dsports.xml' generado exitosamente.")

if __name__ == "__main__":
    extraer_dsports()
