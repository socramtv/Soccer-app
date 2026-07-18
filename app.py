from flask import Flask, render_template, send_from_directory, request, redirect
from funciones.get_events import extraer_eventos
from datetime import datetime
import urllib.parse

app = Flask(__name__)

# Diccionario opcional de hashes AceStream conocidos para automatizar los enlaces en la cartelera
ACESTREAM_DICT = {
    "dazn f1": "02be332ebead0484a5354fa25e97b6833b8b129e",
    "movistar plus+": "1ab443f5b4beb6d586f19e8b25b9f9646cf2ab78",
    "movistar plus": "1ab443f5b4beb6d586f19e8b25b9f9646cf2ab78",
    "m+ vamos": "7e4f6eb38e0d5ef52b7f8b96eb80c1d8c87dad16",
    "m+ deportes": "cf5327fe9c962a29dfff3868f4349ff2b0b4662f",
    "teledeporte": "77cf022557c56cdf8d8115f50e61f846ad72ee05",
    "eurosport 1": "48a589dbeab3544662fafd79888aada7d834cfe9",
    "la 1 tve": "23c952c5b375715db822f2783803c6e28fab0e34",
    "la 1": "23c952c5b375715db822f2783803c6e28fab0e34"
}

@app.route('/')
def index():
    # URL de origen para obtener la cartelera diaria
    url_target = "https://www.futbolenlatv.es"
    eventos_raw = extraer_eventos(url_target)
    
    eventos_procesados = []
    destacados = []
    eventos_agrupados = {}

    for ev in eventos_raw:
        html_canales = []
        tiene_acestream = False
        
        # Procesar la lista de canales de texto plano que extrae el raspador
        for canal in ev.get('canales', []):
            canal_clean = canal.lower().strip()
            stream_url = ""
            
            # Comprobamos si el canal tiene un hash asignado en nuestro diccionario
            for clave_dict, hash_ace in ACESTREAM_DICT.items():
                if clave_dict in canal_clean:
                    stream_url = f"acestream://{hash_ace}"
                    tiene_acestream = True
                    break
            
            # Si no encontramos hash, creamos una ruta interna por defecto basada en su nombre
            if not stream_url:
                stream_url = f"http://placeholder_canal/{urllib.parse.quote(canal)}"
            
            # Construimos el botón HTML con el formato de clase 'btn-canal' que usa tu index
            url_btn = f"/reproductor?url={urllib.parse.quote(stream_url)}&name={urllib.parse.quote(canal)}"
            html_canales.append(f'<a href="{url_btn}" class="btn-canal">{canal}</a>')
        
        # Inyectamos los componentes renderizados y el flag de control de enlaces
        ev['canales_html'] = " ".join(html_canales) if html_canales else '<span class="canal-texto-vacio">* Sin TV Confirmada *</span>'
        ev['has_links'] = tiene_acestream

        # Filtro de partidos destacados (Sevilla FC y Real Betis)
        local = ev.get('equipo_local', '').lower()
        visitante = ev.get('equipo_visitante', '').lower()
        if 'sevilla' in local or 'sevilla' in visitante or 'betis' in local or 'betis' in visitante:
            destacados.append(ev)
            
        eventos_procesados.append(ev)

    # Agrupación secuencial ordenada por días
    for ev in eventos_procesados:
        fecha_partido = ev.get('fecha', 'Hoy')
        if fecha_partido not in eventos_agrupados:
            eventos_agrupados[fecha_partido] = []
        eventos_agrupados[fecha_partido].append(ev)

    # Fecha del sistema para la tarjeta informativa de la cabecera
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    # Lista estática de canales limpios para el módulo de acceso manual inferior
    canales_puros = [
        {"name": "Movistar Plus+", "stream_url": "acestream://1ab443f5b4beb6d586f19e8b25b9f9646cf2ab78"},
        {"name": "DAZN F1", "stream_url": "acestream://02be332ebead0484a5354fa25e97b6833b8b129e"},
        {"name": "M+ Vamos", "stream_url": "acestream://7e4f6eb38e0d5ef52b7f8b96eb80c1d8c87dad16"},
        {"name": "M+ Deportes", "stream_url": "acestream://cf5327fe9c962a29dfff3868f4349ff2b0b4662f"},
        {"name": "Eurosport 1", "stream_url": "acestream://48a589dbeab3544662fafd79888aada7d834cfe9"},
        {"name": "La 1 TVE", "stream_url": "acestream://23c952c5b375715db822f2783803c6e28fab0e34"}
    ]

    return render_template(
        'index.html', 
        fecha=fecha_hoy, 
        destacados=destacados, 
        eventos_agrupados=eventos_agrupados, 
        canales_puros=canales_puros
    )

@app.route('/reproductor')
def reproductor():
    url_stream = request.args.get('url', '')
    nombre_canal = request.args.get('name', 'Streaming')
    # Aquí puedes retornar tu plantilla dedicada del reproductor (HLS/AceStream/Clappr)
    return f"<h2>Reproduciendo: {nombre_canal}</h2><p>Enlace de origen: {url_stream}</p>"

@app.route('/recargar')
def recargar():
    # Fuerza la redirección de limpieza volviendo a invocar el raspador de eventos
    return redirect('/')

# ═══════════════════════════════════════════════════════════════
# ENRUTAMIENTO PWA DESDE LA CARPETA TEMPLATES
# ═══════════════════════════════════════════════════════════════
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('templates', 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('templates', 'sw.js')

@app.route('/icon-192.png')
def serve_icon192():
    return send_from_directory('templates', 'icon-192.png')

@app.route('/icon-512.png')
def serve_icon512():
    return send_from_directory('templates', 'icon-512.png')

if __name__ == '__main__':
    # Ejecución local en modo depuración
    app.run(host='0.0.0.0', port=5000, debug=True)
