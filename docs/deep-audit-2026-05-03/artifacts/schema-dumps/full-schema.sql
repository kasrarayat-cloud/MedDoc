--
-- PostgreSQL database dump
--

\restrict 1XCMJSs8p4ErERD0mf2Oxj9vhNSTiOLr5rya2ooBITCfYmAZCsfJsI7oq8DWqyy

-- Dumped from database version 16.13 (Debian 16.13-1.pgdg12+1)
-- Dumped by pg_dump version 16.13 (Debian 16.13-1.pgdg12+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: AllergySeverity; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."AllergySeverity" AS ENUM (
    'UNKNOWN',
    'MILD',
    'MODERATE',
    'SEVERE'
);


--
-- Name: AppointmentStatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."AppointmentStatus" AS ENUM (
    'SCHEDULED',
    'WAITING',
    'IN_ROOM',
    'COMPLETED',
    'CANCELLED'
);


--
-- Name: AuditAction; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."AuditAction" AS ENUM (
    'LOGIN_SUCCESS',
    'LOGIN_FAILED',
    'LOGOUT',
    'MFA_ENABLED',
    'MFA_DISABLED',
    'MFA_CHALLENGE_PASSED',
    'MFA_CHALLENGE_FAILED',
    'PASSWORD_CHANGED',
    'SESSION_EXPIRED',
    'VIEWED_PATIENT_LIST',
    'VIEWED_PATIENT_FILE',
    'CREATED_PATIENT',
    'UPDATED_PATIENT',
    'ARCHIVED_PATIENT',
    'VIEWED_DOCUMENT',
    'CREATED_DOCUMENT',
    'CREATED_CLINICAL_NOTE',
    'GENERATED_DRAFT_DOCUMENT',
    'EDITED_NOTE',
    'DOWNLOADED_DOCUMENT',
    'DELETED_DOCUMENT',
    'UPLOADED_TO_DROPBOX',
    'SYNCED_FROM_DRCHRONO',
    'PUSHED_TO_DRCHRONO',
    'SCHEDULED_VISIT',
    'UPDATED_APPOINTMENT_STATUS',
    'USER_CREATED',
    'USER_ROLE_CHANGED',
    'USER_DEACTIVATED',
    'EXPORTED_AUDIT_LOG',
    'USER_UPDATED',
    'USER_DELETED',
    'PASSWORD_RESET_BY_ADMIN',
    'DELETED_APPOINTMENT',
    'CREATED_ALLERGY',
    'UPDATED_ALLERGY',
    'DELETED_ALLERGY',
    'CREATED_MEDICATION',
    'UPDATED_MEDICATION',
    'DELETED_MEDICATION',
    'CREATED_TASK',
    'CREATED_BILLING_EVENT',
    'ADMIN_DASHBOARD_ACCESS',
    'VISIT_SIGNED',
    'VISIT_DELETED',
    'VISIT_ARCHIVED',
    'VISIT_UNARCHIVED',
    'VISIT_RESTORED',
    'VISIT_RETRY',
    'VISIT_RETRY_BUDGET_EXHAUSTED',
    'EXPORT_EMAIL_SENT',
    'EXPORT_EMAIL_BLOCKED_DESTINATION',
    'EXPORT_PDF_DOWNLOADED',
    'EXPORT_DOCX_DOWNLOADED',
    'EXPORT_CLIPBOARD_COPIED',
    'TM_PATIENT_CREATED',
    'TM_PATIENT_UPDATED',
    'TM_PATIENT_DELETED',
    'EMAIL_CHANGE_REQUESTED',
    'EMAIL_CHANGE_CONFIRMED',
    'ACCOUNT_DELETED',
    'RX_OVERRIDE_RECORDED',
    'RX_SIGN_BLOCKED_NO_OVERRIDE',
    'ADMIN_API_ACCESS',
    'USER_SUSPENDED',
    'USER_UNSUSPENDED',
    'USER_SOFT_DELETED',
    'USER_FORCE_LOGOUT',
    'USER_PASSWORD_RESET_TRIGGERED',
    'USER_GRANTED_SUPER_ADMIN',
    'USER_REVOKED_SUPER_ADMIN',
    'THREAT_INVESTIGATED',
    'THREAT_RESOLVED',
    'THREAT_DISMISSED_FALSE_POSITIVE',
    'HIPAA_FINDING_RESOLVED',
    'HIPAA_FINDING_REOPENED',
    'AUDIO_UPLOADED',
    'DOC_EDITOR_SAVED',
    'DOC_EDITOR_AI_SUGGESTED',
    'PHI_EXTRACTED_FROM_VOICE',
    'REALTIME_SESSION_STARTED',
    'REALTIME_SESSION_ENDED'
);


--
-- Name: AuthTokenPurpose; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."AuthTokenPurpose" AS ENUM (
    'PASSWORD_RESET',
    'EMAIL_VERIFICATION',
    'EMAIL_CHANGE'
);


--
-- Name: BillingEventStatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."BillingEventStatus" AS ENUM (
    'PENDING_REVIEW',
    'SUBMITTED',
    'PAID',
    'DENIED'
);


--
-- Name: DocumentStatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."DocumentStatus" AS ENUM (
    'DRAFT',
    'FINALIZED',
    'SIGNED',
    'ARCHIVED'
);


--
-- Name: PatientSex; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."PatientSex" AS ENUM (
    'UNKNOWN',
    'MALE',
    'FEMALE',
    'OTHER'
);


--
-- Name: PatientStatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."PatientStatus" AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'ARCHIVED'
);


