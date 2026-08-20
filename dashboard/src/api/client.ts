import axios from 'axios';

// In production (Render), VITE_API_URL points to the deployed backend.
// In development, defaults to localhost:8000.
const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
});

export default api;
