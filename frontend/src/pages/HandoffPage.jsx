import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import apiClient from '../lib/apiClient';
import './HandoffPage.css';

export default function HandoffPage() {
  const { patientId } = useParams();
  const [handoff, setHandoff] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    apiClient.get(`/api/notes/patient/${patientId}/handoff`)
      .then(res => setHandoff(res.data))
      .catch(err => setError(err.response?.data?.detail || 'Could not generate handoff summary.'))
      .finally(() => setLoading(false));
  }, [patientId]);

  const handlePrint = () => window.print();

  if (loading) return <div className="handoff-loading">Generating Safe Handoff Summary…</div>;

  return (
    <div className="handoff-page">
      <div className="handoff-card">
        <div className="handoff-header">
          <div>
            <a href={`/patient/${patientId}`} className="back-link">← Patient Record</a>
            <h1>🤝 Safe Handoff Summary</h1>
            <p className="handoff-meta">
              Patient: <strong>{handoff?.patient_name}</strong>
              {handoff?.last_visit && (
                <> · Last approved: <strong>{new Date(handoff.last_visit).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</strong></>
              )}
            </p>
          </div>
          <button className="print-btn" onClick={handlePrint}>🖨️ Print</button>
        </div>

        {error ? (
          <div className="handoff-error">
            <span>⚠️</span>
            <p>{error}</p>
            <small>Ensure at least one note has been approved for this patient.</small>
          </div>
        ) : (
          <>
            <div className="handoff-summary-box">
              <p>{handoff?.summary}</p>
            </div>

            {handoff?.missing_fields_count > 0 && (
              <div className="handoff-warning">
                <strong>⚠️ Note:</strong> {handoff.missing_fields_count} field(s) were flagged as potentially missing in the source documentation. Please review the full clinical record before making care decisions.
              </div>
            )}

            <div className="handoff-footer">
              <p>This summary was AI-generated from approved clinical notes. The treating clinician is responsible for verifying all information before continuing patient care.</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
