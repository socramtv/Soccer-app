import requests
from bs4 import BeautifulSoup

def extraer_eventos(url_eventos):
    response = requests.get(url_eventos)
    soup = BeautifulSoup(response.content, 'html.parser')

    tbody = soup.find('tbody')
    
    if not tbody:
        return []

    filas = tbody.find_all('tr')[1:] # Ignoramos la cabecera de la tabla
    eventos = []
    
    for fila in filas:
        tds = fila.find_all('td')
        
        if len(tds) not in [4, 5]:
            continue
        
        if len(tds) == 4:
            evento = {
                'hora': tds[0].get_text(strip=True),
                'liga': tds[1].get_text(strip=True),
                'equipos': tds[2].get_text(strip=True),
                'canales': [li.get_text(strip=True) for li in tds[3].find_all('li')],
                'canales_html': ''
            }
        else:
            evento = {
                'hora': tds[0].get_text(strip=True),
                'liga': tds[1].get_text(strip=True),
                'equipos': f"{tds[2].get_text(strip=True)} vs {tds[3].get_text(strip=True)}",
                'canales': [li.get_text(strip=True) for li in tds[4].find_all('li')],
                'canales_html': ''
            }
        
        eventos.append(evento)
    
    return eventos