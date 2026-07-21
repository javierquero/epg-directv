import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time

CANTIDAD_DIAS = 3

def crear_estructura_xmltv():
    return ET.Element("tv")

def procesar_evento(prog_parent, evento):
    inicio_raw = evento.get("startTime", "").replace("-", "").replace(":", "").replace("T", " ")
    fin_raw = evento.get("endTime", "").replace("-", "").replace(":", "").replace("T", " ")

    prog_parent.set("start", inicio_raw)
    prog_parent.set("stop", fin_raw)

    title = ET.SubElement(prog_parent, "title", lang="es")
    title.text = evento.get("title", "Sin título")

    if evento.get("description"):
        desc = ET.SubElement(prog_parent, "desc", lang="es")
        desc.text = evento.get("description")

def generar_archivos_xml():
    session = requests.Session()
    
    # Headers completos imitando un navegador en Argentina
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.directv.com.ar/guia/guia.aspx",
        "Origin": "https://www.directv.com.ar",
        "Connection": "keep-alive"
    }
    session.headers.update(headers)

    print("Conectando a DirecTV Argentina para establecer cookies...")
    try:
        r_init = session.get("https://www.directv.com.ar/guia/guia.aspx", timeout=20)
        print(f"Estado de conexión inicial: {r_init.status_code}")
    except Exception as e:
        print(f"Advertencia al conectar: {e}")

    tv_completa = crear_estructura_xmltv()
    tv_dsports = crear_estructura_xmltv()

    canales_registrados_completa = set()
    canales_registrados_dsports = set()

    hoy = datetime.now()
    fechas = [(hoy + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(CANTIDAD_DIAS)]

    print(f"Consultando fechas: {', '.join(fechas)}")

    for fecha in fechas:
        # Probamos el endpoint principal
        url_api = f"https://www.directv.com.ar/api/epg/getChannels?date={fecha}&country=AR&userType=anonymous"
        
        try:
            res = session.get(url_api, timeout=20)
            print(f"[{fecha}] HTTP Status: {res.status_code}")

            if res.status_code != 200:
                print(f"Error {res.status_code} recibiendo respuesta de la API.")
                continue

            try:
                data = res.json()
            except Exception as json_err:
                print(f"Error decodificando JSON en {fecha}: {json_err}")
                print(f"Contenido recibido (primeros 200 caracteres): {res.text[:200]}")
                continue

            # Extracción del listado de canales
            canales = []
            if isinstance(data, dict):
                canales = data.get("response", {}).get("channels", []) or data.get("channels", [])
            elif isinstance(data, list):
                canales = data

            print(f"  -> {fecha}: Se encontraron {len(canales)} canales.")

            for canal in canales:
                nombre = str(canal.get("name", "")).strip().upper()
                numero_canal = str(canal.get("number", "0"))
                
                # 1. PROCESAR COMPLETA
                id_completa = f"DirecTV.{numero_canal}"
                if id_completa not in canales_registrados_completa:
                    ch_elem = ET.SubElement(tv_completa, "channel", id=id_completa)
                    disp = ET.SubElement(ch_elem, "display-name")
                    disp.text = f"{canal.get('name', '').strip()} ({numero_canal})"
                    canales_registrados_completa.add(id_completa)

                for evento in canal.get("events", []):
                    prog = ET.SubElement(tv_completa, "programme", channel=id_completa)
                    procesar_evento(prog, evento)

                # 2. PROCESAR SOLO DSPORTS
                if "DSPORTS" in nombre or "DIRECTV SPORTS" in nombre:
                    id_dsports = f"DSports.{numero_canal}"
                    if id_dsports not in canales_registrados_dsports:
                        ch_elem = ET.SubElement(tv_dsports, "channel", id=id_dsports)
                        disp = ET.SubElement(ch_elem, "display-name")
                        disp.text = f"{canal.get('name', '').strip()} ({numero_canal})"
                        canales_registrados_dsports.add(id_dsports)

                    for evento in canal.get("events", []):
                        prog = ET.SubElement(tv_dsports, "programme", channel=id_dsports)
                        procesar_evento(prog, evento)

            time.sleep(1)

        except Exception as e:
            print(f"❌ Excepción en {fecha}: {e}")

    # Guardar archivos
    tree_completa = ET.ElementTree(tv_completa)
    tree_completa.write("epg-completa.xml", encoding="utf-8", xml_declaration=True)
    print(f"✅ 'epg-completa.xml' guardado con {len(canales_registrados_completa)} canales.")

    tree_dsports = ET.ElementTree(tv_dsports)
    tree_dsports.write("epg-dsports.xml", encoding="utf-8", xml_declaration=True)
    print(f"✅ 'epg-dsports.xml' guardado con {len(canales_registrados_dsports)} canales.")

if __name__ == "__main__":
    generar_archivos_xml()