--
-- Name: Product; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."Product" AS ENUM (
    'MEDDOC_PRO',
    'TRANSCRIBE_MD',
    'SUPER_ADMIN'
);


--
-- Name: TaskStatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."TaskStatus" AS ENUM (
    'OPEN',
    'IN_PROGRESS',
    'COMPLETED',
    'CANCELLED'
);


--
-- Name: TranscribeVisitStatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."TranscribeVisitStatus" AS ENUM (
    'QUEUED',
    'TRANSCRIBING',
    'EXTRACTING',
    'DRAFTING',
    'CRITIQUING',
    'POLISHING',
    'AUTOMATING',
    'READY',
    'FAILED',
    'SIGNED'
);


--
-- Name: UserRole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."UserRole" AS ENUM (
    'DOCTOR',
    'ADMIN',
    'STAFF',
    'SUPER_ADMIN'
);


--
-- Name: VisitType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."VisitType" AS ENUM (
    'CONSULTATION',
    'FOLLOW_UP',
    'PROCEDURE'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _prisma_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public._prisma_migrations (
    id character varying(36) NOT NULL,
    checksum character varying(64) NOT NULL,
    finished_at timestamp with time zone,
    migration_name character varying(255) NOT NULL,
    logs text,
    rolled_back_at timestamp with time zone,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    applied_steps_count integer DEFAULT 0 NOT NULL
);


--
-- Name: account_deletions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_deletions (
    id text NOT NULL,
    "userId" text NOT NULL,
    email text NOT NULL,
    specialty text,
    "visitCount" integer NOT NULL,
    "deletedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "purgeAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts (
    id text NOT NULL,
    "userId" text NOT NULL,
    type text NOT NULL,
    provider text NOT NULL,
    "providerAccountId" text NOT NULL,
    refresh_token text,
    access_token text,
    expires_at integer,
    token_type text,
    scope text,
    id_token text,
    session_state text
);


--
-- Name: ai_calls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_calls (
    id text NOT NULL,
    "practiceId" text NOT NULL,
    "visitId" text,
    purpose text NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    "promptHash" text NOT NULL,
    "latencyMs" integer NOT NULL,
    "inputTokens" integer,
    "outputTokens" integer,
    "costUsdCents" integer,
    success boolean NOT NULL,
    "errorCode" text,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "errorDetails" text
);


--
-- Name: allergies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.allergies (
    id text NOT NULL,
    "patientId" text NOT NULL,
    allergen text NOT NULL,
    reaction text,
    severity public."AllergySeverity" DEFAULT 'UNKNOWN'::public."AllergySeverity" NOT NULL,
    notes text,
    "practiceId" text NOT NULL,
    "createdById" text,
    "updatedById" text,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(6) with time zone NOT NULL,
    "deletedAt" timestamp(6) with time zone
);


--
-- Name: api_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_usage (
    id text NOT NULL,
    "userId" text NOT NULL,
    tokens integer,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    feature text NOT NULL,
    "durationSeconds" integer,
    "practiceId" text NOT NULL
);


--
-- Name: api_usage_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_usage_events (
    id text NOT NULL,
    "timestamp" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "userId" text,
    "practiceId" text,
    provider text NOT NULL,
    operation text NOT NULL,
    "audioSeconds" integer,
    "inputTokens" integer,
    "outputTokens" integer,
    "emailCount" integer,
    "unitCount" double precision NOT NULL,
    "unitType" text NOT NULL,
    "unitCostUsd" double precision NOT NULL,
    "totalCostUsd" double precision NOT NULL,
    "visitId" text,
    "requestId" text NOT NULL,
    "modelName" text,
    metadata jsonb
);


--
-- Name: api_usage_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_usage_logs (
    id text NOT NULL,
    "userId" text NOT NULL,
    model text NOT NULL,
    "tokensUsed" integer NOT NULL,
    "estimatedCost" double precision NOT NULL,
    action text NOT NULL,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: appointments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointments (
    id text NOT NULL,
    "patientId" text NOT NULL,
    "userId" text NOT NULL,
    "scheduledAt" timestamp with time zone NOT NULL,
    notes text,
    "aiPrepNote" text,
    "createdAt" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone NOT NULL,
    type public."VisitType" DEFAULT 'CONSULTATION'::public."VisitType" NOT NULL,
    status public."AppointmentStatus" DEFAULT 'SCHEDULED'::public."AppointmentStatus" NOT NULL
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id text NOT NULL,
    "userId" text,
    "userEmailSnapshot" text,
    "targetId" text,
    "targetType" text,
    "ipAddress" inet,
    "userAgent" text,
    metadata jsonb,
    success boolean DEFAULT true NOT NULL,
    "errorCode" text,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    action public."AuditAction" NOT NULL,
    "practiceId" text NOT NULL
);


--
-- Name: auth_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_tokens (
    id text NOT NULL,
    "userId" text NOT NULL,
    purpose public."AuthTokenPurpose" NOT NULL,
    "tokenHash" text NOT NULL,
    "expiresAt" timestamp(3) without time zone NOT NULL,
    "usedAt" timestamp(3) without time zone,
    metadata jsonb,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: billing_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_events (
    id text NOT NULL,
    "practiceId" text NOT NULL,
    "patientId" text NOT NULL,
    "clinicianUserId" text NOT NULL,
    "icd10Items" jsonb NOT NULL,
    "cptItems" jsonb NOT NULL,
    status public."BillingEventStatus" DEFAULT 'PENDING_REVIEW'::public."BillingEventStatus" NOT NULL,
    "sourceVisitId" text,
    "sourceScribeOutputId" text,
    "submittedAt" timestamp(6) with time zone,
    "submittedById" text,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(6) with time zone NOT NULL
);


--
-- Name: doctor_edit_patterns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.doctor_edit_patterns (
    id text NOT NULL,
    "visitId" text NOT NULL,
    "doctorId" text NOT NULL,
    "originalSoap" text NOT NULL,
    "editedSoap" text NOT NULL,
    "editDistance" integer NOT NULL,
    embedding public.vector(1536),
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id text NOT NULL,
    "patientId" text,
    title text NOT NULL,
    "procedureType" text,
    content text,
    "dropboxFileId" text,
    "dropboxUrl" text,
    "dropboxPath" text,
    "fileHash" text,
    "fileSizeBytes" integer,
    "mimeType" text,
    "createdById" text,
    "updatedById" text,
    "createdAt" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone NOT NULL,
    "deletedAt" timestamp with time zone,
    status public."DocumentStatus" DEFAULT 'DRAFT'::public."DocumentStatus" NOT NULL,
    "sourceItemIndex" integer,
    "sourceScribeOutputId" text
);


--
-- Name: hipaa_findings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hipaa_findings (
    id text NOT NULL,
    control text NOT NULL,
    severity text NOT NULL,
    title text NOT NULL,
    detail text,
    status text DEFAULT 'open'::text NOT NULL,
    "resolvedAt" timestamp(6) with time zone,
    "resolvedById" text,
    "resolvedByEmail" text,
    "resolutionNote" text,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(6) with time zone NOT NULL
);


--
-- Name: medications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.medications (
    id text NOT NULL,
    "patientId" text NOT NULL,
    name text NOT NULL,
    dosage text,
    frequency text,
    "isActive" boolean DEFAULT true NOT NULL,
    notes text,
    "practiceId" text NOT NULL,
    "createdById" text,
    "updatedById" text,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(6) with time zone NOT NULL,
    "deletedAt" timestamp(6) with time zone,
    "sourceScribeOutputId" text
);


--
-- Name: patients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patients (
    id text NOT NULL,
    "drChronoId" text,
    "lastSyncAt" timestamp with time zone,
    "firstName" text NOT NULL,
    "lastName" text NOT NULL,
    mrn text,
    email text,
    "phoneLast4" character varying(4),
    "birthYear" integer,
    tags text[] DEFAULT '{}'::text[],
    "assignedDoctorId" text,
    "createdById" text,
    "createdAt" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone NOT NULL,
    "deletedAt" timestamp with time zone,
    status public."PatientStatus" DEFAULT 'ACTIVE'::public."PatientStatus" NOT NULL,
    "cellPhone" text,
    "chartId" text,
    "homePhone" text,
    "insuranceVerified" boolean,
    "practiceId" text NOT NULL,
    "briefHistory" text[] DEFAULT ARRAY[]::text[] NOT NULL,
    "addressLine1" text,
    "addressLine2" text,
    city text,
    "pharmacyName" text,
    "pharmacyPhone" text,
    "postalCode" text,
    sex public."PatientSex" DEFAULT 'UNKNOWN'::public."PatientSex" NOT NULL,
    state text,
    "noKnownAllergies" boolean DEFAULT false NOT NULL
);


--
-- Name: practices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.practices (
    id text NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    address text,
    phone text,
    "isActive" boolean DEFAULT true NOT NULL,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(6) with time zone NOT NULL,
    "audioRetentionDays" integer DEFAULT 90 NOT NULL,
    "transcriptRetentionDays" integer DEFAULT 2555 NOT NULL
);


--
-- Name: rx_warning_overrides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rx_warning_overrides (
    id text NOT NULL,
    "visitId" text NOT NULL,
    "rxLineNumber" integer NOT NULL,
    "warningId" text NOT NULL,
    severity text NOT NULL,
    headline text NOT NULL,
    reason text NOT NULL,
    "overriddenBy" text NOT NULL,
    "overriddenAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: session_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.session_logs (
    id text NOT NULL,
    "userId" text NOT NULL,
    "ipAddress" text,
    "userAgent" text,
    action text DEFAULT 'LOGIN'::text NOT NULL,
    "createdAt" timestamp with time zone DEFAULT now() NOT NULL,
    "practiceId" text NOT NULL
);


--
-- Name: sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessions (
    id text NOT NULL,
    "sessionToken" text NOT NULL,
    "userId" text NOT NULL,
    expires timestamp with time zone NOT NULL
);


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tasks (
    id text NOT NULL,
    "practiceId" text NOT NULL,
    "patientId" text NOT NULL,
    "assignedUserId" text,
    "createdByUserId" text,
    title text NOT NULL,
    description text,
    status public."TaskStatus" DEFAULT 'OPEN'::public."TaskStatus" NOT NULL,
    "dueAt" timestamp(6) with time zone,
    "sourceVisitId" text,
    "sourceScribeOutputId" text,
    "sourceItemIndex" integer,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(6) with time zone NOT NULL,
    "completedAt" timestamp(6) with time zone,
    "completedById" text
);


--
-- Name: threat_resolutions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.threat_resolutions (
    id text NOT NULL,
    "threatId" text NOT NULL,
    "resolutionKind" text NOT NULL,
    "resolvedAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "resolvedById" text,
    "resolvedByEmail" text,
    note text,
    "silencePattern" jsonb
);


--
-- Name: transcribe_md_patients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcribe_md_patients (
    id text NOT NULL,
    "practiceId" text NOT NULL,
    name text NOT NULL,
    "dateOfBirth" date,
    "externalId" text,
    "deletedAt" timestamp(6) with time zone,
    "createdAt" timestamp(6) with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(6) with time zone NOT NULL,
    insurance text,
    mrn text,
    "problemList" jsonb
);


--
-- Name: transcribe_visits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcribe_visits (
    id text NOT NULL,
    "userId" text NOT NULL,
    "patientName" text,
    specialty text NOT NULL,
    "chiefComplaint" text,
    "inputMode" text NOT NULL,
    status public."TranscribeVisitStatus" DEFAULT 'QUEUED'::public."TranscribeVisitStatus" NOT NULL,
    "audioKey" text,
    "transcriptText" text,
    "soapNote" jsonb,
    "icdCodes" jsonb,
    "cptCodes" jsonb,
    "rxDrafts" jsonb,
    referrals jsonb,
    "patientSummary" text,
    "confidenceScores" jsonb,
    "signedAt" timestamp(3) without time zone,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "audioMimeType" text,
    "audioSizeBytes" integer,
    "audioDurationSec" integer,
    "audioUploadedAt" timestamp(3) without time zone,
    "transcriptRaw" jsonb,
    "speakerMap" jsonb,
    entities jsonb,
    "soapDraft" text,
    critique jsonb,
    "soapFinal" text,
    "needsReview" boolean DEFAULT false NOT NULL,
    "reviewReason" text,
    "processingStartedAt" timestamp(3) without time zone,
    "processingFinishedAt" timestamp(3) without time zone,
    "processingCostCents" integer,
    "signedSoap" text,
    "dictationAudioKey" text,
    "dictationDurationSec" integer,
    "rawTextInput" text,
    "soapL6Original" text,
    "patientId" text NOT NULL,
    "deletedAt" timestamp(6) with time zone,
    "archivedAt" timestamp(6) with time zone,
    "draftedInSeconds" integer,
    "markedMoments" jsonb,
    "failureCategory" text,
    "manualRetryCount" integer DEFAULT 0 NOT NULL
);


--
-- Name: user_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_sessions (
    id text NOT NULL,
    "userId" text NOT NULL,
    "sessionToken" text NOT NULL,
    "ipAddress" text,
    "userAgent" text,
    "deviceFingerprint" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "lastActiveAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "expiresAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id text NOT NULL,
    email text NOT NULL,
    name text,
    "emailVerified" timestamp with time zone,
    image text,
    "passwordHash" text NOT NULL,
    "mfaEnabled" boolean DEFAULT false NOT NULL,
    "mfaSecret" text,
    "mfaVerifiedAt" timestamp with time zone,
    "lastLogin" timestamp with time zone,
    "failedLoginCount" integer DEFAULT 0 NOT NULL,
    "lockedUntil" timestamp with time zone,
    "isActive" boolean DEFAULT true NOT NULL,
    "deactivatedAt" timestamp with time zone,
    "deactivatedBy" text,
    "createdAt" timestamp with time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp with time zone NOT NULL,
    role public."UserRole" DEFAULT 'STAFF'::public."UserRole" NOT NULL,
    "lastLoginIp" inet,
    "practiceId" text NOT NULL,
    products public."Product"[] DEFAULT ARRAY['MEDDOC_PRO'::public."Product"],
    "clinicName" text,
    npi text,
    specialty text,
    "timeZone" text DEFAULT 'America/Los_Angeles'::text,
    "mfaBackupCodes" text[] DEFAULT ARRAY[]::text[],
    "forceLogoutAt" timestamp(6) with time zone,
    "softDeletedAt" timestamp(6) with time zone,
    "softDeletedBy" text,
    "suspendedAt" timestamp(6) with time zone,
    "suspendedBy" text,
    "suspendedReason" text
);


--
-- Name: verification_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.verification_tokens (
    identifier text NOT NULL,
    token text NOT NULL,
    expires timestamp with time zone NOT NULL
);


--
-- Name: visit_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.visit_deliveries (
    id text NOT NULL,
    "visitId" text NOT NULL,
    channel text NOT NULL,
    destination text,
    "sizeBytes" integer,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: _prisma_migrations _prisma_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public._prisma_migrations
    ADD CONSTRAINT _prisma_migrations_pkey PRIMARY KEY (id);


--
-- Name: account_deletions account_deletions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_deletions
    ADD CONSTRAINT account_deletions_pkey PRIMARY KEY (id);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: accounts accounts_provider_providerAccountId_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT "accounts_provider_providerAccountId_key" UNIQUE (provider, "providerAccountId");


--
-- Name: ai_calls ai_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_calls
    ADD CONSTRAINT ai_calls_pkey PRIMARY KEY (id);


--
-- Name: allergies allergies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allergies
    ADD CONSTRAINT allergies_pkey PRIMARY KEY (id);


--
-- Name: api_usage_events api_usage_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_usage_events
    ADD CONSTRAINT api_usage_events_pkey PRIMARY KEY (id);


--
-- Name: api_usage_logs api_usage_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_usage_logs
    ADD CONSTRAINT api_usage_logs_pkey PRIMARY KEY (id);


--
-- Name: api_usage api_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_usage
    ADD CONSTRAINT api_usage_pkey PRIMARY KEY (id);


--
-- Name: appointments appointments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT appointments_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: auth_tokens auth_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_tokens
    ADD CONSTRAINT auth_tokens_pkey PRIMARY KEY (id);


--
-- Name: billing_events billing_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_events
    ADD CONSTRAINT billing_events_pkey PRIMARY KEY (id);


--
-- Name: doctor_edit_patterns doctor_edit_patterns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctor_edit_patterns
    ADD CONSTRAINT doctor_edit_patterns_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: hipaa_findings hipaa_findings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hipaa_findings
    ADD CONSTRAINT hipaa_findings_pkey PRIMARY KEY (id);


--
-- Name: medications medications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medications
    ADD CONSTRAINT medications_pkey PRIMARY KEY (id);


--
-- Name: patients patients_drChronoId_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT "patients_drChronoId_key" UNIQUE ("drChronoId");


--
-- Name: patients patients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_pkey PRIMARY KEY (id);


--
-- Name: patients patients_practiceId_chartId_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT "patients_practiceId_chartId_key" UNIQUE ("practiceId", "chartId");


--
-- Name: practices practices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practices
    ADD CONSTRAINT practices_pkey PRIMARY KEY (id);


--
-- Name: rx_warning_overrides rx_warning_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rx_warning_overrides
    ADD CONSTRAINT rx_warning_overrides_pkey PRIMARY KEY (id);


--
-- Name: session_logs session_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_logs
    ADD CONSTRAINT session_logs_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_sessionToken_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT "sessions_sessionToken_key" UNIQUE ("sessionToken");


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: threat_resolutions threat_resolutions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threat_resolutions
    ADD CONSTRAINT threat_resolutions_pkey PRIMARY KEY (id);


--
-- Name: transcribe_md_patients transcribe_md_patients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcribe_md_patients
    ADD CONSTRAINT transcribe_md_patients_pkey PRIMARY KEY (id);


--
-- Name: transcribe_visits transcribe_visits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcribe_visits
    ADD CONSTRAINT transcribe_visits_pkey PRIMARY KEY (id);


--
-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: verification_tokens verification_tokens_identifier_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_tokens
    ADD CONSTRAINT verification_tokens_identifier_token_key UNIQUE (identifier, token);


--
-- Name: verification_tokens verification_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_tokens
    ADD CONSTRAINT verification_tokens_token_key UNIQUE (token);


--
-- Name: visit_deliveries visit_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit_deliveries
    ADD CONSTRAINT visit_deliveries_pkey PRIMARY KEY (id);


--
-- Name: account_deletions_purgeAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "account_deletions_purgeAt_idx" ON public.account_deletions USING btree ("purgeAt");


--
-- Name: ai_calls_practiceId_purpose_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "ai_calls_practiceId_purpose_createdAt_idx" ON public.ai_calls USING btree ("practiceId", purpose, "createdAt");


--
-- Name: ai_calls_visitId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "ai_calls_visitId_idx" ON public.ai_calls USING btree ("visitId");


--
-- Name: allergies_patientId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "allergies_patientId_idx" ON public.allergies USING btree ("patientId");


--
-- Name: allergies_practiceId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "allergies_practiceId_idx" ON public.allergies USING btree ("practiceId");


--
-- Name: allergies_severity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX allergies_severity_idx ON public.allergies USING btree (severity);


--
-- Name: api_usage_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "api_usage_createdAt_idx" ON public.api_usage USING btree ("createdAt");


--
-- Name: api_usage_events_practiceId_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "api_usage_events_practiceId_timestamp_idx" ON public.api_usage_events USING btree ("practiceId", "timestamp");


--
-- Name: api_usage_events_provider_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX api_usage_events_provider_timestamp_idx ON public.api_usage_events USING btree (provider, "timestamp");


--
-- Name: api_usage_events_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX api_usage_events_timestamp_idx ON public.api_usage_events USING btree ("timestamp");


--
-- Name: api_usage_events_userId_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "api_usage_events_userId_timestamp_idx" ON public.api_usage_events USING btree ("userId", "timestamp");


--
-- Name: api_usage_logs_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "api_usage_logs_createdAt_idx" ON public.api_usage_logs USING btree ("createdAt");


--
-- Name: api_usage_logs_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "api_usage_logs_userId_idx" ON public.api_usage_logs USING btree ("userId");


--
-- Name: api_usage_practiceId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "api_usage_practiceId_idx" ON public.api_usage USING btree ("practiceId");


--
-- Name: api_usage_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "api_usage_userId_idx" ON public.api_usage USING btree ("userId");


--
-- Name: appointments_patientId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "appointments_patientId_idx" ON public.appointments USING btree ("patientId");


--
-- Name: appointments_scheduledAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "appointments_scheduledAt_idx" ON public.appointments USING btree ("scheduledAt");


--
-- Name: appointments_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "appointments_userId_idx" ON public.appointments USING btree ("userId");


--
-- Name: audit_logs_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_logs_action_idx ON public.audit_logs USING btree (action);


--
-- Name: audit_logs_practiceId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "audit_logs_practiceId_idx" ON public.audit_logs USING btree ("practiceId");


--
-- Name: audit_logs_targetId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "audit_logs_targetId_idx" ON public.audit_logs USING btree ("targetId");


--
-- Name: audit_logs_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_logs_timestamp_idx ON public.audit_logs USING btree ("timestamp");


--
-- Name: audit_logs_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "audit_logs_userId_idx" ON public.audit_logs USING btree ("userId");


--
-- Name: audit_logs_userId_targetId_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "audit_logs_userId_targetId_timestamp_idx" ON public.audit_logs USING btree ("userId", "targetId", "timestamp");


--
-- Name: auth_tokens_expiresAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "auth_tokens_expiresAt_idx" ON public.auth_tokens USING btree ("expiresAt");


--
-- Name: auth_tokens_tokenHash_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "auth_tokens_tokenHash_key" ON public.auth_tokens USING btree ("tokenHash");


--
-- Name: auth_tokens_userId_purpose_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "auth_tokens_userId_purpose_idx" ON public.auth_tokens USING btree ("userId", purpose);


--
-- Name: billing_events_patientId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "billing_events_patientId_idx" ON public.billing_events USING btree ("patientId");


--
-- Name: billing_events_practiceId_status_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "billing_events_practiceId_status_createdAt_idx" ON public.billing_events USING btree ("practiceId", status, "createdAt");


--
-- Name: billing_events_sourceScribeOutputId_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "billing_events_sourceScribeOutputId_key" ON public.billing_events USING btree ("sourceScribeOutputId");


--
-- Name: billing_events_sourceVisitId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "billing_events_sourceVisitId_idx" ON public.billing_events USING btree ("sourceVisitId");


--
-- Name: doctor_edit_patterns_doctorId_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "doctor_edit_patterns_doctorId_createdAt_idx" ON public.doctor_edit_patterns USING btree ("doctorId", "createdAt");


--
-- Name: doctor_edit_patterns_doctorId_editDistance_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "doctor_edit_patterns_doctorId_editDistance_idx" ON public.doctor_edit_patterns USING btree ("doctorId", "editDistance");


--
-- Name: doctor_edit_patterns_visitId_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "doctor_edit_patterns_visitId_key" ON public.doctor_edit_patterns USING btree ("visitId");


--
-- Name: documents_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "documents_createdAt_idx" ON public.documents USING btree ("createdAt");


--
-- Name: documents_createdById_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "documents_createdById_idx" ON public.documents USING btree ("createdById");


--
-- Name: documents_patientId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "documents_patientId_idx" ON public.documents USING btree ("patientId");


--
-- Name: documents_sourceScribeOutputId_sourceItemIndex_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "documents_sourceScribeOutputId_sourceItemIndex_key" ON public.documents USING btree ("sourceScribeOutputId", "sourceItemIndex");


--
-- Name: documents_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX documents_status_idx ON public.documents USING btree (status);


--
-- Name: hipaa_findings_resolvedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "hipaa_findings_resolvedAt_idx" ON public.hipaa_findings USING btree ("resolvedAt");


--
-- Name: hipaa_findings_status_severity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hipaa_findings_status_severity_idx ON public.hipaa_findings USING btree (status, severity);


--
-- Name: medications_isActive_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "medications_isActive_idx" ON public.medications USING btree ("isActive");


--
-- Name: medications_patientId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "medications_patientId_idx" ON public.medications USING btree ("patientId");


--
-- Name: medications_practiceId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "medications_practiceId_idx" ON public.medications USING btree ("practiceId");


--
-- Name: medications_sourceScribeOutputId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "medications_sourceScribeOutputId_idx" ON public.medications USING btree ("sourceScribeOutputId");


--
-- Name: patients_assignedDoctorId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "patients_assignedDoctorId_idx" ON public.patients USING btree ("assignedDoctorId");


--
-- Name: patients_drChronoId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "patients_drChronoId_idx" ON public.patients USING btree ("drChronoId");


--
-- Name: patients_lastName_firstName_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "patients_lastName_firstName_idx" ON public.patients USING btree ("lastName", "firstName");


--
-- Name: patients_practiceId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "patients_practiceId_idx" ON public.patients USING btree ("practiceId");


--
-- Name: patients_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX patients_status_idx ON public.patients USING btree (status);


--
-- Name: practices_slug_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX practices_slug_idx ON public.practices USING btree (slug);


--
-- Name: practices_slug_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX practices_slug_key ON public.practices USING btree (slug);


--
-- Name: rx_warning_overrides_overriddenBy_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "rx_warning_overrides_overriddenBy_idx" ON public.rx_warning_overrides USING btree ("overriddenBy");


--
-- Name: rx_warning_overrides_visitId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "rx_warning_overrides_visitId_idx" ON public.rx_warning_overrides USING btree ("visitId");


--
-- Name: session_logs_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "session_logs_createdAt_idx" ON public.session_logs USING btree ("createdAt");


--
-- Name: session_logs_practiceId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "session_logs_practiceId_idx" ON public.session_logs USING btree ("practiceId");


--
-- Name: session_logs_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "session_logs_userId_idx" ON public.session_logs USING btree ("userId");


--
-- Name: tasks_assignedUserId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "tasks_assignedUserId_idx" ON public.tasks USING btree ("assignedUserId");


--
-- Name: tasks_patientId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "tasks_patientId_idx" ON public.tasks USING btree ("patientId");


--
-- Name: tasks_practiceId_status_dueAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "tasks_practiceId_status_dueAt_idx" ON public.tasks USING btree ("practiceId", status, "dueAt");


--
-- Name: tasks_sourceScribeOutputId_sourceItemIndex_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "tasks_sourceScribeOutputId_sourceItemIndex_key" ON public.tasks USING btree ("sourceScribeOutputId", "sourceItemIndex");


--
-- Name: tasks_sourceVisitId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "tasks_sourceVisitId_idx" ON public.tasks USING btree ("sourceVisitId");


--
-- Name: threat_resolutions_resolutionKind_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "threat_resolutions_resolutionKind_idx" ON public.threat_resolutions USING btree ("resolutionKind");


--
-- Name: threat_resolutions_resolvedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "threat_resolutions_resolvedAt_idx" ON public.threat_resolutions USING btree ("resolvedAt");


--
-- Name: threat_resolutions_resolvedById_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "threat_resolutions_resolvedById_idx" ON public.threat_resolutions USING btree ("resolvedById");


--
-- Name: threat_resolutions_threatId_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "threat_resolutions_threatId_key" ON public.threat_resolutions USING btree ("threatId");


--
-- Name: transcribe_md_patients_name_trgm_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX transcribe_md_patients_name_trgm_idx ON public.transcribe_md_patients USING gin (lower(name) public.gin_trgm_ops);


--
-- Name: transcribe_md_patients_practiceId_deletedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "transcribe_md_patients_practiceId_deletedAt_idx" ON public.transcribe_md_patients USING btree ("practiceId", "deletedAt");


--
-- Name: transcribe_visits_deletedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "transcribe_visits_deletedAt_idx" ON public.transcribe_visits USING btree ("deletedAt");


--
-- Name: transcribe_visits_patientId_deletedAt_archivedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "transcribe_visits_patientId_deletedAt_archivedAt_idx" ON public.transcribe_visits USING btree ("patientId", "deletedAt", "archivedAt");


--
-- Name: transcribe_visits_patientId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "transcribe_visits_patientId_idx" ON public.transcribe_visits USING btree ("patientId");


--
-- Name: transcribe_visits_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX transcribe_visits_status_idx ON public.transcribe_visits USING btree (status);


--
-- Name: transcribe_visits_userId_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "transcribe_visits_userId_createdAt_idx" ON public.transcribe_visits USING btree ("userId", "createdAt");


--
-- Name: transcribe_visits_userId_deletedAt_archivedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "transcribe_visits_userId_deletedAt_archivedAt_idx" ON public.transcribe_visits USING btree ("userId", "deletedAt", "archivedAt");


--
-- Name: user_sessions_expiresAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "user_sessions_expiresAt_idx" ON public.user_sessions USING btree ("expiresAt");


--
-- Name: user_sessions_sessionToken_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "user_sessions_sessionToken_idx" ON public.user_sessions USING btree ("sessionToken");


--
-- Name: user_sessions_sessionToken_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "user_sessions_sessionToken_key" ON public.user_sessions USING btree ("sessionToken");


--
-- Name: user_sessions_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "user_sessions_userId_idx" ON public.user_sessions USING btree ("userId");


--
-- Name: users_isActive_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "users_isActive_idx" ON public.users USING btree ("isActive");


--
-- Name: users_practiceId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "users_practiceId_idx" ON public.users USING btree ("practiceId");


--
-- Name: users_role_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX users_role_idx ON public.users USING btree (role);


--
-- Name: visit_deliveries_visitId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "visit_deliveries_visitId_idx" ON public.visit_deliveries USING btree ("visitId");


--
-- Name: accounts accounts_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT "accounts_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: ai_calls ai_calls_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_calls
    ADD CONSTRAINT "ai_calls_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: allergies allergies_createdById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allergies
    ADD CONSTRAINT "allergies_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: allergies allergies_patientId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allergies
    ADD CONSTRAINT "allergies_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES public.patients(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: allergies allergies_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allergies
    ADD CONSTRAINT "allergies_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: allergies allergies_updatedById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allergies
    ADD CONSTRAINT "allergies_updatedById_fkey" FOREIGN KEY ("updatedById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: api_usage_events api_usage_events_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_usage_events
    ADD CONSTRAINT "api_usage_events_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: api_usage_events api_usage_events_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_usage_events
    ADD CONSTRAINT "api_usage_events_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: api_usage_logs api_usage_logs_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_usage_logs
    ADD CONSTRAINT "api_usage_logs_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: api_usage api_usage_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_usage
    ADD CONSTRAINT "api_usage_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: api_usage api_usage_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_usage
    ADD CONSTRAINT "api_usage_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: appointments appointments_patientId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT "appointments_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES public.patients(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: appointments appointments_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointments
    ADD CONSTRAINT "appointments_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: audit_logs audit_logs_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT "audit_logs_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: audit_logs audit_logs_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT "audit_logs_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: auth_tokens auth_tokens_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_tokens
    ADD CONSTRAINT "auth_tokens_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: billing_events billing_events_clinicianUserId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_events
    ADD CONSTRAINT "billing_events_clinicianUserId_fkey" FOREIGN KEY ("clinicianUserId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: billing_events billing_events_patientId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_events
    ADD CONSTRAINT "billing_events_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES public.patients(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: billing_events billing_events_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_events
    ADD CONSTRAINT "billing_events_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: billing_events billing_events_submittedById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_events
    ADD CONSTRAINT "billing_events_submittedById_fkey" FOREIGN KEY ("submittedById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: doctor_edit_patterns doctor_edit_patterns_doctorId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctor_edit_patterns
    ADD CONSTRAINT "doctor_edit_patterns_doctorId_fkey" FOREIGN KEY ("doctorId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: doctor_edit_patterns doctor_edit_patterns_visitId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctor_edit_patterns
    ADD CONSTRAINT "doctor_edit_patterns_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES public.transcribe_visits(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: documents documents_createdById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT "documents_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: documents documents_patientId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT "documents_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES public.patients(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: documents documents_updatedById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT "documents_updatedById_fkey" FOREIGN KEY ("updatedById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: hipaa_findings hipaa_findings_resolvedById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hipaa_findings
    ADD CONSTRAINT "hipaa_findings_resolvedById_fkey" FOREIGN KEY ("resolvedById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: medications medications_createdById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medications
    ADD CONSTRAINT "medications_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: medications medications_patientId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medications
    ADD CONSTRAINT "medications_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES public.patients(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: medications medications_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medications
    ADD CONSTRAINT "medications_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: medications medications_updatedById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.medications
    ADD CONSTRAINT "medications_updatedById_fkey" FOREIGN KEY ("updatedById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: patients patients_assignedDoctorId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT "patients_assignedDoctorId_fkey" FOREIGN KEY ("assignedDoctorId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: patients patients_createdById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT "patients_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: patients patients_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT "patients_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: rx_warning_overrides rx_warning_overrides_overriddenBy_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rx_warning_overrides
    ADD CONSTRAINT "rx_warning_overrides_overriddenBy_fkey" FOREIGN KEY ("overriddenBy") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: rx_warning_overrides rx_warning_overrides_visitId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rx_warning_overrides
    ADD CONSTRAINT "rx_warning_overrides_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES public.transcribe_visits(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: session_logs session_logs_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_logs
    ADD CONSTRAINT "session_logs_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: session_logs session_logs_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_logs
    ADD CONSTRAINT "session_logs_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: sessions sessions_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT "sessions_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: tasks tasks_assignedUserId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT "tasks_assignedUserId_fkey" FOREIGN KEY ("assignedUserId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: tasks tasks_createdByUserId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT "tasks_createdByUserId_fkey" FOREIGN KEY ("createdByUserId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: tasks tasks_patientId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT "tasks_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES public.patients(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: tasks tasks_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT "tasks_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: threat_resolutions threat_resolutions_resolvedById_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threat_resolutions
    ADD CONSTRAINT "threat_resolutions_resolvedById_fkey" FOREIGN KEY ("resolvedById") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: transcribe_md_patients transcribe_md_patients_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcribe_md_patients
    ADD CONSTRAINT "transcribe_md_patients_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: transcribe_visits transcribe_visits_patientId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcribe_visits
    ADD CONSTRAINT "transcribe_visits_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES public.transcribe_md_patients(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: transcribe_visits transcribe_visits_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcribe_visits
    ADD CONSTRAINT "transcribe_visits_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_sessions user_sessions_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT "user_sessions_userId_fkey" FOREIGN KEY ("userId") REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: users users_practiceId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT "users_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES public.practices(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: visit_deliveries visit_deliveries_visitId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visit_deliveries
    ADD CONSTRAINT "visit_deliveries_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES public.transcribe_visits(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 1XCMJSs8p4ErERD0mf2Oxj9vhNSTiOLr5rya2ooBITCfYmAZCsfJsI7oq8DWqyy

