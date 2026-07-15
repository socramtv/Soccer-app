import re
import time
from datetime import datetime
from flask import Flask, render_template, redirect, url_for
import requests

from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos

app = Flask(__name__)

# Tus URLs seguras
URL_ENLACES = 'https://raw.githubusercontent.com/socramtv/Soccer-app/main/hashes.json'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'

# Sistema de Caché Inteligente
cache_eventos = None
ultimo_scraping = 0
CACHE_EXPIRACION = 600  # 10 minutos

def normalizar_cadena(texto):
    """Limpia tildes, símbolos y estandariza nombres de canales para cruzarlos"""
    texto = texto.lower().strip()
    texto = texto.replace("m+", "movistar").replace("m. ", "movistar ")
    # Quitar acentos comunes
    texto = texto.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    # Eliminar caracteres especiales y símbolos de calidad
    texto = re.sub(r'[\(\)\-\[\]\*\_\|\+]', '', texto)
    return " ".join(texto.split())

def vincular_canales_automatico(canales_evento, lista_enlaces):
    """Busca de forma automática y dinámica los hashes correctos sin usar if/elif"""
    html_resultado = ""
    
    for canal in canales_evento:
        canal_limpio = canal.strip()
        canal_norm = normalizar_cadena(canal_limpio)
        
        # Extraer palabras clave ignorando conectores y calidades
        palabras_web = [w for w in canal_norm.split() if w not in ['hd', 'sd', '1080p', '720p', 'la', 'el', 'los', 'de', 'en']]
        
        if not palabras_web:
            html_resultado += f'<span class="canal-texto">{canal_limpio}</span><br>'
            continue
            
        es_bar = "bar" in canal_norm
        matches_encontrados = []
        
        # Buscar coincidencias en tu hashes.json
        for enc in lista_enlaces:
            nombre_json_norm = normalizar_cadena(enc['name'])
            
            # Control estricto de canales "BAR"
            if es_bar and "bar" not in nombre_json_norm:
                continue
            if not es_bar and "bar" in nombre_json_norm:
                continue
                
            # Si todas las palabras clave de la web están en el canal del JSON, es un Match
            if all(palabra in nombre_json_norm for palabra in palabras_web):
                acestream_url = f"acestream://{enc['id']}"
                # Distinguir visualmente si es canal principal (*) o respaldo (**)
                icono = "★" if "**" in enc['name'] else "⚡"
                matches_encontrados.append(
                    f'<a href="{acestream_url}" class="btn-canal" title="{enc["name"]}">{icono} {enc["name"]}</a>'
                )
        
        # Si encontramos enlaces Acestream los añadimos, si no, dejamos el texto normal
        if matches_encontrados:
            html_resultado += "".join(matches_encontrados)
        else:
            html_resultado += f'<span class="canal-texto-vacio">{canal_limpio}</span>'
            
    return html_resultado

def procesar_eventos():
    global cache_eventos, ultimo_scraping
    ahora = time.time()
    
    # Retornar caché si sigue vigente
    if cache_eventos and (ahora - ultimo_scraping < CACHE_EXPIRACION):
        return cache_eventos
        
    print("🌐 Iniciando actualización de datos en segundo plano...")
    enlaces = extraer_enlaces(URL_ENLACES)
    eventos = extraer_eventos(URL_EVENTOS)
    
    # Procesar y vincular automáticamente cada partido
    for i in range(len(eventos)):
        eventos[i]['canales_html'] = vincular_canales_automatico(eventos[i]['canales'], enlaces)
        
    cache_eventos = eventos
    ultimo_scraping = ahora
    return eventos

@app.route('/')
def home():
    eventos = procesar_eventos()
    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    return render_template('index.html', eventos=eventos, fecha=fecha_actual)

@app.route('/recargar')
def recargar():
    """Ruta especial heredada de Andrenalina para forzar la limpieza de la caché"""
    global cache_eventos, ultimo_scraping
    cache_eventos = None
    ultimo_scraping = 0
    print("♻️ Caché del servidor vaciada manualmente por el usuario.")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
