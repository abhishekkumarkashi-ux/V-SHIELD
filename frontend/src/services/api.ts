import axios from 'axios';
import toast from 'react-hot-toast';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      if (status === 401) {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      } else if (status === 404) {
        toast.error('Endpoint not found (404)');
      } else if (status === 422) {
        toast.error('Validation error (422)');
      } else if (status === 502) {
        toast.error('Backend is offline or unreachable (502 Bad Gateway)');
      } else if (status >= 500) {
        toast.error(`Backend internal error (${status})`);
      } else {
        toast.error(error.response.data?.detail || `API error (${status})`);
      }
    } else if (error.request) {
      toast.error('Network error. Backend or network unavailable.');
    } else {
      toast.error('Request failed before sending.');
    }
    return Promise.reject(error);
  }
);

export const authService = {
  emailLogin: async (email: string, password: string) => {
    const res = await api.post('/auth/login', { email, password });
    return res.data;
  },
  googleLogin: async (credential: string) => {
    const res = await api.post('/auth/google', { credential });
    return res.data;
  },
  logout: async () => {
    await api.post('/auth/logout');
  },
  getMe: async () => {
    const res = await api.get('/auth/me');
    return res.data;
  }
};

export const apiService = {
  getHistory: async () => {
    const res = await api.get('/history');
    return res.data;
  },
  getStatus: async () => {
    const res = await api.get('/status');
    return res.data;
  },
  enrollSpeaker: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post('/enroll', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  }
};

export const healthService = {
  check: async () => {
    const res = await axios.get(API_URL.replace('/api/v1', '/health'));
    return res.data;
  }
};
