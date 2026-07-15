from playwright.sync_api import sync_playwright

def extraer_enlaces(url_enlaces):
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        page = browser.new_page()
        page.goto(url_enlaces)
        
        # Esperamos a que cargue la lista
        elemento = page.wait_for_selector('div.lista-plana-content', timeout=30000)
        query_lista = elemento.query_selector_all('div.lista-plana-item')
        
        enlaces = []
        for item in query_lista:
            name_elem = item.query_selector('div.lista-plana-name')
            id_elem = item.query_selector('div.lista-plana-id')
            
            # Extraer textos
            name = name_elem.inner_text().strip() if name_elem else "No encontrado"
            id_text = id_elem.inner_text().strip() if id_elem else "No encontrado"
            
            # Crear diccionario
            elemento_dict = {
                'name': name,
                'id': id_text
            }
            enlaces.append(elemento_dict)
        browser.close()
    return enlaces