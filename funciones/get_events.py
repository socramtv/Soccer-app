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
        
        # 1. Localizar los elementos que contienen una hora exacta (ej: 18:30)
        elementos_hora = []
        for el in soup.find_all(['td', 'div', 'span', 'p', 'time', 'b']):
            texto = el.text.strip()
            if re.match(r'^\s*\d{2}:\d{2}\s*$', texto):
                elementos_hora.append(el)
        
        tarjetas = []
        vistos = set()
        for el_hora in elementos_hora:
            fila = el_hora.find_parent(['tr', 'div', 'li'])
            if fila and fila not in vistos and len(fila.text) < 1000:
                tarjetas.append(fila)
                vistos.add(fila)

        print(f"🔍 Procesando {len(tarjetas)} encuentros...")

        dias_semana = ['lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes', 'sábado', 'sabado', 'domingo', 'hoy', 'mañana', 'manana', 'ayer']
        current_fecha = "Hoy"

        # 2. Recorrido lineal para asignar la fecha correcta
        for el in soup.find_all(['h2', 'h3', 'h4', 'div', 'tr', 'p']):
            txt = el.text.strip()
            clases = "".join(el.get('class', [])).lower() if el.get('class') else ""
            
            # ¿Es una cabecera de FECHA?
            contiene_dia = any(d in txt.lower() for d in dias_semana)
            es_clase_fecha = any(x in clases for x in ['fecha', 'date', 'day', 'thead', 'fecha-cabecera'])
            contiene_mes = any(m in txt.lower() for m in ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'])
            
            if (contiene_dia or es_clase_fecha or contiene_mes) and len(txt) < 100 and " - " not in txt and not re.search(r'\b\d{2}:\d{2}\b', txt):
                current_fecha = re.sub(r'\s+', ' ', el.text).strip()
                continue
                
            if el in tarjetas:
                tarjetas.remove(el)
                try:
                    hora_match = re.search(r'\d{2}:\d{2}', el.text)
                    hora = hora_match.group(0) if hora_match else "00:00"
                    
                    equipo_local = "Equipo Local"
                    equipo_visitante = "Equipo Visitante"
                    logo_local = ""
                    logo_visitante = ""
                    canales = []

                    tds = el.find_all('td') if el.name == 'tr' else []
                    locales_el = el.select_one('.local, .equipo-local, span[class*="local"]')
                    visitantes_el = el.select_one('.visitante, .equipo-visitante, span[class*="visitante"]')
                    
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
                        texto_cuerpo = el.text.replace(hora, "").strip()
                        lineas = [l.strip() for l in texto_cuerpo.split('\n') if l.strip()]
                        for linea in lineas:
                            if " - " in linea and len(linea) < 100 and not any(x in linea.lower() for x in ['dazn', 'movistar', 'liga', 'tv', 'euro', 'orange']):
                                partes = linea.split(" - ")
                                equipo_local = partes[0].strip()
                                equipo_visitante = partes[1].strip()
                                break

                    # Separar de forma limpia escudos de logos de canales
                    imagenes = el.find_all('img')
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
                        for c_el in el.select('.canal, .tele, .canales, span[class*="canal"], td[class*="canal"]'):
                            c_txt = c_el.text.strip()
                            if c_txt and len(c_txt) < 40 and c_txt not in canales:
                                canales.append(c_txt)

                    equipo_local = re.sub(r'\s+', ' ', equipo_local).strip()
                    equipo_visitante = re.sub(r'\s+', ' ', equipo_visitante).strip()

                    if equipo_local and equipo_local != "Equipo Local":
                        eventos.append({
                            'hora': hora,
                            'fecha': current_fecha,
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

        # Limpiar duplicados
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
