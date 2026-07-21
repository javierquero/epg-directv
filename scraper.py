import requests
import gzip
import io
import xml.etree.ElementTree as ET

# Fuente consolidada de canales deportivos de Latam/Argentina (incluye DSports)
EPG_SOURCE = "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz"

def extraer_dsports():
    print("Descargando EPG de señales deportivas...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    resp = requests.get(EPG_SOURCE, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"❌ Error al descargar: Status {resp.status_code}")
        return

    # Descomprimir la fuente GZIP en memoria
    print("Descomprimiendo y procesando XMLTV...")
    with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as gz:
        xml_data = gz.read()

    root = ET.fromstring(xml_data)

    tv_dsports = ET.Element("tv")
    dsports_channel_ids = set()

    # 1. Mapear y filtrar los canales de DSports (DSports, DSports 2, DSports+, DSports Motor)
    for channel in root.findall("channel"):
        ch_id = channel.get("id", "")
        display_name = channel.find("display-name")
        nombre = display_name.text.upper() if display_name is not None and display_name.text else ""

        if "DSPORTS" in nombre or "DIRECTV SPORTS" in nombre:
            tv_dsports.append(channel)
            dsports_channel_ids.add(ch_id)

    print(f"Se encontraro {len(dsports_channel_ids)} canales de DSports.")

    # 2. Filtrar los eventos (<programme>) asociados a esos canales
    programas_contados = 0
    for prog in root.findall("programme"):
        if prog.get("channel") in dsports_channel_ids:
            tv_dsports.append(prog)
            programas_contados += 1

    print(f"Se procesaron {programas_contados} eventos de programación.")

    # Guardar el archivo epg-dsports.xml
    tree = ET.ElementTree(tv_dsports)
    tree.write("epg-dsports.xml", encoding="utf-8", xml_declaration=True)
    print("✅ 'epg-dsports.xml' generado correctamente.")

if __name__ == "__main__":
    extraer_dsports()
