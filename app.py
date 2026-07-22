import re
import time
import urllib.parse
import requests
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request

from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos

app = Flask(__name__)

# Tus URLs seguras de canales, eventos y lista M3U sin AceStream
URL_ENLACES = 'https://raw.githubusercontent.com/socramtv/Soccer-app/main/hashes.json'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'
URL_NOACE = 'https://raw.githubusercontent.com/socramtv/Soccer-app/refs/heads/main/noace.m3u'

# Sistema de Caché Unificado (30 minutos)
cache_datos = None
ultimo_scraping = 0
CACHE_EXPIRACION = 1800

def normalizar_cadena(texto):
    """Limpia tildes, símbolos, espacios y estandariza nombres para un cruce perfecto"""
    texto = texto.lower().strip()
    texto = texto.replace("m+", "movistar").replace("m. ", "movistar ")
    texto = texto.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    texto = re.sub(r'[\(\)\-\[\]\*\_\|\+\s\.\,\/\:\?\#\§]', '', texto)
    return texto

def extraer_canales_m3u(url_m3u):
    """Descarga tu lista M3U extrayendo el logo (tvg-logo) si existe"""
    canales_lista = []
    dict_m3u = {}
    try:
        respuesta = requests.get(url_m3u, timeout=10)
        if respuesta.status_code == 200:
            lineas = respuesta.text.splitlines()
            nombre_actual = ""
            logo_actual = ""
            for linea in lineas:
                linea = linea.strip()
                if linea.startswith("#EXTINF:"):
                    match_logo = re.search(r'tvg-logo=["\']?(http[^"\', ]+)["\']?', linea, re.IGNORECASE)
                    logo_actual = match_logo.group(1) if match_logo else ""
                    
                    if "," in linea:
                        nombre_actual = linea.split(",", 1)[1].strip()
                elif linea and not linea.startswith("#"):
                    if nombre_actual:
                        url_stream = linea
                        canales_lista.append({
                            'name': nombre_actual,
                            'stream_url': url_stream,
                            'logo': logo_actual
                        })
                        dict_m3u[nombre_actual] = {
                            'url': url_stream,
                            'logo': logo_actual
                        }
                        nombre_actual = ""
                        logo_actual = ""
    except Exception as e:
        print(f"Error cargando lista M3U externa: {e}")
    return canales_lista, dict_m3u

def vincular_canales_automatico(canales_evento, lista_enlaces, dict_m3u_directos):
    """Algoritmo de cruce: Inyecta M3U8 y AceStream leyendo correctamente la clave 'logo' del JSON"""
    html_resultado = ""
    
    def simplificar_canal(texto):
        texto = texto.lower().strip()
        texto = re.sub(r'\(.*?\)', '', texto)
        texto = texto.replace("m+", "movistar").replace("m. ", "movistar ")
        texto = texto.replace("la liga", "laliga").replace("la 1", "la1").replace("la 2", "la2")
        texto = re.sub(r'\b(hd|sd|1080p|720p|4k|1080|720)\b', '', texto)
        texto = re.sub(r'[\-\[\]\*\_\|\+\(\)\.\,\/\:\?\#\§]', ' ', texto)
        palabras = texto.split()
        
        stopwords_ruido = {'tv', 'orange', 'vodafone', 'cat', 'de', 'la', 'el', 'los', 'en', 'y', 'plus', 'dial', 'channel', 'tve', 'play', 'rtve'}
        palabras_limpias = [w for w in palabras if w not in stopwords_ruido]
        
        if "dazn" in palabras_limpias and "mundial" in palabras_limpias:
            if not any(w.isdigit() for w in palabras_limpias):
                palabras_limpias.append("1")
                
        letras = [w for w in palabras_limpias if not w.isdigit()]
        digitos = [w for w in palabras_limpias if w.isdigit()]
        return set(letras), set(digitos)

    for canal in canales_evento:
        canal_limpio = canal.strip()
        canal_norm = normalizar_cadena(canal_limpio)
        matches_encontrados = []

        # 1. BUSCAR EN M3U DINÁMICO (DIRECTOS)
        for nombre_m3u, datos_m3u in dict_m3u_directos.items():
            m3u_norm = normalizar_cadena(nombre_m3u)
            if m3u_norm in canal_norm or canal_norm in m3u_norm:
                url_m3u = datos_m3u['url']
                logo_m3u = datos_m3u['logo']
                
                if logo_m3u:
                    icono_html = f'<img src="{logo_m3u}" class="icono-canal-peq" loading="lazy" onerror="this.outerHTML=\'🔸\'">'
                else:
                    icono_html = "🔸"
                
                url_reproductor = f"/reproductor?url={urllib.parse.quote(url_m3u)}&name={urllib.parse.quote(canal_limpio)}"
                matches_encontrados.append(
                    f'<a href="{url_reproductor}" class="btn-canal" title="{canal_limpio}">{icono_html} {canal_limpio}</a>'
                )

        # 2. BUSCAR EN HASHES ACESTREAM (Leyendo correctamente la clave 'logo')
        web_letras, web_digitos = simplificar_canal(canal_limpio)
        
        if web_letras or web_digitos:
            es_bar = "bar" in canal_limpio.lower() or "bar" in web_letras
            
            for enc in lista_enlaces:
                nombre_json = enc.get('name', '') or enc.get('title', '')
                # AQUÍ LEEMOS EXACTAMENTE EL CAMPO "logo" DE TU JSON
                logo_ace = enc.get('logo', '')
                
                json_letras, json_digitos = simplificar_canal(nombre_json)
                
                json_es_bar = "bar" in nombre_json.lower() or "bar" in json_letras
                if es_bar != json_es_bar:
                    continue
                    
                KEYWORDS_CRITICOS = {'laliga', 'campeones', 'f1', 'motogp', 'mundial', 'deportes', 'vamos', 'tennis', 'golf', 'bar', 'la1', 'la2', 'baloncesto'}
                conflicto_tematico = False
                for kw in KEYWORDS_CRITICOS:
                    if (kw in web_letras) != (kw in json_letras):
                        conflicto_tematico = True
                        break
                if conflicto_tematico:
                    continue
                    
                coincide_letras = web_letras.issubset(json_letras) or json_letras.issubset(web_letras)
                coincide_numeros = (web_digitos == json_digitos)

                if coincide_letras and coincide_numeros:
                    hash_val = enc.get('id', '') or enc.get('hash', '')
                    hash_match = re.search(r'([a-fA-F0-9]{40})', hash_val)
                    if hash_match:
                        hash_puro = hash_match.group(1)
                        stream_url = f"http://127.0.0.1:6878/ace/manifest.m3u8?id={hash_puro}"
                        icono_char = "🔸" if "**" in nombre_json else "🔹"
                        
                        if logo_ace:
                            icono_html = f'<img src="{logo_ace}" class="icono-canal-peq" loading="lazy" onerror="this.outerHTML=\'{icono_char}\'">'
                        else:
                            icono_html = icono_char
                        
                        url_reproductor = f"/reproductor?url={urllib.parse.quote(stream_url)}&name={urllib.parse.quote(nombre_json)}"
                        matches_encontrados.append(
                            f'<a href="{url_reproductor}" class="btn-canal" title="{nombre_json}">{icono_html} {nombre_json}</a>'
                        )
        
        if matches_encontrados:
            html_resultado += "".join(sorted(list(set(matches_encontrados))))
        else:
            html_resultado += f'<span class="canal-texto-vacio">{canal_limpio}</span>'
            
    return html_resultado

