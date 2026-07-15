import requests

def extraer_enlaces(url_enlaces):
    enlaces = []
    
    try:
        # Hacemos la petición directa al archivo JSON
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        respuesta = requests.get(url_enlaces, headers=headers, timeout=15)
        
        # Convertimos el texto recibido en datos de Python (Listas/Diccionarios)
        datos = respuesta.json()
        
        # CASO 1: Si el JSON es un diccionario directo tipo {"DAZN 1": "hash123", "DAZN 2": "hash456"}
        if isinstance(datos, dict):
            for k, v in datos.items():
                enlaces.append({
                    'name': str(k).strip(),
                    'id': str(v).strip()
                })
                
        # CASO 2: Si el JSON es una lista de objetos tipo [{"name": "DAZN 1", "id": "123"}, ...]
        elif isinstance(datos, list):
            for item in datos:
                # Buscamos las claves dinámicamente por si se llaman 'name', 'nombre', 'id' o 'hash'
                name = item.get('name') or item.get('nombre') or item.get('channel') or "No encontrado"
                id_text = item.get('id') or item.get('hash') or item.get('val') or "No encontrado"
                
                enlaces.append({
                    'name': str(name).strip(),
                    'id': str(id_text).strip()
                })
                
        print(f"✅ Se han cargado {len(enlaces)} canales correctamente desde el JSON.")
        
    except Exception as e:
        print(f"⚠️ Error al leer o procesar el archivo JSON de canales: {e}")
        return []
        
    return enlaces
