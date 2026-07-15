import requests

def extraer_enlaces(url_enlaces):
    enlaces = []
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        respuesta = requests.get(url_enlaces, headers=headers, timeout=15)
        datos = respuesta.json()
        
        # PASO 1: Si viene envuelto en un diccionario, extraemos la lista interna
        if isinstance(datos, dict):
            for clave_interna in ['hashes', 'channels', 'lista', 'enlaces', 'data']:
                if clave_interna in datos and isinstance(datos[clave_interna], (list, dict)):
                    datos = datos[clave_interna]
                    break

        # PASO 2: Procesamos los datos estructurados (IF independiente, NO un elif)
        if isinstance(datos, dict):
            # Caso diccionario directo: {"Canal": "hash"}
            for k, v in datos.items():
                enlaces.append({
                    'name': str(k).strip(),
                    'id': str(v).strip()
                })
                
        elif isinstance(datos, list):
            # Caso lista de canales (como tu nuevo hashes.json)
            for item in datos:
                if isinstance(item, dict):
                    # Buscamos primero 'title' (que es el tuyo), luego 'name', 'nombre', etc.
                    name = item.get('title') or item.get('name') or item.get('nombre') or item.get('channel')
                    # Buscamos primero 'hash' (que es el tuyo), luego 'id', 'url', etc.
                    id_text = item.get('hash') or item.get('id') or item.get('val') or item.get('url')
                    
                    if name and id_text:
                        enlaces.append({
                            'name': str(name).strip(),
                            'id': str(id_text).strip()
                        })
                        
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    enlaces.append({
                        'name': str(item[0]).strip(),
                        'id': str(item[1]).strip()
                    })
                    
        print(f"✅ Éxito: Se han extraído {len(enlaces)} canales correctamente del archivo JSON.")
        
    except Exception as e:
        print(f"⚠️ Error al procesar el archivo JSON de canales: {e}")
        return []
        
    return enlaces
