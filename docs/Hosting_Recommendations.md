# Hosting Architecture for ClinFlow

Based on the requirement for continuous, scalable uptime without the cold-start delays of traditional free tiers (like Render), the chosen hosting platform for ClinFlow is **Firebase**. 

## 1. Frontend Hosting: Firebase Hosting (React JS)
- **Deployment:** The React frontend will be deployed via Firebase Hosting.
- **Why it fits:** Firebase Hosting provides a fast, global CDN, free SSL certificates, and seamless deployment using the Firebase CLI. 
- **Cost:** 100% Free. No credit card required for the frontend alone.

## 2. Backend Hosting: Firebase Cloud Functions 2nd Gen (Python FastAPI)
- **Deployment:** The FastAPI backend will be wrapped in a Firebase Cloud Function (2nd Gen, powered by Google Cloud Run) and deployed as a serverless container.
- **Why it fits:** Serverless architecture means the backend can scale to zero when not in use but will wake up almost instantly (1-3 seconds) compared to Render's 50-second cold start. This ensures the app feels continuously available to users.
- **Cost & Requirements:** The free tier includes 2 million invocations per month, which is highly generous. **Note:** Deploying Cloud Functions requires the Firebase project to be on the **Blaze (Pay-as-you-go) plan**. This requires attaching a billing account/credit card, but no charges will be incurred unless the massive free tier limits are exceeded.

## 3. Database & Authentication: Supabase (PostgreSQL)
- **Deployment:** While Firebase offers NoSQL databases (Firestore), ClinFlow's structured data relies on **PostgreSQL**. Therefore, the database and authentication will remain on **Supabase**.
- **Interaction:** The FastAPI backend running in Firebase Cloud Functions will connect securely to the Supabase Postgres database over the internet.
- **Cost:** Supabase offers a robust free tier (500MB DB space, 1GB storage, 50,000 MAU) that is completely free and does not require a credit card upfront.

## Summary of the Chosen Stack
1. **Frontend:** React JS on **Firebase Hosting**.
2. **Backend:** Python FastAPI on **Firebase Cloud Functions (Python)**.
3. **Database & Auth:** Managed via **Supabase**.
4. **AI Layer:** Connected via backend to **OpenAI API** (Pay-per-use).
