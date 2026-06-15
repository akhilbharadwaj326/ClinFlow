import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import apiClient from '../lib/apiClient';
import './PatientDetailPage.css';

const statusColors = {
  approved: '#10b981',
  pending_review: '#f59e0b',
  rejected: '#ef4444',
};

export default function PatientDetailPage() {
  const { patientId } = useParams();
  const [patient, setPatient] = useState(null);
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiClient.get(`/api/patients/${patientId}`),
      apiClient.get(`/api/notes/patient/${patientId}`),
    ])
      .then(([pRes, nRes]) => {
        setPatient(pRes.data);
        setNotes(nRes.data);
      })
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) return <div className="detail-loading">Loading patient record…</div>;

  return (
    <div className="detail-page">
      {/* Header */}
      <header className="detail-header">
        <Link to="/dashboard" className="back-link">← Dashboard</Link>
        <div className="patient-hero">
          <div className="patient-avatar-lg">
            {patient?.full_name?.charAt(0).toUpperCase()}
          </div>
          <div>
            <h1>{patient?.full_name}</h1>
            <p>DOB: {patient?.date_of_birth || 'N/A'} · {patient?.gender || 'N/A'} · {patient?.contact_number || 'No contact'}</p>
          </div>
          <div className="header-actions">
            <Link to={`/patient/${patientId}/handoff`} className="btn-handoff">
              🤝 Safe Handoff
            </Link>
            <Link to="/upload" state={{ patientId }} className="btn-primary">
              + Add Note
            </Link>
          </div>
        </div>
      </header>

      {/* Timeline */}
      <main className="detail-main">
        <h2 className="section-title">Clinical Timeline</h2>
        {notes.length === 0 && (
          <div className="empty-timeline">
            <span>📄</span>
            <p>No clinical notes yet. Upload the first note to begin the record.</p>
          </div>
        )}
        <div className="timeline">
          {notes.map(note => (
            <div className="timeline-item" key={note.id}>
              <div className="timeline-dot" style={{ background: statusColors[note.status] }} />
              <div className="timeline-content">
                <div className="timeline-meta">
                  <span className="note-date">
                    {new Date(note.created_at).toLocaleDateString('en-IN', {
                      day: 'numeric', month: 'short', year: 'numeric',
                    })}
                  </span>
                  <span
                    className="note-status"
                    style={{ color: statusColors[note.status], borderColor: statusColors[note.status] }}
                  >
                    {note.status.replace('_', ' ')}
                  </span>
                </div>

                {/* Structured note preview */}
                {note.ai_output && (
                  <div className="note-preview">
                    {note.ai_output.symptoms && (
                      <p><strong>Symptoms:</strong> {note.ai_output.symptoms.join(', ')}</p>
                    )}
                    {note.ai_output.diagnosis_assessment && (
                      <p><strong>Assessment:</strong> {note.ai_output.diagnosis_assessment}</p>
                    )}
                    {note.ai_output.follow_up && (
                      <p><strong>Follow-up:</strong> {note.ai_output.follow_up}</p>
                    )}
                  </div>
                )}

                {/* Missing fields warning */}
                {note.missing_fields?.length > 0 && (
                  <div className="missing-warning">
                    ⚠️ {note.missing_fields.length} field(s) flagged as missing
                  </div>
                )}

                {note.status === 'pending_review' && (
                  <Link to={`/review/${note.id}`} className="review-btn">
                    Review & Approve →
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
