import requests
from bs4 import BeautifulSoup
import re

def extraer_eventos(url_eventos):
    eventos = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        
        print(f"📡 Descargando cartelera de partidos desde: {url_eventos}")
        respuesta = requests.get(url_eventos, headers=headers, timeout=15)
        
        if respuesta.status_code != 200:
            print(f"⚠️ Error al acceder a la web de eventos: Código {respuesta.status_code}")
            return []

        soup = BeautifulSoup(respuesta.text, 'html.parser')
        base_url = "https://www.futbolenlatv.es"
        
        # 1. Encontrar todos los bloques de las filas que contienen horas reales (hh:mm)
        elementos_hora = []
        for el in soup.find_all(['td', 'div', 'span', 'p', 'time', 'b']):
            texto = el.text.strip()
            if re.match(r'^\s*\d{2}:\d{2}\s*$', texto):
                elementos_hora.append(el)
        
        tarjetas = []
        vistos = set()
        for el_hora in elementos_hora:
            fila = el_hora.find_parent(['tr', 'div', 'li'])
            if fila and fila not in vistos and len(fila.text) < 1200:
                tarjetas.append(fila)
                vistos.add(fila)

        print(f"🔍 Procesando {len(tarjetas)} encuentros con algoritmo adaptativo...")

        dias_semana = ['lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes', 'sábado', 'sabado', 'domingo', 'hoy', 'mañana', 'manana', 'ayer']
        current_fecha = "Hoy"
        current_global_liga = "Otros Deportes"

        # 2. Recorrer de arriba a abajo para capturar la fecha y liga estructural
        for el in soup.find_all(['h2', 'h3', 'h4', 'div', 'tr', 'p']):
            txt = el.text.strip()
            clases = "".join(el.get('class', [])).lower() if el.get('class') else ""
            
            # Capturar Fecha de las barras de día principales
            contiene_dia = any(d in txt.lower() for d in dias_semana)
            es_clase_fecha = any(x in clases for x in ['fecha', 'date', 'day', 'thead', 'fecha-cabecera'])
            contiene_mes = any(m in txt.lower() for m in ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'])
            
            if (contiene_dia or es_clase_fecha or contiene_mes) and len(txt) < 100 and " - " not in txt and not re.search(r'\b\d{2}:\d{2}\b', txt):
                current_fecha = re.sub(r'\s+', ' ', el.text).strip()
                continue
                
            # Capturar Liga de las sub-barras de competición
            if any(x in clases for x in ['torneo', 'liga', 'competicion', 'titulo-liga']) and len(txt) < 100 and " - " not in txt:
                current_global_liga = txt
                continue
                
            if el in tarjetas:
                tarjetas.remove(el)
                try:
                    hora_match = re.search(r'\d{2}:\d{2}', el.text)
                    hora = hora_match.group(0) if hora_match else "00:00"
                    
                    # --- EXTRAER LISTA DE CANALES EN TEXTO ---
                    canales = []
                    for a in el.find_all('a'):
                        txt_a = a.text.strip()
                        if not txt_a and a.find('img'):
                            txt_a = a.find('img').get('alt', '').strip() or a.find('img').get('title', '').strip()
                        if txt_a and len(txt_a) < 50 and not any(x in txt_a.lower() for x in ['vs', 'torneo', 'itf', 'atp', 'wta']):
                            txt_a = txt_a.rstrip(',').strip()
                            if txt_a and txt_a not in canales:
                                canales.append(txt_a)
                                
                    if not canales:
                        for c_el in el.select('.canal, .tele, .canales, span[class*="canal"]'):
                            c_txt = c_el.text.replace(',', '').strip()
                            if c_txt and len(c_txt) < 40 and c_txt not in canales:
                                canales.append(c_txt)

                    # --- DETERMINAR LA COMPETICIÓN/LIGA DE ESTA FILA ---
                    liga = current_global_liga
                    liga_interna = el.select_one('h3, h4, h5, .torneo, .competicion, .titulo-torneo')
                    if liga_interna and len(liga_interna.text.strip()) < 80 and not any(x in liga_interna.text.lower() for x in ['vs', '-', 'canal']):
                        liga = liga_interna.text.strip()
                    liga = re.sub(r'\s+', ' ', liga).strip()

                    # --- SEPARAR LÍNEAS DE TEXTO PARA EXTRAER ENCUENTROS ---
                    lineas_raw = [l.strip() for l in el.get_text('\n').split('\n') if l.strip()]
                    
                    # Palabras clave de categorías, torneos o fases que NUNCA son nombres de equipos o jugadores
                    keywords_competicion = {
                        'torneo', 'liga', 'campeonato', 'copa', 'championship', 'grand prix', 'prix', 'tour', 'atp', 'wta', 'itf', 
                        'fórmula', 'formula', 'g.p.', 'gp', 'etapa', 'sesión', 'sesion', 'clasificación', 'clasificacion', 
                        'nations', 'europeo', 'mundial', 'jornada', 'friendly', 'amistoso', 'premier padel', 'open', 
                        'sub-20', 'sub-17', 'femenino', 'masculino', 'semifinal', 'cuartos', 'final', '3er puesto', 
                        'canal por confirmar', 'vitoria-gasteiz', 'gstaad', 'bastad', 'pozoblanco', 'ecuador', 'uruguay'
                    }
                    
                    lineas_equipos = []
                    for linea in lineas_raw:
                        linea_lower = linea.lower()
                        if linea == hora or linea_lower == liga.lower():
                            continue
                        if any(c.lower() in linea_lower for c in canales):
                            continue
                        if any(kw in linea_lower for kw in keywords_competicion):
                            continue
                        if len(linea) > 50:
                            continue
                        if linea not in lineas_equipos:
                            lineas_equipos.append(linea)

                    # --- CLASIFICACIÓN FINAL DEL EVENTO (VERSUS VS INDIVIDUAL) ---
                    equipo_local = ""
                    equipo_visitante = ""
                    
                    if len(lineas_equipos) >= 2:
                        equipo_local = lineas_equipos[0]
                        equipo_visitante = lineas_equipos[1]
                    else:
                        detalles_evento = []
                        for l in lineas_raw:
                            if l != hora and not any(c.lower() in l.lower() for c in canales) and len(l) < 60:
                                if l not in detalles_evento:
                                    detalles_evento.append(l)
                        equipo_local = " - ".join(detalles_evento)
                        equipo_visitante = ""

                    # --- EXTRACCIÓN QUIRÚRGICA DE ESCUDOS/BANDERAS REALES ---
                    logo_local = ""
                    logo_visitante = ""

                    # Buscamos de manera exacta dentro de los contenedores .local y .visitante
                    local_el = el.select_one('.local')
                    if local_el:
                        img_l = local_el.find('img')
                        if img_l and img_l.get('src'):
                            src_l = img_l.get('src')
                            logo_local = base_url + src_l if src_l.startswith('/') else src_l

                    visitante_el = el.select_one('.visitante')
                    if visitante_el:
                        img_v = visitante_el.find('img')
                        if img_v and img_v.get('src'):
                            src_v = img_v.get('src')
                            logo_visitante = base_url + src_v if src_v.startswith('/') else src_v

                    # Fallback exclusivo para eventos individuales (F1, Carreras) que no usan las clases .local/.visitante
                    if not logo_local:
                        for img in el.find_all('img'):
                            src = img.get('src', '')
                            alt = img.get('alt', '').lower()
                            title = img.get('title', '').lower()
                            
                            # Ignorar por completo si la imagen está dentro del contenedorImgCompeticion
                            es_competicion = any('contenedorimgcompeticion' in "".join(p.get('class', [])).lower() for p in img.parents if p.name != '[document]' and p.get('class'))
                            es_tv = any(x in alt or x in title or x in src.lower() for x in ['canal', 'tv', 'tele', 'logo', 'movistar', 'dazn', 'gol', 'eurosport', 'tve', 'la1', 'la2', 'vodafone', 'orange', 'm+', 'onefootball', 'play', 'youtube', 'confirmar'])
                            
                            if src and not es_competicion and not es_tv:
                                logo_local = base_url + src if src.startswith('/') else src
                                break

                    equipo_local = re.sub(r'\s+', ' ', equipo_local).strip()
                    equipo_visitante = re.sub(r'\s+', ' ', equipo_visitante).strip()

                    if equipo_local and equipo_local != "Equipo Local" and equipo_local != equipo_visitante:
                        eventos.append({
                            'hora': hora,
                            'fecha': current_fecha,
                            'liga': liga if liga else "Otros Deportes",
                            'equipos': f"{equipo_local} - {equipo_visitante}" if equipo_visitante else equipo_local,
                            'equipo_local': equipo_local,
                            'equipo_visitante': equipo_visitante,
                            'logo_local': logo_local,
                            'logo_visitante': logo_visitante,
                            'canales': canales,
                            'canales_html': ""
                        })
                except Exception:
                    continue

        # Eliminar duplicados exactos en la parrilla final
        eventos_unicos = []
        vistos_ev = set()
        for ev in eventos:
            clave = f"{ev['fecha']}-{ev['hora']}-{ev['equipos']}"
            if clave not in vistos_ev:
                eventos_unicos.append(ev)
                vistos_ev.add(clave)

        return eventos_unicos

    except Exception as e:
        print(f"⚠️ Error crítico en el raspado de eventos: {e}")
        return []
