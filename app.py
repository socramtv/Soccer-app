import re
import time
import urllib.parse
import requests
import asyncio
import os
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request

from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos

# --- IMPORTACIÓN Y CONFIGURACIÓN DEL BOT DE TELEGRAM (WEBHOOK) ---
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_DISPONIBLE = True
except ImportError:
    TELEGRAM_DISPONIBLE = False

app = Flask(__name__)

# Zona horaria de España para corregir la diferencia con el servidor en la nube
TIMEZONE_ES = ZoneInfo("Europe/Madrid")

# Tus URLs seguras de canales, eventos y listas
URL_ENLACES = 'https://raw.githubusercontent.com/socramtv/Soccer-app/main/hashes.json'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'
URL_NOACE = 'https://raw.githubusercontent.com/socramtv/Soccer-app/refs/heads/main/noace.m3u'
URL_OTROS_CANALES = 'https://raw.githubusercontent.com/socramtv/Soccer-app/refs/heads/main/hashes_2.txt'

# Token de tu Bot de Telegram
TELEGRAM_TOKEN = '8948215840:AAHCbocnBx2Wk4Nq9vPnMrq49V2FHZyO94g'

# Inicializamos la aplicación de Telegram sin el Updater clásico (gestionado por Flask mediante Webhook)
if TELEGRAM_DISPONIBLE:
    application = Application.builder().token(TELEGRAM_TOKEN).updater(None).build()

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⚽ ¡Hola Marco! El bot de Sσcяαм Tν está activo por Webhook.\n\nEscribe /agenda para consultar los partidos.")

    async def cmd_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("⏳ Consultando cartelera...")
        try:
            datos = obtener_datos_completos()
            fechas_disponibles = list(datos['eventos_agrupados'].keys())
            if not fechas_disponibles:
                await msg.edit_text("❌ No hay eventos disponibles ahora mismo.")
                return

            fecha_hoy = fechas_disponibles[0]
            partidos = datos['eventos_agrupados'][fecha_hoy]
            
            mensaje = f"📅 *AGENDA Sσcяαм Tν* - {fecha_hoy}\n\n"
            contador = 0
            
            for ev in partidos:
                if contador >= 25:
                    mensaje += "\n_(Y más eventos disponibles en la web...)_"
                    break
                
                local = ev.get('equipo_local', '')
                visit = ev.get('equipo_visitante', '')
                partido_txt = f"{local} vs {visit}" if visit else local
                hora = ev.get('hora', '')
                liga = ev.get('liga', '')
                
                tiene_enlace = "🟢" if ev.get('has_links') else "⚪"
                mensaje += f"• `{hora}` {tiene_enlace} *{partido_txt}* ({liga})\n"
                contador += 1
                
            await msg.edit_text(mensaje, parse_mode='Markdown')
        except Exception as e:
            await msg.edit_text(f"⚠️ Error al obtener la agenda: {e}")

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("agenda", cmd_agenda))

    # Configuración automática del Webhook al iniciar en Render
    async def setup_webhook():
        await application.initialize()
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        if render_url:
            webhook_url = f"{render_url}/webhook/{TELEGRAM_TOKEN}"
            await application.bot.set_webhook(url=webhook_url)
            print(f"🔗 Webhook configurado correctamente en: {webhook_url}")

    try:
        asyncio.run(setup_webhook())
    except Exception as e:
        print(f"Aviso en setup_webhook: {e}")

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

