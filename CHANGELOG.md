# Changelog

All notable changes to Theek Karo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive README with architecture diagram and full documentation
- CONTRIBUTING.md with detailed development guidelines
- Issue and PR templates for GitHub
- Social preview image for repository sharing
- CHANGELOG.md to track releases

### Changed
- Updated repository description and topics on GitHub

## [0.9.0] - 2026-08-20

### Added
- **Maps v2 & Evidence v2**
  - Real tile basemap behind marker/cluster API
  - Heatmap data endpoint for density visualization
  - Timeline data endpoint for chronological views
  - Video evidence support (MP4/QuickTime/WebM)
  - Before/after evidence pair support
  - Tamper-evident SHA-256 evidence chain
  - Frontend evidence chain and report media API client

- **i18n Full (15 Languages)**
  - All 15 Indian languages registered: English, Hindi, Bengali, Telugu, Marathi, Tamil, Gujarati, Kannada, Malayalam, Odia, Punjabi, Assamese, Urdu, Maithili, Sindhi
  - English + Hindi fully translated (400+ keys each)
  - Community translation architecture ready
  - Language registry with fallback chains

- **AI & Civic Assistant Polish**
  - Conversation history API (create, list, get messages, save)
  - Official persona deep-dive tool
  - Source freshness tracking tool
  - Department context integration
  - Multi-turn conversation context in prompts
  - Frontend conversation API client methods

- **Agentic Capabilities (V2)**
  - Triage agent with 5-minute SLA
  - Batch triage support with confidence scoring
  - Recidivism analytics (180-day window)
  - ML moderation assist (10 categories, advisory only)
  - 6 new API endpoints under `/api/v1/ai/`

- **Hardening & Release**
  - Privacy notice v2 (full DPDP Act 2023 compliance)
  - MFA enforcement validation endpoint
  - SLO validation endpoint (p95 latency + error rate)
  - Security health endpoint improvements

### Changed
- Enhanced evidence chain with tamper-evident hashing
- Improved AI conversation context handling
- Updated frontend evidence display components

### Fixed
- Security health endpoint (NULL expires_at handling)
- Enum comparison issues in security checks

## [0.8.0] - 2026-08-19

### Added
- **Security, Privacy, Trust & Compliance (Phase 28)**
  - Security incidents tracking system
  - IP blocking and rate limiting
  - Abuse detection engine
  - Input validation framework
  - Data classification system
  - SSRF protection
  - Prompt injection protection
  - Security audit logging
  - Security health monitoring
  - Enhanced security headers
  - 15 API endpoints under `/api/v1/security/`
  - 24 dedicated security tests

- **Production Readiness (Phase 29)**
  - Caching layer with Redis
  - Performance budgets and monitoring
  - Cost tracking and optimization
  - SLO monitoring and alerting
  - Health check endpoints
  - Database optimization
  - Pagination improvements
  - Capacity planning tools
  - 10 API endpoints under `/api/v1/production/`
  - 30 dedicated production tests

- **Production Deployment (Phase 30)**
  - GitHub Actions CI/CD pipelines
  - Terraform Infrastructure as Code
  - ECS Fargate deployment configuration
  - RDS PostgreSQL setup
  - ElastiCache Redis configuration
  - S3/CloudFront CDN setup
  - Smoke test suite
  - 7 operational runbooks
  - Go-live checklist
  - Release process documentation
  - 21 dedicated deployment tests

### Changed
- Improved security headers middleware
- Enhanced rate limiting across all endpoints
- Updated CI/CD pipeline with security scanning

### Fixed
- CI pipeline reliability issues
- Deployment pipeline error handling

## [0.7.0] - 2026-08-18

### Added
- **AI Platform (Phase 27)**
  - AI Gateway with provider-neutral abstraction
  - 10 specialized AI agents
  - 10 reusable AI skills
  - 3 multi-agent workflows
  - 13 golden evaluation test cases
  - Safety agent with circuit breaker
  - Model router with cost optimization
  - Prompt registry and versioning
  - 20+ API endpoints under `/api/v1/ai-platform/`
  - 61 dedicated AI tests

- **Government Workflow Platform (Phase 25)**
  - Routing rules engine
  - Case routing with confidence scoring
  - Case handoff workflow
  - Official responses with versioning
  - Configurable workflow definitions
  - Government integration adapter
  - External case references
  - Sync run tracking
  - Dashboard analytics
  - Work queue management
  - 20+ API endpoints under `/api/v1/government/`
  - 14 dedicated government tests

