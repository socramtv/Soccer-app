import requests
from bs4 import BeautifulSoup
import re

def extraer_eventos(url_eventos):
    eventos = []
    
    try:
        # Cabecera para simular un navegador real y evitar bloqueos
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
        
        # En futbolenlatv cada bloque de partido suele estar etiquetado con la clase 'partido' o dentro de filas comunes
        tarjetas = soup.select('div.partido, div.row-partido, .partido-box')
        
        if not tarjetas:
            # Selector alternativo por si cambia ligeramente la estructura de la web
            tarjetas = soup.find_all('div', class_=re.compile(r'partido|evento|match-item'))

        for tarjeta in tarjetas:
            try:
                # 1. Extraer la Hora del encuentro
                hora_elem = tarjeta.select_one('.hora, .time, span[class*="hora"]')
                hora = hora_elem.text.strip() if hora_elem else "00:00"
                
                # 2. Extraer la Competición / Liga
                liga_elem = tarjeta.select_one('.torneo, .competicion, .liga, .copete, span[class*="torneo"]')
                if liga_elem and liga_elem.find('img'):
                    liga = liga_elem.find('img').get('alt', '').strip()
                else:
                    liga = liga_elem.text.strip() if liga_elem else ""
                
                # Si no se encuentra dentro de la fila, buscamos el encabezado de liga anterior más cercano
                if not liga:
                    bloque_padre = tarjeta.find_previous(['h2', 'h3', 'div'], class_=re.compile(r'torneo|liga|competicion|titulo-liga'))
                    liga = bloque_padre.text.strip() if bloque_padre else "Otros Deportes"

                # 3. Extraer Nombres de Equipos e Imágenes de Escudos
                locales = tarjeta.select_one('.local, .equipo-local, span[class*="local"]')
                visitantes = tarjeta.select_one('.visitante, .equipo-visitante, span[class*="visitante"]')
                
                equipo_local = "Equipo Local"
                equipo_visitante = "Equipo Visitante"
                logo_local = ""
                logo_visitante = ""

                if locales and visitantes:
                    equipo_local = locales.text.strip()
                    equipo_visitante = visitantes.text.strip()
                    
                    # Extraer el src del escudo si viene dentro del bloque del equipo
                    img_local = locales.find('img')
                    img_visitante = visitantes.find('img')
                    if img_local: logo_local = img_local.get('src', '')
                    if img_visitante: logo_visitante = img_visitante.get('src', '')
                else:
                    # Alternativa si los nombres vienen juntos en una sola cadena (ej: "Sevilla - Betis")
                    info_junta = tarjeta.select_one('.equipos, .partido-nombre, .evento-titulo, h9')
                    texto_junto = info_junta.text.strip() if info_junta else ""
                    if " - " in texto_junto:
                        partes = texto_junto.split(" - ")
                        equipo_local = partes[0].strip()
                        equipo_visitante = partes[1].strip()
                    elif texto_junto:
                        equipo_local = texto_junto

                # Si los escudos no estaban dentro del span de equipos, buscamos todas las imágenes libres de la fila
                if not logo_local or not logo_visitante:
                    imagenes_fila = [img for img in tarjeta.find_all('img') if not img.find_parent(class_=re.compile(r'canal|tele|tv|logo-canal'))]
                    # Descartamos la primera si es el logo de la propia liga
                    if imagenes_fila and tarjetas[0].select_one('.torneo') and len(imagenes_fila) > 2:
                        imagenes_fila.pop(0)
                        
                    if not logo_local and len(imagenes_fila) >= 1:
                        logo_local = imagenes_fila[0].get('src', '')
                    if not logo_visitante and len(imagenes_fila) >= 2:
                        logo_visitante = imagenes_fila[1].get('src', '')

                # Convertir URLs relativas (/images/...) en URLs absolutas completas
                if logo_local and logo_local.startswith('/'):
                    logo_local = base_url + logo_local
                if logo_visitante and logo_visitante.startswith('/'):
                    logo_visitante = base_url + logo_visitante

                # 4. Extraer Canales de TV que retransmiten
                canales = []
                # Buscamos logotipos o textos en la sección de canales del partido
                canales_elementos = tarjeta.select('.canal, .tele, .canales, div[class*="canal"] img, span[class*="canal"]')
                
                for element in canales_elementos:
                    nombre_canal = ""
                    if element.name == 'img':
                        nombre_canal = element.get('alt', '').strip() or element.get('title', '').strip()
                    else:
                        img_interna = element.find('img')
                        if img_interna:
                            nombre_canal = img_interna.get('alt', '').strip() or img_interna.get('title', '').strip()
                        else:
                            nombre_canal = element.text.strip()
                    
                    if nombre_canal and nombre_canal not in canales and len(nombre_canal) < 50:
                        canales.append(nombre_canal)

                # Construimos el diccionario estructurado exactamente como lo necesita tu app.py
                evento_dict = {
                    'hora': hora,
                    'liga': liga,
                    'equipos': f"{equipo_local} - {equipo_visitante}",
                    'equipo_local': equipo_local,
                    'equipo_visitante': equipo_visitante,
                    'logo_local': logo_local,
                    'logo_visitante': logo_visitante,
                    'canales': canales,
                    'canales_html': ""  # Se rellenará automáticamente en tu app.py
                }
                
                if hora and equipo_local != "Equipo Local":
                    eventos.append(evento_dict)

            except Exception as e_tarjeta:
                print(f"⚠️ Alerta: Saltado un partido por error de formato interno: {e_tarjeta}")
                continue

        print(f"✅ Extracción finalizada con éxito. {len(eventos)} partidos listos.")

    except Exception as e:
        print(f"⚠️ Error crítico en el raspado de eventos: {e}")
        return []
        
    return eventos
