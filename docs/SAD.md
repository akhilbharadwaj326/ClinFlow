# System Architecture Document (SAD) - ClinFlow

## 1. System Overview
ClinFlow is built using a modern full-stack web architecture, separating the client interface from the backend API services, and integrating an advanced AI processing layer. This ensures scalability, security, and performance for multi-tenant clinic operations.

## 2. Technology Stack
- **Frontend Layer:** React.js
  - Handles the clinic staff user interface (Dashboard, Document Upload, Patient Timeline, Review Workspace).
  - Deployed on **Firebase Hosting** for high performance and global CDN.
- **Backend API Layer:** Python FastAPI
  - High-performance asynchronous REST API.
  - Deployed as serverless containers on **Firebase Cloud Functions (2nd Gen)** for continuous availability and near-instant scaling.
- **AI Processing Layer:** OpenAI API
  - Utilizes LLMs (via user-provided API key) for terminology normalization, note structuring, and missing information detection.
  - Configured strictly to ground outputs and prevent hallucinations.
- **Database Layer:** PostgreSQL
  - Local Development: Local Postgres instance.
  - Production Deployment: Supabase (managed Postgres, including Auth and row-level security).

## 3. Core Architectural Components

### 3.1 Frontend Web Client
- **Authentication & State:** Integrates with Supabase Auth for JWT-based secure sessions.
- **Workspaces:** Multi-doctor shared environment for viewing and approving AI-generated structured notes.
- **Data Fetching:** React Query (or similar) to interact seamlessly with the FastAPI backend.

### 3.2 Backend Services (FastAPI)
- **Ingestion Service:** Receives inputs via REST endpoints (OCR image uploads, Telegram webhooks, manual text entry).
- **OCR Engine:** Processes images/PDFs into raw text data using tools like Tesseract or external OCR APIs.
- **AI Orchestrator Service:** Prompts the OpenAI API with strict guidelines for extracting clinical data, retaining source references, and preventing the invention of information.
- **Validation & Approval Workflow:** Temporarily stores AI-structured data until human review is completed, ensuring immutable source history.

### 3.3 Database Schema (Supabase/PostgreSQL)
- **Tenants:** Clinic-level isolation.
- **Patients:** Core patient records (Name, DOB, demographics).
- **Documents:** Raw, immutable source files (Images, Telegram texts) linked to patient records.
- **Structured_Notes:** Final, human-approved clinical structured data (Symptoms, History, Decisions).
- **Audit_Logs:** Tracks every modification, extraction, and approval to maintain legal and clinical compliance.

## 4. Security & Compliance
- **Data Isolation:** Row-Level Security (RLS) in Supabase ensures clinics only access their own patient records.
- **Traceability:** Every AI extraction is linked to the exact source document to provide an immutable audit trail.
- **Access Control:** Role-based access (Doctors, Assistants, Owners) managed via Supabase Auth.
