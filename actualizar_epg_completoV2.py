import sys
import os
import json
import time
import random
import logging
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: Se requiere 'playwright'. Instalalo usando: pip install playwright")
    print("Y luego ejecutá: playwright install chromium")
    sys.exit(1)


# ==========================================================
# CONFIGURACIÓN GENERAL Y LOGGING
# ==========================================================
URL_DIRECTV = "https://www.directv.com.ar/guia/guia.aspx"
ARCHIVO_XML_COMPLETO = "epg_directv_completo.xml"
ARCHIVO_XML_DSPORTS = "epg_directv_dsports.xml"
ARCHIVO_LOG = "actualizar_epg.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(ARCHIVO_LOG, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EPG_DirecTV")

# Palabras clave para filtrar canales DSports
DSPORTS_KEYWORDS = ["dsports", "dtv sports", "dtvshd", "dtsr", "dtsa", "direcTV sports"]


# ==========================================================
# CLASE 1: CAPTURADOR Y ACUMULADOR DE RED
# ==========================================================
class NetworkCapture:
    """
    Escucha y acumula las respuestas JSON de programación que envía DirecTV.
    """
    def __init__(self):
        self.canales_acumulados = {}

    def install(self, page):
        def handle_response(response):
            try:
                if response.status == 200 and "json" in response.headers.get("content-type", "").lower():
                    content_len = int(response.headers.get("content-length", 0))
                    if content_len > 1500 or content_len == 0:
                        data = response.json()
                        self._procesar_y_acumular(data)
            except Exception:
                pass

        page.on("response", handle_response)

    def _procesar_y_acumular(self, data):
        target = data.get("d") if isinstance(data, dict) and "d" in data else data
        if isinstance(target, list) and len(target) > 0:
            sample = target[0]
            if isinstance(sample, dict) and ("ProgramList" in sample or "ChannelNumber" in sample):
                nuevos = 0
                for item in target:
                    num_canal = str(item.get("ChannelNumber", "")).strip()
                    if num_canal:
                        if num_canal not in self.canales_acumulados:
                            self.canales_acumulados[num_canal] = item
                            nuevos += 1
                        else:
                            # Fusionar programas para evitar duplicados
                            existentes = self.canales_acumulados[num_canal].get("ProgramList", [])
                            nuevos_progs = item.get("ProgramList", [])
                            tiempos_existentes = {p.get("startTimeString") for p in existentes}
                            for p in nuevos_progs:
                                if p.get("startTimeString") not in tiempos_existentes:
                                    existentes.append(p)
                            self.canales_acumulados[num_canal]["ProgramList"] = existentes
                
                if nuevos > 0:
                    logger.info(f"[+] Se capturaron {nuevos} canales. Total acumulado: {len(self.canales_acumulados)}.")


# ==========================================================
# CLASE 2: NAVEGADOR STEALTH
# ==========================================================
class HumanStealthBrowser:
    def __init__(self, headless=True):
        self.headless = headless

    def run_stealth_session(self, url, capture_timeout=35):
        with sync_playwright() as p:
            logger.info("Iniciando navegador con configuración Stealth...")
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                ]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="es-AR",
                timezone_id="America/Argentina/Buenos_Aires"
            )

            page = context.new_page()

            # Evitar detección básica de bot
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', {get: () => ['es-AR', 'es', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            """)

            capture = NetworkCapture()
            capture.install(page)

            logger.info(f"Navegando a {url}...")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                
                # Esperar a que la red cargue los datos iniciales
                start_time = time.time()
                while len(capture.canales_acumulados) == 0 and (time.time() - start_time) < capture_timeout:
                    page.evaluate("window.scrollBy({top: 150, behavior: 'smooth'});")
                    time.sleep(1.5)

                # Pequeño scroll adicional solo si la página lo requiere para refrescar
                if len(capture.canales_acumulados) > 0:
                    logger.info("Respuesta de red recibida correctamente. Finalizando captura.")
                    time.sleep(2)

            except Exception as e:
                logger.error(f"Error de navegación: {e}")
            finally:
                browser.close()

            return list(capture.canales_acumulados.values())


# ==========================================================
# MÓDULO 3: PROCESADOR Y GENERADOR XMLTV
# ==========================================================
def parsear_fecha_directv(cadena_fecha):
    if not cadena_fecha:
        return ""
    try:
        dt = datetime.strptime(cadena_fecha.strip(), "%m/%d/%Y %I:%M:%S %p")
        return dt.strftime("%Y%m%d%H%M%S -0300")
    except ValueError:
        try:
            dt = datetime.strptime(cadena_fecha.strip(), "%m/%d/%Y %H:%M:%S")
            return dt.strftime("%Y%m%d%H%M%S -0300")
        except Exception:
            return ""

def es_canal_dsports(nombre_canal, num_canal):
    """Verifica si un canal corresponde a la cadena DSports."""
    cadena_busqueda = f"{nombre_canal} {num_canal}".lower()
    return any(kw in cadena_busqueda for kw in DSPORTS_KEYWORDS)