- **Communication & Notification (Phase 26)**
  - Provider abstraction layer
  - Delivery pipeline with retry/dead-letter
  - Public alerts lifecycle
  - Template versioning
  - User device management
  - Campaign communication
  - Analytics and provider health
  - 18+ API endpoints under `/api/v1/communication/`
  - 10 dedicated communication tests

- **Data Trust & Provenance (Phase 23)**
  - Evidence registry with integrity hashing
  - Verification records (append-only)
  - Data quality engine (7 dimensions)
  - Conflict detection and resolution
  - Dispute management
  - Change history tracking
  - Provenance chain
  - Metric definitions catalog
  - Data quarantine system
  - Source health monitoring
  - 15 API endpoints under `/api/v1/data-trust/`
  - 23 dedicated data trust tests

- **Identity & Organization (Phase 24)**
  - User profiles with privacy controls
  - User preferences system
  - Identity verification framework (7 types)
  - Organization identity and membership
  - Institution claims workflow
  - Representative assignments
  - Identity provider links
  - Account status history
  - 18 API endpoints under `/api/v1/identity/`
  - 26 dedicated identity tests

### Changed
- Enhanced RBAC with government and organization permissions
- Improved audit logging across all modules
- Updated API router with new endpoints

## [0.6.0] - 2026-08-18

### Added
- **Community Confirmation (Phase 15)**
  - Two-confirmer gate for resolution closure
  - Citizen follow-up signals (observed improvement / issue still exists)
  - Reopen signal queue with human review
  - Analytics for community confirmations
  - 7 dedicated community confirmation tests

- **Security Hardening (Phase 16)**
  - MFA with TOTP (RFC 6238 verified)
  - Per-account login backoff
  - Authorization audit suite
  - IDOR protection tests
  - Upload security improvements
  - Object storage audit
  - PII inventory and retention purge
  - Database pool optimization
  - Disaster recovery and restore testing
  - Redis/queue reliability
  - AI safety measures
  - Observability improvements
  - Frontend security hardening
  - CI dependency audits
  - India-scale readiness validation
  - k6 SLO smoke tests (p95 11.9ms)

### Changed
- Enhanced security headers middleware
- Improved rate limiting
- Updated authentication flow with MFA support

### Fixed
- Flaky test issues in community harness
- Notification quiet-hours determinism
- Login throttle edge cases

## [0.5.0] - 2026-08-17

### Added
- **Community & Civic Participation (Phase 18)**
  - Civic initiatives with full lifecycle
  - Volunteer system with privacy-safe profiles
  - Community groups with moderation
  - Deterministic badges system
  - Initiative follows and observations
  - AI community tools (summarize, relate, recommend)
  - 20+ API endpoints under `/api/v1/community/`
  - 13 dedicated community tests
  - Community guidelines and moderation docs

- **Government Data Integration (Phase 10)**
  - UDISE+, NHP, CCTNS, eCourts, PMGSY connectors
  - SSRF protection
  - CSV formula sanitization
  - PII scrubbing
  - Multi-signal entity matching
  - Rule-based discrepancy engine
  - Digital Twin comparative matrix

- **AI Intelligence & RAG (Phase 11)**
  - Provider-neutral AI abstraction
  - Model router with PII scrubbing
  - Prompt injection defense
  - Read-only domain tools
  - Access-controlled hybrid RAG
  - Agent orchestrator with audit
  - Civic assistant chat (14 languages)
  - Citations tray

- **Analytics & Dashboards (Phase 12)**
  - Metric catalog and registry
  - Time-series aggregations
  - Category rollups
  - Resolution integrity and velocity
  - Backlog aging buckets
  - Multi-level geographic drilldowns
  - Data quality scorecards
  - AI cost and token telemetry
  - CSV/JSON export with privacy protection
  - Public analytics dashboard
  - Admin command center

### Changed
- Enhanced report lifecycle with community confirmation
- Improved evidence chain with tamper detection
- Updated frontend with new community features

## [0.4.0] - 2026-08-17

### Added
- **Departments & Civic Cases (Phase 14)**
  - Department registry with verification
  - Organization membership and roles
  - Case lifecycle FSM (18 statuses)
  - Assignment history tracking
  - SLA policies with weighted matching
  - SLA clocks with pause/resume
  - Escalation engine (manual + automatic)
  - Worker sweep for SLA evaluation
  - Resolution workflow with evidence review
  - Independent reviewer validation
  - Department-scoped access control
  - 9 dedicated Phase-14 API tests