def asignar_logo_deporte(evento):
    """Asigna el icono del deporte correcto analizando liga, equipos y los canales con palabras clave ampliadas"""
    texto = f"{evento.get('liga', '')} {evento.get('equipo_local', '')} {evento.get('equipo_visitante', '')} {' '.join(evento.get('canales', []))}".lower()
    
    base_url = "https://raw.githubusercontent.com/socramtv/Soccer-app/refs/heads/main/icon-depor/"
    
    # 🎾 Tenis
    if any(x in texto for x in ["tenis", "tennis", "atp", "wta", "wimbledon", "garros", "davis", "masters 1000", "us open"]): return base_url + "tenis.webp"
    # 🏃 Atletismo
    if any(x in texto for x in ["atletismo", "maratón", "marathon", "diamond league", "mitin", "meeting", "sesión matinal", "sesión vespertina", "pista cubierta", "cross country"]): return base_url + "atletismo.webp"
    # 🏎️ Automovilismo
    if any(x in texto for x in ["f1", "f2", "f3", "fórmula", "automovilismo", "rally", "nascar", "indy", "motorsport", "dtm", "wec", "wrc", "imsa", "le mans", "gt world"]): return base_url + "automovilismo.webp"
    # 🏀 Baloncesto
    if any(x in texto for x in ["baloncesto", "nba", "acb", "euroliga", "euroleague", "fiba"]): return base_url + "baloncesto.webp"
    # 🤾 Balonmano
    if any(x in texto for x in ["balonmano", "asobal", "ehf"]): return base_url + "balonmano.webp"
    # 🥊 Boxeo
    if any(x in texto for x in ["boxeo", "boxing", "velada"]): return base_url + "boxeo.webp"
    # 🚴 Ciclismo
    if any(x in texto for x in ["ciclismo", "tour de", "vuelta a", "giro d"]): return base_url + "ciclismo.webp"
    # 🏈 Fútbol Americano
    if any(x in texto for x in ["nfl", "fútbol americano", "americano", "super bowl"]): return base_url + "futbol-americano.webp"
    # ⚽ Fútbol Sala
    if any(x in texto for x in ["sala", "futsal", "lnfs"]): return base_url + "futbol-sala.webp"
    # ⛳ Golf 
    if any(x in texto for x in ["golf", "pga", "masters de augusta", "ryder"]): return base_url + "golf.webp"
    # 🤼 MMA / UFC
    if any(x in texto for x in ["ufc", "mma", "bellator"]): return base_url + "mma.webp"
    # 🏍️ Motociclismo
    if any(x in texto for x in ["motogp", "moto2", "moto3", "superbike", "motociclismo"]): return base_url + "motociclismo.webp"
    # 🎾 Pádel
    if any(x in texto for x in ["pádel", "padel", "premier padel", "wpt"]): return base_url + "padel.webp"
    
    # ⚽ Por defecto
    return base_url + "futbol.webp"

def extraer_canales_m3u(url_m3u):
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
                        
                        # 🚀 TRANSFORMACIÓN AUTOMÁTICA DE GETSTREAM A MANIFEST.M3U8
                        url_stream = url_stream.replace("/ace/getstream?infohash=", "/ace/manifest.m3u8?infohash=")
                        url_stream = url_stream.replace("/ace/getstream?id=", "/ace/manifest.m3u8?id=")
                        
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

