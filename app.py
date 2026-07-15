import re
import time
from datetime import datetime
from flask import Flask, render_template, redirect, url_for
import requests

from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos

app = Flask(__name__)

# Tus URLs seguras de canales y eventos
URL_ENLACES = 'https://raw.githubusercontent.com/socramtv/Soccer-app/main/hashes.json'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'

# Sistema de Caché Unificado para evitar desincronizaciones
cache_datos = None
ultimo_scraping = 0
CACHE_EXPIRACION = 600  # 10 minutos

def normalizar_cadena(texto):
    """Limpia tildes, símbolos y estandariza nombres de canales para cruzarlos"""
    texto = texto.lower().strip()
    texto = texto.replace("m+", "movistar").replace("m. ", "movistar ")
    texto = texto.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    texto = re.sub(r'[\(\)\-\[\]\*\_\|\+]', '', texto)
    return " ".join(texto.split())

def vincular_canales_automatico(canales_evento, lista_enlaces):
    """Busca de forma automática y dinámica los hashes correctos sin usar if/elif"""
    html_resultado = ""
    
    for canal in canales_evento:
        canal_limpio = canal.strip()
        canal_norm = normalizar_cadena(canal_limpio)
        
        palabras_web = [w for w in canal_norm.split() if w not in ['hd', 'sd', '1080p', '720p', 'la', 'el', 'los', 'de', 'en']]
        
        if not palabras_web:
            html_resultado += f'<span class="canal-texto">{canal_limpio}</span><br>'
            continue
            
        es_bar = "bar" in canal_norm
        matches_encontrados = []
        
        for enc in lista_enlaces:
            nombre_json_norm = normalizar_cadena(enc['name'])
            
            if es_bar and "bar" not in nombre_json_norm:
                continue
            if not es_bar and "bar" in nombre_json_norm:
                continue
                
            if all(palabra in nombre_json_norm for palabra in palabras_web):
                acestream_url = f"acestream://{enc['id']}"
                icono = "★" if "**" in enc['name'] else "⚡"
                matches_encontrados.append(
                    f'<a href="{acestream_url}" class="btn-canal" title="{enc["name"]}">{icono} {enc["name"]}</a>'
                )
        
        if matches_encontrados:
            html_resultado += "".join(matches_encontrados)
        else:
            html_resultado += f'<span class="canal-texto-vacio">{canal_limpio}</span>'
            
    return html_resultado

def obtener_datos_completos():
    global cache_datos, ultimo_scraping
    ahora = time.time()
    
    if cache_datos and (ahora - ultimo_scraping < CACHE_EXPIRACION):
        return cache_datos
        
    print("🌐 Descargando y organizando canales y cartelera...")
    enlaces = extraer_enlaces(URL_ENLACES)
    eventos = extraer_eventos(URL_EVENTOS)
    
    # Vincular canales automáticos a los partidos
    for i in range(len(eventos)):
        eventos[i]['canales_html'] = vincular_canales_automatico(eventos[i]['canales'], enlaces)
        
    # Agrupar los partidos por liga/competición
    eventos_agrupados = {}
    for ev in eventos:
        liga = ev.get('liga', 'Otras Competiciones').strip()
        if liga not in eventos_agrupados:
            eventos_agrupados[liga] = []
        eventos_agrupados[liga].append(ev)
        
    # Guardamos todo en la estructura de caché
    cache_datos = {
        'eventos_agrupados': eventos_agrupados,
        'canales_puros': enlaces
    }
    ultimo_scraping = ahora
    return cache_datos

@app.route('/')
def home():
    datos = obtener_datos_completos()
    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    
    # Enviamos los partidos organizados y los canales puros al HTML
    return render_template(
        'index.html', 
        eventos_agrupados=datos['eventos_agrupados'], 
        canales_puros=datos['canales_puros'], 
        fecha=fecha_actual
    )

@app.route('/recargar')
def recargar():
    global cache_datos, ultimo_scraping
    cache_datos = None
    ultimo_scraping = 0
    print("♻️ Caché del servidor vaciada por completo.")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
