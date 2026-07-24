from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import time

URL_GUIA = "https://www.directv.com.ar/guia/guia.aspx"
URL_API = "https://www.directv.com.ar/guia/guia.aspx/GetProgramming"
CANTIDAD_DIAS = 2

# Códigos reales de canal para DSports (confirmados inspeccionando la respuesta real)
CODIGOS_DSPORTS = {"DTSA", "DTSAHD", "DTS2", "DTS+", "DTS+HD", "DTSV", "DTSU", "DTSR", "DTS3", "DTS4", "DTS6", "DTS7"}


def parsear_fecha_hora(fecha_str):
    """Convierte '7/23/2026 4:15:00 PM' a formato XMLTV 'YYYYMMDDHHMMSS -0300'."""
    if not fecha_str:
        return ""
    try:
        dt = datetime.strptime(fecha_str, "%m/%d/%Y %I:%M:%S %p")
        return dt.strftime("%Y%m%d%H%M%S") + " -0300"
    except Exception:
        return ""


def agregar_canal_y_programas(tv_root, canal, prefix, registrados_canal, eventos_vistos):
    nombre = canal.get("ChannelName", "").strip()
    numero = str(canal.get("ChannelNumber", "0"))
    ch_id = f"{prefix}.{numero}.{nombre}"

    if ch_id not in registrados_canal:
        ch_elem = ET.SubElement(tv_root, "channel", id=ch_id)
        disp = ET.SubElement(ch_elem, "display-name")
        disp.text = f"{canal.get('ChannelFullName', nombre)} ({numero})"
        registrados_canal.add(ch_id)

    for evento in canal.get("ProgramList", []) or []:
        event_id = evento.get("eventId")
        clave_evento = (ch_id, event_id)
        if event_id and clave_evento in eventos_vistos:
            continue  # ya lo agregamos, evita duplicados
        if event_id:
            eventos_vistos.add(clave_evento)

        inicio = parsear_fecha_hora(evento.get("startTimeString", ""))
        fin = parsear_fecha_hora(evento.get("endTimeString", ""))
        if not inicio or not fin:
            continue
        prog = ET.SubElement(tv_root, "programme", start=inicio, stop=fin, channel=ch_id)
        title = ET.SubElement(prog, "title", lang="es")
        title.text = evento.get("title", "Sin título")
        if evento.get("description"):
            desc = ET.SubElement(prog, "desc", lang="es")
            desc.text = evento.get("description")


def pedir_dia_desde_navegador(page, fecha):
    """Ejecuta un fetch() dentro del navegador para pedir la programación de una fecha específica,
    reutilizando la sesión real que ya pasó el control de Radware."""
    body = {
        "filterParam": {
            "day": fecha.day,
            "month": fecha.month,
            "year": fecha.year,
            "time": fecha.hour,
            "minute": fecha.minute,
            "offSetValue": 0,
            "isHd": "",
            "homeScreenFilter": "",
            "filtersScreenFilters": [""]
        }
    }

    resultado = page.evaluate(
        """async (args) => {
            const [url, body] = args;
            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json; charset=UTF-8',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(body),
                    credentials: 'include'
                });
                const status = res.status;
                const text = await res.text();
                return { status, text };
            } catch (e) {
                return { status: 0, text: String(e) };
            }
        }""",
        [URL_API, body],
    )
    return resultado


def generar_archivos_xml():
    tv_completa = ET.Element("tv")
    tv_dsports = ET.Element("tv")
    registrados_completa = set()
    registrados_dsports = set()
    eventos_vistos_completa = set()
    eventos_vistos_dsports = set()

    hoy = datetime.now()
    fechas = [hoy + timedelta(days=i) for i in range(CANTIDAD_DIAS)]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="es-AR",
        )
        page = context.new_page()

        print(f"Navegando a {URL_GUIA} para establecer sesión real...")
        page.goto(URL_GUIA, timeout=30000)
        print("Esperando carga inicial (8s)...")
        page.wait_for_timeout(9000)

        for fecha in fechas:
            print(f"\nPidiendo programación para {fecha.strftime('%Y-%m-%d')} desde el navegador...")
            resultado = pedir_dia_desde_navegador(page, fecha)
            print(f"  Status: {resultado['status']}")

            if resultado["status"] != 200:
                print(f"  ⚠️ Error, contenido: {resultado['text'][:200]}")
                continue

            import json
            try:
                data = json.loads(resultado["text"])
            except Exception as e:
                print(f"  ⚠️ No se pudo decodificar JSON: {e}")
                print(f"  Contenido: {resultado['text'][:200]}")
                continue

            canales = data.get("d", data) if isinstance(data, dict) else data
            if not isinstance(canales, list):
                print(f"  ⚠️ Formato inesperado: {type(canales)}")
                continue

            print(f"  -> {len(canales)} canales recibidos.")

            for canal in canales:
                agregar_canal_y_programas(tv_completa, canal, "DirecTV", registrados_completa, eventos_vistos_completa)

                nombre = canal.get("ChannelName", "").strip().upper()
                if nombre in CODIGOS_DSPORTS:
                    agregar_canal_y_programas(tv_dsports, canal, "DSports", registrados_dsports, eventos_vistos_dsports)

            time.sleep(1.5)

        browser.close()

    tree_completa = ET.ElementTree(tv_completa)
    tree_completa.write("epg-completa.xml", encoding="utf-8", xml_declaration=True)
    print(f"\n✅ 'epg-completa.xml' guardado con {len(registrados_completa)} canales.")

    tree_dsports = ET.ElementTree(tv_dsports)
    tree_dsports.write("epg-dsports.xml", encoding="utf-8", xml_declaration=True)
    print(f"✅ 'epg-dsports.xml' guardado con {len(registrados_dsports)} canales.")


if __name__ == "__main__":
    generar_archivos_xml()
