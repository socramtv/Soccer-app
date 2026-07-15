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

# Sistema de Caché Unificado
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
    """Algoritmo inteligente bidireccional y tolerante a nombres con operadores y diales"""
    html_resultado = ""
    
    # Palabras de ruido absoluto que se limpian para el cruce de datos
    STOPWORDS = {'hd', 'sd', '1080p', '720p', 'la', 'el', 'los', 'de', 'en', 'ver', 'directo', 'orange', 'tv', 'vodafone', 'movistar', 'plus'}
    
    for canal in canales_evento:
        canal_limpio = canal.strip()
        
        # 1. Eliminar por completo el contenido entre paréntesis de la web (ej: "(Ver en directo)", "(131)")
        canal_sin_paren = re.sub(r'\(.*?\)', '', canal_limpio)
        canal_norm = normalizar_cadena(canal_sin_paren)
        
        # Obtener las palabras clave esenciales y los dígitos de la web por separado
        palabras_web = [w for w in canal_norm.split() if w not in STOPWORDS and not w.isdigit()]
        digitos_web = [w for w in canal_norm.split() if w.isdigit()]
        
        if not palabras_web:
            palabras_web = [w for w in canal_norm.split() if w.strip()]
            
        es_bar = "bar" in canal_norm
        matches_encontrados = []
        
        for enc in lista_enlaces:
            nombre_json = enc['name']
            nombre_json_norm = normalizar_cadena(nombre_json)
            
            # Control estricto de canales BAR
            if es_bar != ("bar" in nombre_json_norm):
                continue
                
            palabras_json = [w for w in nombre_json_norm.split() if w not in STOPWORDS and not w.isdigit()]
            digitos_json = [w for w in nombre_json_norm.split() if w.isdigit()]
            
            # Coincidencia inteligente en ambas direcciones (A en B o B en A)
            coincide_palabras = all(p in nombre_json_norm for p in palabras_web) or all(p in canal_norm for p in palabras_json)
            
            # Control estricto de números de canales (ej: Evita que DAZN 1 empareje con DAZN 2)
            coincide_numeros = True
            if digitos_web:
                coincide_numeros = any(d in digitos_json for d in digitos_web)
            
            if coincide_palabras and coincide_numeros:
                acestream_url = f"acestream://{enc['id']}"
                icono = "★" if "**" in nombre_json else "⚡"
                matches_encontrados.append(
                    f'<a href="{acestream_url}" class="btn-canal" title="{nombre_json}">{icono} {nombre_json}</a>'
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
    
    for i in range(len(eventos)):
        eventos[i]['canales_html'] = vincular_canales_automatico(eventos[i]['canales'], enlaces)
        
    eventos_agrupados = {}
    for ev in eventos:
        liga = ev.get('liga', 'Otras Competiciones').strip()
        if liga not in eventos_agrupados:
            eventos_agrupados[liga] = []
        eventos_agrupados[liga].append(ev)
        
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
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
