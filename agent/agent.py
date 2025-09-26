import os
import json
from openai import OpenAI
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=r'../.env')
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# local API URL
API_BASE_URL = "http://localhost:8000"
# apip endpoint update token
API_TOKEN = os.getenv(
    "API_TOKEN"
)

def interpret_query_with_ai(query: str):
    system_prompt = (
        "Eres un agente inteligente que traduce consultas de usuario en español a acciones sobre una API de publicaciones.\n"
        "La API tiene los siguientes endpoints:\n"
        "- GET /records -> lista todas las publicaciones.\n"
        "- GET /records/{id} -> obtiene detalles de una publicación por ID.\n"
        "- GET /filter?keyword=XYZ&year=YYYY&language=LL -> busca publicaciones por palabra clave y filtros de año/idioma.\n"
        "- POST /update -> refresca los datos que estan guardados en la base de datos y los vuelve a cargar ejecutando la ETL"
        "Si la consulta del usuario es ambigua o muy general, responde con la acción 'clarify' y un mensaje pidiendo más información.\n"
        "Responde solo en formato JSON con las claves: action (list_all, get_by_id, search, update, clarify), "
        "keyword, year, language, id, y message (esta última solo si action es clarify).\n"
        'para language, debes enviar como parametro language = "en" si el usuario pide ingles, language = "es" si el usuario pide español'
        'si la accion es search y faltan campos por especificar dejalos en null'
        "Deja en blanco o null los campos que no apliquen."
    )
    user_prompt = f"Consulta del usuario: \"{query}\""

    try:
        response = client.chat.completions.create(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        result = response.choices[0].message.content
        try:
            plan = json.loads(result)
        except Exception:
            plan = {"action": "clarify", "message": "Lo siento, no entendí la consulta. ¿Podrías reformularla?"}
        return plan
    except Exception:
        return {"action": "clarify", "message": "Hubo un error al interpretar la consulta. Intenta de nuevo más tarde."}

def api_update():
    """Llama POST /update con header X-API-Key."""
    url = f"{API_BASE_URL}/update"
    headers = {"X-API-Key": API_TOKEN}
    r = requests.post(url, headers=headers, timeout=200)
    if r.status_code == 401:
        return {"status": "error", "detail": "Unauthorized (token inválido)"}
    if r.status_code >= 400:
        return {"status": "error", "detail": r.text}
    return r.json()

def answer_query(query: str):
    plan = interpret_query_with_ai(query)
    action = plan.get("action")
    print(plan)
    if action == "clarify":
        return plan.get("message", "No entendí la consulta, ¿puedes reformularla?")

    elif action == "list_all":
        url = f"{API_BASE_URL}/records"
        res = requests.get(url)
        data = res.json()
        results = data.get("results", [])
        total = data.get("total", len(results))
        top = results[:5]
        respuesta = f"Se encontraron {total} publicaciones en total. Las 5 primeras son:\n"
        for i, rec in enumerate(top, start=1):
            title = rec.get("title") or "(sin título)"
            year = rec.get("publication_year") or "¿?"
            doi = rec.get("doi") or "N/A"
            respuesta += f'{i}. "{title}" ({year}) – DOI: {doi}\n'
        if total > len(top):
            respuesta += "...\n(Por claridad, se muestran solo 5 resultados.)"
        return respuesta

    elif action == "get_by_id":
        record_id = plan.get("id")
        if not record_id:
            return "Por favor proporciona el ID o DOI de la publicación que deseas consultar."
        url = f"{API_BASE_URL}/records/{record_id}"
        res = requests.get(url)
        if res.status_code == 404:
            return "No se encontró ninguna publicación con ese ID."
        record = res.json()
        titulo = record.get("title") or "(sin título)"
        anio = record.get("publication_year")
        idioma = record.get("language")
        doi = record.get("doi")
        host = record.get("host_organization_name")
        respuesta = f"**{titulo}**"
        if anio:   respuesta += f" ({anio})"
        if host:   respuesta += f", publicado en *{host}*"
        if idioma: respuesta += f", idioma: {idioma}"
        respuesta += f". DOI: {doi}." if doi else "."
        refs = record.get("referenced_works")
        if refs:
            respuesta += f" Esta publicación referencia {len(refs)} otros trabajos."
        return respuesta

    elif action == "search":
        keyword = plan.get("keyword")
        year = plan.get("year")
        language = plan.get("language")
        if not keyword and not year and not language:
            return "¿Qué te gustaría buscar? Por favor indica una palabra clave, año o idioma."
        params = {}
        if keyword:  params["keyword"] = keyword
        if year:     params["year"] = year
        if language: params["language"] = language
        url = f"{API_BASE_URL}/filter"
        res = requests.get(url, params=params)
        print(res)
        data = res.json()
        results = data.get("results", [])
        total = data.get("total", len(results))
        if total == 0:
            return "No se encontraron publicaciones que coincidan con la búsqueda."
        top = results[:5]
        if keyword:
            respuesta = f"Resultados para **\"{keyword}\"**"
            if year:     respuesta += f" en el año **{year}**"
            if language: respuesta += f" en idioma **{language}**"
            respuesta += ":\n"
        else:
            respuesta = "Resultados de la búsqueda:\n"
        for i, rec in enumerate(top, start=1):
            title = rec.get("title") or "(sin título)"
            year = rec.get("publication_year") or "¿?"
            doi = rec.get("doi") or "N/A"
            host = rec.get("host_organization_name")
            respuesta += f"{i}. **{title}** ({year})"
            if host: respuesta += f" – *{host}*"
            respuesta += f". DOI: {doi}\n"
        if total > len(top):
            respuesta += f"... (Mostrando 5 de {total} resultados)\n"
        return respuesta

    elif action == "update":
        res = api_update()
        if res.get("status") == "error":
            return f"Falló la actualización: {res.get('detail')}"
        return f"Actualización ejecutada correctamente."

    else:
        return "Lo siento, no pude interpretar tu solicitud. Intenta reformular la pregunta."

# --- use cases ---
if __name__ == "__main__":
    consultas = [
        "Listar todas las publicaciones disponibles",
        "¿Cuál es el título de la publicación con ID W2100837269",
        "Dame publicaciones de prisma idioma ingles en del año 2009",
        "actualiza los datos por favor",
        "Quiero buscar trabajos, pero no sé qué buscar"
    ]
    for q in consultas:
        print("Consulta:", q)
        print("Agente:", answer_query(q))
        print("-" * 80)
