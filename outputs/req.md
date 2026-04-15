## Phase 2: Engineering-Ready PRD  

**Project Overview**  
- **One‑line summary:** A client‑side‑encrypted, one‑time‑secret sharing service that lets developers create a self‑destructing link for any secret and send it to a general‑audience recipient.  
- **Core user flow:**  
  1. **Developer** opens the web app, pastes a secret into the textarea, and clicks **Create Link**.  
  2. The browser **encrypts** the secret with a random symmetric key (AES‑GCM) using the Web Crypto API.  
  3. The ciphertext is **POSTed** to the backend; the backend stores it under a unique ID and returns that ID.  
  4. The browser builds a shareable URL: `https://service.example.com/<id>#<base64‑key>`. The key resides only in the URL fragment (never sent to the server).  
  5. The developer copies and sends the URL to the recipient (general audience).  
  6. Recipient opens the link; the browser extracts the ID and key, **GETs** the ciphertext, decrypts it locally, and displays the secret.  
  7. After successful decryption, the browser signals the backend (via a hidden fetch or the same GET response) to **delete** the stored ciphertext.  
  8. If the link is accessed again, the backend returns 404/Gone because the secret was already destroyed.  

---

### Functional Requirements  

| # | Feature | Description | Acceptance Criteria |
|---|---------|-------------|---------------------|
| FR‑1 | **Secret Input UI** | Simple textarea (max 10 KB) with a “Create Link” button. | User can paste any text ≤10 KB; button is disabled when empty. |
| FR‑2 | **Client‑Side Encryption** | Encrypt secret in browser using AES‑GCM‑256 with a random 256‑bit key; IV generated per encryption. | Ciphertext + IV + tag are produced; secret never leaves browser in plaintext. |
| FR‑3 | **Backend Storage Endpoint** | `POST /secrets` accepts JSON `{ciphertext, iv, tag}` and returns `{id}`. Store ciphertext (encrypted blob) with a TTL‑less record; deletion only on read. | Server responds 201 with a UUID‑v4 ID; stored data is immutable until deletion. |
| FR‑4 | **Link Construction** | Frontend builds URL `https://<host>/<id>#<base64(key||iv||tag)>`. Fragment never sent to server. | Opening the URL in a new tab yields the same ID and key; no network request contains the key. |
| FR‑5 | **Retrieval & Decryption Endpoint** | `GET /secrets/:id` returns the stored ciphertext blob (or 404 if missing/burned). | Response includes `Content-Type: application/octet-stream` and the exact blob previously stored. |
| FR‑6 | **Client‑Side Decryption & Display** | Browser extracts key/IV/tag from fragment, calls Web Crypto `decrypt`, shows plaintext in a read‑only box with a “Copy” button. | Secret appears correctly; copy button places plaintext on clipboard. |
| FR‑7 | **Burn‑After‑Read** | After successful decryption, frontend sends `DELETE /secrets/:id` (or reuses GET with a `burn=true` flag) to instruct server to delete the stored blob. Server responds 204 and permanently removes the record. | Subsequent GET for same ID returns 410 Gone; no ciphertext persists. |
| FR‑8 | **Error Handling** | - Invalid/missing ID → 404. <br> - Already burned → 410. <br> - Crypto failure → show user‑friendly “Unable to retrieve secret” message. | UI displays appropriate inline error; no stack traces leaked. |
| FR‑9 | **Link Copy & Share** | “Copy Link” button places the full URL (including fragment) on clipboard. | Clipboard contains exact URL; one‑click copy works on desktop and mobile browsers. |
| FR‑10 | **Basic Usage Analytics (opt‑out)** | Anonymized counters: total links created, total successful reads, error rates. No personal data stored. | Metrics endpoint exposed to internal monitoring; GDPR‑compliant (no IPs or user‑agents stored). |
| FR‑11 | **Responsive Design** | UI works on viewport widths ≥320px (mobile) and ≥1024px (desktop). | Layout adjusts; all touch targets ≥44 dp. |

*No user accounts, authentication, password protection, multi‑view, audit UI, or administrative dashboard are required for V1.*  

---

### Security & Architecture  

| Aspect | Decision | Rationale / Details |
|--------|----------|----------------------|
| **Transport Security** | Enforce HTTPS only (TLS 1.2+). HSTS with `max‑age=31536000; includeSubDomains; preload`. | Prevents MITM; satisfies “high” protection requirement. |
| **Encryption at Rest** | Store only the ciphertext blob (already encrypted client‑side). Additionally enable server‑side AES‑256‑GCM encryption of the blob (defense‑in‑depth) using a key managed by the cloud KMS (or equivalent). | Even if storage is compromised, attacker needs both client key (in URL) and server key. |
| **Key Management** | Client‑generated random key never transmitted to server; resides only in URL fragment. Server‑side storage key rotated automatically via KMS. | Guarantees that service operators cannot decrypt secrets. |
| **Data Lifecycle** | 1. Secret encrypted in browser. 2. Ciphertext persisted (with optional server‑side encryption). 3. On first successful read, backend deletes the blob (hard delete). 4. If not read within a configurable window (e.g., 24 h), a background job deletes the blob to prevent orphaned data. | Meets “deletion guarantee” SLA; limits storage growth. |
| **Access Controls** | No authentication; any entity with the URL can read the secret. Access is limited by knowledge of the fragment (key). | Simplicity; matches threat model where secrecy relies on URL confidentiality. |
| **Audit Logging** | Store minimal, anonymized logs for operational debugging: `<timestamp>, <id>, <action (create/read/delete)>, <outcome>, <region>`. No IP, user‑agent, or secret data. Logs retained 7 days, then purged. | Supports secondary audience (general audience) needing basic visibility into service health without exposing secrets. |
| **Dependency Security** | Use Subresource Integrity (SRI) for any third‑party JS/CSS; serve all assets from same origin; CSP `default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; object-src 'none'; base-uri 'self';`. | Reduces XSS risk. |
| **Vulnerability Management** | Dependabot/renovate for automated dependency updates; quarterly manual penetration test; static analysis (SonarQube) in CI. | Ongoing assurance of “secure and reliable”. |

