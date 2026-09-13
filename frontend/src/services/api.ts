import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('vshield_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('vshield_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authService = {
  googleLogin: async (credential: string) => {
    const res = await api.post('/auth/google', { credential });
    if (res.data.token) {
      localStorage.setItem('vshield_token', res.data.token);
    }
    return res.data;
  },
  logout: async () => {
    await api.post('/auth/logout');
    localStorage.removeItem('vshield_token');
  },
  getMe: async () => {
    const res = await api.get('/auth/me');
    return res.data;
  }
};

export const healthService = {
  check: async () => {
    const res = await axios.get(API_URL.replace('/api/v1', '/health'));
    return res.data;
  }
};