def generar_xmltv(canales_raw, solo_dsports=False):
    tipo_str = "DSports" if solo_dsports else "Completo"
    logger.info(f"Construyendo XMLTV ({tipo_str})...")

    if not isinstance(canales_raw, list) or len(canales_raw) == 0:
        logger.error("No hay lista de canales para procesar.")
        return None

    # Filtrar si se solicitó solo DSports
    if solo_dsports:
        canales_filtrados = [
            c for c in canales_raw 
            if es_canal_dsports(str(c.get("ChannelName", "")), str(c.get("ChannelNumber", "")))
        ]
    else:
        canales_filtrados = canales_raw

    if len(canales_filtrados) == 0 and solo_dsports:
        logger.warning("No se encontraron canales DSports específicos en los datos capturados.")
        return None

    root = ET.Element("tv", {
        "generator-info-name": f"Scraper EPG DirecTV {tipo_str}",
        "source-info-name": "DirecTV Argentina"
    })

    canales_procesados = set()
    programas_count = 0

    # 1. Nodos <channel>
    for item in canales_filtrados:
        num_canal = str(item.get("ChannelNumber", "")).strip()
        nombre_canal = item.get("ChannelName", "").strip()

        if not num_canal:
            continue

        channel_id = f"DirecTV.{num_canal}.ar"

        if channel_id not in canales_procesados:
            canales_procesados.add(channel_id)
            nodo_canal = ET.SubElement(root, "channel", id=channel_id)
            display_name = f"{num_canal} - {nombre_canal}" if nombre_canal else num_canal
            
            ET.SubElement(nodo_canal, "display-name").text = display_name
            ET.SubElement(nodo_canal, "display-name").text = num_canal

    # 2. Nodos <programme>
    for item in canales_filtrados:
        num_canal = str(item.get("ChannelNumber", "")).strip()
        if not num_canal:
            continue

        channel_id = f"DirecTV.{num_canal}.ar"
        program_list = item.get("ProgramList", [])

        if not isinstance(program_list, list):
            continue

        for prog in program_list:
            start_str = prog.get("startTimeString", "")
            end_str = prog.get("endTimeString", "")

            start_xmltv = parsear_fecha_directv(start_str)
            end_xmltv = parsear_fecha_directv(end_str)

            if not start_xmltv or not end_xmltv:
                continue

            nodo_prog = ET.SubElement(root, "programme", {
                "start": start_xmltv,
                "stop": end_xmltv,
                "channel": channel_id
            })

            titulo = prog.get("title", "Sin título")
            ET.SubElement(nodo_prog, "title", lang="es").text = titulo

            ep_title = prog.get("episodeTitle")
            if ep_title:
                ET.SubElement(nodo_prog, "sub-title", lang="es").text = str(ep_title)

            desc = prog.get("description")
            if desc:
                ET.SubElement(nodo_prog, "desc", lang="es").text = str(desc)

            category = prog.get("subCategoryName") or prog.get("categoryId")
            if category:
                ET.SubElement(nodo_prog, "category", lang="es").text = str(category)

            img_url = prog.get("imageUrl")
            if img_url:
                ET.SubElement(nodo_prog, "icon", src=str(img_url))

            programas_count += 1

    logger.info(f"XMLTV {tipo_str} generado: {len(canales_procesados)} canales y {programas_count} programas.")

    xml_str = ET.tostring(root, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    return parsed_xml.toprettyxml(indent="  ", encoding="UTF-8")


# ==========================================================
# EJECUCIÓN PRINCIPAL
# ==========================================================
def main():
    logger.info("==================================================")
    logger.info("Iniciando Generador de EPG DirecTV (Doble Salida)")
    logger.info("==================================================")
    
    # Modo invisible desactivado por defecto (headless=True para velocidad)
    stealth_browser = HumanStealthBrowser(headless=True)
    
    canales_capturados = stealth_browser.run_stealth_session(URL_DIRECTV, capture_timeout=30)

    if not canales_capturados:
        logger.error("CRÍTICO: No se obtuvieron datos de la programación.")
        sys.exit(1)

    # 1. Generar XML COMPLETO
    xml_completo = generar_xmltv(canales_capturados, solo_dsports=False)
    if xml_completo:
        with open(ARCHIVO_XML_COMPLETO, "wb") as f:
            f.write(xml_completo)
        logger.info(f"[+] Guardado completo en: {os.path.abspath(ARCHIVO_XML_COMPLETO)}")

    # 2. Generar XML SOLO DSPORTS
    xml_dsports = generar_xmltv(canales_capturados, solo_dsports=True)
    if xml_dsports:
        with open(ARCHIVO_XML_DSPORTS, "wb") as f:
            f.write(xml_dsports)
        logger.info(f"[+] Guardado DSports en: {os.path.abspath(ARCHIVO_XML_DSPORTS)}")

    logger.info("Proceso completado con éxito.")

if __name__ == "__main__":
    main()
