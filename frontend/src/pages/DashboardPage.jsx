import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../lib/apiClient';
import clinflowLogo from '../assets/clinflow-logo.png';
import './DashboardPage.css';

export default function DashboardPage() {
  const { user, signOut } = useAuth();
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    apiClient.get('/api/patients/')
      .then(res => setPatients(res.data))
      .catch(() => setError('Failed to load patients.'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = patients.filter(p =>
    p.full_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="dashboard-page">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <img src={clinflowLogo} alt="ClinFlow" className="sidebar-logo-img" />
        </div>
        <nav className="sidebar-nav">
          <Link to="/dashboard" className="nav-item active">📋 Patients</Link>
          <Link to="/upload" className="nav-item">⬆️ Upload Note</Link>
        </nav>
        <div className="sidebar-bottom">
          <p className="sidebar-user">{user?.email}</p>
          <button className="signout-btn" onClick={signOut}>Sign Out</button>
        </div>
      </aside>

      {/* Main content */}
      <main className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <h1>Patient Dashboard</h1>
            <p>Select a patient to view their clinical record</p>
          </div>
          <Link to="/upload" className="btn-primary">+ Upload Note</Link>
        </header>

        {/* Search */}
        <div className="search-bar">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search patients by name…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Patient list */}
        {loading && <p className="state-msg">Loading patients…</p>}
        {error && <p className="state-msg error">{error}</p>}
        {!loading && filtered.length === 0 && (
          <div className="empty-state">
            <span>👤</span>
            <p>No patients found. Upload a note to create one.</p>
          </div>
        )}

        <div className="patient-grid">
          {filtered.map(p => (
            <Link to={`/patient/${p.id}`} className="patient-card" key={p.id}>
              <div className="patient-avatar">
                {p.full_name.charAt(0).toUpperCase()}
              </div>
              <div className="patient-info">
                <h3>{p.full_name}</h3>
                <p>{p.date_of_birth ? `DOB: ${p.date_of_birth}` : 'DOB not recorded'}</p>
                <p>{p.gender || 'Gender not recorded'}</p>
              </div>
              <span className="patient-arrow">→</span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
