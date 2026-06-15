import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../lib/apiClient';
import './ReviewPage.css';

const severityColors = { high: '#ef4444', medium: '#f59e0b', low: '#3b82f6' };

export default function ReviewPage() {
  const { noteId } = useParams();
  const navigate = useNavigate();

  const [note, setNote] = useState(null);
  const [editedData, setEditedData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiClient.get(`/api/notes/patient/placeholder`)
      .catch(() => {})
      .finally(() => {});

    // We fetch all notes and find the one matching noteId
    // In a production build, an endpoint /api/notes/{note_id} would exist
    // For now we use the document endpoint as a proxy.
    // Replace with a dedicated endpoint when available.
    apiClient.get(`/api/notes/note/${noteId}`)
      .then(res => {
        setNote(res.data);
        setEditedData(res.data.ai_output || {});
      })
      .catch(() => {
        // Fallback — attempt to fetch via patient endpoint not available here;
        // show a placeholder state
        setNote(null);
      })
      .finally(() => setLoading(false));
  }, [noteId]);

  const handleApprove = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/api/notes/${noteId}/approve`, { approved_data: editedData });
      navigate(`/patient/${note.patient_id}`);
    } catch {
      alert('Failed to approve note. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleReject = async () => {
    if (!window.confirm('Are you sure you want to reject this note? It will be marked as rejected but preserved for audit.')) return;
    setSaving(true);
    try {
      await apiClient.patch(`/api/notes/${noteId}/reject`);
      navigate(`/patient/${note.patient_id}`);
    } catch {
      alert('Failed to reject note. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (key, value) => {
    setEditedData(prev => ({ ...prev, [key]: value }));
  };

  if (loading) return <div className="review-loading">Loading note for review…</div>;

  if (!note) return (
    <div className="review-loading">
      <p>Note not found.</p>
      <a href="/dashboard">← Back to Dashboard</a>
    </div>
  );

  return (
    <div className="review-page">
      <header className="review-header">
        <a href="/dashboard" className="back-link">← Dashboard</a>
        <h1>Review Clinical Note</h1>
        <p>Verify the AI-extracted information against the original source before approving.</p>
      </header>

      <div className="review-layout">
        {/* Left panel: AI output (editable) */}
        <section className="review-panel">
          <h2>AI-Structured Output <span className="editable-hint">(editable)</span></h2>

          <div className="field-group">
            <label>Symptoms</label>
            <textarea
              rows={3}
              value={Array.isArray(editedData?.symptoms) ? editedData.symptoms.join(', ') : editedData?.symptoms || ''}
              onChange={e => updateField('symptoms', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
            />
          </div>

          <div className="field-group">
            <label>Medical History</label>
            <textarea
              rows={3}
              value={Array.isArray(editedData?.medical_history) ? editedData.medical_history.join(', ') : editedData?.medical_history || ''}
              onChange={e => updateField('medical_history', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
            />
          </div>

          <div className="field-group">
            <label>Diagnosis / Assessment</label>
            <textarea
              rows={2}
              value={editedData?.diagnosis_assessment || ''}
              onChange={e => updateField('diagnosis_assessment', e.target.value)}
            />
          </div>

          <div className="field-group">
            <label>Treatment Plan</label>
            <textarea
              rows={2}
              value={editedData?.treatment_plan || ''}
              onChange={e => updateField('treatment_plan', e.target.value)}
            />
          </div>

          <div className="field-group">
            <label>Follow-Up</label>
            <textarea
              rows={2}
              value={editedData?.follow_up || ''}
              onChange={e => updateField('follow_up', e.target.value)}
            />
          </div>

          {/* Action buttons */}
          <div className="review-actions">
            <button className="btn-approve" onClick={handleApprove} disabled={saving}>
              {saving ? 'Saving…' : '✅ Approve & Save'}
            </button>
            <button className="btn-reject" onClick={handleReject} disabled={saving}>
              ❌ Reject
            </button>
          </div>
        </section>

        {/* Right panel: Missing fields + Source references */}
        <aside className="review-sidebar">
          {/* Missing fields */}
          {note.missing_fields?.length > 0 && (
            <div className="sidebar-section">
              <h3>⚠️ Flagged Missing Fields</h3>
              {note.missing_fields.map((m, i) => (
                <div className="missing-item" key={i} style={{ borderColor: severityColors[m.severity] }}>
                  <div className="missing-header">
                    <span className="missing-field">{m.field}</span>
                    <span className="missing-severity" style={{ color: severityColors[m.severity] }}>
                      {m.severity}
                    </span>
                  </div>
                  <p>{m.reason}</p>
                </div>
              ))}
            </div>
          )}

          {/* Source references */}
          {note.ai_output?.source_references?.length > 0 && (
            <div className="sidebar-section">
              <h3>🔗 Source References</h3>
              {note.ai_output.source_references.map((ref, i) => (
                <div className="source-ref" key={i}>
                  <span className="ref-field">{ref.field}</span>
                  <span className="ref-text">"{ref.source_text}"</span>
                </div>
              ))}
            </div>
          )}

          <div className="sidebar-section safety-note">
            <h3>🛡️ Safety Reminder</h3>
            <p>You are responsible for reviewing this AI output before it becomes part of the patient's trusted record. All information should be verified against the original source.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