---

### Success Metrics (V1)  

| Metric | Target | Measurement Method |
|--------|--------|---------------------|
| **Link Availability (Uptime)** | ≥ 99.9 % monthly | Synthetic probe every 5 min from multiple regions; count successful HTTP 200 on health endpoint. |
| **Read Latency** | ≤ 200 ms 95th percentile (from request to decrypted secret displayed) | Browser‑side performance timing (navigationStart → secret displayed) aggregated via beacon to internal analytics. |
| **Burn‑After‑Read Reliability** | ≥ 99.9 % of successful reads result in immediate deletion (verified by follow‑up GET returning 410) | Server logs count of delete actions vs. read actions; alert on deviation >0.1 %. |
| **Error Rate** | ≤ 0.1 % of requests (4xx/5xx excluding expected 404/410 for burned links) | API gateway metrics. |
| **User Satisfaction** | NPS ≥ 30 (post‑release survey) | In‑app optional survey after successful secret retrieval. |
| **Adoption** | ≥ 1 000 secrets shared in first 4 weeks | Counter of created links stored in analytics. |
| **Security Incidents** | 0 confirmed plaintext leaks | External bug bounty program + internal review; any incident triggers immediate P1 response. |

---

### Out of Scope (V1)  

- User accounts, login, or any form of authentication.  
- Passphrase‑protected secrets (the key is always URL‑fragment based).  
- Multi‑read or “view‑N‑times” modes.  
- Administrative dashboard for viewing logs, metrics, or managing secrets (beyond basic health endpoint).  
- API keys or programmatic access for bulk secret creation.  
- Custom branding, white‑labeling, or mandatory sub‑domain (service can run on any domain the operator chooses).  
- Compliance reporting exports (SOC 2, ISO 27001, etc.) – though logs are retained for operational debugging.  
- Integration with external secret vaults (AWS Secrets Manager, HashiCorp Vault, etc.).  
- Rate limiting or CAPTCHA (to be added later if abuse observed).  

---

### Next Steps  

1. **Technical Spike (1 wk)**  
   - Prove client‑side AES‑GCM encryption/decryption using Web Crypto API across target browsers (Chrome, Firefox, Safari, Edge).  
   - Verify that URL fragment never leaves browser (network inspection).  

2. **Architecture Decision (2 days)**  
   - Choose backend language/runtime (e.g., Go 1.22 or Node.js 20) based on team expertise.  
   - Select storage: Redis with `EXPIRE` on read (or PostgreSQL with `DELETE` trigger).  
   - Choose cloud provider (AWS, GCP, Azure) – no preference expressed; default to current company VPC.  

3. **Backend Development (2 wks)**  
   - Implement `/secrets` POST (store) and GET/DELETE (retrieve & burn) endpoints.  
   - Add server‑side encryption of blobs via KMS envelope encryption.  
   - Implement background TTL cleanup job (e.g., every hour).  
   - Add structured logging (JSON) to stdout for log‑aggregation.  

4. **Frontend Development (2 wks)**  
   - Build React (or Vue) app with the UI described in FR‑1/FR‑9.  
   - Integrate Web Crypto encryption/decryption helpers.  
   - Add URL parsing, copy‑to‑clipboard, and error UI.  
   - Write unit tests (Jest/Vitest) and e2e tests (Cypress/Playwright).  

5. **Security Review (1 wk)**  
   - Threat model walkthrough (STRIDE).  
   - Verify CSP, SRI, HSTS headers.  
   - Conduct dependency scan and manual pen‑test on staging.  

6. **Performance & Load Testing (1 wk)**  
   - Simulate 10k concurrent link creations and reads using k6/Locust.  
   - Validate latency and availability targets.  

7. **Beta Release & Monitoring (1 wk)**  
   - Deploy to a canary sub‑domain (e.g., `beta.secrets.example.com`).  
   - Enable internal dogfooding; collect NPS and error metrics.  
   - Adjust TTL cleanup window based on observed usage.  

8. **General Availability Launch**  
   - Promote to production domain.  
   - Publish short developer guide (README) and embeddable badge for docs.  
   - Set up alerting (latency >200 ms, error rate >0.1 %, deletion failure).  

**Assumptions made where answers were ambiguous**  
- Q4 “yes” interpreted as a requirement for **client‑side encryption** (the stronger option).  
- Q2 “yes, general audience” interpreted as the **secondary audience being the recipients of the secret link** (non‑developers who will view the secret).  
- No explicit constraints on hosting, domains, or branding → we assume a flexible, cloud‑agnostic deployment with HTTPS only.  

With these decisions, the PRD is now concrete, unambiguous, and ready for the engineering team to begin implementation.