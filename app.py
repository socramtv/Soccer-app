import re
import time
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request

from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos

app = Flask(__name__)

# Tus URLs seguras de canales y eventos
URL_ENLACES = 'https://raw.githubusercontent.com/socramtv/Soccer-app/main/hashes.json'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'

# Sistema de Caché Unificado (10 minutos)
cache_datos = None
ultimo_scraping = 0
CACHE_EXPIRACION = 600

def normalizar_cadena(texto):
    """Limpia tildes, símbolos y estandariza nombres de canales para cruzarlos"""
    texto = texto.lower().strip()
    texto = texto.replace("m+", "movistar").replace("m. ", "movistar ")
    texto = texto.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    texto = re.sub(r'[\(\)\-\[\]\*\_\|\+]', '', texto)
    return " ".join(texto.split())

def vincular_canales_automatico(canales_evento, lista_enlaces):
    """Algoritmo de cruce avanzado por descomposición de tokens y exclusión de categorías"""
    html_resultado = ""
    
    def simplificar_canal(texto):
        """Limpia el canal aislando sus palabras clave reales de los números y del ruido"""
        texto = texto.lower().strip()
        # Estandarizar cadenas comunes para que coincidan sin importar cómo estén escritas
        texto = texto.replace("m+", "movistar").replace("m. ", "movistar ")
        texto = texto.replace("la liga", "laliga").replace("la liga", "laliga")
        
        # Eliminar contenido entre paréntesis por completo
        texto = re.sub(r'\(.*?\)', '', texto)
        # Convertir todos los símbolos extraños en espacios limpios
        texto = re.sub(r'[\-\[\]\*\_\|\+\(\)\.\,\/\:\?]', ' ', texto)
        
        palabras = texto.split()
        # Ruido puro que no aporta valor al nombre del canal
        stopwords_ruido = {'hd', 'sd', '1080p', '720p', 'el', 'los', 'de', 'en', 'ver', 'directo', 'orange', 'tv', 'vodafone', 'plus', 'dial', 'channel'}
        palabras_limpias = [w for w in palabras if w not in stopwords_ruido]
        
        # Separamos las letras de los números identificadores de diales/canales
        letras = [w for w in palabras_limpias if not w.isdigit()]
        digitos = [w for w in palabras_limpias if w.isdigit()]
        return letras, digitos

    for canal in canales_evento:
        canal_limpio = canal.strip()
        web_letras, web_digitos = simplificar_canal(canal_limpio)
        
        # Si la celda está vacía o no tiene texto legible, la saltamos
        if not web_letras and not web_digitos:
            html_resultado += f'<span class="canal-texto-vacio">{canal_limpio}</span>'
            continue
            
        es_bar = "bar" in canal_limpio.lower()
        matches_encontrados = []
        
        for enc in lista_enlaces:
            nombre_json = enc['name']
            json_letras, json_digitos = simplificar_canal(nombre_json)
            
            # 1. Filtro estricto para canales BAR
            if es_bar != ("bar" in json_letras or "bar" in nombre_json.lower()):
                continue
                
            # 2. Control de palabras clave críticas (Evita que DAZN 1 sintonice DAZN LaLiga o DAZN F1)
            KEYWORDS_CRITICOS = {'laliga', 'campeones', 'f1', 'motogp', 'mundial', 'deportes', 'vamos', 'tennis', 'golf', 'bar', 'la1', 'la2'}
            conflicto_detectado = False
            for kw in KEYWORDS_CRITICOS:
                if (kw in web_letras) != (kw in json_letras):
                    conflicto_detectado = True
                    break
            if conflicto_detectado:
                continue
                
            # 3. Comprobar coincidencia de marcas (ej: 'movistar', 'dazn', 'eurosport'...)
            coincide_letras = all(w in json_letras for w in web_letras) or all(w in web_letras for w in json_letras)
            
            # 4. Control estricto de números de canales (ej: Multi-canales o diales diferentes)
            coincide_numeros = True
            if web_digitos:
                coincide_numeros = any(d in json_digitos for d in web_digitos)

            if coincide_letras and coincide_numeros:
                hash_match = re.search(r'([a-fA-F0-9]{40})', enc['id'])
                if hash_match:
                    hash_puro = hash_match.group(1)
                    stream_url = f"http://127.0.0.1:6878/ace/manifest.m3u8?id={hash_puro}"
                    icono = "★" if "**" in nombre_json else "⚡"
                    matches_encontrados.append(
                        f'<a href="/reproductor?url={stream_url}&name={nombre_json}" class="btn-canal" title="{nombre_json}">{icono} {nombre_json}</a>'
                    )
        
        if matches_encontrados:
            # Eliminamos duplicados y ordenamos alfabéticamente los botones resultantes
            html_resultado += "".join(sorted(list(set(matches_encontrados))))
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

    # Agrupamos única y exclusivamente por FECHA
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
    
    # Limpieza automática de la lista inferior de accesos directos
    canales_directos_limpios = []
    for c in datos['canales_puros']:
        hash_match = re.search(r'([a-fA-F0-9]{40})', c['id'])
        if hash_match:
            hash_puro = hash_match.group(1)
            stream_url = f"http://127.0.0.1:6878/ace/manifest.m3u8?id={hash_puro}"
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

@app.route('/reproductor')
def reproductor():
    """Carga de forma nativa e independiente el reproductor.html"""
    stream_url = request.args.get('url', '')
    canal_name = request.args.get('name', 'Canal Deportivo')
    return render_template('reproductor.html', stream_url=stream_url, canal_name=canal_name)

@app.route('/recargar')
def recargar():
    global cache_datos, ultimo_scraping
    cache_datos = None
    ultimo_scraping = 0
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
