# ClinFlow Development Roadmap

This roadmap breaks down the MVP development into actionable sprints, ensuring that infrastructure, backend logic, AI integration, and frontend workflows are built in a logical sequence.

## Sprint 1: Project Setup & Infrastructure (Week 1)
**Goal:** Establish the foundational repositories, environments, and basic deployments.
- [ ] Initialize GitHub repository with `frontend` and `backend` directories.
- [ ] Set up React JS (Vite or Create React App) in the `frontend` folder.
- [ ] Set up Python FastAPI in the `backend` folder.
- [ ] Configure Firebase project (Hosting for frontend, Cloud Functions for backend).
- [ ] Configure Supabase project (Database and Auth).
- [ ] Deploy "Hello World" versions to Firebase to verify CI/CD and deployment pipelines.

## Sprint 2: Database Schema & Authentication (Week 2)
**Goal:** Secure the application and establish the data model.
- [ ] Define PostgreSQL tables in Supabase (`Tenants`, `Users`, `Patients`, `Documents`, `Structured_Notes`).
- [ ] Implement Row-Level Security (RLS) in Supabase so doctors only see their clinic's patients.
- [ ] Integrate Supabase Auth into the React frontend (Login/Signup screens).
- [ ] Create FastAPI middleware to validate Supabase JWT tokens on protected routes.

## Sprint 3: Document Ingestion & OCR (Week 3)
**Goal:** Allow users to upload handwritten notes and extract raw text.
- [ ] **Frontend:** Build a secure document upload component (drag-and-drop for images/PDFs).
- [ ] **Backend:** Create FastAPI endpoint to receive file uploads.
- [ ] **Backend:** Save the raw image/file to Supabase Storage.
- [ ] **Backend:** Integrate an OCR engine (e.g., Tesseract or Google Cloud Vision) to extract raw text from the uploaded images.

## Sprint 4: AI Structuring & Core Logic (Week 4)
**Goal:** Transform raw text into structured clinical records safely.
- [ ] **Backend:** Integrate the OpenAI API securely.
- [ ] **Backend:** Write strict LLM prompts for terminology normalization, symptom extraction, and missing information detection.
- [ ] **Backend:** Implement the "Grounding/Traceability" logic to ensure AI outputs map back to the original text.
- [ ] **Backend:** Save the pending/unapproved AI structured note to Supabase.
- [ ] **Frontend:** Build the Patient Timeline view to see historical records.

## Sprint 5: Human Review Workspace & Handoffs (Week 5)
**Goal:** Build the interface where doctors review AI outputs before they become official.
- [ ] **Frontend:** Build the "Review Workspace" UI showing the original image side-by-side with the AI-generated structured note.
- [ ] **Frontend:** Allow doctors to edit, approve, or reject the AI extractions.
- [ ] **Frontend:** Implement the "Safe Handoff Summary" view for quickly reading a patient's case.
- [ ] **Backend:** Finalize the state transition of a note from `pending_review` to `approved`.

## Sprint 6: Polish, Testing, & MVP Launch (Week 6)
**Goal:** Ensure the system is robust, bug-free, and ready for clinic testing.
- [ ] Perform end-to-end testing of the "Upload -> OCR -> AI -> Review" workflow.
- [ ] Test Firebase Cloud Function cold starts (ensure they wake up quickly).
- [ ] Ensure mobile responsiveness for the clinic assistant uploading notes via iPad/Phone.
- [ ] Final security audit (checking RLS policies and API keys).
- [ ] MVP Launch.
