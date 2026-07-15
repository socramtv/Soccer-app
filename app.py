from flask import Flask, render_template
from datetime import datetime
import re
import time

# Importamos tus funciones existentes
from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos
from funciones.obtener_enlaces import obtener_enlaces

app = Flask(__name__)

# Configuración de URLs
URL_ENLACES = 'https://vacaionesenelmar.xo.je/hashes.json'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'

# VARIABLES DE CACHÉ (Evitan saturar el servidor de Render)
cache_eventos = None
ultimo_scraping = 0
CACHE_EXPIRACION = 600  # Tiempo de vida de la caché: 10 minutos (600 segundos)

def procesar_eventos():
    global cache_eventos, ultimo_scraping
    ahora = time.time()

    # Si ya tenemos datos guardados y han pasado menos de 10 minutos, los devolvemos al instante
    if cache_eventos and (ahora - ultimo_scraping < CACHE_EXPIRACION):
        print("🔄 [Caché] Cargando eventos guardados (carga instantánea)")
        return cache_eventos

    print("🌐 [Live] Iniciando scraping en vivo (esto puede tardar unos segundos)...")
    enlaces = extraer_enlaces(URL_ENLACES)
    eventos = extraer_eventos(URL_EVENTOS)

    for i in range(len(eventos)):
        # Inicializamos el campo para evitar errores
        eventos[i]['canales_html'] = ""
        
        for canal in eventos[i]['canales']:
            if re.search(r"dazn 1\b", canal, re.IGNORECASE) and "bar" not in canal.lower():
                a = obtener_enlaces(enlaces, r"^dazn 1(?!\s+bar)\b")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"dazn 2\b", canal, re.IGNORECASE) and "bar" not in canal.lower():
                a = obtener_enlaces(enlaces, r"^dazn 2(?!\s+bar)\b")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"dazn 3\b", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"^dazn 3\b")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"dazn 4\b", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"^dazn 4\b")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"dazn 1.*bar", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"dazn 1\s+bar")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"dazn 2.*bar", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"dazn 2\s+bar")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"dazn.*liga\s+[^\d]", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"dazn.*liga\s+1")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"dazn.*liga\s+2", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"dazn.*liga\s+2")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*liga\s+\(", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*liga\s+[^\d]")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*liga\s+2", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*liga\s+2")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*liga\s+3", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*liga\s+3")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*liga\s+4", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*liga\s+4")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"campeones\s+\(", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"campeones\s+[^\d]")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"campeones\s+2", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"campeones\s+2")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"campeones\s+3", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"campeones\s+3")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"campeones\s+4", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"campeones\s+4")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"campeones\s+5", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"campeones\s+5")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"movistar plus\+?\s+\(", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"movistar plus\+?\s+[^\d]")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"movistar plus\+?\s+2", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"movistar plus\+?\s+2")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*deportes\s+[^\d]", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*deportes\s+[^\d]")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*deportes\s+2", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*deportes\s+2")
                eventos[i]['canales_html'] += a + '<br>\n'
                
            elif re.search(r"m.*deportes\s+3", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*deportes\s+3")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*deportes\s+4", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*deportes\s+4")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*deportes\s+5", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*deportes\s+5")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*deportes\s+6", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*deportes\s+6")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"m.*vamos\s+\(", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"m.*vamos\s+[^\d]")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"tennis\s+channel", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"tennis\s+channel")
                eventos[i]['canales_html'] += a + '<br>\n'

            elif re.search(r"dazn\s+f1", canal, re.IGNORECASE):
                a = obtener_enlaces(enlaces, r"dazn\s+f1")
                eventos[i]['canales_html'] += a + '<br>\n'
                
            else: 
                eventos[i]['canales_html'] += canal + '<br>\n'
                
    # Guardamos el resultado en caché
    cache_eventos = eventos
    ultimo_scraping = ahora
    return eventos

@app.route('/')
def home():
    eventos = procesar_eventos()
    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    return render_template('index.html', eventos=eventos, fecha=fecha_actual)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
