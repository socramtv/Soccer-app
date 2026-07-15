import requests
from bs4 import BeautifulSoup
import re

def extraer_eventos(url_eventos):
    eventos = []
    
    try:
        # Cabecera para simular un navegador real y evitar bloqueos de red
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
        
        # --- DETECTOR ADAPTATIVO DE FILAS DE PARTIDOS ---
        # Buscamos cualquier elemento de texto que sea estrictamente una hora (ej: 20:45)
        elementos_hora = []
        for el in soup.find_all(['td', 'div', 'span', 'p', 'time']):
            texto = el.text.strip()
            if re.match(r'^\s*\d{2}:\d{2}\s*$', texto):
                elementos_hora.append(el)
        
        tarjetas = []
        vistos = set()
        for el_hora in elementos_hora:
            # Subimos al contenedor fila más inmediato (un tr, un div o un li)
            fila = el_hora.find_parent(['tr', 'div', 'li'])
            if fila and fila not in vistos and len(fila.text) < 1500:
                tarjetas.append(fila)
                vistos.add(fila)

        # Respaldo clásico si fallara el detector de horas
        if not tarjetas:
            tarjetas = soup.select('tr.partido, div.partido, .partido-box, tr')

        print(f"🔍 Procesando {len(tarjetas)} filas de encuentros localizadas...")

        for tarjeta in tarjetas:
            try:
                # 1. Extraer la Hora exacta
                hora_match = re.search(r'\d{2}:\d{2}', tarjeta.text)
                if not hora_match:
                    continue
                hora = hora_match.group(0)
                
                # 2. Extraer la Competición / Liga (Buscamos el encabezado superior más cercano)
                liga = ""
                previo = tarjeta.find_previous(['h2', 'h3', 'h4', 'div', 'tr'], class_=re.compile(r'torneo|liga|competicion|titulo|date|fecha|thead'))
                if previo:
                    liga = previo.text.strip()
                if not liga or len(liga) > 80:
                    img_torneo = tarjeta.find('img', class_=re.compile(r'torneo|liga'))
                    liga = img_torneo.get('alt', '').strip() if img_torneo else "Otros Deportes"
                
                liga = re.sub(r'\s+', ' ', liga).strip()

                # 3. Inicializar variables de equipos
                equipo_local = "Equipo Local"
                equipo_visitante = "Equipo Visitante"
                logo_local = ""
                logo_visitante = ""
                canales = []

                # Separación por celdas si es una fila de tabla (tr)
                tds = tarjeta.find_all('td') if tarjeta.name == 'tr' else []
                
                # Método A: Intentar por clases específicas de la web (.local y .visitante)
                locales_el = tarjeta.select_one('.local, .equipo-local, span[class*="local"]')
                visitantes_el = tarjeta.select_one('.visitante, .equipo-visitante, span[class*="visitante"]')
                
                if locales_el and visitantes_el:
                    equipo_local = locales_el.text.strip()
                    equipo_visitante = visitantes_el.text.strip()
                    img_l = locales_el.find('img')
                    img_v = visitantes_el.find('img')
                    if img_l: logo_local = img_l.get('src', '')
                    if img_v: logo_visitante = img_v.get('src', '')
                    
                # Método B: Analizar celdas de tabla buscando el separador " - " o " vs "
                elif len(tds) >= 2:
                    for td in tds:
                        txt = td.text.strip()
                        if " - " in txt and len(txt) < 120 and ":" not in txt:
                            partes = txt.split(" - ")
                            equipo_local = partes[0].strip()
                            equipo_visitante = partes[1].strip()
                            imgs = td.find_all('img')
                            if len(imgs) >= 2:
                                logo_local = imgs[0].get('src', '')
                                logo_visitante = imgs[1].get('src', '')
                            break
                
                # Método C: Ruptura de cadenas general por líneas de texto limpio
                if equipo_local == "Equipo Local" or not equipo_visitante:
                    texto_cuerpo = tarjeta.text.replace(hora, "").strip()
                    lineas = [l.strip() for l in texto_cuerpo.split('\n') if l.strip()]
                    for linea in lineas:
                        if " - " in linea and len(linea) < 100 and not any(x in linea.lower() for x in ['dazn', 'movistar', 'liga', 'tv']):
                            partes = linea.split(" - ")
                            equipo_local = partes[0].strip()
                            equipo_visitante = partes[1].strip()
                            break

                # 4. Clasificar imágenes de la fila de forma inteligente (Escudos vs Canales TV)
                imagenes = tarjeta.find_all('img')
                escudos_libres = []
                
                for img in imagenes:
                    src = img.get('src', '')
                    alt = img.get('alt', '').lower()
                    title = img.get('title', '').lower()
                    clase = "".join(img.get('class', [])).lower()
                    
                    # Si el alt o título contiene palabras de televisión, va a canales
                    if any(x in alt or x in title or x in clase for x in ['canal', 'tv', 'tele', 'logo', 'movistar', 'dazn', 'gol', 'eurosport', 'tve', 'la1', 'vodafone', 'orange']):
                        nombre_c = img.get('alt', '').strip() or img.get('title', '').strip()
                        if nombre_c and nombre_c not in canales:
                            canales.append(nombre_c)
                    else:
                        if src and src not in escudos_libres:
                            escudos_libres.append(src)

                # Asignar escudos libres encontrados en la fila si no se capturaron antes
                if not logo_local and len(escudos_libres) >= 1:
                    logo_local = escudos_libres[0]
                if not logo_visitante and len(escudos_libres) >= 2:
                    logo_visitante = escudos_libres[1]

                # Convertir rutas de imágenes locales a enlaces absolutos
                if logo_local and logo_local.startswith('/'): logo_local = base_url + logo_local
                if logo_visitante and logo_visitante.startswith('/'): logo_visitante = base_url + logo_visitante

                # 5. Extraer canales por texto si la fila no usaba logotipos de televisión
                if not canales:
                    for c_el in tarjeta.select('.canal, .tele, .canales, span[class*="canal"], td[class*="canal"]'):
                        c_txt = c_el.text.strip()
                        if c_txt and len(c_txt) < 40 and c_txt not in canales:
                            canales.append(c_txt)

                # Limpieza final de espacios residuales
                equipo_local = re.sub(r'\s+', ' ', equipo_local).strip()
                equipo_visitante = re.sub(r'\s+', ' ', equipo_visitante).strip()

                # Guardar el partido si es válido y contiene datos
                if equipo_local and equipo_local != "Equipo Local":
                    eventos.append({
                        'hora': hora,
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

        # Eliminar duplicados si la estructura HTML repite elementos
        eventos_unicos = []
        vistos_ev = set()
        for ev in eventos:
            clave = f"{ev['hora']}-{ev['equipos']}"
            if clave not in vistos_ev:
                eventos_unicos.append(ev)
                vistos_ev.add(clave)

        print(f"✅ Extracción finalizada. {len(eventos_unicos)} partidos estructurados con éxito.")
        return eventos_unicos

    except Exception as e:
        print(f"⚠️ Error crítico en el raspado de eventos: {e}")
        return []
