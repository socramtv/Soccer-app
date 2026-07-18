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
        
        # 1. Encontrar todas las filas reales de la tabla principal
        tarjetas = []
        for fila in soup.find_all('tr'):
            if fila.find(class_='hora') or fila.find(class_='detalles'):
                tarjetas.append(fila)

        print(f"🔍 Procesando {len(tarjetas)} filas deportivas con mapeo estructural...")

        dias_semana = ['lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes', 'sábado', 'sabado', 'domingo', 'hoy', 'mañana', 'manana', 'ayer']
        current_fecha = "Hoy"

        # 2. Iterar sobre las filas de forma secuencial
        for el in tarjetas:
            # Capturar cambio de cabecera de día/fecha
            if el.get('class') and 'cabeceraTabla' in el.get('class'):
                texto_fecha = el.text.strip()
                match_f = re.search(r'(\d{2}/\d{2}/\d{4})', texto_fecha)
                if match_f:
                    current_fecha = match_f.group(1)
                else:
                    current_fecha = texto_fecha
                continue

            try:
                hora_el = el.find(class_='hora')
                if not hora_el:
                    continue
                hora = hora_el.text.strip()
                
                # --- EXTRAER COMPETICIÓN / LIGA ---
                liga = "Otros Deportes"
                span_directo = el.select_one('.ajusteDoslineas[title], span.ajusteDoslineas[title]')
                label_el = el.select_one('.detalles label[title]')
                
                if label_el and span_directo:
                    liga = f"{label_el.get('title')} | {span_directo.get('title')}"
                elif span_directo:
                    liga = span_directo.get('title') or span_directo.text.strip()
                elif label_el:
                    liga = label_el.get('title')
                else:
                    comp_interna = el.select_one('.torneo, .competicion')
                    if comp_interna:
                        liga = comp_interna.text.strip()
                
                liga = re.sub(r'\s+', ' ', liga).strip()

                # --- EXTRAER LISTA DE CANALES EN TEXTO ---
                canales = []
                canales_list = el.select('.listaCanales li, .canales li')
                for canal in canales_list:
                    canal_titulo = canal.get('title') or canal.text.strip()
                    if canal_titulo:
                        last_paren = canal_titulo.lastIndexOf(')') if hasattr(canal_titulo, 'lastIndexOf') else canal_titulo.rfind(')')
                        if last_paren != -1:
                            canal_titulo = canal_titulo[:last_paren + 1].strip()
                        if canal_titulo not in canales:
                            canales.append(canal_titulo)

                if not canales:
                    for c_el in el.select('.canal, .tele, .canales, span[class*="canal"]'):
                        c_txt = c_el.text.replace(',', '').strip()
                        if c_txt and len(c_txt) < 40 and c_txt not in canales:
                            canales.append(c_txt)

                # --- CLASIFICACIÓN DE EVENTO (INDIVIDUAL VS ENFRENTAMIENTO) ---
                equipo_local = ""
                equipo_visitante = ""
                logo_local = ""
                logo_visitante = ""

                evento_unico_el = el.select_one('.eventoUnico, .detalles .sinDetalles')
                local_el = el.select_one('.local')
                visitante_el = el.select_one('.visitante')

                if evento_unico_el and not (local_el or visitante_el):
                    # Caso de deportes individuales (F1, Ciclismo, Golf)
                    equipo_local = evento_unico_el.text.strip()
                    equipo_visitante = ""
                elif local_el or visitante_el:
                    # Caso de deportes de enfrentamiento (Fútbol, Baloncesto, Tenis)
                    if local_el:
                        span_l = local_el.find('span')
                        equipo_local = span_l.get('title') if span_l and span_l.get('title') else local_el.text.strip()
                        img_l = local_el.find('img')
                        if img_l and img_l.get('src'):
                            logo_local = base_url + img_l.get('src') if img_l.get('src').startswith('/') else img_l.get('src')
                    
                    if visitante_el:
                        span_v = visitante_el.find('span')
                        equipo_visitante = span_v.get('title') if span_v and span_v.get('title') else visitante_el.text.strip()
                        img_v = visitante_el.find('img')
                        if img_v and img_v.get('src'):
                            logo_visitante = base_url + img_v.get('src') if img_v.get('src').startswith('/') else img_v.get('src')
                else:
                    # Fallback de seguridad basado en texto plano si las clases fallan
                    textos_interiores = [t.strip() for t in el.get_text('\n').split('\n') if t.strip()]
                    lineas_filtradas = [l for l in textos_interiores if l != hora and l != liga and not any(c in l for c in canales)]
                    if len(lineas_filtradas) >= 2:
                        equipo_local = lineas_filtradas[0]
                        equipo_visitante = lineas_filtradas[1]
                    elif len(lineas_filtradas) == 1:
                        equipo_local = lineas_filtradas[0]

                # Si el campo quedó vacío por estructuras complejas, limpiamos la cadena
                if not equipo_local:
                    equipo_local = el.text.replace(hora, "").strip()[:50]

                # --- ASIGNACIÓN DE CATEGORÍA DEPORTIVA PRECISA ---
                deporte = "Otros"
                
                # Buscar imágenes identificadoras del deporte (estructura origen de futbolenlatv)
                for img in el.find_all('img'):
                    src_img = img.get('src', '').lower()
                    alt_img = img.get('alt', '').lower()
                    title_img = img.get('title', '').lower()
                    
                    if any(x in src_img or x in alt_img or x in title_img for x in ['baloncesto', 'basket', 'nba', 'acb']):
                        deporte = "Baloncesto"
                        break
                    if any(x in src_img or x in alt_img or x in title_img for x in ['futbol', 'soccer', 'laliga', 'champions']):
                        deporte = "Fútbol"
                        break
                    if any(x in src_img or x in alt_img or x in title_img for x in ['tennis', 'tenis', 'atp', 'wta', 'itf']):
                        deporte = "Tenis"
                        break
                    if any(x in src_img or x in alt_img or x in title_img for x in ['formula', 'f1', 'automobilismo', 'gp', 'g.p.', 'motor', 'indy']):
                        deporte = "Motor"
                        break
                    if any(x in src_img or x in alt_img or x in title_img for x in ['ciclismo', 'tour', 'bike', 'ruta']):
                        deporte = "Ciclismo"
                        break

                # Mapeo secundario basado en texto si no hay imágenes descriptoras de disciplina
                if deporte == "Otros":
                    texto_analisis = (liga + " " + equipo_local + " " + equipo_visitante).lower()
                    if any(x in texto_analisis for x in ['futbol', 'balón', 'amistoso', 'copa mundial', 'girona', 'betis', 'valencia', 'cadiz']):
                        deporte = "Fútbol"
                    elif any(x in texto_analisis for x in ['baloncesto', 'basket', 'fiba', 'nba', 'summer league']):
                        deporte = "Baloncesto"
                    elif any(x in texto_analisis for x in ['tenis', 'tennis', 'atp', 'wta', 'itf', 'gstaad', 'bastad', 'iasi', 'badosa', 'rublev']):
                        deporte = "Tenis"
                    elif any(x in texto_analisis for x in ['fórmula', 'formula', 'f1', 'gp bélgica', 'spa', 'indycar', 'nashville', 'f3', 'f2']):
                        deporte = "Motor"
                    elif any(x in texto_analisis for x in ['ciclismo', 'tour de francia', 'etapa', 'km', 'markstein', 'belfort']):
                        deporte = "Ciclismo"

                equipo_local = re.sub(r'\s+', ' ', equipo_local).strip()
                equipo_visitante = re.sub(r'\s+', ' ', equipo_visitante).strip()

                if equipo_local and equipo_local != equipo_visitante:
                    eventos.append({
                        'hora': hora,
                        'fecha': current_fecha,
                        'liga': liga,
                        'deporte': deporte,
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

        # Eliminar duplicaciones idénticas en la lista final
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
