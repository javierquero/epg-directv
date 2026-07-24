# EPG DirecTV / DSports Argentina

Genera guías de programación (EPG) en formato **XMLTV** a partir de la grilla web oficial de DirecTV Argentina, con foco en las señales de **DSports**.

Produce dos archivos:

- `epg-completa.xml` — toda la grilla de canales disponibles.
- `epg-dsports.xml` — solo las señales de DSports (Argentina, Uruguay, Venezuela, HD y radio).

Ambos incluyen título, horario (huso horario de Buenos Aires, `-0300`), descripción cuando está disponible, y una imagen (`<icon>`) del programa.

## ⚠️ Importante: por qué esto NO está automatizado en la nube

La grilla de DirecTV está protegida por un sistema anti-bot comercial (Radware) que bloquea con captcha las requests que no parecen provenir de una persona navegando de forma normal. Por este motivo:

- La captura de datos **se hace en una máquina local** (PC o dispositivo con IP residencial), nunca desde un servidor en la nube (GitHub Actions, VPS, etc.).
- El script abre un navegador real, carga la página **una sola vez** (igual que lo haría cualquier persona) y no hace pedidos repetidos ni paralelos.
- Si en algún momento aparece un CAPTCHA, hay que resolverlo a mano en el navegador antes de volver a correr el script.

No se incluye ni se dará soporte a métodos para evadir esta protección de forma automatizada.

## Requisitos

- Python 3.10+
- Google Chrome / Chromium disponible para Playwright

```bash
pip install playwright requests --break-system-packages
python3 -m playwright install chromium
```

## Uso

### 1. Actualizar el EPG (captura + generación de XML en un solo paso)

```bash
python3 actualizar_epg.py
```

Esto:

1. Abre un navegador real y carga `https://www.directv.com.ar/guia/guia.aspx`.
2. Intercepta la respuesta real de la grilla y la guarda en `respuesta_capturada.json`.
3. Genera `epg-completa.xml` y `epg-dsports.xml`, deduplicados por canal + horario + título.

Si aparece un CAPTCHA en la ventana del navegador, resolvelo a mano, esperá a que la página cargue normal, y volvé a correr el script.

### 2. Descargar logos de canales (opcional)

```bash
python3 descargar_logos.py
```

Lee `respuesta_capturada.json` y descarga el logo de cada canal a `logos_canales/`.

### 3. Descargar imágenes de programas (opcional)

```bash
python3 descargar_logos_programas.py
```

Lee `respuesta_capturada.json` y descarga la miniatura de cada programa a `logos_programas/`.

## Subir los cambios a GitHub

```bash
git add -A
git commit -m "Actualizar EPG del día"
git push
```

## Usar el EPG en un reproductor IPTV

Una vez subido a GitHub, la URL raw del archivo sirve como fuente de EPG en cualquier reproductor compatible con XMLTV (TiviMate, IPTV Smarters, Kodi, etc.):

```
https://raw.githubusercontent.com/javierquero/epg-directv/main/epg-dsports.xml
```

Los `tvg-id` de tu lista `.m3u` deben coincidir con los `id` de canal usados en el XML (formato `DSports.<número>.<código>`, por ejemplo `DSports.612.DTS2`).

## Estructura del proyecto

```
epg-directv/
├── actualizar_epg.py            # Captura + genera los XML (todo en uno)
├── descargar_logos.py           # Logos de canales (opcional)
├── descargar_logos_programas.py # Imágenes de programas (opcional)
├── respuesta_capturada.json     # Última captura cruda (se sobreescribe cada vez)
├── epg-completa.xml             # EPG con todos los canales
├── epg-dsports.xml              # EPG solo de DSports
├── logos_canales/                # Logos descargados (opcional)
└── logos_programas/              # Miniaturas descargadas (opcional)
```

## Frecuencia de actualización

Este EPG solo cubre el **día en curso** al momento de correr el script (la grilla web de DirecTV no permite consultar días futuros de forma confiable sin activar el sistema anti-bot). Se recomienda correr `actualizar_epg.py` una vez por día.
