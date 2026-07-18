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
        
        # 1. Localizar los elementos que contienen una hora exacta (ej: 13:30)
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

        print(f"🔍 Procesando {len(tarjetas)} encuentros con algoritmo multi-deporte...")

        dias_semana = ['lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes', 'sábado', 'sabado', 'domingo', 'hoy', 'mañana', 'manana', 'ayer']
        current_fecha = "Hoy"
        current_global_liga = "Otros Deportes"

        # 2. Recorrido del árbol para asignar fechas y ligas de forma precisa
        for el in soup.find_all(['h2', 'h3', 'h4', 'div', 'tr', 'p']):
            txt = el.text.strip()
            clases = "".join(el.get('class', [])).lower() if el.get('class') else ""
            
            # Detectar cabeceras globales de FECHA (Barras azules grandes)
            contiene_dia = any(d in txt.lower() for d in dias_semana)
            es_clase_fecha = any(x in clases for x in ['fecha', 'date', 'day', 'thead', 'fecha-cabecera'])
            contiene_mes = any(m in txt.lower() for m in ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'])
            
            if (contiene_dia or es_clase_fecha or contiene_mes) and len(txt) < 100 and " - " not in txt and not re.search(r'\b\d{2}:\d{2}\b', txt):
                current_fecha = re.sub(r'\s+', ' ', el.text).strip()
                continue
                
            # Detectar cabeceras globales de COMPETICIÓN (Barras grises/moradas de fútbol)
            if any(x in clases for x in ['torneo', 'liga', 'competicion', 'titulo-liga']) and len(txt) < 100 and " - " not in txt:
                current_global_liga = txt
                continue
                
            if el in tarjetas:
                tarjetas.remove(el)
                try:
                    hora_match = re.search(r'\d{2}:\d{2}', el.text)
                    hora = hora_match.group(0) if hora_match else "00:00"
                    
                    # --- EXTRAER EXTRA DE CANALES (Todos los enlaces <a> de la fila) ---
                    canales = []
                    enlaces_tv = el.find_all('a')
                    for a in enlaces_tv:
                        txt_a = a.text.strip()
                        # Si el enlace viene con una imagen de logo en vez de texto
                        if not txt_a and a.find('img'):
                            txt_a = a.find('img').get('alt', '').strip() or a.find('img').get('title', '').strip()
                        
                        if txt_a and len(txt_a) < 50 and not any(x in txt_a.lower() for x in ['vs', 'torneo', 'itf', 'atp', 'wta']):
                            # Limpiar comas residuales que deje la web
                            txt_a = txt_a.rstrip(',').strip()
                            if txt_a and txt_a not in canales:
                                canales.append(txt_a)
                                
                    # Respaldo si los canales vienen en texto plano sin enlace wrapping
                    if not canales:
                        for c_el in el.select('.canal, .tele, .canales, span[class*="canal"]'):
                            c_txt = c_el.text.replace(',', '').strip()
                            if c_txt and len(c_txt) < 40 and c_txt not in canales:
                                canales.append(c_txt)

                    # --- DETECTAR LIGA/TORNEO INTERNO (Caso del Tenis: Torneo de Gstaad) ---
                    liga = current_global_liga
                    liga_interna = el.select_one('h3, h4, h5, .torneo, .competicion, .titulo-torneo')
                    if liga_interna and len(liga_interna.text.strip()) < 80 and not any(x in liga_interna.text.lower() for x in ['vs', '-', 'canal']):
                        liga = liga_interna.text.strip()

                    # --- ALGORITMO QUIRÚRGICO DE EXTRACCIÓN DE EQUIPOS/JUGADORES ---
                    equipo_local = ""
                    equipo_visitante = ""
                    
                    # Obtenemos de forma limpia todas las líneas de texto dentro de la fila del encuentro
                    lineas_cuerpo = [l.strip() for l in el.get_text('\n').split('\n') if l.strip()]
                    
                    # Palabras de control de fases o rondas televisivas que debemos limpiar
                    palabras_descarte = {'semifinal', 'cuartos', 'final', 'atp 250', 'atp 500', 'atp 1000', 'wta', 'itf', 'friendly', 'amistoso', 'fase', 'grupo', '3er puesto', 'canal por confirmar'}
                    
                    lineas_filtradas = []
                    for linea in lineas_cuerpo:
                        linea_lower = linea.lower()
                        # Descartamos la propia hora, la propia liga y los textos de los canales extraídos
                        if linea == hora or linea_lower == liga.lower():
                            continue
                        if any(c.lower() in linea_lower for c in canales):
                            continue
                        if any(d in linea_lower for d in palabras_descarte):
                            continue
                        if len(linea) > 60:
                            continue
                        lineas_filtradas.append(linea)

                    # Si el formato viene apilado línea a línea (Caso Tenis o Marcadores verticales)
                    if len(lineas_filtradas) >= 2:
                        # Los dos bloques principales de texto restantes tras la limpieza son los contendientes
                        equipo_local = lineas_filtradas[0]
                        equipo_visitante = lineas_filtradas[1]
                    # Si viene en formato clásico con guion intermedio
                    elif len(lineas_filtradas) == 1 and " - " in lineas_filtradas[0]:
                        partes = lineas_filtradas[0].split(" - ")
                        equipo_local = partes[0].strip()
                        equipo_visitante = partes[1].strip()
                    else:
                        # Último recurso por clases tradicionales
                        locales_el = el.select_one('.local, .equipo-local, span[class*="local"]')
                        visitantes_el = el.select_one('.visitante, .equipo-visitante, span[class*="visitante"]')
                        if locales_el and visitantes_el:
                            equipo_local = locales_el.text.strip()
                            equipo_visitante =访问antes_el.text.strip()

                    # --- ASIGNACIÓN SECUENCIAL DE ESCUDOS/BANDERAS ---
                    logo_local = ""
                    logo_visitante = ""
                    imagenes_fila = el.find_all('img')
                    escudos_validos = []
                    
                    for img in imagenes_fila:
                        src = img.get('src', '')
                        alt = img.get('alt', '').lower()
                        title = img.get('title', '').lower()
                        
                        # Filtramos las imágenes de canales de TV o logos de ligas
                        es_img_canal = any(x in alt or x in title or x in src.lower() for x in ['canal', 'tv', 'tele', 'logo', 'movistar', 'dazn', 'tve', 'la1', 'la2', 'orange', 'vodafone'])
                        es_img_liga = liga.lower() in alt or liga.lower() in title
                        
                        if src and not es_img_canal and not es_img_liga:
                            if src not in escudos_validos:
                                escudos_validos.append(src)

                    # Mapeamos los dos primeros escudos libres a local y visitante respectivamente
                    if len(escudos_validos) >= 1: logo_local = escudos_validos[0]
                    if len(escudos_validos) >= 2: logo_visitante = escudos_validos[1]

                    # Convertir rutas relativas a absolutas para renderizarlas en tu app
                    if logo_local and logo_local.startswith('/'): logo_local = base_url + logo_local
                    if logo_visitante and logo_visitante.startswith('/'): logo_visitante = base_url + logo_visitante

                    # Formateo y limpieza final de cadenas de texto
                    equipo_local = re.sub(r'\s+', ' ', equipo_local).strip()
                    equipo_visitante = re.sub(r'\s+', ' ', equipo_visitante).strip()
                    liga = re.sub(r'\s+', ' ', liga).strip()

                    # Guardar el evento si ha sido procesado correctamente
                    if equipo_local and equipo_local != "Equipo Local" and equipo_local != equipo_visitante:
                        eventos.append({
                            'hora': hora,
                            'fecha': current_fecha,
                            'liga': liga if liga else "Otros Deportes",
                            'equipos': f"{equipo_local} - {equipo_visitante}",
                            'equipo_local': equipo_local,
                            'equipo_visitante': equipo_visitante,
                            'logo_local': logo_local,
                            'logo_visitante': logo_visitante,
                            'canales': canales,
                            'canales_html': ""
                        })
                except Exception:
                    continue

        # Limpieza de duplicados exactos en la lista final
        eventos_unicos = []
        vistos_ev = set()
        for ev in eventos:
            clave = f"{ev['fecha']}-{ev['hora']}-{ev['equipos']}"
            if clave not in vistos_ev:
                eventos_unicos.append(ev)
                vistos_ev.add(clave)

        print(f"✅ Extracción completada sin errores. {len(eventos_unicos)} eventos listos en parrilla.")
        return eventos_unicos

    except Exception as e:
        print(f"⚠️ Error crítico en el raspado de eventos: {e}")
        return []
