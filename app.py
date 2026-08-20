import re
import time
import urllib.parse
import requests
import asyncio
import os
import threading
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request

from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos

# --- IMPORTACIÓN DEL BOT DE TELEGRAM ---
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_DISPONIBLE = True
except ImportError:
    TELEGRAM_DISPONIBLE = False

app = Flask(__name__)

# Tus URLs seguras de canales, eventos y lista M3U sin AceStream
URL_ENLACES = 'https://raw.githubusercontent.com/socramtv/Soccer-app/main/hashes.json'
URL_EVENTOS = 'https://www.futbolenlatv.es/deporte'
URL_NOACE = 'https://raw.githubusercontent.com/socramtv/Soccer-app/refs/heads/main/noace.m3u'

# Token de tu Bot de Telegram
TELEGRAM_TOKEN = '8948215840:AAHCbocnBx2Wk4Nq9vPnMrq49V2FHZyO94g'

# ==========================================
# 🤖 CONFIGURACIÓN GLOBAL DEL BOT DE TELEGRAM
# ==========================================
if TELEGRAM_DISPONIBLE:
    application = Application.builder().token(TELEGRAM_TOKEN).updater(None).build()
    bot_loop = asyncio.new_event_loop()

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "⚽ ¡Hola Marco! El bot de Sσcяαм Tν está activo.\n\n"
            "Comandos disponibles:\n"
            "/agenda - Ver partidos de hoy y sus enlaces\n"
            "/m3u - Descargar lista M3U completa"
        )

    async def cmd_m3u(update: Update, context: ContextTypes.DEFAULT_TYPE):
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://soccer-app-qt60.onrender.com")
        url_lista = f"{render_url}/lista.m3u"
        
        teclado = [[InlineKeyboardButton("📥 Descargar Lista M3U", url=url_lista)]]
        reply_markup = InlineKeyboardMarkup(teclado)
        
        await update.message.reply_text(
            "📁 *Tu lista M3U unificada está lista para descargar o usar en tus apps:*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def cmd_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("⏳ Consultando cartelera y enlaces...")
        try:
            datos = obtener_datos_completos()
            fechas_disponibles = list(datos['eventos_agrupados'].keys())
            if not fechas_disponibles:
                await msg.edit_text("❌ No hay eventos disponibles ahora mismo.")
                return

            fecha_hoy = fechas_disponibles[0]
            partidos = datos['eventos_agrupados'][fecha_hoy]
            render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://soccer-app-qt60.onrender.com")
            
            mensaje = f"📅 *AGENDA Sσcяαм Tν* - {fecha_hoy}\n\n"
            contador = 0
            
            for ev in partidos:
                if contador >= 15:
                    mensaje += "\n_(Y bastantes más eventos en la web...)_"
                    break
                
                local = ev.get('equipo_local', '')
                visit = ev.get('equipo_visitante', '')
                partido_txt = f"{local} vs {visit}" if visit else local
                hora = ev.get('hora', '')
                liga = ev.get('liga', '')
                
                tiene_enlace = "🟢" if ev.get('has_links') else "⚪"
                mensaje += f"• `{hora}` {tiene_enlace} *{partido_txt}* ({liga})\n"
                
                canales_html = ev.get('canales_html', '')
                enlaces = re.findall(r'href="/reproductor\?url=([^"&]+)[^>]*>(.*?)</a>', canales_html)
                
                if enlaces:
                    for url_codificada, contenido in enlaces:
                        url_real = urllib.parse.unquote(url_codificada)
                        nombre_canal = re.sub(r'<[^>]+>', '', contenido).replace('🔸', '').replace('🔹', '').strip()
                        mensaje += f"   └ 📺 [{nombre_canal}]({url_real})\n"
                else:
                    mensaje += f"   └ _Sin enlaces activos_\n"
                
                mensaje += "\n"
                contador += 1
            
            teclado = [[InlineKeyboardButton("📥 Descargar Lista M3U Completa", url=f"{render_url}/lista.m3u")]]
            reply_markup = InlineKeyboardMarkup(teclado)
                
            await msg.edit_text(mensaje, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)
        except Exception as e:
            await msg.edit_text(f"⚠️ Error al obtener la agenda: {e}")

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("agenda", cmd_agenda))
    application.add_handler(CommandHandler("m3u", cmd_m3u))

    async def setup_and_run_bot():
        await application.initialize()
        await application.start()
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://soccer-app-qt60.onrender.com")
        webhook_url = f"{render_url}/webhook/{TELEGRAM_TOKEN}"
        await application.bot.set_webhook(url=webhook_url)
        print(f"🔗 Webhook configurado correctamente en: {webhook_url}")

    def run_bot_thread():
        asyncio.set_event_loop(bot_loop)
        bot_loop.run_until_complete(setup_and_run_bot())
        bot_loop.run_forever()

    if not os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        hilo_bot = threading.Thread(target=run_bot_thread, daemon=True)
        hilo_bot.start()


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
    if any(x in texto for x in ["golf", "pga", "masters", "ryder"]): return base_url + "golf.webp"
    # 🤼 MMA / UFC
    if any(x in texto for x in ["ufc", "mma", "bellator"]): return base_url + "mma.webp"
    # 🏍️ Motociclismo
    if any(x in texto for x in ["motogp", "moto2", "moto3", "superbike", "motociclismo"]): return base_url + "motociclismo.webp"
    # 🎾 Pádel
    if any(x in texto for x in ["pádel", "padel", "premier padel", "wpt"]): return base_url + "padel.webp"
    # 🎾 Tenis
    if any(x in texto for x in ["tenis", "atp", "wta", "wimbledon", "garros", "davis"]): return base_url + "tenis.webp"
    
    # ⚽ Por defecto (Si no coincide con nada, será fútbol)
    return base_url + "futbol.webp"

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
    """Algoritmo de cruce: Inyecta M3U8 y AceStream leyendo correctamente la clave 'logo' y detectando infohash o id"""
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

        # 2. BUSCAR EN HASHES ACESTREAM (Leyendo correctamente la clave 'logo' e infohash/id)
        web_letras, web_digitos = simplificar_canal(canal_limpio)
        
        if web_letras or web_digitos:
            es_bar = "bar" in canal_limpio.lower() or "bar" in web_letras
            
            for enc in lista_enlaces:
                nombre_json = enc.get('name', '') or enc.get('title', '')
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
                        
                        # DETECCIÓN INTELIGENTE DE ID vs INFOHASH
                        if "infohash=" in hash_val.lower():
                            stream_url = f"http://127.0.0.1:6878/ace/manifest.m3u8?infohash={hash_puro}"
                        else:
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
        
        # ASIGNAR LOGO DE DEPORTE (AHORA ANALIZA EL EVENTO COMPLETO)
        eventos[i]['logo_deporte'] = asignar_logo_deporte(eventos[i])
        
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


