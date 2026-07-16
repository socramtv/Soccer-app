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
        
        # PASO 1: Localizar los elementos que contienen una hora exacta (ej: 18:30)
        elementos_hora = []
        for el in soup.find_all(['td', 'div', 'span', 'p', 'time', 'b']):
            texto = el.text.strip()
            if re.match(r'^\s*\d{2}:\d{2}\s*$', texto):
                elementos_hora.append(el)
        
        tarjetas = []
        vistos = set()
        for el_hora in elementos_hora:
            # Buscamos el contenedor de la fila lo más específico posible (un tr o un div partido)
            fila = el_hora.find_parent(lambda tag: tag.name == 'tr' or (tag.name == 'div' and tag.get('class') and any('partido' in c.lower() for c in tag.get('class'))))
            if not fila:
                fila = el_hora.find_parent(['tr', 'div', 'li'])
                
            if fila and fila not in vistos and len(fila.text) < 1000:
                tarjetas.append(fila)
                vistos.add(fila)

        print(f"🔍 Detectadas {len(tarjetas)} filas individuales de partidos. Analizando procedencias...")

        dias_semana = ['lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes', 'sábado', 'sabado', 'domingo', 'hoy', 'mañana', 'manana', 'ayer']

        # PASO 2: Procesar cada partido de forma totalmente AISLADA
        for tarjeta in tarjetas:
            try:
                hora_match = re.search(r'\d{2}:\d{2}', tarjeta.text)
                hora = hora_match.group(0) if hora_match else "00:00"
                
                # Cada partido nace con sus valores limpios por defecto
                fecha = "Hoy"
                liga = "Otros Deportes"
                
                found_fecha = False
                found_liga = False
                
                # ALGORITMO GENEALÓGICO: Subimos por la cadena de padres del partido
                for ancestro in [tarjeta] + list(tarjeta.parents):
                    if ancestro.name == '[document]':
                        continue
                        
                    # Revisamos los hermanos que tiene este padre justo por encima (de cerca a lejos)
                    for hermano in ancestro.find_previous_siblings():
                        txt_h = hermano.text.strip()
                        txt_h_lower = txt_h.lower()
                        clases_h = "".join(hermano.get('class', [])).lower() if hermano.get('class') else ""
                        
                        # A. ¿Este hermano de arriba es una cabecera de FECHA?
                        contiene_dia = any(d in txt_h_lower for d in dias_semana)
                        es_clase_fecha = any(x in clases_h for x in ['fecha', 'date', 'day', 'thead', 'fecha-cabecera'])
                        contiene_mes = any(m in txt_h_lower for m in ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'])
                        
                        if not found_fecha and (contiene_dia or es_clase_fecha or contiene_mes) and len(txt_h) < 100 and " - " not in txt_h and not re.search(r'\b\d{2}:\d{2}\b', txt_h):
                            fecha = re.sub(r'\s+', ' ', hermano.text).strip()
                            found_fecha = True
                            
                        # B. ¿Este hermano de arriba es una cabecera de COMPETICIÓN / DEPORTE?
                        tiene_clase_liga = any(x in clases_h for x in ['torneo', 'liga', 'competicion', 'copete', 'deporte', 'deportes', 'titulo', 'head', 'cabecera', 'categoria', 'sport', 'sport-title'])
                        es_h_deporte = hermano.name in ['h2', 'h3', 'h4']
                        
                        if not found_liga and (tiene_clase_liga or es_h_deporte) and len(txt_h) < 100 and " - " not in txt_h and not re.search(r'\b\d{2}:\d{2}\b', txt_h) and txt_h != fecha:
                            img_torneo = hermano.find('img')
                            if img_torneo and img_torneo.get('alt'):
                                liga = img_torneo.get('alt', '').strip()
                            else:
                                liga = txt_h
                            liga = re.sub(r'\s+', ' ', liga).strip()
                            found_liga = True
                            
                        # Si en este nivel ya tenemos ambos, dejamos de mirar hermanos
                        if found_fecha and found_liga:
                            break
                    
                    # Si ya hemos encontrado su Deporte y su Día, no seguimos subiendo a más padres
                    if found_fecha and found_liga:
                        break
                
                # 3. Extraer nombres de equipos, escudos y canales de la fila
                equipo_local = "Equipo Local"
                equipo_visitante = "Equipo Visitante"
                logo_local = ""
                logo_visitante = ""
                canales = []

                tds = tarjeta.find_all('td') if tarjeta.name == 'tr' else []
                locales_el = tarjeta.select_one('.local, .equipo-local, span[class*="local"]')
                visitantes_el = tarjeta.select_one('.visitante, .equipo-visitante, span[class*="visitante"]')
                
                if locales_el and visitantes_el:
                    equipo_local = locales_el.text.strip()
                    equipo_visitante = visitantes_el.text.strip()
                    img_l = locales_el.find('img')
                    img_v = visitantes_el.find('img')
                    if img_l: logo_local = img_l.get('src', '')
                    if img_v: logo_visitante = img_v.get('src', '')
                elif len(tds) >= 2:
                    for td in tds:
                        txt_td = td.text.strip()
                        if " - " in txt_td and len(txt_td) < 120 and ":" not in txt_td:
                            partes = txt_td.split(" - ")
                            equipo_local = partes[0].strip()
                            equipo_visitante = partes[1].strip()
                            imgs = td.find_all('img')
                            if len(imgs) >= 2:
                                logo_local = imgs[0].get('src', '')
                                logo_visitante = imgs[1].get('src', '')
                            break
                
                if equipo_local == "Equipo Local" or not equipo_visitante:
                    texto_cuerpo = tarjeta.text.replace(hora, "").strip()
                    lineas = [l.strip() for l in texto_cuerpo.split('\n') if l.strip()]
                    for linea in lineas:
                        if " - " in linea and len(linea) < 100 and not any(x in linea.lower() for x in ['dazn', 'movistar', 'liga', 'tv', 'euro', 'orange']):
                            partes = linea.split(" - ")
                            equipo_local = partes[0].strip()
                            equipo_visitante = partes[1].strip()
                            break

                # Filtrado de imágenes de la fila (Escudos vs Canales)
                imagenes = tarjeta.find_all('img')
                escudos_libres = []
                for img in imagenes:
                    src = img.get('src', '')
                    alt = img.get('alt', '').lower()
                    title = img.get('title', '').lower()
                    clase = "".join(img.get('class', [])).lower()
                    
                    if any(x in alt or x in title or x in clase for x in ['canal', 'tv', 'tele', 'logo', 'movistar', 'dazn', 'gol', 'eurosport', 'tve', 'la1', 'vodafone', 'orange', 'm+']):
                        nombre_c = img.get('alt', '').strip() or img.get('title', '').strip()
                        if nombre_c and nombre_c not in canales:
                            canales.append(nombre_c)
                    else:
                        if src and src not in escudos_libres:
                            escudos_libres.append(src)

                if not logo_local and len(escudos_libres) >= 1: logo_local = escudos_libres[0]
                if not logo_visitante and len(escudos_libres) >= 2: logo_visitante = escudos_libres[1]

                if logo_local and logo_local.startswith('/'): logo_local = base_url + logo_local
                if logo_visitante and logo_visitante.startswith('/'): logo_visitante = base_url + logo_visitante

                if not canales:
                    for c_el in tarjeta.select('.canal, .tele, .canales, span[class*="canal"], td[class*="canal"]'):
                        c_txt = c_el.text.strip()
                        if c_txt and len(c_txt) < 40 and c_txt not in canales:
                            canales.append(c_txt)

                equipo_local = re.sub(r'\s+', ' ', equipo_local).strip()
                equipo_visitante = re.sub(r'\s+', ' ', equipo_visitante).strip()

                if equipo_local and equipo_local != "Equipo Local":
                    eventos.append({
                        'hora': hora,
                        'fecha': fecha,
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

        # Limpieza final de duplicados exactos
        eventos_unicos = []
        vistos_ev = set()
        for ev in eventos:
            clave = f"{ev['fecha']}-{ev['hora']}-{ev['equipos']}"
            if clave not in vistos_ev:
                eventos_unicos.append(ev)
                vistos_ev.add(clave)

        print(f"✅ Éxito absoluto: {len(eventos_unicos)} partidos aislados sin contaminación.")
        return eventos_unicos

    except Exception as e:
        print(f"⚠️ Error crítico en el raspado de eventos: {e}")
        return []