- **Community & Moderation (Phase 13)**
  - Feed ranking and tabs
  - Threaded comments (depth ≤ 2)
  - Moderation queue with appeals
  - Reactions and saves
  - Follows and blocks
  - Public profiles
  - Share previews
  - Notification grouping

- **Maps, GIS & Location (Phase 9)**
  - PostGIS bounding-box queries
  - Spatial clustering
  - Haversine nearby discovery
  - Forward and reverse geocoding
  - Geographic aggregation summaries
  - Density heatmap
  - MapExplore component

### Changed
- Enhanced report lifecycle with negative states
- Improved evidence upload with scan gate
- Updated frontend with map features

## [0.3.0] - 2026-08-16

### Added
- **Authentication & Authorization (Phase 7)**
  - Argon2id password hashing
  - Single-use token hashes
  - Session tracking and revocation
  - 9-role RBAC system
  - Fine-grained permission keys
  - IDOR protection
  - Google OAuth integration
  - DPDP account anonymization
  - Security pages

- **Civic Reporting & Media (Phase 8)**
  - Draft lifecycle management
  - Observation vs submission timestamps
  - Coordinate source tracking
  - Media upload slots with SHA-256 verification
  - Trust scoring and auto-promotion
  - Heuristic duplicate detection
  - AI-assisted intake (suggest-only)
  - SubmitWizard and ReportDetail components

- **Government Data Integration (Phase 10)**
  - Official data connectors
  - Provenance tracking
  - Discrepancy detection

### Changed
- Enhanced report schema with new fields
- Improved media pipeline with security checks
- Updated API with idempotency keys

## [0.2.0] - 2026-08-16

### Added
- **Database & Schema (Phase 3)**
  - 95 tables with PostGIS geometry
  - Identity and authentication tables
  - Geography registry (12-level hierarchy)
  - Institution digital twins
  - Provenance-typed data fields
  - Category and issue type registry
  - Report lifecycle with state machine
  - Evidence and media pipeline
  - Community and moderation tables
  - Resolution and reputation system
  - Subscription and notification tables
  - i18n content tables
  - AI and RAG tables
  - Analytics tables

- **Backend Foundation (Phase 5)**
  - FastAPI modular monolith
  - Core pagination and sorting
  - RFC 9457 error handling
  - Correlation middleware
  - Geography hierarchy APIs
  - Institution digital twins
  - Civic issue types
  - Report lifecycle FSM
  - Multi-domain search
  - Centralized router registry

- **Frontend Foundation (Phase 6)**
  - Next.js 16 App Router
  - React 19 with TypeScript
  - Tailwind CSS v4
  - Modular API client
  - AppShell component
  - GlobalSearch
  - Dynamic geography navigation
  - Institutions Digital Twin
  - Reports feed and detail
  - Submit wizard flow
  - Map abstraction
  - Profile pages
  - i18n (14 languages)
  - WCAG 2.2 AA accessibility

### Changed
- Initialized project structure
- Set up development environment
- Configured CI/CD pipeline

## [0.1.0] - 2026-08-16

### Added
- Initial project setup
- Repository structure
- Docker Compose configuration
- Development documentation
- Architecture decision records

---

## Release Notes

### Version 0.9.0 Highlights

This release completes Cycle 2 Phase 1 product scope:

- **15 Languages**: All major Indian languages registered with English + Hindi fully translated
- **Agentic AI**: Triage agents with SLA, recidivism analytics, ML moderation
- **Evidence Chain**: Tamper-evident SHA-256 hashing for all evidence
- **Privacy Compliance**: Full DPDP Act 2023 privacy notice

### Version 0.8.0 Highlights

Production readiness and security hardening:

- **532 Tests**: Comprehensive test suite with security and deployment tests
- **CI/CD**: GitHub Actions pipelines for build, test, and deployment
- **Infrastructure**: Terraform IaC for AWS (ECS, RDS, ElastiCache, S3)
- **SLOs**: p95 latency < 500ms, error rate < 1%

### Version 0.7.0 Highlights

Enterprise features and government integration:

- **AI Platform**: 10 specialized agents, 10 skills, 3 workflows
- **Government Workflows**: Routing, handoffs, official responses
- **Data Trust**: Evidence registry, verification, quality scoring
- **Communication**: Multi-channel delivery with retry/dead-letter

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
