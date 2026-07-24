from playwright.sync_api import sync_playwright
from datetime import datetime
import xml.etree.ElementTree as ET
import json

URL_GUIA = "https://www.directv.com.ar/guia/guia.aspx"
CODIGOS_DSPORTS = {"DTSA", "DTSAHD", "DTS2", "DTS+", "DTS+HD", "DTSV", "DTSU", "DTSR", "DTS3", "DTS4", "DTS6", "DTS7"}


# ---------- Paso 1: capturar con Playwright ----------

def capturar_programacion():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="es-AR",
        )
        page = context.new_page()

        capturas = []

        def manejar_respuesta(response):
            if "GetProgramming" in response.url and response.status == 200:
                try:
                    capturas.append(response.json())
                except Exception:
                    pass

        page.on("response", manejar_respuesta)

        print(f"Navegando a {URL_GUIA} (una sola carga, sin pedidos extra)...")
        page.goto(URL_GUIA, timeout=30000)

        print("Esperando que cargue la grilla (10s)...")
        page.wait_for_timeout(10000)

        browser.close()

    if not capturas:
        print("❌ No se interceptó ninguna respuesta de GetProgramming.")
        print("   Si te apareció un CAPTCHA en la ventana, resolvelo a mano navegando el sitio")
        print("   normalmente y volvé a correr este script.")
        return None

    # Nos quedamos con la primera captura válida (evita duplicados de respuestas repetidas)
    data = capturas[0]
    with open("respuesta_capturada.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Se capturó la respuesta y se guardó en 'respuesta_capturada.json'.")

    canales = data.get("d", data) if isinstance(data, dict) else data
    return canales if isinstance(canales, list) else None


# ---------- Paso 2: generar los XML ----------

def parsear_fecha_hora(fecha_str):
    if not fecha_str:
        return ""
    try:
        dt = datetime.strptime(fecha_str, "%m/%d/%Y %I:%M:%S %p")
        return dt.strftime("%Y%m%d%H%M%S") + " -0300"
    except Exception:
        return ""


def recolectar_datos(canales, filtro_dsports=False):
    canales_info = {}
    programas_por_canal = {}

    for canal in canales:
        nombre = canal.get("ChannelName", "").strip()
        numero = str(canal.get("ChannelNumber", "0"))

        if filtro_dsports and nombre.upper() not in CODIGOS_DSPORTS:
            continue

        prefix = "DSports" if filtro_dsports else "DirecTV"
        ch_id = f"{prefix}.{numero}.{nombre}"

        if ch_id not in canales_info:
            canales_info[ch_id] = f"{canal.get('ChannelFullName', nombre)} ({numero})"
            programas_por_canal[ch_id] = {}

        for evento in canal.get("ProgramList", []) or []:
            inicio = parsear_fecha_hora(evento.get("startTimeString", ""))
            fin = parsear_fecha_hora(evento.get("endTimeString", ""))
            titulo = evento.get("title", "Sin título")
            if not inicio or not fin:
                continue

            clave_contenido = (inicio, fin, titulo)
            if clave_contenido not in programas_por_canal[ch_id]:
                programas_por_canal[ch_id][clave_contenido] = {
                    "inicio": inicio,
                    "fin": fin,
                    "titulo": titulo,
                    "descripcion": evento.get("description", ""),
                    "imagen": evento.get("imageUrl", ""),
                }

    return canales_info, programas_por_canal


def construir_xml(canales_info, programas_por_canal):
    tv = ET.Element("tv")

    for ch_id, display_name in canales_info.items():
        ch_elem = ET.SubElement(tv, "channel", id=ch_id)
        disp = ET.SubElement(ch_elem, "display-name")
        disp.text = display_name

    for ch_id, programas in programas_por_canal.items():
        eventos_ordenados = sorted(programas.values(), key=lambda e: e["inicio"])
        for evento in eventos_ordenados:
            prog = ET.SubElement(tv, "programme", start=evento["inicio"], stop=evento["fin"], channel=ch_id)
            title = ET.SubElement(prog, "title", lang="es")
            title.text = evento["titulo"]
            if evento["descripcion"]:
                desc = ET.SubElement(prog, "desc", lang="es")
                desc.text = evento["descripcion"]
            if evento["imagen"]:
                ET.SubElement(prog, "icon", src=evento["imagen"])

    return tv


def generar_xml(canales):
    print(f"\nProcesando {len(canales)} entradas de canal...")

    info_completa, programas_completa = recolectar_datos(canales, filtro_dsports=False)
    tv_completa = construir_xml(info_completa, programas_completa)
    ET.ElementTree(tv_completa).write("epg-completa.xml", encoding="utf-8", xml_declaration=True)
    total_prog_completa = sum(len(p) for p in programas_completa.values())
    print(f"✅ 'epg-completa.xml': {len(info_completa)} canales, {total_prog_completa} programas.")

    info_dsports, programas_dsports = recolectar_datos(canales, filtro_dsports=True)
    tv_dsports = construir_xml(info_dsports, programas_dsports)
    ET.ElementTree(tv_dsports).write("epg-dsports.xml", encoding="utf-8", xml_declaration=True)
    total_prog_dsports = sum(len(p) for p in programas_dsports.values())
    print(f"✅ 'epg-dsports.xml': {len(info_dsports)} canales, {total_prog_dsports} programas.")


# ---------- Main ----------

if __name__ == "__main__":
    canales = capturar_programacion()
    if canales:
        generar_xml(canales)
    else:
        print("\nNo se generaron los XML porque no hubo captura válida.")