def obtener_datos_completos():
    global cache_datos, ultimo_scraping
    ahora = time.time()
    
    if cache_datos and (ahora - ultimo_scraping < CACHE_EXPIRACION):
        return cache_datos
        
    print("🌐 Cargando cartelera unificada por días, M3U dinámico y hashes AceStream...")
    enlaces = extraer_enlaces(URL_ENLACES)
    eventos = extraer_eventos(URL_EVENTOS)
    canales_m3u, dict_m3u = extraer_canales_m3u(URL_NOACE)
    
    destacados = []
    eventos_agrupados = {}
    
    for i in range(len(eventos)):
        eventos[i]['canales_html'] = vincular_canales_automatico(eventos[i]['canales'], enlaces, dict_m3u)
        
        if 'equipo_local' not in eventos[i] or 'equipo_visitante' not in eventos[i]:
            partes = eventos[i]['equipos'].split(' - ')
            eventos[i]['equipo_local'] = partes[0].strip() if len(partes) >= 1 else eventos[i]['equipos']
            eventos[i]['equipo_visitante'] = partes[1].strip() if len(partes) == 2 else ""
            
        if not eventos[i].get('logo_local'):
            eventos[i]['logo_local'] = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23555'><path d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z'/></svg>"
        if not eventos[i].get('logo_visitante'):
            eventos[i]['logo_visitante'] = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23555'><path d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H7c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z'/></svg>"

        # MARCAR SI TIENE ENLACE ACTIVO
        eventos[i]['has_links'] = 'btn-canal' in eventos[i]['canales_html']

        # DETECTAR SI ES PARTIDO DEL SEVILLA O DEL BETIS
        nombre_local_norm = normalizar_cadena(eventos[i]['equipo_local'])
        nombre_vis_norm = normalizar_cadena(eventos[i]['equipo_visitante'])
        
        if "sevilla" in nombre_local_norm or "sevilla" in nombre_vis_norm or "betis" in nombre_local_norm or "betis" in nombre_vis_norm:
            destacados.append(eventos[i])

        # Agrupación cronológica por Día
        fecha = eventos[i].get('fecha', 'Hoy').strip()
        if fecha not in eventos_agrupados:
            eventos_agrupados[fecha] = []
        eventos_agrupados[fecha].append(eventos[i])
        
    cache_datos = {
        'eventos_agrupados': eventos_agrupados,
        'destacados': destacados,
        'canales_puros': enlaces,
        'canales_directos_m3u8': canales_m3u
    }
    ultimo_scraping = ahora
    return cache_datos

@app.route('/')
def home():
    datos = obtener_datos_completos()
    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    
    canales_directos_limpios = []
    for c in datos['canales_puros']:
        hash_val = c.get('id', '') or c.get('hash', '')
        hash_match = re.search(r'([a-fA-F0-9]{40})', hash_val)
        if hash_match:
            hash_puro = hash_match.group(1)
            stream_url = f"http://127.0.0.1:6878/ace/manifest.m3u8?id={hash_puro}"
            nombre_c = c.get('name', '') or c.get('title', '')
            logo_c = c.get('logo', '')
            canales_directos_limpios.append({
                'name': nombre_c,
                'stream_url': stream_url,
                'logo': logo_c
            })
            
    return render_template(
        'index.html', 
        eventos_agrupados=datos['eventos_agrupados'], 
        destacados=datos['destacados'],
        canales_puros=canales_directos_limpios,
        canales_directos=datos['canales_directos_m3u8'],
        fecha=fecha_actual
    )

@app.route('/reproductor')
def reproductor():
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
