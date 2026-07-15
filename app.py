from flask import Flask, render_template
from datetime import datetime
import re

# Importamos tus funciones existentes
from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos
from funciones.obtener_enlaces import obtener_enlaces

app = Flask(__name__)

# Configuración de URLs
URL_ENLACES = 'https://ipfs.io/ipns/k2k4r8lm8tkmuxbc8lkmq1in3v0oya1p6pe9o5bu0hu30br5ko08k2gb/?tab=lista'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'

def procesar_eventos():
    """Obtiene los eventos y genera el HTML de los canales de forma dinámica"""
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
                
    return eventos

@app.route('/')
def home():
    # Obtenemos los eventos actualizados al cargar la web
    eventos = procesar_eventos()
    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    
    # Renderizamos la plantilla HTML pasándole los datos dinámicos
    return render_template('index.html', eventos=eventos, fecha=fecha_actual)

if __name__ == '__main__':
    # Ejecuta el servidor local en modo desarrollo
    app.run(debug=True, port=5000)
