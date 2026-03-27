# Complete Role-Based Access Control (RBAC) & Metrics Documentation

## Executive Summary

This document provides the complete Role-Based Access Control (RBAC) system implementation details including security architecture, role definitions, permission matrix, metrics visibility, and action freedom for the Political Communication Platform. The architecture implements a two-tier security model with granular permission management across multiple user roles and comprehensive audit trails.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Authentication Flow](#authentication-flow)
3. [Role Definitions](#role-definitions)
4. [Permission Matrix](#permission-matrix)
5. [Access Control Patterns](#access-control-patterns)
6. [Metrics Visibility Matrix](#metrics-visibility-matrix)
7. [Role-Specific Metrics Details](#role-specific-metrics-details)
8. [Action Freedom by Feature](#action-freedom-by-feature)
9. [Feature-by-Feature Access Control](#feature-by-feature-access-control)
10. [Data Aggregation and Privacy](#data-aggregation-and-privacy)
11. [Security Implementation](#security-implementation)
12. [Audit and Compliance](#audit-and-compliance)

---

# PART 1: RBAC SECURITY ARCHITECTURE

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

# PART 2: METRICS & ACTION FREEDOM

## Metrics Visibility Matrix

### High-Level Overview

| Metric Category | Corporator | Leader | Voter | OPS |
|---|---|---|---|---|
| System Overview | Full System | Territory Only | None | Full System |
| User Statistics | All Users | Territory Users | Own Profile | All Users |
| Role Distribution | All | Territory | None | All |
| Complaint Metrics | All | Territory | Own Only | All |
| Event Analytics | All | Territory | Own | All |
| Chat Analytics | All | None | None | All |
| Campaign Metrics | All | None | None | All |
| Sentiment Analysis | All | None | None | All |
| Leader Performance | All Leaders | Self Only | None | All Leaders |
| Geographic Analytics | All Areas | Own Territory | None | All Areas |
| Demographic Insights | All | None | None | All |
| Engagement Metrics | System-wide | Territory | Own | System-wide |

---

## Role-Specific Metrics Details

### 1. CORPORATOR Metrics Visibility

**Access Level**: Strategic Executive

**System Overview Metrics**:
- Total active users (by role: voters, leaders, corporators)
- User growth trends (daily, weekly, monthly)
- Geographic distribution of users
- Role-wise user breakdown
- Platform health indicators
- System feature availability status

**User Statistics**:
- Total voter count with engagement levels
- Total leader count with performance scores
- Corporator count in organization
- User registration trends over time
- User deactivation/churn metrics
- User demographics (age, gender, district, state)

**Complaint Management Metrics**:
- Total complaints system-wide
- Complaint status distribution (open, pending, resolved, escalated)
- Complaint categories (infrastructure, services, governance, etc.)
- Average complaint resolution time
- Complaint SLA compliance rates
- Complaints by geographic area
- Complaints by priority level
- Unresolved complaint trends

**Poll and Survey Metrics**:
- Total polls created
- Poll participation rates
- Poll response distribution
- Sentiment from poll responses
- Most impactful poll topics
- Engagement levels per poll

**Event Analytics**:
- Total events created
- Event attendance rates
- Attendance by geographic area
- Event participation trends
- Event engagement metrics
- Events by category

**Announcement Metrics**:
- Total announcements published
- Announcement reach (number of viewers)
- Announcement engagement (shares, reactions, acknowledgments)
- Announcement delivery status
- Most engaged announcements
- Announcement view patterns by role
- Acknowledgment rates

**Feedback Collection**:
- Total feedback received
- Feedback by sentiment (positive, neutral, negative)
- Feedback themes and categories
- Most common feedback topics
- Feedback response rates
- Feedback actionability metrics

**Leader Performance Metrics**:
- Individual leader performance scores
- Leader engagement levels
- Leader response times
- Leader complaint resolution rates
- Leader territory coverage
- Leader activity levels
- Leader ratings from voters
- Complaints handled per leader

**Voter Intelligence Metrics**:
- Voter segmentation by engagement level (highly engaged, moderate, low, inactive)
- Voter distribution by demographics (age groups, gender, location)
- Voter participation patterns in polls
- Voter feedback submission rates
- Voter appointment request behavior
- Silent/inactive voter identification and count
- Voter satisfaction trends

**Sentiment Analysis Metrics**:
- Overall system sentiment (positive, neutral, negative percentages)
- Sentiment trends over time (daily, weekly, monthly)
- Sentiment by geographic area
- Sentiment by feedback source (feedback form, complaints, poll responses)
- Negative sentiment spikes and triggers
- Sentiment impact of announcements/events
- Sentiment correlation with external events

**Chat and Communication Metrics**:
- Total messages sent
- Message types distribution (broadcast, individual, group)
- Message engagement (reactions, shares, forwards)
- Most active message topics
- Broadcast performance metrics
- Message delivery rates
- Community engagement through chat

**Campaign Metrics**:
- Campaign participation rates
- Campaign reach (total targeted vs. actual viewers)
- Campaign conversion rates
- Campaign budget vs. performance
- Campaign effectiveness scores
- Campaigns by category
- Campaign timeline tracking

**Geographic Analytics**:
- Complaint density by ward/area
- User distribution by ward/area
- Engagement rates by geographic region
- Most active areas
- Area-wise sentiment distribution
- Resource allocation recommendations by area
- Leader coverage by geographic area

**Real-Time Dashboards Available**:
- Executive Summary: Key metrics at a glance
- System Health: Platform performance, uptime, feature availability
- Operational Dashboard: All metrics updated in real-time
- Geographic Heatmap: Issue density visualization
- Sentiment Dashboard: Real-time sentiment tracking
- Leadership Dashboard: Individual and team performance
- Campaign Dashboard: Active campaign tracking

**Data Refresh Rate**: Real-time to 5-minute intervals

---

### 2. LEADER Metrics Visibility

**Access Level**: Territory Manager

**Metrics Visible to Leader** (Territory-Scoped Only):

**Personal Metrics**:
- Own profile and performance statistics
- Own task completion rates
- Own average response time
- Own rating from voters
- Own complaint handling count

**Territory-Specific Metrics**:
- User count in assigned territory
- Voter distribution in territory
- Number of active voters in territory
- Voter engagement levels in territory
- Voter demographics in territory (aggregated, not individual)

**Complaint Metrics** (Territory Only):
- Total complaints in territory
- Complaint status distribution (pending, in-progress, resolved)
- Complaints assigned to self
- Complaints from voters in territory
- Average resolution time for territory complaints
- Most common complaint categories in territory
- Complaints by priority in territory
- Territory-specific issue trends

**Feedback Metrics** (Territory Only):
- Feedback received from voters in territory
- Feedback sentiment distribution (positive, neutral, negative)
- Feedback themes in territory
- Most common topics in territory feedback
- Aggregated voter satisfaction in territory

**Appointment Metrics**:
- Appointments scheduled in territory
- Appointment confirmation rates
- Appointment cancellation rates
- Average appointment duration
- Appointment patterns by time/day
- No-show rates

**Event Metrics** (Territory Only):
- Events scheduled in territory
- Event attendance rates
- Events assigned to self
- Event participation trends in territory
- Event engagement in territory

**Activity Metrics**:
- Personal activity log (last login, last action)
- Tasks completed today/this week/this month
- Ground verification activities logged
- Area visits and coverage
- Call/meeting logs

**Real-Time Dashboards Available**:
- Personal Dashboard: Own metrics and activity
- Territory Overview: Territory-specific summary
- My Complaints: Complaints in own territory
- Appointment Calendar: Scheduled appointments
- Task Status: Active tasks and completions

**Metrics NOT Visible to Leaders**:
- Metrics from other territories
- System-wide metrics
- Other leaders' performance
- Voter intelligence (aggregated or individual)
- Sentiment analysis
- Campaign metrics
- Chat analytics
- Geographic areas outside territory
- Demographic segments outside territory

**Data Refresh Rate**: Hourly to Real-time for own activities

---

### 3. VOTER Metrics Visibility

**Access Level**: Personal Records Only

**Metrics Visible to Voter** (Personal Data Only):

**Personal Engagement Metrics**:
- Own participation in polls (history and results)
- Own feedback submissions (count and status)
- Own appointment requests (status and confirmations)
- Personal rating/feedback from leaders (if applicable)
- Own engagement level classification

**Personal Complaint Metrics**:
- Complaints created by self (count and history)
- Status of own complaints
- Resolution time for own complaints
- Notes added to own complaints
- Feedback on complaint resolution
- Complaint satisfaction rating option

**Appointment Metrics**:
- Own appointment requests
- Appointment dates and times
- Appointment status (pending, confirmed, completed, cancelled)
- Leader assigned to appointment
- Appointment location
- Appointment history

**Feedback on Services**:
- Option to provide feedback on complaint resolution
- Option to provide general platform feedback
- Option to rate leader interactions

**Announcements Received**:
- Count of announcements viewed
- Announcement titles and summaries (not individual acknowledgment counts)
- Acknowledgment status (read/unread)
- Personalized announcement targeting (by location/interests)

**Community Engagement** (Non-Identifying):
- Poll participation rates (own only)
- Engagement level classification (e.g., "highly engaged", "moderate", "low")
- Community events participated in (own attendance only)

**Activity Metrics**:
- Login frequency (own account)
- Last login time
- Feature usage patterns (own only)

**Real-Time Dashboards Available**:
- My Dashboard: Personal summary
- My Complaints: Complaint status tracking
- My Appointments: Appointment calendar
- My Polls: Poll participation history
- My Feedback: Feedback submissions history
- My Announcements: Announcement inbox

**Metrics NOT Visible to Voters**:
- Any other voter's data
- System-wide metrics
- Leader metrics
- Demographic distributions
- Sentiment analysis
- Geographic analytics
- Campaign metrics
- Chat analytics
- Complaint statistics (except own)
- Policy or performance data

**Data Refresh Rate**: Real-time for own data

---

### 4. OPS Metrics Visibility

**Access Level**: Operational Administration

**System Overview Metrics** (All Users, Aggregated):
- Total users by role
- User growth and trends
- User activation/deactivation rates
- User retention metrics
- Churn rate analysis
- Geographic user distribution (all areas)

**User Analytics**:
- Total voter count with segmentation
- Total leader count with performance
- Total corporator count
- User registration trends
- User demographics (aggregated, not individual profiles)
- User engagement distribution
- Inactive user identification (count of silent voters)
- Territory assignment status

**Role-Specific Analytics**:
- Voter metrics: Participation rates, engagement levels, demographics
- Leader metrics: Performance scores, efficiency, response times, coverage
- Corporator metrics: Active count, system administration activities

**Complaint Management** (System-Wide):
- Total complaints across all territories
- Complaint status distribution
- Complaint categories analysis
- Complaints by priority
- Complaints by geographic area
- Average resolution time (system-wide and by area)
- SLA compliance metrics
- Complaint escalation trends
- Leader complaint assignment distribution
- Complaints per leader metrics
- Complaint resolution patterns
- Complaint feedback and satisfaction

**Assignment and Triage Metrics**:
- Complaints awaiting assignment
- Assignment distribution fairness
- Average complaints per leader
- Under-assigned territories
- Over-loaded leaders

**Appointment Management**:
- Total appointments system-wide
- Appointment status distribution
- Appointment cancellation rates
- No-show rates by leader
- Average appointment duration
- Appointment confirmation rates
- Appointment trends over time

**Event Analytics**:
- Total events system-wide
- Event status tracking
- Event attendance rates
- Event participation by role
- Event effectiveness metrics
- Events by category
- Attendance trends

**Chat and Communication Analytics**:
- Total messages sent across system
- Messages by type (broadcast, individual, group)
- Message engagement rates (reactions, shares)
- Most active communication channels
- Communication patterns by time
- Broadcasting effectiveness metrics
- Message delivery rates
- Response time metrics

**Feedback Collection Metrics**:
- Total feedback received
- Feedback sentiment distribution (positive, neutral, negative, critical)
- Feedback by source (form, complaints, polls, chat)
- Feedback themes and topics
- Feedback actionability scores
- Feedback response rates
- Trends in feedback topics

**Sentiment Analysis** (System-Wide Aggregated):
- Overall system sentiment percentage
- Sentiment trends over time (daily, weekly, monthly)
- Sentiment by geographic area
- Sentiment by content type (announcements, events, decisions)
- Negative sentiment spike detection and analysis
- Area with highest negativity
- Sentiment impact before/after major announcements
- Sentiment correlation with complaints
- Sentiment correlation with events
- Early warning signals for sentiment decline

**Leader Performance Dashboard** (All Leaders):
- Performance scores for all leaders
- Individual leader efficiency metrics
- Leader response time rankings
- Leader complaint resolution rates
- Leader engagement with voters
- Leader task completion rates
- Leader activity tracking
- Leader territory coverage
- Leader ratings from voters
- Performance trends per leader

**Issue Intelligence** (Aggregated):
- Issue categories and frequencies
- Issue density by geography
- Issue trends over time
- Repeated issue identification
- Category-wise resolution patterns
- High-impact issues identification
- Issue resolution time by category
- Area-specific issue patterns

**Campaign Effectiveness**:
- Campaign participation rates
- Campaign reach vs. target
- Campaign conversion metrics
- Campaign budget tracking
- Campaign effectiveness scores
- Campaign timing impact
- Campaign messaging performance
- Audience segmentation effectiveness

**Geographic Analytics** (All Areas):
- Complaint density heatmap
- Issue heatmap by location
- User distribution by ward
- Engagement rates by area
- Sentiment distribution by area
- Event concentration by area
- Leader coverage gaps by area
- Resource allocation recommendations
- Area-specific trends and patterns

**Demographic Analytics** (Aggregated Only):
- User distribution by age group
- User distribution by gender
- User distribution by state/city
- Engagement patterns by demographic
- Sentiment by demographic
- Issue patterns by demographic
- Demographics of inactive users

**Real-Time Dashboards Available**:
- OPS Overview: System-wide dashboard with key metrics
- User Analytics: User segmentation and trends
- Complaint Management: System-wide complaint tracking
- Leader Performance: All leaders ranked and detailed
- Geographic Heatmap: Issue and user density visualization
- Sentiment Dashboard: Real-time sentiment monitoring
- Chat Analytics: Communication patterns and effectiveness
- Broadcast Performance: Announcement reach and engagement
- Campaign Tracking: Active campaigns and performance
- Area Detail: Drill-down into specific wards/territories
- Leader Detail: Individual leader performance analysis
- Demographic Segments: User distribution and patterns
- Activity Feed: Real-time system activities

**Advanced OPS Features**:
- Custom date range filtering (all endpoints support custom ranges)
- Geographic filtering and drill-down
- Role-based filtering (voters, leaders, corporators)
- Category and status filtering
- SLA threshold configuration
- Performance benchmarking
- Trend analysis (daily, weekly, monthly, yearly)
- Anomaly detection
- Comparative analysis between areas/leaders
- Export capabilities (aggregated data)

**Data Refresh Rate**: Real-time to 1-minute intervals

---

## Action Freedom by Feature

### 1. Announcement Management

#### Actions Available by Role

**CORPORATOR Actions**:
- Create announcements with targeting by role, geography, interests
- Publish announcements to live audience
- Edit published announcements (limited fields)
- Delete announcements (draft only)
- Archive announcements
- View announcement performance metrics
- Send announcement to specific user groups
- Set priority levels (low, normal, high, urgent)
- Schedule announcements for future publication
- View who acknowledged announcements (anonymized)
- See viewer counts and engagement

**LEADER Actions**:
- Create announcements for territory
- View territory announcements
- Cannot publish system-wide announcements
- Cannot delete or modify announcements
- Can acknowledge announcements
- Can view local announcement performance

**VOTER Actions**:
- View published announcements targeted to self
- Acknowledge receipt of announcements
- React to announcements (like, share, flag)
- View announcement history
- Cannot create announcements
- Cannot modify announcements
- Cannot see who else viewed announcements

**OPS Actions**:
- View all announcements
- Cannot create announcements
- Cannot delete announcements
- Cannot modify announcements
- View announcement performance from operational perspective

---

### 2. Poll and Survey Management

#### Actions Available by Role

**CORPORATOR Actions**:
- Create polls with single or multiple choice questions
- Set poll target audience (by role, geography)
- Publish polls for participants
- Close polls before deadline
- View poll results in real-time
- View participation breakdown by demographic
- View sentiment of poll responses
- Delete unpublished polls
- Export poll results
- Analyze poll response patterns

**LEADER Actions**:
- Cannot create polls
- Can participate in polls
- Can view poll options and results (aggregated)
- Can see participation from own territory
- Cannot close or modify polls

**VOTER Actions**:
- View published polls
- Participate in polls (vote once per poll)
- View poll results after voting or poll closure
- Cannot create polls
- Cannot see individual response details
- Cannot modify votes

**OPS Actions**:
- View all polls
- Cannot create polls
- Cannot delete polls
- Cannot modify polls
- View aggregate participation metrics
- View sentiment analysis of responses

---

### 3. Complaint Management

#### Actions Available by Role

**CORPORATOR Actions**:
- View all complaints system-wide
- Cannot directly create complaints (use Leader/Voter mechanisms)
- View complaint history and trends
- Approve complaint resolution
- Review complaint resolution quality
- View SLA compliance
- Assign complaints to leaders (via system rules)
- View all complaint notes and discussions
- Escalate complaints if needed
- Generate complaint reports
- Monitor complaint resolution rates

**LEADER Actions**:
- Create complaints on behalf of assigned voters (with voter consent/notification)
- View complaints from assigned territory
- Cannot view complaints from other territories
- Update complaint status (limited statuses: acknowledged, in-progress)
- Add notes to complaints
- Cannot close/resolve complaints without OPS
- Cannot reassign complaints
- View complaint history in territory
- Track complaint resolution progress

**VOTER Actions**:
- Create own complaints
- View own complaints only
- Cannot view other voters' complaints
- Update complaint description/details (draft stage only)
- Add follow-up information to own complaints
- Cannot change complaint status
- Cannot close own complaints
- Request updates on own complaints
- Provide feedback on complaint resolution
- Rate resolution quality

**OPS Actions**:
- View all complaints
- Assign complaints to appropriate handlers/leaders
- Update complaint status (all statuses available)
- Close/resolve complaints
- Reopen complaints if needed
- Add notes to complaints
- Verify complaint resolution
- Cannot create complaints
- Cannot delete complaints
- View audit trail of all changes
- Bulk operations on complaints (export, filter, analyze)
- Track SLA metrics

---

### 4. Appointment Scheduling

#### Actions Available by Role

**CORPORATOR Actions**:
- View all appointments system-wide
- Cannot create appointments directly
- View appointment calendar for all leaders
- View appointment statistics
- Analyze appointment patterns
- Monitor appointment fulfillment
- Cancel appointments if necessary (with justification)
- Reschedule appointments
- Cannot request appointments (personal)

**LEADER Actions**:
- View own appointment calendar
- Cannot create appointments directly for self
- Accept appointment requests from voters
- Reschedule appointments
- Cancel appointments with reason
- View appointment history
- Track no-shows
- View voter details for appointments (territory-scoped)

**VOTER Actions**:
- Request appointments with leaders
- View own appointment requests and history
- View appointment status (pending, confirmed, cancelled)
- Reschedule own appointments
- Cancel own appointments
- View leader details for appointment
- Provide feedback after appointment

**OPS Actions**:
- View all appointments
- Manage appointment conflicts
- Approve/disapprove appointment requests
- Reschedule appointments
- Cancel appointments
- Track appointment metrics
- Ensure appointment compliance
- Cannot request appointments

---

### 5. Event Management

#### Actions Available by Role

**CORPORATOR Actions**:
- Create events for system-wide or targeted audience
- Edit event details (before/after creation)
- Delete events
- Assign leaders to events
- Assign specific voters to events
- Set event scope (open, by-invitation, restricted)
- View event attendance
- Modify event status (draft, published, completed, cancelled)
- View event engagement metrics
- Cancel events
- Modify event date/time/location
- Set event capacity limits
- View registration list

**LEADER Actions**:
- Cannot create events
- Can view events in assigned territory
- Can update event participation status
- View event details
- Cannot modify event details
- Cannot delete events
- View who registered from territory
- Track territory participation
- Cannot invite others to events

**VOTER Actions**:
- View available events
- Register for public/open events
- View event details (location, time, description)
- Mark attendance at events
- Cannot create events
- Cannot modify event details
- Cannot cancel events
- Can unregister from events

**OPS Actions**:
- View all events
- Cannot create events
- Cannot delete events
- Cannot modify event details
- View event metrics and participation
- Track event effectiveness
- Generate event reports

---

### 6. Feedback Collection

#### Actions Available by Role

**CORPORATOR Actions**:
- View all feedback system-wide
- View feedback by category
- View feedback by source (form, complaint, poll)
- Analyze feedback trends
- View feedback sentiment distribution
- Cannot create feedback directly
- Cannot delete feedback
- Cannot modify feedback
- Generate feedback reports
- Identify feedback patterns and themes

**LEADER Actions**:
- Create feedback (personal)
- View feedback from own territory
- Cannot view feedback from other territories
- Cannot modify others' feedback
- Cannot delete feedback
- View aggregated sentiment in territory

**VOTER Actions**:
- Create own feedback
- View own feedback submissions
- Cannot view other voters' feedback
- Cannot modify submitted feedback
- Cannot delete feedback
- Optional: Rate/review feedback usefulness

**OPS Actions**:
- View all feedback
- Cannot create feedback directly
- Cannot delete feedback
- Cannot modify feedback
- View feedback by any filter
- Track feedback themes
- Generate feedback analytics
- Identify actionable feedback

---

### 7. User Management

#### Actions Available by Role

**CORPORATOR Actions**:
- Create new user accounts (any role)
- View all user profiles
- Edit user information
- Delete user accounts (with deactivation)
- Assign leaders to territories
- Change user roles
- Reset user passwords
- View user activity history
- Deactivate/reactivate accounts
- Manage user permissions (within system constraints)
- View user engagement scores
- Bulk user operations

**LEADER Actions**:
- Cannot create new users
- View own profile
- Edit own profile (limited fields: phone, address, preferences)
- View profiles of voters in territory
- Cannot delete users
- Cannot change roles
- Cannot reset passwords
- Cannot edit other leaders' profiles
- View aggregated user stats for territory

**VOTER Actions**:
- View own profile
- Edit own profile (phone, address, preferences, language, interests)
- Cannot edit other profiles
- Cannot create users
- Cannot delete users
- Cannot change roles
- Cannot view other voters' profiles

**OPS Actions**:
- View all user profiles
- Cannot create users
- Cannot delete users
- Cannot modify user details
- Cannot reset passwords
- Cannot change roles
- View user analytics and metrics
- Generate user reports
- Track user activity

---

### 8. Notification System

#### Actions Available by Role

**CORPORATOR Actions**:
- Send notifications to all users or specific groups
- Send notifications to territories
- Send notifications to role-based groups
- Schedule notifications
- View notification delivery status
- View notification acknowledgment rates
- Cannot receive notifications (no read permission)

**LEADER Actions**:
- Cannot send notifications to system
- View notifications received
- Cannot create notifications

**VOTER Actions**:
- View notifications received
- Mark notifications as read
- Cannot send notifications

**OPS Actions**:
- View notification delivery metrics
- View notification performance
- Cannot send notifications
- Cannot delete notifications

---

### 9. Analytics and Reporting

#### Actions Available by Role

**CORPORATOR Actions**:
- Access all analytics dashboards
- View system-wide metrics
- Generate custom reports
- Filter by any dimension (role, geography, time period)
- Export reports
- Schedule recurring reports
- View real-time dashboards
- Drill-down into specific areas/leaders
- Comparative analysis
- Trend analysis
- Cannot modify analytics data
- Cannot delete historical data

**LEADER Actions**:
- Access personal performance dashboard
- View territory-specific metrics
- Cannot view system-wide metrics
- Cannot view other territories
- Cannot view other leaders' metrics
- Limited report generation (territory-scoped)
- Cannot export data
- Cannot access advanced analytics

**VOTER Actions**:
- Cannot access analytics
- Cannot view system metrics
- Can view own engagement level (classification only)
- Can view personal activity summary

**OPS Actions**:
- Access all analytics dashboards
- View system-wide metrics
- Drill-down capability (areas, leaders, demographics)
- Generate system reports
- Custom date range filtering
- Export aggregated data
- Cannot modify analytics
- Cannot delete data
- Cannot create ad-hoc metrics
- Comprehensive dashboards with all filters

---

### 10. Chat and Messaging

#### Actions Available by Role

**CORPORATOR Actions**:
- Send broadcast messages to all users
- Send messages to specific groups
- View aggregated chat metrics
- Monitor communication patterns
- Cannot view individual message content (privacy)
- Cannot delete messages

**LEADER Actions**:
- Send messages within territory
- Cannot broadcast system-wide
- Participate in group chats
- Cannot view other territory messages
- Cannot delete messages

**VOTER Actions**:
- Receive broadcast messages
- Participate in group chats
- Cannot send broadcast messages
- Cannot view system metrics

**OPS Actions**:
- View aggregated chat metrics
- Monitor communication patterns
- View chat performance (delivery, engagement)
- Cannot view individual message content
- Cannot send messages
- Cannot delete messages

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

## Data Aggregation and Privacy

### Critical Privacy Principles

**Voter Data Never Exposed Individually**:
- Demographic analysis shows distributions, not names
- Sentiment analysis shows percentages, not voter-to-opinion mapping
- Feedback themes are extracted, not tied to individuals
- Geographic analysis shows area-level counts, not household-level
- Silent voter identification shows count, not names/IDs

**Example - Voter Intelligence Endpoint**:
```
VISIBLE TO CORPORATOR AND OPS:
- 45% of voters in Ward 5 are highly engaged
- 30% are moderately engaged
- 25% are inactive
- Age group 25-35 has highest engagement
- Gender split: 52% male, 48% female
- 127 voters identified as silent (inactive 30+ days)

NOT VISIBLE:
- Names of inactive voters
- Individual voter IDs
- Specific voter addresses
- Specific voter engagement patterns
- Individual voter demographics
```

**Example - Sentiment Analysis**:
```
VISIBLE TO CORPORATOR AND OPS:
- Overall system sentiment: 68% positive, 22% neutral, 10% negative
- Negative spike on March 15 (40% negative)
- Issue: Infrastructure complaints triggered spike
- Area with highest negativity: Ward 7 (35% negative)
- Age group 45+ shows 25% negative sentiment

NOT VISIBLE:
- Which specific voter submitted negative feedback
- Names tied to complaints
- Individual sentiment tracking
- Voter-to-complaint mapping
```

### Data Aggregation Levels

**Territory Level** (Leader Access):
- Aggregated metrics for assigned territory only
- Counts and distributions within territory
- Trends specific to territory

**Area Level** (OPS & Corporator):
- Aggregated metrics by geographic area
- Comparison between areas
- Area-level trends

**System Level** (OPS & Corporator):
- System-wide aggregated metrics
- Role-wise distributions
- Overall platform trends

---

## Real-Time Dashboard Access

### CORPORATOR Dashboard

**Executive Summary**:
- Active users (total, by role)
- Complaints pending (count)
- Events active (count)
- Sentiment status (positive %)
- System health indicator

**Drill-Down Dashboards**:
1. Geographic Heatmap: Click on area for detail
2. Leader Performance: Sort and compare leaders
3. Complaint Analysis: Filter by category, priority, status
4. Sentiment Trends: Time-series visualization
5. Campaign Effectiveness: Current campaigns performance
6. Engagement Patterns: User participation trends

### LEADER Dashboard

**Personal Summary**:
- My complaints (pending, in-progress, resolved)
- My appointments (today, upcoming)
- Territory user count
- Territory engagement status
- My performance metrics (response time, rating)

**Territory View**:
- Active voters in territory
- Recent complaints
- Upcoming appointments
- Territory sentiment status

### VOTER Dashboard

**Personal Summary**:
- My complaints (status and count)
- My appointments (upcoming and history)
- Polls available to me
- Recent announcements
- Engagement level

### OPS Dashboard

**System Overview Tab**:
- User statistics (all roles)
- Complaint metrics (all territories)
- Event tracking (all active)
- Chat metrics (all channels)
- Campaign effectiveness (all)
- Sentiment status (system-wide)
- Health indicators

**Drill-Down Tabs**:
1. Users: Role-wise breakdown with detail
2. Complaints: All dimensions filterable
3. Leaders: Individual performance analysis
4. Geographic: Ward-by-ward detail
5. Campaigns: Campaign performance tracking
6. Chat: Communication pattern analysis
7. Sentiment: Real-time mood tracking
8. Feedback: Theme and action items

---

## Limitations and Restrictions

### CORPORATOR Limitations

- Cannot perform day-to-day operations (cannot update complaint status individually)
- Cannot view individual voter data (privacy protected)
- Cannot send direct messages to individual voters
- Cannot modify analytic calculations
- Cannot bypass SLA or system rules
- Cannot view chat message content (only metrics)

### LEADER Limitations

- Cannot access metrics outside assigned territory
- Cannot create system-level communications
- Cannot modify user accounts
- Cannot access advanced analytics
- Cannot view other leaders' data
- Cannot change system settings
- Cannot escalate complaints beyond limited scope
- Cannot view voter personal information beyond territory assignment

### VOTER Limitations

- Cannot view any user's data except own
- Cannot view system metrics
- Cannot create system content
- Cannot modify any complaint status
- Cannot send broadcast messages
- Cannot view aggregate analytics
- Cannot access operational dashboards
- Cannot modify their own role or permissions

### OPS Limitations

- Cannot create any content (announcements, events, polls, users)
- Cannot delete any content or users
- Cannot modify core complaint/appointment details
- Cannot send messages or broadcasts
- Cannot change user roles
- Cannot create new features
- Cannot modify analytics methodology
- Cannot access individual voter personal data (only aggregated)

---

## Action Audit Trail

All sensitive actions are logged:

**Actions Logged**:
- Complaint status changes (by OPS/Leader)
- User creation/deletion/modification (by Corporator)
- Permission changes (by Corporator)
- Appointment modifications (by anyone)
- Event creation/modification (by Corporator)
- User access to sensitive data (OPS analytics access)
- Bulk operations

**Audit Information Retained**:
- User ID who performed action
- Action type and description
- Resource ID affected
- Before/after values (for modifications)
- Timestamp
- IP address (if available)
- Reason/justification (if provided)

**Retention Policy**: Minimum 90 days (configurable, recommend 1 year)

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

## Summary Table: Action Freedom

| Action | Corporator | Leader | Voter | OPS |
|--------|---|---|---|---|
| Create Announcement | Yes (system) | Yes (territory) | No | No |
| Create Poll | Yes | No | No | No |
| Create Complaint | No | Yes (behalf) | Yes (own) | No |
| Manage Complaint Status | View only | Limited | No | Yes (full) |
| Create Event | Yes | No | No | No |
| Register for Event | Yes | Yes | Yes | No |
| Create Feedback | No | Yes | Yes | No |
| Create User | Yes | No | No | No |
| Send Notification | Yes | No | No | No |
| View All Metrics | Yes | No (territory) | No (personal) | Yes |
| Export Reports | Yes | Limited | No | Yes (aggregated) |
| View Chat Content | No (metrics only) | No | No | No (metrics only) |
| Modify Analytics | No | No | No | No |
| Delete Users | Yes (deactivate) | No | No | No |

---

## Complete Role Hierarchy and Permissions Summary

### Role Hierarchy (Political Authority Chain)

```
CORPORATOR (Rank 2 - Highest Authority)
    |
    v
LEADER (Rank 1 - Field Authority)
    |
    v
VOTER (Rank 0 - End User)

OPS (Rank None - Separate from Hierarchy)
```

### Permission Count by Role

- **Corporator**: 40 permissions (Full system access)
- **Leader**: 18 permissions (Territory-scoped)
- **Voter**: 8 permissions (Personal data only)
- **OPS**: 18 permissions (Management and analytics only)

### Key Distinctions

- **Corporator vs OPS**: Corporator has political authority but OPS has operational management (no creation/deletion)
- **Leader vs Voter**: Leader manages territory; Voter manages personal records
- **All Roles**: Privacy-first approach ensures no individual data exposure

---

This comprehensive documentation provides complete clarity on RBAC security architecture, metrics visibility, and action freedom for each role, enabling informed decision-making during pitch presentations and stakeholder discussions.