def vincular_canales_automatico(canales_evento, lista_enlaces, dict_m3u_unificado):
    html_resultado = ""
    urls_agregadas = set()
    matches_encontrados = []
    textos_vacios = []
    
    def son_canales_equivalentes(orig_abajo, orig_arriba):
        txt_a = str(orig_abajo).lower()
        txt_b = str(orig_arriba).lower()

        # 0. Bloqueo de Canales Promocionales / Avances
        es_avances_a = any(x in txt_a for x in ['avances', 'promo', 'trailer', 'preview'])
        es_avances_b = any(x in txt_b for x in ['avances', 'promo', 'trailer', 'preview'])
        if es_avances_a != es_avances_b:
            return False

        # 1. Bloqueo DAZN vs Movistar
        if ('dazn' in txt_a) != ('dazn' in txt_b): return False
        
        # 2. Bloqueo Hipermotion
        es_hyper_a = 'hipermotion' in txt_a or 'hypermotion' in txt_a
        es_hyper_b = 'hipermotion' in txt_b or 'hypermotion' in txt_b
        if es_hyper_a != es_hyper_b: return False

        # 3. Bloqueo numérico (Caza perfectamente los M2, M3, BAR 2, etc.)
        txt_a_sin_res = re.sub(r'1080p?|720p?|4k|fhd|hd', '', txt_a)
        txt_b_sin_res = re.sub(r'1080p?|720p?|4k|fhd|hd', '', txt_b)
        
        for i in range(2, 10):
            regex = r'(?:^|\D)' + str(i) + r'(?:\D|$)'
            tiene_num_a = bool(re.search(regex, txt_a_sin_res))
            tiene_num_b = bool(re.search(regex, txt_b_sin_res))
            if tiene_num_a != tiene_num_b:
                return False

        # 4. Limpieza base para textos
        limpio_a = re.sub(r'[^a-z0-9]', '', txt_a_sin_res)
        limpio_b = re.sub(r'[^a-z0-9]', '', txt_b_sin_res)

        if len(limpio_a) < 3 or len(limpio_b) < 3: return False

        # 🔥 PROTECCIÓN MOVISTAR+ GENÉRICO
        if limpio_b == "movistar" or limpio_b == "movistarplus":
            if "laliga" in limpio_a or "campeones" in limpio_a or "deportes" in limpio_a or "golf" in limpio_a:
                return False
            if limpio_a == "movistar" or limpio_a == "movistarplus" or limpio_a == "movistarplus1080":
                return True
            return False

        # 🔥 PROTECCIÓN LALIGA TV vs MOVISTAR LALIGA
        es_laligatv_a = 'laligatv' in limpio_a or 'bar' in limpio_a
        es_laligatv_b = 'laligatv' in limpio_b or 'bar' in limpio_b
        
        es_movistarlaliga_a = 'movistarlaliga' in limpio_a or 'mlaliga' in limpio_a
        es_movistarlaliga_b = 'movistarlaliga' in limpio_b or 'mlaliga' in limpio_b
        
        if (es_laligatv_a and es_movistarlaliga_b) or (es_laligatv_b and es_movistarlaliga_a):
            return False

        # Coincidencia base
        if limpio_a in limpio_b or limpio_b in limpio_a: return True

        # Sinónimos si logran pasar los candados
        if ('laliga' in limpio_a or 'movistarlaliga' in limpio_a) and ('laliga' in limpio_b or 'laligatv' in limpio_b):
            return True
        if 'campeones' in limpio_a and 'campeones' in limpio_b: return True
        if 'vamos' in limpio_a and 'vamos' in limpio_b: return True

        return False

    for canal in canales_evento:
        canal_limpio = canal.strip()
        encontro_algo = False

        for nombre_m3u, datos_m3u in dict_m3u_unificado.items():
            if son_canales_equivalentes(nombre_m3u, canal_limpio):
                encontro_algo = True
                url_m3u = datos_m3u['url']
                if url_m3u not in urls_agregadas:
                    logo_m3u = datos_m3u['logo']
                    icono_html = f'<img src="{logo_m3u}" class="icono-canal-peq" loading="lazy" onerror="this.outerHTML=\'🔸\'">' if logo_m3u else "🔸"
                    url_reproductor = f"/reproductor?url={urllib.parse.quote(url_m3u)}&name={urllib.parse.quote(nombre_m3u)}"
                    
                    matches_encontrados.append(f'<a href="{url_reproductor}" class="btn-canal" title="{nombre_m3u}">{icono_html} {nombre_m3u}</a>')
                    urls_agregadas.add(url_m3u)

        for enc in lista_enlaces:
            nombre_json = enc.get('name', '') or enc.get('title', '')
            if son_canales_equivalentes(nombre_json, canal_limpio):
                encontro_algo = True
                hash_val = enc.get('id', '') or enc.get('hash', '')
                hash_match = re.search(r'([a-fA-F0-9]{40})', hash_val)
                if hash_match:
                    hash_puro = hash_match.group(1)
                    if "infohash=" in hash_val.lower():
                        stream_url = f"http://127.0.0.1:6878/ace/manifest.m3u8?infohash={hash_puro}"
                    else:
                        stream_url = f"http://127.0.0.1:6878/ace/manifest.m3u8?id={hash_puro}"
                        
                    if stream_url not in urls_agregadas:
                        logo_ace = enc.get('logo', '')
                        icono_char = "🔸" if "**" in nombre_json else "🔹"
                        icono_html = f'<img src="{logo_ace}" class="icono-canal-peq" loading="lazy" onerror="this.outerHTML=\'{icono_char}\'">' if logo_ace else icono_char
                        url_reproductor = f"/reproductor?url={urllib.parse.quote(stream_url)}&name={urllib.parse.quote(nombre_json)}"
                        
                        matches_encontrados.append(f'<a href="{url_reproductor}" class="btn-canal" title="{nombre_json}">{icono_html} {nombre_json}</a>')
                        urls_agregadas.add(stream_url)
        
        if not encontro_algo:
            textos_vacios.append(canal_limpio)
            
    html_resultado = "".join(sorted(matches_encontrados))
    for vacio in set(textos_vacios):
        html_resultado += f'<span class="canal-texto-vacio">{vacio}</span>'
        
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
    otros_canales, dict_otros = extraer_canales_m3u(URL_OTROS_CANALES)
    
    dict_m3u_unificado = {**dict_m3u, **dict_otros}
    
    destacados = []
    eventos_agrupados = {}
    
    ahora_dt = datetime.now(TIMEZONE_ES)
    limite_tiempo = ahora_dt - timedelta(hours=2)
    str_slash = ahora_dt.strftime("%d/%m")
    str_dash = ahora_dt.strftime("%d-%m")
    
    for i in range(len(eventos)):
        fecha_texto = eventos[i].get('fecha', 'Hoy').strip().lower()
        es_hoy = "hoy" in fecha_texto or str_slash in fecha_texto or str_dash in fecha_texto
        
        if es_hoy:
            hora_ev = eventos[i].get('hora', '00:00')
            try:
                h_partes = hora_ev.split(':')
                if len(h_partes) >= 2:
                    hora_ev_int = int(h_partes[0])
                    min_ev_int = int(h_partes[1])
                    ev_dt = ahora_dt.replace(hour=hora_ev_int, minute=min_ev_int, second=0, microsecond=0)
                    
                    if ev_dt < limite_tiempo:
                        continue
            except Exception:
                pass

        eventos[i]['canales_html'] = vincular_canales_automatico(eventos[i]['canales'], enlaces, dict_m3u_unificado)
        eventos[i]['logo_deporte'] = asignar_logo_deporte(eventos[i])
        
        if 'equipo_local' not in eventos[i] or 'equipo_visitante' not in eventos[i]:
            partes = eventos[i]['equipos'].split(' - ')
            eventos[i]['equipo_local'] = partes[0].strip() if len(partes) >= 1 else eventos[i]['equipos']
            eventos[i]['equipo_visitante'] = partes[1].strip() if len(partes) == 2 else ""
            
        if not eventos[i].get('logo_local'):
            eventos[i]['logo_local'] = ""
        if not eventos[i].get('logo_visitante'):
            eventos[i]['logo_visitante'] = ""

        eventos[i]['has_links'] = 'btn-canal' in eventos[i]['canales_html']

        nombre_local_norm = normalizar_cadena(eventos[i]['equipo_local'])
        nombre_vis_norm = normalizar_cadena(eventos[i]['equipo_visitante'])
        
        if "sevilla" in nombre_local_norm or "sevilla" in nombre_vis_norm or "betis" in nombre_local_norm or "betis" in nombre_vis_norm:
            destacados.append(eventos[i])

        fecha = eventos[i].get('fecha', 'Hoy').strip()
        if fecha not in eventos_agrupados:
            eventos_agrupados[fecha] = []
        eventos_agrupados[fecha].append(eventos[i])
        
    cache_datos = {
        'eventos_agrupados': eventos_agrupados,
        'destacados': destacados,
        'canales_puros': enlaces,
        'canales_directos_m3u8': canales_m3u,
        'otros_canales': otros_canales
    }
    ultimo_scraping = ahora
    return cache_datos


