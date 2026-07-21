from DrissionPage import ChromiumPage, ChromiumOptions
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

CANTIDAD_DIAS = 3

def crear_estructura_xmltv():
    return ET.Element("tv")

def procesar_evento(prog_parent, evento):
    # Formato de fecha para XMLTV (YYYYMMDDHHMMSS +0000)
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
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')

    page = ChromiumPage(co)
    
    print("Navegando a DirecTV para inicializar sesión...")
    page.get('https://www.directv.com.ar/guia/guia.aspx')
    page.wait.load_start()

    tv_completa = crear_estructura_xmltv()
    tv_dsports = crear_estructura_xmltv()

    canales_registrados_completa = set()
    canales_registrados_dsports = set()

    hoy = datetime.now()
    fechas = [(hoy + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(CANTIDAD_DIAS)]

    print(f"Obteniendo programación para {CANTIDAD_DIAS} días: {', '.join(fechas)}")

    for fecha in fechas:
        url_api = f"https://www.directv.com.ar/api/epg/getChannels?date={fecha}&country=AR&userType=anonymous"
        
        try:
            res = page.s_get(url_api)
            if res.status_code != 200:
                print(f"⚠️ Error {res.status_code} al consultar la fecha {fecha}")
                continue

            data = res.json()
            canales = data.get("response", {}).get("channels", []) if isinstance(data, dict) else []

            for canal in canales:
                nombre = canal.get("name", "").strip().upper()
                numero_canal = canal.get("number", "0")
                
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

        except Exception as e:
            print(f"❌ Error al procesar el día {fecha}: {e}")

    page.quit()

    # Guardar archivos
    tree_completa = ET.ElementTree(tv_completa)
    tree_completa.write("epg-completa.xml", encoding="utf-8", xml_declaration=True)

    tree_dsports = ET.ElementTree(tv_dsports)
    tree_dsports.write("epg-dsports.xml", encoding="utf-8", xml_declaration=True)
    
    print(" Archivos XML generados con éxito.")

if __name__ == "__main__":
    generar_archivos_xml()
