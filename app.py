import re
import time
from datetime import datetime
from flask import Flask, render_template, redirect, url_for
import requests

from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos

app = Flask(__name__)

URL_ENLACES = 'https://raw.githubusercontent.com/socramtv/Soccer-app/main/hashes.json'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'

cache_datos = None
ultimo_scraping = 0
CACHE_EXPIRACION = 600

def normalizar_cadena(texto):
    texto = texto.lower().strip()
    texto = texto.replace("m+", "movistar").replace("m. ", "movistar ")
    texto = texto.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    texto = re.sub(r'[\(\)\-\[\]\*\_\|\+]', '', texto)
    return " ".join(texto.split())

def vincular_canales_automatico(canales_evento, lista_enlaces):
    html_resultado = ""
    STOPWORDS = {'hd', 'sd', '1080p', '720p', 'la', 'el', 'los', 'de', 'en', 'ver', 'directo', 'orange', 'tv', 'vodafone', 'movistar', 'plus'}
    
    for canal in canales_evento:
        canal_limpio = canal.strip()
        canal_sin_paren = re.sub(r'\(.*?\)', '', canal_limpio)
        canal_norm = normalizar_cadena(canal_sin_paren)
        
        palabras_web = [w for w in canal_norm.split() if w not in STOPWORDS and not w.isdigit()]
        digitos_web = [w for w in canal_norm.split() if w.isdigit()]
        
        if not palabras_web:
            palabras_web = [w for w in canal_norm.split() if w.strip()]
            
        es_bar = "bar" in canal_norm
        matches_encontrados = []
        
        for enc in lista_enlaces:
            nombre_json = enc['name']
            nombre_json_norm = normalizar_cadena(nombre_json)
            
            if es_bar != ("bar" in nombre_json_norm):
                continue
                
            palabras_json = [w for w in nombre_json_norm.split() if w not in STOPWORDS and not w.isdigit()]
            digitos_json = [w for w in nombre_json_norm.split() if w.isdigit()]
            
            coincide_palabras = all(p in nombre_json_norm for p in palabras_web) or all(p in canal_norm for p in palabras_json)
            coincide_numeros = True
            if digitos_web:
                coincide_numeros = any(d in digitos_json for d in digitos_web)
            
            if coincide_palabras and coincide_numeros:
                # LIMPIEZA AUTOMÁTICA: Extrae solo los 40 caracteres del hash, ignore prefijos
                hash_match = re.search(r'([a-fA-F0-9]{40})', enc['id'])
                if hash_match:
                    hash_puro = hash_match.group(1)
                    stream_url = f"http://127.0.0.1:6878/ace/getstream?id={hash_puro}"
                    icono = "★" if "**" in nombre_json else "⚡"
                    # Transforma el enlace en una acción directa para el reproductor interactivo
                    matches_encontrados.append(
                        f'<button onclick="abrirReproductor(\'{stream_url}\', \'{nombre_json}\')" class="btn-canal" title="{nombre_json}">{icono} {nombre_json}</button>'
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
        
    print("🌐 Cargando cartelera unificada por días...")
    enlaces = extraer_enlaces(URL_ENLACES)
    eventos = extraer_eventos(URL_EVENTOS)
    
    for i in range(len(eventos)):
        eventos[i]['canales_html'] = vincular_canales_automatico(eventos[i]['canales'], enlaces)
        
        if 'equipo_local' not in eventos[i] or 'equipo_visitante' not in eventos[i]:
            partes = eventos[i]['equipos'].split(' - ')
            eventos[i]['equipo_local'] = partes[0].strip() if len(partes) >= 1 else eventos[i]['equipos']
            eventos[i]['equipo_visitante'] = partes[1].strip() if len(partes) == 2 else ""
            
        if not eventos[i].get('logo_local'):
            eventos[i]['logo_local'] = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23555'><path d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z'/></svg>"
        if not eventos[i].get('logo_visitante'):
            eventos[i]['logo_visitante'] = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23555'><path d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z'/></svg>"

    eventos_agrupados = {}
    for ev in eventos:
        fecha = ev.get('fecha', 'Hoy').strip()
        if fecha not in eventos_agrupados:
            eventos_agrupados[fecha] = []
        eventos_agrupados[fecha].append(ev)
        
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
    
    # MEJORA: Limpiar también los hashes de la lista de acceso directo de abajo
    canales_directos_limpios = []
    for c in datos['canales_puros']:
        hash_match = re.search(r'([a-fA-F0-9]{40})', c['id'])
        if hash_match:
            hash_puro = hash_match.group(1)
            stream_url = f"http://127.0.0.1:6878/ace/getstream?id={hash_puro}"
            canales_directos_limpios.append({
                'name': c['name'],
                'stream_url': stream_url
            })
            
    return render_template(
        'index.html', 
        eventos_agrupados=datos['eventos_agrupados'], 
        canales_puros=canales_directos_limpios, 
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
