"""ORM model aggregation point.

Every module with models registers them here so that Alembic autogenerate and
``Base.metadata.create_all`` (tests) see the complete schema.
"""

from tk_api.ai.models import (  # noqa: F401
    AiAnnotation,
    AiCitation,
    AiConversation,
    AiEvaluation,
    AiFeedback,
    AiMessage,
    AiOutput,
    AiReview,
    AiRun,
)
from tk_api.ai_platform.models import (  # noqa: F401
    AiAgentRegistry,
    AiAgentRun,
    AiCostRecord,
    AiEvalResult,
    AiPromptVersion,
    AiSkill,
    AiToolExecution,
    AiTraceSpan,
)
from tk_api.analytics.models import AnalyticsDaily, AnalyticsEvent  # noqa: F401
from tk_api.auth.models import RefreshToken  # noqa: F401
from tk_api.cases.models import (  # noqa: F401
    CaseAction,
    CaseAssignment,
    CaseEscalation,
    CaseReopenRequest,
    CaseResponse,
    CaseStatusHistory,
    CivicCase,
    EscalationRule,
    SlaInstance,
    SlaPause,
    SlaPolicy,
)
from tk_api.civic.models import Campaign, CampaignScope, Category  # noqa: F401
from tk_api.civic_action.models import (  # noqa: F401
    ActionDependency,
    ActionEvidence,
    ActionMilestone,
    ActionPlan,
    ActionReview,
    ActionTask,
    ActionUpdate,
    CampaignInitiativeLink,
    CampaignMember,
    CivicEvent,
    CivicTeam,
    CivicTeamMember,
    EventParticipant,
    ImpactMeasurement,
    ImpactMetric,
    TaskComment,
    VolunteerApplication,
)
from tk_api.communication.models import (  # noqa: F401
    CommAnalytics,
    CommCampaign,
    CommTemplate,
    CommunicationEvent,
    DeliveryRecord,
    DigestRecord,
    PublicAlert,
    UserDevice,
)
from tk_api.community.models import (  # noqa: F401
    Badge,
    Bookmark,
    CategoryFollower,
    CivicInitiative,
    CommunityGroup,
    ContentReport,
    GeographyFollower,
    GroupMember,
    InitiativeFollower,
    InitiativeMember,
    InitiativeObservation,
    InstitutionFollower,
    ModerationAction,
    ModerationAppeal,
    ModerationDecision,
    Post,
    Reaction,
    UserBadge,
    UserBlock,
    UserFollow,
    VolunteerOpportunity,
    VolunteerProfile,
    VolunteerSignup,
)
from tk_api.core.audit import AuditLog  # noqa: F401
from tk_api.data_trust.models import (  # noqa: F401
    DataChangeHistory,
    DataConflict,
    DataPublicationSnapshot,
    DataQualityResult,
    DataQuarantineRecord,
    DisputeRecord,
    EvidenceRecord,
    MetricDefinition,
    SourceHealthSnapshot,
    VerificationRecord,
)
from tk_api.departments.models import (  # noqa: F401
    Department,
    DepartmentCategory,
    DepartmentType,
    DepartmentUser,
    JurisdictionScope,
    OrganizationVerification,
)
from tk_api.geography.models import Geography, GeographyTranslation, GeographyType  # noqa: F401
from tk_api.govdata.models import GovDataset, GovDatasetRecord, GovImportJob  # noqa: F401
from tk_api.government.models import (  # noqa: F401
    BulkOperationLog,
    CaseHandoff,
    CaseRoute,
    ExternalCaseReference,
    GovernmentIntegration,
    OfficialResponse,
    RoutingRule,
    SyncRun,
    WorkflowDefinition,
    WorkflowTransition,
)
from tk_api.identity.models import (  # noqa: F401
    EmailVerification,
    OAuthAccount,
    PasswordResetToken,
    Permission,
    RolePermission,
    SecurityEvent,
    Session,
    UserMfa,
)
from tk_api.identity.profile_models import (  # noqa: F401
    AccountStatusHistory,
    IdentityProviderLink,
    IdentityVerification,
    InstitutionClaim,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    RepresentativeAssignment,
    UserPreferences,
    UserProfile,
)
from tk_api.institutions.models import (  # noqa: F401
    Institution,
    InstitutionAttributeDefinition,
    InstitutionAttributeValue,
    InstitutionTranslation,
    InstitutionType,
)
from tk_api.integrations.models import (  # noqa: F401
    IntegrationConnector,
    OutboxEvent,
    WebhookDelivery,
    WebhookSubscription,
)
from tk_api.intelligence.models import (  # noqa: F401
    AnomalyEvent,
    CivicSignal,
    ForecastResult,
    ForecastRun,
    IntelligenceReport,
    IntelligenceReview,
    IssueCluster,
    ModelVersion,
    SignalEvidence,
    SignalSource,
    TrendSnapshot,
)
from tk_api.localization.models import ContentTranslation  # noqa: F401
from tk_api.measurement.models import MeasurementSnapshot  # noqa: F401
from tk_api.media.models import MediaObject, ReportMedia  # noqa: F401
from tk_api.notifications.models import (  # noqa: F401
    Notification,
    NotificationPreference,
    NotificationQueue,
    NotificationReceipt,
    NotificationTemplate,
)
from tk_api.provenance.models import (  # noqa: F401
    DataSource,
    ExternalSource,
    ProvenanceRecord,
    SourceRecord,
    SourceVersion,
)
from tk_api.publicdata.models import (  # noqa: F401
    DataCorrectionRequest,
    DataExportJob,
    PublicApiKey,
    PublicApiUsage,
    PublicDataset,
    PublicDatasetLineage,
    PublicDatasetVersion,
    SavedResearchQuery,
)
from tk_api.rag.models import RagChunk, RagDocument, RagDocumentVersion  # noqa: F401
from tk_api.reports.models import (  # noqa: F401
    Report,
    ReportCollaboration,
    ReportComment,
    ReportFollower,
    ReportStatusHistory,
    ReportString,
    ReportVerification,
)
from tk_api.resolution.models import (  # noqa: F401
    Device,
    ReputationEvent,
    ReputationPolicy,
    ResolutionDispute,
    ResolutionEvidence,
    ResolutionSubmission,
    ResolutionVerification,
    Subscription,
)
from tk_api.security.models import (  # noqa: F401
    AbuseScore,
    DataRetentionPolicy,
    IPBlock,
    SecurityAuditEntry,
    SecurityIncident,
    SecurityPolicy,
)
from tk_api.users.models import Consent, Role, User, UserRole  # noqa: F401
