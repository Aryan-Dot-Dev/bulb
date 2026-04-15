# Security Threat Model & Architecture  
**Application:** One‑time‑secret sharing service (client‑side‑encrypted, self‑destructing link)  
**Version:** V1 (MVP)  
**Prepared for:** Security Engineers, Developers, Operations  
**Date:** 2025‑09‑16  

---  

## 1. Executive Summary  

| Item | Description |
|------|-------------|
| **Application overview** | A stateless web service that lets any user create a URL containing an encrypted secret. The secret is encrypted in the browser with a random AES‑GCM key; only the ciphertext is stored server‑side. The decryption key lives exclusively in the URL fragment, never transmitted to the server. After the first successful read the server deletes the ciphertext (burn‑after‑read). |
| **Key security goals** | • Confidentiality of the secret (only holder of the URL fragment can decrypt). <br>• Integrity & authenticity of stored ciphertext (tamper‑evident via AES‑GCM tag). <br>• Guaranteed deletion after read (no residual plaintext or ciphertext). <br>• Minimal data collection (no PII, no logs containing secret material). |
| **Top risks (severity)** | 1. **URL leakage** – secret exposed if the link is intercepted, logged, or shared unintentionally. **(High)** <br>2. **Client‑side crypto misuse** – weak IV, reuse of keys, or incorrect Web Crypto usage leading to plaintext recovery. **(Medium)** <br>3. **Server‑side storage compromise** – attacker gains read access to stored blobs; without the client key they cannot decrypt, but could attempt brute‑force or side‑channel attacks. **(Medium)** <br>4. **Replay / burn‑failure** – delete request fails or is skipped, leaving ciphertext accessible for a second read. **(Low)** <br>5. **Denial‑of‑service via storage exhaustion** – abusive creation of many secrets fills storage. **(Low)** |
| **Risk acceptance recommendations** | • Accept URL‑leakage risk as inherent to the threat model; mitigate via user education, short‑lived TTL cleanup, and referral‑policy headers. <br>• Treat client‑side crypto misuse as a development‑time risk; enforce via code review, automated tests, and CSP/SRI. <br>• Accept storage‑compromise risk because encryption is client‑side; still enforce server‑side envelope encryption as defense‑in‑depth. |
| **Overall security posture** | **Strong** – confidentiality relies on client‑side encryption and URL fragment secrecy; no authentication surface; minimal data retention; defense‑in‑depth layers (TLS, HSTS, server‑side envelope encryption, CSP, SRI). Continuous monitoring and automated dependency updates keep the posture current. |

---  

## 2. Threat Modeling  

### 2.1 Data Flow Diagram (DFD) – Trust Boundaries  

```
+-------------------+          HTTPS/TLS 1.2+          +-------------------+
|   Browser (User)  | <------------------------------> |   Edge / LB     |
|  (Trust Boundary) |                                 | (TLS termination)|
+-------------------+          HTTPS/TLS 1.2+          +-------------------+
                                   |                           |
                                   v                           v
                         +-------------------+       +-------------------+
                         |   API Gateway     |       |   WAF (optional)  |
                         +-------------------+       +-------------------+
                                   |                           |
                                   v                           v
                         +-------------------+       +-------------------+
                         |   Backend Service |       |   KMS / HSM       |
                         | (Secrets API)    |<----->| (Envelope Key)    |
                         +-------------------+       +-------------------+
                                   |                           |
                                   v                           v
                         +-------------------+       +-------------------+
                         |   Data Store      |       |   Audit Log Store |
                         | (Redis/Postgres)  |       | (Append‑only)     |
                         +-------------------+       +-------------------+
```

*Trust boundaries*: Browser ↔ Network (TLS), Network ↔ Backend (mutual TLS not required – server authenticates via TLS cert), Backend ↔ KMS (IAM role), Backend ↔ Datastore (service account).  

### 2.2 Threat Actors  

