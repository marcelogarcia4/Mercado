import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// La URL base del backend.
// Para desarrollo local, puedes crear un archivo .env en la carpeta frontend con:
// REACT_APP_API_BASE_URL=http://localhost:5000
// Para producción, esta variable se configurará en la plataforma de despliegue (ej. Vercel, Netlify).
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

function App() {
  const [searchTerm, setSearchTerm] = useState('');
  const [results, setResults] = useState([]);
  const [categories, setCategories] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [userInfo, setUserInfo] = useState(null); // Para mostrar info del backend (ej. si está logueado)

  // Chequear el estado de autenticación al cargar la app (opcional)
  useEffect(() => {
    const fetchUserStatus = async () => {
      try {
        // Esta llamada es para verificar si hay una sesión activa en el backend
        // El backend en '/' podría devolver algo si el usuario está logueado
        const response = await axios.get(`${API_BASE_URL}/`, { withCredentials: true });
        // Asumimos que si hay token, el backend responde con algo que lo indique
        // Esto es solo un ejemplo, el backend no devuelve info de usuario en '/' actualmente.
        // Podríamos añadir un endpoint /me para esto.
        if (response.data && typeof response.data === 'string' && response.data.startsWith("Autenticado")) {
          setUserInfo(response.data);
        } else {
          setUserInfo(null);
        }
        console.log("Endpoint: / (GET) - User status check response:", response);
      } catch (err) {
        console.error("Error fetching user status:", err);
        // No es un error crítico para el funcionamiento de la app si esto falla
      }
    };
    fetchUserStatus();
  }, []);


  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchTerm.trim()) return;

    setIsLoading(true);
    setError(null);
    setResults([]); // Limpiar resultados anteriores

    console.log(`Endpoint: /buscar?q=${searchTerm} (GET)`);
    try {
      // Asegurarse de que las cookies (si existen, como la de sesión) se envíen con la solicitud
      const response = await axios.get(`${API_BASE_URL}/buscar`, { params: { q: searchTerm }, withCredentials: true });
      console.log("JSON Response from /buscar:", response.data);
      setResults(response.data.results || []);
      if ((response.data.results || []).length === 0) {
        setError("No se encontraron productos para tu búsqueda.");
      }
    } catch (err) {
      console.error("Error fetching search results:", err.response ? err.response.data : err.message);
      setError(err.response?.data?.error || "Error al buscar productos. ¿Iniciaste sesión?");
      if (err.response?.status === 401) {
        setError("No autorizado. Por favor, inicia sesión con Mercado Libre e intenta de nuevo.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const fetchCategories = async () => {
    setIsLoading(true);
    setError(null);
    setCategories([]); // Limpiar categorías anteriores

    console.log("Endpoint: /categorias (GET)");
    try {
      // Asegurarse de que las cookies se envíen con la solicitud
      const response = await axios.get(`${API_BASE_URL}/categorias`, { withCredentials: true });
      console.log("JSON Response from /categorias:", response.data);
      setCategories(response.data || []);
      if ((response.data || []).length === 0) {
        setError("No se pudieron cargar las categorías.");
      }
    } catch (err) {
      console.error("Error fetching categories:", err.response ? err.response.data : err.message);
      setError(err.response?.data?.error || "Error al cargar categorías. ¿Iniciaste sesión?");
       if (err.response?.status === 401) {
        setError("No autorizado. Por favor, inicia sesión con Mercado Libre e intenta de nuevo.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Motor de Recomendación de Productos</h1>
        <p>Mercado Libre Chile API</p>
        {userInfo ? (
          <p className="user-info">{userInfo}</p>
        ) : (
          <a href={`${API_BASE_URL}/login`} className="login-button">
            Iniciar Sesión con Mercado Libre
          </a>
        )}
      </header>

      <main>
        <section className="search-section">
          <h2>Buscar Productos</h2>
          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Ej: iPhone 15, Zapatillas Nike"
              className="search-input"
            />
            <button type="submit" disabled={isLoading} className="search-button">
              {isLoading ? 'Buscando...' : 'Buscar'}
            </button>
          </form>
        </section>

        <section className="categories-section">
          <h2>Categorías Principales</h2>
          <button onClick={fetchCategories} disabled={isLoading} className="action-button">
            {isLoading ? 'Cargando...' : 'Ver Categorías'}
          </button>
          {categories.length > 0 && (
            <ul className="categories-list">
              {categories.map(category => (
                <li key={category.id} className="category-item">{category.name}</li>
              ))}
            </ul>
          )}
        </section>

        {error && <p className="error-message">{error}</p>}

        {results.length > 0 && (
          <section className="results-section">
            <h2>Resultados de Búsqueda</h2>
            <div className="results-grid">
              {results.map(item => (
                <div key={item.id} className="result-item">
                  <img src={item.thumbnail.replace(/^http:/, 'https:')} alt={item.title} className="item-image" />
                  <h3 className="item-title">{item.title}</h3>
                  <p className="item-price">Precio: {item.currency_id} ${item.price}</p>
                  <p className="item-category">Categoría ID: {item.category_id}</p>
                  <a href={item.permalink} target="_blank" rel="noopener noreferrer" className="item-link">
                    Ver en Mercado Libre
                  </a>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      <footer className="App-footer">
        <p>Desarrollado con React y Flask para la API de Mercado Libre.</p>
        <p>Recuerda configurar CORS en el backend si es necesario para el desarrollo local.</p>
      </footer>
    </div>
  );
}

export default App;
