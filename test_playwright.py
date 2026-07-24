from playwright.sync_api import sync_playwright
import json

URL_GUIA = "https://www.directv.com.ar/guia/guia.aspx"

def probar_captura():
    with sync_playwright() as p:
        # headless=False para que abra una ventana real (más difícil de detectar que headless)
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="es-AR",
        )
        page = context.new_page()

        respuesta_capturada = {}

        def manejar_respuesta(response):
            if "GetProgramming" in response.url:
                print(f"\n🎯 Interceptado: {response.url} -> Status {response.status}")
                try:
                    respuesta_capturada["data"] = response.json()
                    print(f"   Tipo de contenido recibido: {type(respuesta_capturada['data'])}")
                except Exception as e:
                    print(f"   No se pudo parsear como JSON: {e}")
                    respuesta_capturada["data"] = response.text()

        page.on("response", manejar_respuesta)

        print(f"Navegando a {URL_GUIA} ...")
        page.goto(URL_GUIA, timeout=30000)

        print("Esperando que cargue la grilla (10 segundos)...")
        page.wait_for_timeout(10000)

        if "data" in respuesta_capturada:
            print("\n✅ ¡Se capturó la respuesta de GetProgramming!")
            with open("respuesta_capturada.json", "w", encoding="utf-8") as f:
                json.dump(respuesta_capturada["data"], f, ensure_ascii=False, indent=2)
            print("Guardado en 'respuesta_capturada.json' para revisar.")
        else:
            print("\n❌ No se interceptó ninguna respuesta de GetProgramming.")
            print("Puede que Radware haya bloqueado la carga o el nombre del endpoint cambió.")

        input("\nPresioná Enter para cerrar el navegador...")
        browser.close()

if __name__ == "__main__":
    probar_captura()