| Actor | Motivation | Capability |
|-------|------------|------------|
| **External attacker** (Internet) | Steal secrets, cause disruption, harvest URLs for phishing | Network sniffing, compromised third‑party sites, ability to craft malicious URLs |
| **Insider / privileged operator** | Curiosity, sabotage, data exfiltration | Access to logs, backend, KMS, ability to modify code |
| **Competitor / abusive user** | Exhaust storage, cause denial‑of‑service | Automated scripts to create many secrets |
| **Malicious recipient** (general audience) | Re‑share secret, retain copy | Can copy URL, forward to others |

### 2.3 Attack Vectors & Entry Points  

| Vector | Description | Mitigation |
|--------|-------------|------------|
| **URL leakage via Referer header** | Browser sends full URL (including fragment) as Referer when navigating to third‑party sites. | Set `Referrer-Policy: origin-when-cross-origin` or `no-referrer-when-downgrade`; educate users not to paste links into untrusted fields. |
| **Logging of URLs** | Proxies, CDNs, WAFs may log full URLs (including fragment) inadvertently. | Ensure logging strips fragment; configure CDN/WAF to omit query strings/fragments; retain only path. |
| **Man‑in‑the‑middle (MITM)** | Attacker intercepts TLS traffic. | Enforce TLS 1.2+, HSTS with preload, certificate pinning optional. |
| **Cross‑site scripting (XSS)** | Malicious JS steals fragment from `location.hash` and exfiltrates. | CSP `script-src 'self'`, `object-src 'none'`, `base-uri 'self'`, SRI for third‑party assets, sanitize any user‑generated content (none in V1). |
| **Cross‑site request forgery (CSRF)** | Attacker forces victim’s browser to call `/secrets/:id` (GET) or DELETE. | Stateless endpoints; rely on same‑origin policy; no cookies used for auth; CSRF token not required but can add SameSite cookie for any future auth. |
| **Client‑side crypto flaws** | Re‑using IV, weak key generation, incorrect handling of tag. | Use Web Crypto `getRandomValues` for key and IV; AES‑GCM with 96‑bit IV; verify tag on decryption; unit‑test crypto helpers. |
| **Server‑side storage breach** | Attacker reads ciphertext blobs. | Defense‑in‑depth: envelope encrypt blobs with KMS‑managed DEK; rotate DEK regularly; restrict IAM to least privilege. |
| **Delete‑failure / race condition** | Delete request lost or delayed; second read succeeds. | Use atomic `GETANDDELETE` (or `GET` with conditional delete) backed by transactional store (Redis `GETDEL` or PostgreSQL `DELETE RETURNING`). |
| **Denial‑of‑service via storage exhaustion** | Bulk secret creation fills disk. | Background TTL job (e.g., 24 h) deletes unread secrets; rate‑limit per IP can be added later if abuse observed. |
| **Side‑channel timing** | Measuring decryption time to infer key bits. | Use constant‑time Web Crypto operations (built‑in); avoid early‑exit on tag verification failures. |
| **Supply‑chain compromise** | Malicious third‑party JS/CSS injects key exfiltration. | SRI hashes for all external resources; CSP restricts sources; lock dependency versions; automated vulnerability scanning. |

### 2.4 Threat Scenarios (Critical Workflows)  

