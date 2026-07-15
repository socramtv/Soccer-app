from playwright.sync_api import sync_playwright

def extraer_enlaces(url_enlaces):
    enlaces = []
    
    try:
        with sync_playwright() as p:
            # Quitamos los argumentos '--single-process' y '--no-zygote' 
            # ya que a veces congelan el renderizado headless en Linux
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            
            # Configuramos un contexto con una resolución normal y un User-Agent real
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            
            page = context.new_page()
            
            # wait_until="domcontentloaded" acelera drásticamente la entrada en pasarelas IPFS
            page.goto(url_enlaces, timeout=45000, wait_until="domcontentloaded")
            
            # Esperamos a que la lista esté visible (máximo 30 segundos)
            elemento = page.wait_for_selector('div.lista-plana-content', timeout=30000)
            query_lista = elemento.query_selector_all('div.lista-plana-item')
            
            for item in query_lista:
                name_elem = item.query_selector('div.lista-plana-name')
                id_elem = item.query_selector('div.lista-plana-id')
                
                # Extraer textos de forma segura
                name = name_elem.inner_text().strip() if name_elem else "No encontrado"
                id_text = id_elem.inner_text().strip() if id_elem else "No encontrado"
                
                elemento_dict = {
                    'name': name,
                    'id': id_text
                }
                enlaces.append(elemento_dict)
                
            browser.close()
            
    except Exception as e:
        # Si hay un timeout o error de red, lo registra en la consola de Render 
        # pero permite que la Web App siga funcionando sin romperse
        print(f"⚠️ Aviso: No se pudieron extraer los enlaces debido a: {e}")
        return []
        
    return enlaces
