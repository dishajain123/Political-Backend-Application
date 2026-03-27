# Role-Based Access Control (RBAC) Security Architecture

## Executive Summary

This document outlines the comprehensive Role-Based Access Control (RBAC) system implemented in the Political Communication Platform. The architecture provides granular permission management across multiple user roles, enforcing security at both the route and service layers. The system is designed for scalability, auditability, and clear separation of concerns between political authority hierarchies and operational management functions.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Authentication Flow](#authentication-flow)
3. [Role Definitions](#role-definitions)
4. [Permission Matrix](#permission-matrix)
5. [Access Control Patterns](#access-control-patterns)
6. [Feature-by-Feature Access Control](#feature-by-feature-access-control)
7. [Security Implementation](#security-implementation)
8. [Audit and Compliance](#audit-and-compliance)

---

## System Overview

The RBAC system operates on a two-tier security model:

### Tier 1: Route-Level Authorization
- Permission-based access to API endpoints
- Validates user credentials and role permissions
- Enforced through FastAPI dependency injection

### Tier 2: Service-Level Data Isolation
- Scope-based access within business logic
- Ensures users can only access data appropriate to their role
- Prevents data leakage between role boundaries

### Key Principles

1. **Least Privilege**: Users receive minimum permissions required for their role
2. **Separation of Concerns**: Political authority (Corporator-Leader-Voter) is separate from operational authority (OPS)
3. **Auditability**: All OPS modifications are logged for compliance
4. **Role Inheritance**: Higher-authority roles inherit permissions of lower roles where applicable
5. **Service Enforcement**: Database-layer checks complement permission checks

---

## Authentication Flow

### Token-Based Authentication

Users authenticate through JWT (JSON Web Token) bearer authentication:

1. **Login**: User provides credentials (email/phone + password)
2. **Token Creation**: Server validates credentials and generates JWT access token containing:
   - User ID (sub claim)
   - User Role (role claim)
   - Token Type (type: "access")
   - Expiration (exp claim)
   - Issued At (iat claim)

3. **Token Storage**: Client stores access token for subsequent API calls

4. **Middleware Validation**: AuthMiddleware validates token on each request:
   - Extracts token from Authorization header (format: "Bearer <token>")
   - Decodes JWT signature
   - Validates token type is "access" (not refresh)
   - Adds user context to request

5. **Route Authorization**: Individual routes verify:
   - Token validity
   - User existence in database
   - Role consistency between token and database
   - Permission requirements for endpoint

### Password Security

- Passwords hashed using bcrypt (PBKDF2-based)
- Hashed values stored in database, plain text never retained
- Verification performed using constant-time comparison

### Public Endpoints (No Authentication Required)

- `/health` - Health check
- `/api/v1/auth/login` - User login
- `/api/v1/auth/register` - User registration
- `/api/v1/auth/refresh` - Token refresh
- `/api/v1/auth/forgot-password` - Password reset initiation
- `/api/v1/auth/reset-password` - Password reset completion
- `/api/v1/auth/verify-email` - Email verification
- `/api/v1/auth/verify-mobile` - Mobile verification
- `/docs` - API documentation
- `/redoc` - Alternative documentation
- `/openapi.json` - OpenAPI schema

---

## Role Definitions

### 1. Corporator (Top Authority)

**Title**: Corporator / Head

**Description**: Executive-level user representing political authority at district/state level (MLA, MP, Party Head).

**Characteristics**:
- Highest authority in political hierarchy
- Strategic decision-making capability
- System-wide visibility and control
- Full feature management capabilities

**Hierarchy Position**: Rank 2 (Highest in political chain)

**Default Permissions**: Full administrative access across all features

---

### 2. Leader (Field Authority)

**Title**: Leader / Field Representative

**Description**: Mid-level user responsible for ground-level execution and management in assigned territory.

**Characteristics**:
- Operates within assigned geographic territory
- Reports to Corporator
- Manages voter interactions in region
- Limited modification capabilities
- Data scoped to assigned territory

**Hierarchy Position**: Rank 1 (Middle of political chain)

**Default Permissions**: Territory-scoped feature access with limited modification rights

---

### 3. Voter (End User)

**Title**: Voter / Citizen

**Description**: End-user representing citizens and followers in the political ecosystem.

**Characteristics**:
- Participatory access to platform features
- Cannot create administrative elements
- Access restricted to own data (personal records)
- Read-only access to public content
- Engagement through participation features

**Hierarchy Position**: Rank 0 (Lowest in political chain)

**Default Permissions**: Participation and personal data management only

---

### 4. OPS (Operational Authority)

**Title**: Operations Console User

**Description**: Administrative user for operations management, analytics, and complaint resolution.

**Characteristics**:
- Not part of political hierarchy
- Read and update access (no create/delete capabilities)
- Full visibility into operational metrics
- Audit trail responsibility
- System-level analytics and monitoring

**Hierarchy Position**: None (Separate from political chain)

**Default Permissions**: Management and analytics access only

**Important**: OPS role operates independently from political hierarchy. Cannot use role-hierarchy checks; must use permission-based validation.

---

## Permission Matrix

### Overview

The system defines 40+ granular permissions across 10 feature categories. Each role receives a specific subset of permissions based on operational requirements.

### Permission Categories

#### 1. Announcement Management (4 permissions)
- `CREATE_ANNOUNCEMENT` - Create new announcements
- `VIEW_ANNOUNCEMENT` - View published announcements
- `UPDATE_ANNOUNCEMENT` - Modify existing announcements
- `DELETE_ANNOUNCEMENT` - Remove announcements

#### 2. Poll Management (5 permissions)
- `CREATE_POLL` - Create new polls/surveys
- `VIEW_POLL` - View poll details
- `PARTICIPATE_POLL` - Vote in polls
- `VIEW_POLL_RESULTS` - See poll results
- `CLOSE_POLL` - End active polls

#### 3. Complaint Management (7 permissions)
- `CREATE_COMPLAINT` - File new complaints
- `VIEW_COMPLAINT` - View complaint details (scope-dependent)
- `ASSIGN_COMPLAINT` - Assign to handlers
- `UPDATE_COMPLAINT_STATUS` - Change complaint status
- `ADD_COMPLAINT_NOTE` - Add notes to complaints
- `RESOLVE_COMPLAINT` - Mark complaints resolved
- `VIEW_ALL_COMPLAINTS` - View all complaints system-wide

#### 4. Appointment Management (5 permissions)
- `REQUEST_APPOINTMENT` - Request appointment slot
- `VIEW_APPOINTMENT` - View appointment details (scope-dependent)
- `APPROVE_APPOINTMENT` - Accept appointment requests
- `RESCHEDULE_APPOINTMENT` - Modify appointment timing
- `CANCEL_APPOINTMENT` - Cancel appointments

#### 5. Event Management (6 permissions)
- `CREATE_EVENT` - Create new events
- `VIEW_EVENT` - View event information
- `UPDATE_EVENT` - Modify event details
- `DELETE_EVENT` - Remove events
- `ASSIGN_EVENT_LEADER` - Assign leaders to events
- `TRACK_EVENT_PARTICIPATION` - Monitor event attendance

#### 6. Feedback Management (3 permissions)
- `CREATE_FEEDBACK` - Submit feedback
- `VIEW_FEEDBACK` - View feedback (scope-dependent)
- `VIEW_ALL_FEEDBACK` - View all feedback system-wide

#### 7. User Management (6 permissions)
- `CREATE_USER` - Create new user accounts
- `VIEW_USER` - View user profiles
- `UPDATE_USER` - Modify user information
- `DELETE_USER` - Remove user accounts
- `ASSIGN_LEADER_TERRITORY` - Assign territories to leaders
- `VIEW_USER_ANALYTICS` - View user performance metrics

#### 8. Notification System (2 permissions)
- `SEND_NOTIFICATION` - Send notifications to users
- `VIEW_NOTIFICATION` - View received notifications

#### 9. Analytics and Insights (5 permissions)
- `VIEW_BASIC_ANALYTICS` - Access foundational metrics
- `VIEW_ADVANCED_ANALYTICS` - Access detailed analysis
- `VIEW_VOTER_INTELLIGENCE` - Analyze voter demographics/patterns
- `VIEW_LEADER_PERFORMANCE` - Monitor leader metrics
- `VIEW_SENTIMENT_ANALYSIS` - Analyze sentiment trends

#### 10. Communication Analytics (2 permissions)
- `VIEW_CHAT_ANALYTICS` - Monitor messaging metrics
- `VIEW_BROADCAST_PERFORMANCE` - Track broadcast effectiveness

### Complete Role-Permission Mapping

#### Corporator Permissions (40 total)

**Announcements**: Create, View, Update, Delete

**Polls**: Create, View, View Results, Close, Participate

**Complaints**: View All, View, Assign, Update Status, Add Notes, Resolve

**Appointments**: View, Approve, Reschedule, Cancel

**Events**: Create, View, Update, Delete, Assign Leaders, Track Participation

**Feedback**: View All, View

**Users**: Create, View, Update, Delete, Assign Territory

**Notifications**: Send, View

**Analytics**: Basic, Advanced, Voter Intelligence, Leader Performance, Sentiment Analysis

**Communication Analytics**: Chat Analytics, Broadcast Performance

---

#### Leader Permissions (18 total)

**Announcements**: Create, View

**Polls**: View, Participate, View Results

**Complaints**: Create (territory-scoped), View (territory-scoped), Add Notes, Update Status

**Appointments**: Request, View, Approve, Reschedule

**Events**: View (territory-scoped)

**Feedback**: Create, View (territory-scoped)

**Users**: View (territory-scoped)

**Notifications**: View

**Analytics**: None

**Communication Analytics**: None

**Note**: Leader permissions are scoped to assigned territory through service-layer enforcement

---

#### Voter Permissions (8 total)

**Announcements**: View

**Polls**: View, Participate

**Complaints**: Create, View (personal only)

**Appointments**: Request, View (personal only)

**Events**: View

**Feedback**: Create, View (personal only)

**Users**: None

**Notifications**: View

**Analytics**: None

**Communication Analytics**: None

**Note**: Voter permissions are scoped to personal records through service-layer enforcement

---

#### OPS Permissions (18 total)

**Announcements**: None

**Polls**: None

**Complaints**: View All, View, Assign, Update Status, Resolve, Add Notes

**Appointments**: View, Approve, Reschedule

**Feedback**: View All, View

**Events**: None

**Users**: View, View Analytics

**Notifications**: View

**Analytics**: Basic, Advanced, Voter Intelligence, Leader Performance, Sentiment Analysis

**Communication Analytics**: Chat Analytics, Broadcast Performance

**Note**: OPS has no creation or deletion rights; all modifications logged for audit

---

## Access Control Patterns

### Route-Level Authorization

All protected API endpoints enforce authorization through FastAPI dependency injection:

```python
@router.get("/endpoint")
async def endpoint(
    current_user: CurrentUser = Depends(require_permission(Permission.REQUIRED_PERMISSION))
):
    # User authenticated and has permission
    pass
```

The `require_permission()` dependency:
1. Extracts and validates JWT token
2. Verifies user exists in database
3. Confirms role matches between token and database
4. Checks permission assignment for role
5. Returns `CurrentUser` object containing user_id and role

---

### Service-Layer Data Isolation

Beyond route-level permission checks, service layers enforce data isolation to prevent privilege escalation:

#### Voter Data Isolation

Voters can only access their own records:

- **Complaints**: Only view/modify complaints created by themselves
- **Appointments**: Only view/modify appointments requested by themselves
- **Feedback**: Only view feedback submitted by themselves

Implementation through `VoterAccessControl` class:
```python
verify_complaint_ownership(voter_user_id, complaint_id) -> bool
verify_appointment_ownership(voter_user_id, appointment_id) -> bool
verify_feedback_ownership(voter_user_id, feedback_id) -> bool
```

Service retrieval methods:
```python
get_voter_complaints(voter_user_id, skip, limit) -> List
get_voter_appointments(voter_user_id, skip, limit) -> List
```

---

#### Leader Territory Isolation

Leaders can only access resources within assigned territory:

- **Complaints**: Only manage complaints from assigned territory
- **Feedback**: Only view feedback from assigned territory
- **Users**: Only view users in assigned territory

Implementation through `LeaderAccessControl` class:
```python
get_leader_territory(leader_user_id) -> str
verify_territory_access(leader_user_id, territory_id) -> bool
get_leader_complaints(leader_user_id, skip, limit) -> List
```

Territory assignment validated before each data access operation.

---

#### OPS Audit Logging

OPS modifications logged for compliance and audit:

- Every status change recorded with timestamp and user
- Changes include original and modified values
- Enables full audit trail reconstruction

Implementation through `OpsAccessControl` class:
```python
log_ops_action(ops_user_id, action, resource_type, resource_id, changes) -> bool
```

Logged actions:
- UPDATE_STATUS - Status changes on complaints/appointments
- ASSIGN - Assignment of resources to handlers
- RESOLVE - Complaint resolution
- Other management actions

---

### Role Hierarchy

The system defines political authority hierarchy for route-level access control:

```
CORPORATOR (Rank 2) > LEADER (Rank 1) > VOTER (Rank 0)
```

Higher-rank users inherit permissions of lower ranks in specific scenarios (e.g., Corporator can do everything Voter can do).

**Important**: OPS role is NOT part of hierarchy. OPS users must use permission-based checks exclusively.

Hierarchy validation method:
```python
has_higher_or_equal_role(user_role, required_role) -> bool
```

Returns `False` if OPS role involved; hierarchy-based checks cannot be used for OPS.

---

## Feature-by-Feature Access Control

### Announcements

**Purpose**: Disseminate official communications and updates

| Action | Corporator | Leader | Voter | OPS |
|--------|------------|--------|-------|-----|
| Create | Yes | Yes | No | No |
| View | Yes | Yes | Yes | No |
| Update | Yes | No | No | No |
| Delete | Yes | No | No | No |

**Service Layer**: No scope restrictions; all announcements visible to authenticated users.

**Workflow**:
1. Corporator creates announcement with content
2. Leader can create local announcements for territory
3. Voter views published announcements
4. OPS cannot manage announcements (operational role)

---

### Polls and Surveys

**Purpose**: Gather public opinion and feedback through structured surveys

| Action | Corporator | Leader | Voter | OPS |
|--------|------------|--------|-------|-----|
| Create | Yes | No | No | No |
| View | Yes | Yes | Yes | No |
| Participate | Yes | Yes | Yes | No |
| View Results | Yes | Yes | No | No |
| Close | Yes | No | No | No |

**Service Layer**: No scope restrictions; polls visible to all users.

**Workflow**:
1. Corporator creates poll with questions and options
2. Leader and Voter participate in polls
3. Corporator and Leader view poll results
4. Corporator closes poll after deadline

---

### Complaints Management

**Purpose**: Record and resolve citizen grievances

| Action | Corporator | Leader | Voter | OPS |
|--------|------------|--------|-------|-----|
| Create | No | Yes (territory) | Yes | No |
| View | Yes (all) | Yes (territory) | Yes (own) | Yes (all) |
| Assign | Yes | No | No | Yes |
| Update Status | Yes | Yes (limited) | No | Yes |
| Add Notes | Yes | Yes | No | Yes |
| Resolve | Yes | No | No | Yes |

**Service Layer Enforcement**:
- Voter sees only complaints they created
- Leader sees only complaints from assigned territory
- OPS sees all complaints system-wide

**Audit Trail**: All OPS modifications logged with timestamp and user

**Workflow**:
1. Voter files complaint
2. Leader handles complaints in territory, updates status
3. OPS assigns to handlers, resolves, tracks metrics
4. Corporator oversees all complaints

---

### Appointment Scheduling

**Purpose**: Manage meeting slots between leaders and voters

| Action | Corporator | Leader | Voter | OPS |
|--------|------------|--------|-------|-----|
| Request | No | Yes | Yes | No |
| View | Yes (all) | Yes | Yes (own) | Yes (all) |
| Approve | Yes | Yes | No | Yes |
| Reschedule | Yes | Yes | No | Yes |
| Cancel | Yes | Yes | No | No |

**Service Layer Enforcement**:
- Voter sees only appointments they requested
- Leader sees appointments for requested meetings
- OPS sees all appointments

**Workflow**:
1. Voter requests appointment slot
2. Leader approves from their calendar
3. OPS manages scheduling conflicts
4. Parties reschedule as needed

---

### Events Management

**Purpose**: Organize and track political events and campaigns

| Action | Corporator | Leader | Voter | OPS |
|--------|------------|--------|-------|-----|
| Create | Yes | No | No | No |
| View | Yes | Yes (territory) | Yes | No |
| Update | Yes | No | No | No |
| Delete | Yes | No | No | No |
| Assign Leaders | Yes | No | No | No |
| Track Participation | Yes | Yes | No | No |

**Service Layer Enforcement**:
- Leader sees events in assigned territory
- Voter sees public events

**Workflow**:
1. Corporator creates campaign event
2. Corporator assigns Leaders to manage regions
3. Leader tracks participation in territory
4. Voters register and participate

---

### Feedback Collection

**Purpose**: Gather qualitative insights from users

| Action | Corporator | Leader | Voter | OPS |
|--------|------------|--------|-------|-----|
| Create | No | Yes | Yes | No |
| View | Yes (all) | Yes (territory) | Yes (own) | Yes (all) |

**Service Layer Enforcement**:
- Voter sees only feedback they submitted
- Leader sees feedback from assigned territory
- OPS sees all feedback for analysis

**Workflow**:
1. Voter submits feedback
2. Leader reviews feedback in territory
3. OPS analyzes feedback for insights
4. Corporator reviews aggregated insights

---

### User Management

**Purpose**: Create and manage user accounts and roles

| Action | Corporator | Leader | Voter | OPS |
|--------|------------|--------|-------|-----|
| Create | Yes | No | No | No |
| View | Yes (all) | Yes (territory) | No | Yes (all) |
| Update | Yes | No | No | No |
| Delete | Yes | No | No | No |
| Assign Territory | Yes | No | No | No |
| View Analytics | No | No | No | Yes |

**Service Layer Enforcement**:
- Leader views users only in assigned territory
- OPS views all users with analytics capability

**Workflow**:
1. Corporator creates user accounts
2. Corporator assigns territories to leaders
3. Corporator updates user information
4. OPS analyzes user behavior and metrics

---

### Notifications

**Purpose**: Send alerts and updates to users

| Action | Corporator | Leader | Voter | OPS |
|--------|------------|--------|-------|-----|
| Send | Yes | No | No | No |
| View | Yes | Yes | Yes | Yes |

**Service Layer**: No scope restrictions; notification receipts visible to recipients only.

**Workflow**:
1. Corporator sends system notification
2. All users receive and view notifications

---

### Analytics and Insights

**Purpose**: Monitor platform performance and user engagement

| Feature | Corporator | Leader | Voter | OPS |
|---------|------------|--------|-------|-----|
| Basic Analytics | Yes | No | No | Yes |
| Advanced Analytics | Yes | No | No | Yes |
| Voter Intelligence | Yes | No | No | Yes |
| Leader Performance | Yes | No | No | Yes |
| Sentiment Analysis | Yes | No | No | Yes |
| Chat Analytics | Yes | No | No | Yes |
| Broadcast Performance | Yes | No | No | Yes |

**Access Pattern**: View-only; no modification capability.

**Data Visibility**:
- Corporator: System-wide analytics
- OPS: System-wide analytics with operational focus

**Workflow**:
1. Corporator reviews strategic metrics
2. OPS monitors operational health
3. Both use insights for decision-making

---

## Security Implementation

### Authentication Security

**Token Format**: JWT (JSON Web Token)

**Signature Algorithm**: HS256 (HMAC with SHA-256)

**Token Content**:
```json
{
  "sub": "user_id",
  "role": "user_role",
  "type": "access",
  "exp": 1234567890,
  "iat": 1234567800
}
```

**Token Validation**:
- Signature verified against server secret key
- Token type checked (must be "access", not "refresh")
- Expiration validated (current time < exp time)
- User verified to exist in database
- Role consistency checked between token and database

**Token Expiration**: Configurable via environment variable
- Default: 30 minutes for access tokens
- Refresh tokens issued for long-term authentication

---

### Password Security

**Hashing Algorithm**: bcrypt (PBKDF2-based)

**Salting**: Automatic per bcrypt specification

**Verification**: Constant-time comparison to prevent timing attacks

**Storage**: Only hashed values stored in database

**Requirements**: Enforced at registration time
- Minimum length requirement
- Complexity validation (optional)

---

### Authorization Enforcement

**Layer 1 - Route Level**:
- FastAPI HTTPBearer dependency validates token format
- `require_permission()` dependency validates permission
- Unauthorized access returns 401 or 403 status

**Layer 2 - Service Level**:
- Database queries scoped to user's accessible data
- Ownership verification before data modification
- Territory checks for leader-scoped resources
- Audit logging for sensitive operations

**Fail-Safe Principles**:
- Unknown roles default to no access
- Missing permissions default to denied
- Service layer always validates data ownership

---

### HTTPS and Transport Security

**Protocol**: HTTPS (SSL/TLS) required for production

**Headers**: Security headers included:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`

**CORS**: Configured for specified origin domains

---

## Audit and Compliance

### Audit Logging

**OPS Modifications Logged**:
- User ID of modifier
- Action type (UPDATE_STATUS, ASSIGN, RESOLVE, etc.)
- Resource type (complaint, appointment, etc.)
- Resource ID
- Changes made (before/after values)
- Timestamp of modification

**Log Retention**: Configurable (recommended: minimum 90 days)

**Log Access**: Restricted to authorized personnel only

---

### Compliance Features

**Data Isolation**: No user can access another user's personal data
- Voter cannot view other voters' complaints
- Leader cannot view other territories' data
- OPS has full visibility but cannot modify without audit

**Role-Based Permissions**: Enforced granularly across 40+ permissions

**Authentication Records**: Login attempts logged for security

**Password Policies**: Hashing and salting enforced

**Principle of Least Privilege**: Users receive minimum required permissions

---

### Monitoring and Alerting

**Suspicious Activity Detection**:
- Multiple failed login attempts
- Unauthorized access attempts
- Token manipulation attempts
- Unusual permission requests

**Admin Dashboard**: OPS console monitors:
- Active user sessions
- Recent login activity
- Failed authentication attempts
- Audit log review

---

## Summary

The Political Communication Platform implements a comprehensive, multi-layered RBAC system providing:

1. **Clear Role Separation**: Corporator > Leader > Voter hierarchy, with separate OPS role
2. **Granular Permissions**: 40+ permissions across 10 feature categories
3. **Dual-Layer Enforcement**: Route-level authorization + service-level data isolation
4. **Audit Compliance**: All sensitive operations logged with full change tracking
5. **Security First**: JWT token validation, bcrypt hashing, fail-safe defaults
6. **Scalability**: Permission matrix easily extensible for new features
7. **Operational Safety**: OPS role read-only with full audit trail

This architecture ensures secure, compliant operation while maintaining flexibility for organizational growth and feature expansion.
