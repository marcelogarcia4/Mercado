import os
from flask import Flask, redirect, request, session, url_for, jsonify
import requests
from dotenv import load_dotenv
from flask_cors import CORS # Importar Flask-CORS

load_dotenv() # Carga las variables de entorno desde .env

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey") # Clave secreta para la sesión de Flask

# Configurar CORS para permitir solicitudes desde el frontend de React (ej. http://localhost:3000)
# Es mejor ser específico con los orígenes en producción.
# Para desarrollo, '*' puede ser más fácil, o la URL específica del frontend.
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}}, supports_credentials=True)
# supports_credentials=True es importante si el frontend necesita enviar cookies (como la de sesión de Flask)
# y el backend necesita reconocerlas. El frontend (axios) también debe configurarse con withCredentials: true.

# Variables de configuración de Mercado Libre (cargadas desde .env)
CLIENT_ID = os.getenv("MELI_CLIENT_ID")
CLIENT_SECRET = os.getenv("MELI_CLIENT_SECRET")
REDIRECT_URI = os.getenv("MELI_REDIRECT_URI")

# URLs de la API de Mercado Libre
MELI_AUTH_URL = "https://auth.mercadolibre.com.ar/authorization" # Para Argentina, ajustar si es MLC directamente
MELI_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
MELI_API_BASE_URL = "https://api.mercadolibre.com"

# Constante para el site_id de Chile
SITE_ID = "MLC"

@app.route('/')
def home():
    # Verificar si ya tenemos un token de acceso en la sesión
    if 'meli_access_token' in session:
        return f"Autenticado. Token: {session['meli_access_token'][:20]}..."
    return 'Bienvenido al Backend. <a href="/login">Iniciar sesión con Mercado Libre</a>'

@app.route('/login')
def login():
    """
    Redirige al usuario a la página de autenticación de Mercado Libre.
    """
    if not CLIENT_ID or not REDIRECT_URI:
        return "Error: CLIENT_ID o REDIRECT_URI no configurados en el servidor.", 500

    # Construir la URL de autorización de Mercado Libre
    # El scope 'offline_access' es necesario para obtener un refresh_token
    auth_url = f"{MELI_AUTH_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=read write offline_access"

    # Imprimir la URL para depuración (opcional)
    print(f"Redirigiendo a: {auth_url}")

    return redirect(auth_url)

@app.route('/callback')
def callback():
    """
    Ruta a la que Mercado Libre redirige después de la autenticación.
    Recibe el authorization_code y solicita el access_token.
    """
    authorization_code = request.args.get('code')

    if not authorization_code:
        return "Error: No se recibió el código de autorización.", 400

    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        return "Error: Configuración de cliente incompleta en el servidor.", 500

    # Payload para solicitar el token de acceso
    token_payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': authorization_code,
        'redirect_uri': REDIRECT_URI
    }

    try:
        # Realizar la solicitud POST para obtener el token
        response = requests.post(MELI_TOKEN_URL, data=token_payload, timeout=10)
        response.raise_for_status()  # Lanza una excepción para códigos de error HTTP (4xx o 5xx)

        token_data = response.json()

        # Almacenar los tokens de forma segura (en sesión para este ejemplo)
        # En producción, considera un almacenamiento más persistente y seguro.
        session['meli_access_token'] = token_data.get('access_token')
        session['meli_refresh_token'] = token_data.get('refresh_token')
        session['meli_token_expires_in'] = token_data.get('expires_in')
        # Aquí podrías guardar también el tiempo de expiración para manejar el refresh.

        return redirect(url_for('home')) # Redirige a la home o a una página de "éxito"

    except requests.exceptions.RequestException as e:
        # Manejo de errores en la solicitud del token
        error_message = f"Error al solicitar el token de acceso: {e}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                error_message += f" - Detalles: {error_details}"
            except ValueError: # Si la respuesta no es JSON
                error_message += f" - Contenido de la respuesta: {e.response.text}"
        return error_message, 500
    except Exception as e:
        return f"Un error inesperado ocurrió: {str(e)}", 500

# --- Helper para refrescar token (a implementar si es necesario) ---
def refresh_access_token():
    """
    Refresca el access_token usando el refresh_token.
    Devuelve True si fue exitoso, False en caso contrario.
    """
    if 'meli_refresh_token' not in session:
        return False

    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: CLIENT_ID o CLIENT_SECRET no configurados para refrescar token.")
        return False

    payload = {
        'grant_type': 'refresh_token',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': session['meli_refresh_token']
    }

    try:
        response = requests.post(MELI_TOKEN_URL, data=payload, timeout=10)
        response.raise_for_status()
        new_token_data = response.json()

        session['meli_access_token'] = new_token_data.get('access_token')
        # Mercado Libre puede o no devolver un nuevo refresh_token. Si lo hace, actualízalo.
        if new_token_data.get('refresh_token'):
            session['meli_refresh_token'] = new_token_data.get('refresh_token')
        session['meli_token_expires_in'] = new_token_data.get('expires_in')
        # Aquí también deberías actualizar el tiempo de expiración.
        print("Token de acceso refrescado exitosamente.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error al refrescar el token: {e}")
        # Si el refresh token es inválido, podría ser necesario re-autenticar al usuario.
        # Considera limpiar la sesión aquí.
        session.pop('meli_access_token', None)
        session.pop('meli_refresh_token', None)
        session.pop('meli_token_expires_in', None)
        return False

