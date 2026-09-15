import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';

import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import LiveAnalysis from './pages/LiveAnalysis';
import CallAnalysis from './pages/CallAnalysis';
import SpeakerVerification from './pages/SpeakerVerification';
import RiskIntelligence from './pages/RiskIntelligence';
import History from './pages/History';
import SecurityAlerts from './pages/SecurityAlerts';
import AIModelCenter from './pages/AIModelCenter';
import Analytics from './pages/Analytics';
import Integrations from './pages/Integrations';
import Settings from './pages/Settings';
import Profile from './pages/Profile';

function App() {
  return (
    <>
      <Toaster position="top-right" toastOptions={{
        style: {
          background: '#1e293b',
          color: '#f8fafc',
          border: '1px solid #334155'
        }
      }} />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/live-analysis" element={<LiveAnalysis />} />
            <Route path="/call-analysis" element={<CallAnalysis />} />
            <Route path="/speaker" element={<SpeakerVerification />} />
            <Route path="/risk-intelligence" element={<RiskIntelligence />} />
            <Route path="/history" element={<History />} />
            <Route path="/security-alerts" element={<SecurityAlerts />} />
            <Route path="/ai-models" element={<AIModelCenter />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/integrations" element={<Integrations />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/profile" element={<Profile />} />
          </Route>
          
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;
