import re

def obtener_enlaces(enlaces, patron):
    resultados = []
    
    for canal in enlaces:
        if re.search(patron, canal['name'], re.IGNORECASE):
            resultados.append(canal)

    html = ""
    for i, canal in enumerate(resultados):
        if i == 0:  # Primer enlace - mostrar nombre completo
            html += f"<a href='acestream://{canal['id']}'>{canal['name']}</a> "
        else:       # Demás enlaces - mostrar número
            html += f"<a href='acestream://{canal['id']}'>[{i+1}]</a> "
    
    return html