import json
import xml.etree.ElementTree as ET
from datetime import datetime

ARCHIVO_JSON = "respuesta_capturada.json"

CODIGOS_DSPORTS = {"DTSA", "DTSAHD", "DTS2", "DTS+", "DTS+HD", "DTSV", "DTSU", "DTSR", "DTS3", "DTS4", "DTS6", "DTS7"}


def parsear_fecha_hora(fecha_str):
    if not fecha_str:
        return ""
    try:
        dt = datetime.strptime(fecha_str, "%m/%d/%Y %I:%M:%S %p")
        return dt.strftime("%Y%m%d%H%M%S") + " -0300"
    except Exception:
        return ""


def cargar_canales(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    canales = data.get("d", data) if isinstance(data, dict) else data
    if not isinstance(canales, list):
        raise ValueError(f"Formato inesperado: {type(canales)}")
    return canales


def recolectar_datos(canales, filtro_dsports=False):
    """Recolecta canales y programas ya deduplicados por contenido real, no por eventId."""
    canales_info = {}   # ch_id -> display_name
    programas_por_canal = {}  # ch_id -> dict( (inicio, fin, titulo) -> datos del evento )

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

            # Clave de deduplicación real: mismo canal + mismo horario + mismo título
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

    # 1. Primero todos los <channel>, agrupados
    for ch_id, display_name in canales_info.items():
        ch_elem = ET.SubElement(tv, "channel", id=ch_id)
        disp = ET.SubElement(ch_elem, "display-name")
        disp.text = display_name

    # 2. Después todos los <programme>, ordenados por canal y horario
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


def generar_xml_desde_json():
    canales = cargar_canales(ARCHIVO_JSON)
    print(f"Procesando {len(canales)} entradas de canal del JSON...")

    # Completa
    info_completa, programas_completa = recolectar_datos(canales, filtro_dsports=False)
    tv_completa = construir_xml(info_completa, programas_completa)
    ET.ElementTree(tv_completa).write("epg-completa.xml", encoding="utf-8", xml_declaration=True)
    total_prog_completa = sum(len(p) for p in programas_completa.values())
    print(f"✅ 'epg-completa.xml': {len(info_completa)} canales, {total_prog_completa} programas.")

    # Solo DSports
    info_dsports, programas_dsports = recolectar_datos(canales, filtro_dsports=True)
    tv_dsports = construir_xml(info_dsports, programas_dsports)
    ET.ElementTree(tv_dsports).write("epg-dsports.xml", encoding="utf-8", xml_declaration=True)
    total_prog_dsports = sum(len(p) for p in programas_dsports.values())
    print(f"✅ 'epg-dsports.xml': {len(info_dsports)} canales, {total_prog_dsports} programas.")


if __name__ == "__main__":
    generar_xml_desde_json()