# ==========================================
# RUTA WEBHOOK DE TELEGRAM
# ==========================================
@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    if TELEGRAM_DISPONIBLE:
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, application.bot)
        
        async def process():
            await application.process_update(update)
            
        asyncio.run(process())
    return 'OK', 200


# ==========================================
# RUTAS DE FLASK (LA WEB)
# ==========================================
@app.route('/lista.m3u')
def descargar_lista_m3u():
    datos = obtener_datos_completos()
    
    epg_url = "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiaiptv.xml"
    m3u_texto = f'#EXTM3U tvg-url="{epg_url}"\n'
    
    ahora_esp = datetime.now(TIMEZONE_ES)
    ahora_str = ahora_esp.strftime("%d/%m/%Y %H:%M")
    logo_update = "https://raw.githubusercontent.com/socramtv/Soccer-app/main/templates/update.png"
    m3u_texto += f'#EXTINF:-1 tvg-logo="{logo_update}" group-logo="{logo_update}" group-tag="{logo_update}" group-title="Actualizada",{ahora_str}\n'
    m3u_texto += 'http://update.local\n'
    
    for fecha, eventos in datos['eventos_agrupados'].items():
        for evento in eventos:
            if evento.get('has_links'):
                local = evento.get('equipo_local', '')
                visit = evento.get('equipo_visitante', '')
                nombre_partido = f"{local} vs {visit}" if visit else local
                liga = evento.get('liga', 'Otros Deportes')
                logo = evento.get('logo_deporte', '')
                
                hora = evento.get('hora', '')
                prefijo_hora = f"⏰ {hora} - " if hora else ""
                
                canales_html = evento.get('canales_html', '')
                enlaces = re.findall(r'href="/reproductor\?url=([^"&]+)[^>]*>(.*?)</a>', canales_html)
                
                for url_codificada, contenido in enlaces:
                    url_real = urllib.parse.unquote(url_codificada)
                    nombre_canal = re.sub(r'<[^>]+>', '', contenido).replace('🔸', '').replace('🔹', '').strip()
                    
                    m3u_texto += f'#EXTINF:-1 tvg-logo="{logo}" group-logo="{logo}" group-tag="{logo}" group-title="{liga}",{prefijo_hora}{nombre_partido} ({nombre_canal})\n'
                    m3u_texto += f'{url_real}\n'
                    
    respuesta = app.response_class(m3u_texto, mimetype='audio/x-mpegurl')
    hoy_str = ahora_esp.strftime("%d-%m-%Y")
    nombre_archivo = f"SocramTv_Acestream_{hoy_str}.m3u"
    respuesta.headers['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return respuesta


@app.route('/')
def home():
    datos = obtener_datos_completos()
    fecha_actual = datetime.now(TIMEZONE_ES).strftime("%d-%m-%Y")
    
    canales_directos_limpios = []
    for c in datos['canales_puros']:
        hash_val = c.get('id', '') or c.get('hash', '')
        hash_match = re.search(r'([a-fA-F0-9]{40})', hash_val)
        if hash_match:
            hash_puro = hash_match.group(1)
            
            if "infohash=" in hash_val.lower():
                stream_url = f"http://127.0.0.1:6878/ace/manifest.m3u8?infohash={hash_puro}"
            else:
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
        otros_canales=datos['otros_canales'],
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