| Scenario | Steps | Impact | Likelihood | Risk Rating |
|----------|-------|--------|------------|-------------|
| **T1 – URL leaked via Referer** | User shares secret link on a public forum; forum software logs Referer header with full URL; attacker harvests URL from logs. | Secret disclosed → confidentiality breach. | Medium (common in forums) | **High** |
| **T2 – XSS steals fragment** | Malicious ad injects script that reads `location.hash` and sends to attacker server. | Secret disclosed. | Low (CSP/SRI in place) | **Medium** |
| **T3 – Insider reads logs** | Operator with access to log aggregation views raw logs containing URLs (if fragment not stripped). | Potential secret exposure. | Low (logging policy) | **Medium** |
| **T4 – Storage compromise + brute‑force** | Attacker obtains backup of encrypted blobs; attempts offline brute‑force of client key (256‑bit). | Computationally infeasible → negligible impact. | Very Low | **Low** |
| **T5 – Delete failure (race)** | Network glitch prevents DELETE after GET; second user reads same ciphertext. | Secret read twice → violates burn‑after‑read guarantee. | Low (idempotent delete) | **Medium** |
| **T6 – DoS via secret flood** | Bot creates 1M secrets; storage fills; legitimate users get 503. | Service unavailable. | Low (rate‑limit not yet) | **Low** (mitigated by TTL cleanup) |
| **T7 – MITM on HTTP (mis‑config)** | Operator accidentally serves HTTP; attacker sniffes ciphertext + key (if key sent via query). | Secret disclosed. | Very Low (enforced HTTPS/HSTS) | **Low** |

---  

## 3. Asset Inventory  

| Asset | Description | Classification | Sensitivity | Protection Requirements |
|-------|-------------|----------------|-------------|--------------------------|
| **Secret plaintext** (user‑provided) | Text ≤10 KB entered in textarea. | Confidential (user‑defined) | **High** (depends on user) | Must never leave browser in plaintext; encrypted client‑side; destroyed after read. |
| **Ciphertext blob** (AES‑GCM output) | Encrypted secret + IV + tag stored server‑side. | Internal (encrypted) | **Medium** (only useful with client key) | Store encrypted at rest (envelope encryption); immutable until deletion; access limited to API. |
| **Client‑side key material** (key‖IV‖tag) | Random 256‑bit key, 96‑bit IV, 128‑bit tag, base64‑encoded in URL fragment. | Confidential (only known to creator & recipient) | **High** | Never transmitted to server; must stay in URL fragment; protected by TLS; not logged. |
| **URL (path + fragment)** | `https://host/<id>#<base64(key||iv||tag)>`. | Internal (path) + Confidential (fragment) | **High** (fragment) | Path may be logged; fragment must be omitted from logs, Referer, etc. |
| **API endpoints** (`POST /secrets`, `GET /secrets/:id`, `DELETE /secrets/:id`) | Stateless REST‑like interface. | Public (exposed) | **Low** (no auth) | Must enforce TLS, rate‑limit (future), input validation, proper HTTP status codes. |
| **Backend service code & config** | Go/Node binary, env vars, KMS credentials. | Internal | **Medium** | Secure build pipeline, secrets management, least‑privilege IAM. |
| **Datastore (Redis/Postgres)** | Holds ciphertext blobs with TTL. | Internal | **Medium** | Encrypted at rest (envelope), access restricted to service account, backups encrypted. |
| **Audit log store** | Timestamp, ID, action, outcome, region (no IPs, no UA). | Internal | **Low** (no PII) | Retention 7 days, encrypted at rest, access‑controlled. |
| **KMS / HSM keys** | Master key used to encrypt DEK for envelope encryption. | Secret | **High** | Rotated automatically, access limited to service role, hardware‑backed if possible. |
| **Third‑party dependencies** (libraries, CDN assets) | External JS/CSS, npm/go modules. | Internal | **Medium** | SRI hashes, CSP, SBOM, dependency scanning. |
| **Monitoring & alerting system** | Metrics, logs, alerts. | Internal | **Low** | No secret data; ensure no accidental logging of fragments. |

---  

## 4. Vulnerability Assessment  

### 4.1 OWASP Top 10 (2021) Mapping  

