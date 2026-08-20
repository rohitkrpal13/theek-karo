# Security Policy

Theek Karo is committed to ensuring the security and privacy of our users and their data. We appreciate your efforts to responsibly disclose security vulnerabilities.

## 📋 Table of Contents

- [Supported Versions](#supported-versions)
- [Reporting a Vulnerability](#reporting-a-vulnerability)
- [Scope](#scope)
- [Response Timeline](#response-timeline)
- [Safe Harbor](#safe-harbor)
- [Disclosure Policy](#disclosure-policy)
- [Recognition](#recognition)
- [Security Measures](#security-measures)
- [Contact](#contact)

## Supported Versions

| Version | Supported | End of Life |
|---------|-----------|-------------|
| 0.9.x (latest) | ✅ | Active development |
| 0.8.x | ✅ | Until next major release |
| < 0.8.0 | ❌ | Upgrade recommended |

We provide security updates for the latest two minor versions. Please upgrade to the most recent version before reporting.

## Reporting a Vulnerability

### ⚠️ Important: Do NOT report security vulnerabilities through public GitHub issues

Instead, please report them through one of the following channels:

### 1. GitHub Security Advisories (Preferred)

**[Report Vulnerability via GitHub](https://github.com/rohitkrpal13/theek-karo/security/advisories/new)**

This is the most secure and preferred method. GitHub will encrypt your report and keep it confidential until a fix is available.

### 2. Email

**Email:** [security@theek-karo.dev](mailto:security@theek-karo.dev)

**PGP Key:** [Download Public Key](https://theek-karo.dev/.well-known/security.txt)

For email reports, please use our PGP key to encrypt sensitive information.

### 3. Bug Bounty Program

We're planning a bug bounty program. Stay tuned for details!

## Scope

### ✅ In Scope

The following are eligible for bounty rewards:

**Critical Severity**
- Remote code execution
- SQL injection
- Authentication bypass
- Privilege escalation to admin/superadmin
- Full account takeover
- Data exfiltration of user PII
- SSRF leading to internal network access

**High Severity**
- Stored XSS in user-generated content
- CSRF on sensitive actions (account deletion, role changes)
- IDOR exposing other users' private data
- File upload leading to code execution
- Business logic flaws allowing data manipulation
- API rate limiting bypass
- Session fixation/hijacking

**Medium Severity**
- Reflected XSS
- Information disclosure (stack traces, debug info)
- Missing security headers
- Insecure direct object references (limited exposure)
- Weak password policy
- Missing input validation

**Low Severity**
- Version disclosure
- Missing HTTP security headers (non-critical)
- Information leakage in error messages
- Clickjacking (if frameable)

### ❌ Out of Scope

The following are NOT eligible for bounty rewards:

- Vulnerabilities in third-party dependencies (report to upstream)
- Issues requiring physical access to devices
- Social engineering attacks
- Denial of service (DoS) attacks
- Issues in staging/dev environments
- Self-XSS (only affects the attacker)
- Issues already known or reported
- Missing security features not in scope
- Rate limiting on public endpoints (by design)
- Open redirect on login pages (acceptable for OAuth flows)

## Response Timeline

| Severity | Initial Response | Fix Timeline | Disclosure |
|----------|------------------|--------------|------------|
| **Critical** | 24 hours | 7 days | 30 days |
| **High** | 48 hours | 14 days | 45 days |
| **Medium** | 5 business days | 30 days | 60 days |
| **Low** | 10 business days | 90 days | 90 days |

### What to Expect

1. **Acknowledgment**: We'll confirm receipt of your report within the timeline above
2. **Triage**: We'll assess severity and validity
3. **Updates**: We'll provide status updates at least every 7 days
4. **Fix**: We'll develop and test a fix
5. **Disclosure**: We'll coordinate public disclosure with you
6. **Bounty**: We'll process your reward (if applicable)

## Safe Harbor

### We Support Responsible Disclosure

We will not pursue legal action against researchers who:

- Make a good faith effort to avoid privacy violations, data destruction, or service disruption
- Only interact with accounts you own or with explicit permission of the account holder
- Stop testing and report immediately once you've confirmed a vulnerability
- Do not exploit vulnerabilities beyond what's necessary to prove the issue
- Do not access, modify, or delete data belonging to other users
- Do not perform actions that could harm the platform or its users
- Comply with all applicable laws and regulations

### Conditions

- You must report the vulnerability to us before making it public
- You must give us reasonable time to fix the issue before disclosure
- You must not access or download more data than necessary to prove the vulnerability
- You must not use automated scanning tools that could impact service availability
- You must not perform destructive testing

### Legal Protection

We will not:
- Pursue civil litigation against security researchers
- Report you to law enforcement for good-faith security research
- Ask for compensation for the vulnerability report

We reserve the right to take legal action against researchers who:
- Act in bad faith
- Violate user privacy
- Cause service disruption
- Exceed the scope of this policy

## Disclosure Policy

### Coordinated Disclosure

We follow coordinated disclosure practices:

1. **Report**: You report the vulnerability to us
2. **Acknowledge**: We acknowledge receipt and begin triage
3. **Fix**: We develop and test a fix
4. **Coordinate**: We work with you on public disclosure timing
5. **Disclose**: We publish a security advisory after the fix is released
6. **Credit**: We credit you in the disclosure (unless you prefer anonymity)

### Disclosure Timeline

- We aim to disclose within 30 days of the fix being released
- We will coordinate with you on the exact timing
- You may disclose after we've had 30 days to address the issue
- We may request an extension for complex fixes (maximum 90 days total)

### Public Disclosure Format

When we disclose, we will:
- Publish a GitHub Security Advisory
- Credit the reporter (with permission)
- Describe the vulnerability and its impact
- Provide remediation guidance
- Include upgrade instructions

## Recognition

### Hall of Fame

We recognize security researchers who help improve our security:

| Researcher | Vulnerability | Severity | Date |
|------------|---------------|----------|------|
| *No reports yet* | — | — | — |

### Rewards (Planned)

We're developing a bug bounty program with the following tiers:

| Severity | Reward |
|----------|--------|
| Critical | $500 - $2,000 |
| High | $200 - $500 |
| Medium | $50 - $200 |
| Low | $25 - $50 |
| Informational | Recognition only |

*Note: Bug bounty program coming soon. Until then, we offer public recognition and swag.*

### Eligibility

To qualify for rewards:
- You must be the first to report the vulnerability
- You must follow our responsible disclosure policy
- You must not have violated any laws
- You must not be an employee or contractor of Theek Karo
- You must be at least 18 years old (or have parental consent)

## Security Measures

### What We Protect

**User Data**
- Authentication credentials (hashed with Argon2id)
- Personal identifiable information (PII)
- Location data
- Communication records
- Government identification

**Platform Integrity**
- Report and case data
- Evidence and attachments
- Audit logs
- Analytics data
- System configuration

### Our Security Stack

**Authentication & Authorization**
- JWT tokens with short expiration (15 min)
- Refresh token rotation with reuse detection
- Multi-factor authentication (TOTP)
- Role-based access control (RBAC)
- Permission-key based authorization

**Data Protection**
- Encryption at rest (AES-256)
- Encryption in transit (TLS 1.3)
- Database encryption
- Backup encryption
- Secure key management (AWS Secrets Manager)

**Infrastructure**
- WAF (Web Application Firewall)
- DDoS protection
- Rate limiting
- IP blocking
- Security headers (CSP, HSTS, X-Frame-Options)

**Application Security**
- Input validation and sanitization
- SQL injection prevention (parameterized queries)
- XSS protection (output encoding)
- CSRF protection (tokens)
- Content Security Policy

**Monitoring & Detection**
- Security audit logging
- Intrusion detection
- Anomaly detection
- File upload scanning
- Vulnerability scanning

**Compliance**
- DPDP Act 2023 (India)
- OWASP Top 10 mitigation
- Security headers (OWASP recommendations)
- Regular security assessments

## Contact

### Security Team

- **Email:** [security@theek-karo.dev](mailto:security@theek-karo.dev)
- **PGP Key:** [Download](https://theek-karo.dev/.well-known/security.txt)
- **GitHub:** [Security Advisories](https://github.com/rohitkrpal13/theek-karo/security/advisories)

### Response Hours

We monitor security reports:
- **Critical/High**: 24/7
- **Medium/Low**: Business hours (IST)

### Emergency Contact

For urgent security matters:
- **Email:** [security-urgent@theek-karo.dev](mailto:security-urgent@theek-karo.dev)
- **Phone:** Available upon request for critical vulnerabilities

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [DPDP Act 2023](https://www.meity.gov.in/data-protection-framework)
- [Our Security Architecture](docs/SECURITY.md)

---

**Thank you for helping keep Theek Karo and our users safe!** 🇮🇳

*Last updated: August 2026*