# --- Helper para realizar llamadas a la API de Mercado Libre ---
def make_meli_api_request(endpoint, params=None):
    """
    Realiza una solicitud GET a la API de Mercado Libre adjuntando el token de acceso.
    Maneja la lógica de refresco de token si es necesario (simplificado).
    """
    if 'meli_access_token' not in session:
        # Opcional: intentar refrescar si hay refresh token pero no access token.
        # if 'meli_refresh_token' in session and refresh_access_token():
        #     pass # El token ha sido refrescado, continuar
        # else:
        return None, {"error": "No autenticado. Por favor, inicie sesión.", "status_code": 401}

    access_token = session['meli_access_token']
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    full_url = f"{MELI_API_BASE_URL}{endpoint}"

    try:
        response = requests.get(full_url, headers=headers, params=params, timeout=10)

        # Si el token expiró (401 Unauthorized), intenta refrescarlo y reintentar la llamada UNA VEZ.
        if response.status_code == 401:
            print("Token expirado o inválido. Intentando refrescar...")
            if refresh_access_token():
                # Reintenta la llamada con el nuevo token
                headers['Authorization'] = f'Bearer {session["meli_access_token"]}'
                response = requests.get(full_url, headers=headers, params=params, timeout=10)
            else:
                # No se pudo refrescar, devolver error de autenticación
                return None, {"error": "Falló el refresco del token. Por favor, re-autentique.", "status_code": 401}

        response.raise_for_status() # Lanza excepción para otros errores HTTP
        return response.json(), None
    except requests.exceptions.HTTPError as http_err:
        error_details = {"error": f"Error HTTP: {http_err}", "status_code": http_err.response.status_code}
        try:
            error_details["meli_error"] = http_err.response.json()
        except ValueError:
            error_details["meli_error_raw"] = http_err.response.text
        return None, error_details
    except requests.exceptions.RequestException as req_err:
        return None, {"error": f"Error en la solicitud a la API: {req_err}", "status_code": 500}


@app.route('/buscar')
def buscar_productos():
    """
    Permite realizar una búsqueda de productos en Mercado Libre Chile.
    Ejemplo: /buscar?q=iphone
    """
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Parámetro 'q' (query) es requerido"}), 400

    # Construir el endpoint de búsqueda para el sitio MLC
    # Documentación: https://developers.mercadolibre.com.ar/es_ar/items-y-busquedas#Obtener-publicaciones-a-partir-de-una-b%C3%BAsqueda
    endpoint = f"/sites/{SITE_ID}/search"
    params = {'q': query}

    data, error = make_meli_api_request(endpoint, params=params)

    if error:
        return jsonify(error), error.get("status_code", 500)

    # Devolver solo algunos campos para simplificar la respuesta inicial
    # Puedes ajustar esto para devolver más o menos información según necesites.
    simplified_results = []
    if data and 'results' in data:
        for item in data['results'][:10]: # Limitar a 10 resultados por ahora
            simplified_results.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "price": item.get("price"),
                "currency_id": item.get("currency_id"),
                "thumbnail": item.get("thumbnail"),
                "category_id": item.get("category_id"),
                "permalink": item.get("permalink")
            })

    return jsonify({
        "query": query,
        "results": simplified_results,
        "original_count": data.get("paging", {}).get("total", 0) if data else 0
        # "raw_data": data # Descomentar para ver la respuesta completa de MELI
    })

@app.route('/categorias')
def obtener_categorias():
    """
    Obtiene las categorías principales del sitio chileno (MLC).
    Documentación: https://developers.mercadolibre.com.ar/es_ar/categorias-y-publicaciones#Categor%C3%ADas-por-Sitio
    """
    endpoint = f"/sites/{SITE_ID}/categories"
    data, error = make_meli_api_request(endpoint)

    if error:
        return jsonify(error), error.get("status_code", 500)

    return jsonify(data)


if __name__ == '__main__':
    # Es importante ejecutar en HTTPS para el redirect_uri de Mercado Libre en producción.
    # Para desarrollo local, MELI a menudo permite HTTP si está configurado en la app.
    # Para el redirect URI de MELI, si usas localhost, asegúrate de que MELI lo permita.
    # Si usas 'localhost' en REDIRECT_URI, el servidor Flask debe escuchar en 0.0.0.0 para ser accesible
    # desde el navegador si este resuelve localhost a 127.0.0.1 y Flask solo escucha en 127.0.0.1.
    # Escuchar en 0.0.0.0 hace que Flask esté disponible en todas las interfaces de red.
    app.run(host='0.0.0.0', port=5000, debug=True)
