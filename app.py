import re
import time
import urllib.parse
import requests
import asyncio
import os
import traceback
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request

from funciones.get_links import extraer_enlaces
from funciones.get_events import extraer_eventos

# --- IMPORTACIÓN CORRECTA DE TELEGRAM Y BOTONES ---
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
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

# Token de tu Bot de Telegram (Oculto en las variables de entorno de Render)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

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
        if limpio_a in
