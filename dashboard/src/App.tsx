import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import Overview from './pages/Overview';
import Agents from './pages/Agents';
import AuditTrail from './pages/AuditTrail';
import Simulation from './pages/Simulation';

function App() {
    return (
        <BrowserRouter>
            <Layout>
                <Routes>
                    <Route path="/" element={<Overview />} />
                    <Route path="/agents" element={<Agents />} />
                    <Route path="/audit" element={<AuditTrail />} />
                    <Route path="/simulation" element={<Simulation />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </Layout>
        </BrowserRouter>
    );
}

export default App;
