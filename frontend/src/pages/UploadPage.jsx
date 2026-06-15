import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import apiClient from '../lib/apiClient';
import './UploadPage.css';

export default function UploadPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const [patientMode, setPatientMode] = useState('existing'); // 'existing' | 'new'
  const [patientId, setPatientId] = useState(location.state?.patientId || '');
  const [newPatient, setNewPatient] = useState({ full_name: '', date_of_birth: '', gender: '', contact_number: '' });
  const [sourceType, setSourceType] = useState('image');
  const [file, setFile] = useState(null);
  const [manualText, setManualText] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStatus('');
    setError('');

    try {
      let pid = patientId;

      // Create a new patient if needed
      if (patientMode === 'new') {
        const pRes = await apiClient.post('/api/patients/', newPatient);
        pid = pRes.data.id;
      }

      // Upload the document
      const formData = new FormData();
      formData.append('patient_id', pid);
      formData.append('source_type', sourceType);
      if (sourceType === 'manual') {
        formData.append('manual_text', manualText);
      } else if (file) {
        formData.append('file', file);
      }

      setStatus('Uploading document…');
      const uploadRes = await apiClient.post('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      // Trigger OCR + AI processing
      setStatus('Running OCR and AI structuring…');
      const processRes = await apiClient.post(
        `/api/documents/${uploadRes.data.id}/process`
      );

      setStatus('Done! Redirecting to review…');
      navigate(`/review/${processRes.data.structured_note_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-page">
      <div className="upload-card">
        <a href="/dashboard" className="back-link">← Dashboard</a>
        <h1>Upload Clinical Note</h1>
        <p className="upload-subtitle">
          Upload a handwritten note, image, or paste text from Telegram.
        </p>

        <form onSubmit={handleSubmit} className="upload-form">
          {/* ── Patient ── */}
          <section className="form-section">
            <h3>1. Patient</h3>
            <div className="radio-group">
              <label>
                <input type="radio" value="existing" checked={patientMode === 'existing'} onChange={() => setPatientMode('existing')} />
                Existing patient (paste Patient ID)
              </label>
              <label>
                <input type="radio" value="new" checked={patientMode === 'new'} onChange={() => setPatientMode('new')} />
                New patient
              </label>
            </div>

            {patientMode === 'existing' ? (
              <input
                className="text-input"
                placeholder="Patient UUID"
                value={patientId}
                onChange={e => setPatientId(e.target.value)}
                required
              />
            ) : (
              <div className="new-patient-grid">
                <input className="text-input" placeholder="Full Name *" value={newPatient.full_name} onChange={e => setNewPatient({ ...newPatient, full_name: e.target.value })} required />
                <input className="text-input" placeholder="Date of Birth (YYYY-MM-DD)" value={newPatient.date_of_birth} onChange={e => setNewPatient({ ...newPatient, date_of_birth: e.target.value })} />
                <input className="text-input" placeholder="Gender" value={newPatient.gender} onChange={e => setNewPatient({ ...newPatient, gender: e.target.value })} />
                <input className="text-input" placeholder="Contact Number" value={newPatient.contact_number} onChange={e => setNewPatient({ ...newPatient, contact_number: e.target.value })} />
              </div>
            )}
          </section>

          {/* ── Source type ── */}
          <section className="form-section">
            <h3>2. Note Type</h3>
            <div className="source-tabs">
              {['image', 'pdf', 'telegram', 'manual'].map(t => (
                <button key={t} type="button" className={`source-tab ${sourceType === t ? 'active' : ''}`} onClick={() => setSourceType(t)}>
                  {t === 'image' ? '🖼️ Image' : t === 'pdf' ? '📄 PDF' : t === 'telegram' ? '📱 Telegram' : '✏️ Manual'}
                </button>
              ))}
            </div>
          </section>

          {/* ── File / text input ── */}
          <section className="form-section">
            <h3>3. Content</h3>
            {sourceType === 'manual' || sourceType === 'telegram' ? (
              <textarea
                className="textarea-input"
                placeholder="Paste the clinical note or Telegram message here…"
                value={manualText}
                onChange={e => setManualText(e.target.value)}
                rows={8}
                required
              />
            ) : (
              <div
                className={`drop-zone ${dragOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => document.getElementById('file-input').click()}
              >
                <input
                  id="file-input"
                  type="file"
                  accept={sourceType === 'pdf' ? '.pdf' : 'image/*'}
                  onChange={e => setFile(e.target.files[0])}
                  style={{ display: 'none' }}
                />
                {file ? (
                  <>
                    <span className="drop-icon">✅</span>
                    <p>{file.name}</p>
                    <small>Click to replace</small>
                  </>
                ) : (
                  <>
                    <span className="drop-icon">📂</span>
                    <p>Drag & drop or click to upload</p>
                    <small>{sourceType === 'pdf' ? 'PDF files only' : 'JPG, PNG, etc.'}</small>
                  </>
                )}
              </div>
            )}
          </section>

          {status && <p className="status-msg">⏳ {status}</p>}
          {error && <p className="error-msg">❌ {error}</p>}

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading ? 'Processing…' : 'Upload & Analyze'}
          </button>
        </form>
      </div>
    </div>
  );
}