# ==========================================
# RUTAS DE FLASK Y WEBHOOK
# ==========================================
@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    if TELEGRAM_DISPONIBLE:
        try:
            data = request.get_json(force=True)
            update = Update.de_json(data, application.bot)
            asyncio.run_coroutine_threadsafe(application.process_update(update), bot_loop)
        except Exception as e:
            print(f"Error procesando webhook: {e}")
    return 'OK', 200

@app.route('/lista.m3u')
def descargar_lista_m3u():
    datos = obtener_datos_completos()
    
    epg_url = "https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiaiptv.xml"
    m3u_texto = f'#EXTM3U tvg-url="{epg_url}"\n'
    
    ahora_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    logo_update = "https://raw.githubusercontent.com/socramtv/Soccer-app/main/templates/update.png"
    m3u_texto += f'#EXTINF:-1 tvg-logo="{logo_update}" group-logo="{logo_update}" group-title="Actualizada",{ahora_str}\n'
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
                    
                    m3u_texto += f'#EXTINF:-1 tvg-logo="{logo}" group-logo="{logo}" group-title="{liga}",{prefijo_hora}{nombre_partido} ({nombre_canal})\n'
                    m3u_texto += f'{url_real}\n'
                    
    respuesta = app.response_class(m3u_texto, mimetype='audio/x-mpegurl')
    hoy_str = datetime.now().strftime("%d-%m-%Y")
    nombre_archivo = f"SocramTv_Acestream_{hoy_str}.m3u"
    respuesta.headers['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return respuesta

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
            
            # DETECCIÓN INTELIGENTE DE ID vs INFOHASH EN EL BOTÓN DIRECTO
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