| OWASP Category | Relevance to V1 | Status / Mitigation |
|----------------|----------------|---------------------|
| **A01:2021 – Broken Access Control** | No auth; access relies on URL fragment. | Ensure fragment never leaked; enforce Referrer‑Policy; no insecure direct object references (ID is random UUID). |
| **A02:2021 – Cryptographic Failures** | Client‑side AES‑GCM; server‑side envelope encryption. | Use Web Crypto API correctly; random key/IV; verify tag; server‑side envelope encryption with KMS; rotate DEK. |
| **A03:2021 – Injection** | No SQL/NoSQL injection surface (simple key‑value store). | Use parameterized queries / Redis commands; validate UUID format. |
| **A04:2021 – Insecure Design** | Reliance on URL secrecy; burn‑after‑read guarantee. | Threat model performed; TTL cleanup; delete‑atomic operation; UI guidance. |
| **A05:2021 – Security Misconfiguration** | TLS, HSTS, CSP, SRI, logging. | Enforce HTTPS only; HSTS preload; CSP strict; SRI for assets; disable directory listing; least‑privilege IAM. |
| **A06:2021 – Vulnerable & Out‑of‑Date Components** | Dependencies (framework, crypto libs). | Dependabot/Renovate; quarterly manual pen‑test; SBOM generation. |
| **A07:2021 – Identification and Authentication Failures** | N/A (no auth). | N/A. |
| **A08:2021 – Software and Data Integrity Failures** | Potential supply‑chain attack via CDN/JS. | SRI hashes; CSP `script-src 'self'`; code signing for internal builds; verify integrity of container images. |
| **A09:2021 – Security Logging and Monitoring Failures** | Minimal audit logs; no secret data. | Structured JSON logs; retention 7 days; alert on anomalous delete/failure rates. |
| **A10:2021 – Server‑Side Request Forgery (SSRF)** | No outbound HTTP calls from backend (except to KMS via IAM). | Restrict outbound network; use IAM roles; validate any user‑provided URLs (none). |

### 4.2 Common Weakness Enumeration (CWE) Highlights  

| CWE-ID | Description | Relevance | Mitigation |
|--------|-------------|-----------|------------|
| CWE-200 | Exposure of Sensitive Information to an Unauthorized Actor | URL fragment leakage, logging | Referrer‑Policy, strip fragment from logs, educate users |
| CWE-326 | Inadequate Encryption Strength | AES‑GCM‑256 with random key | Use Web Crypto `getRandomValues`; verify tag |
| CWE-327 | Use of a Broken or Risky Cryptographic Algorithm | None (AES‑GCM approved) | N/A |
| CWE-330 | Use of Insufficiently Random Values | Key/IV generation | Web Crypto `getRandomValues` (CSPRNG) |
| CWE-352 | Cross‑Site Request Forgery | Stateless endpoints, no cookies | SameSite cookie if any auth added; rely on origin |
| CWE-79 | Improper Neutralization of Input During Web Page Generation (XSS) | Potential via CSP bypass | CSP `script-src 'self'`, SRI, sanitize any user‑generated HTML (none) |
| CWE-22 | Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal') | Not applicable (no file upload) | N/A |
| CWE-613 | Insufficient Session Expiration | No sessions | N/A |
| CWE-798 | Use of Hard‑coded Credentials | None (secrets via KMS/IAM) | Secrets management, no hardcoded keys |
| CWE-284 | Improper Access Control | Access via URL only | Ensure UUID unguessable; rate‑limit creation if abuse observed |

### 4.3 Known Vulnerabilities in Proposed Tech Stack  

| Component | Typical CVEs (as of 2024‑09) | Mitigation |
|-----------|-----------------------------|------------|
| **Go 1.22** | Occasional stdlib issues (e.g., CVE‑2022‑XXXXX in net/http) | Keep Go version updated via Dependabot; monitor CVE feeds. |
| **Node.js 20** | Periodic vulnerabilities in dependencies (e.g., lodash, minimist) | Lock versions; run `npm audit`; use `package-lock.json`. |
| **Redis 7** | CVE‑2022‑XXXXX ( Lua sandbox escape ) – only if Lua scripting