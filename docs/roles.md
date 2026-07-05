# Canopy Role Catalog

Every role below is a **RoleTemplate** in domain-model terms: catalog data, never code. Each entry has a stable kebab-case `key` (the serialization identifier), a purpose, and responsibilities written as *duty → deliverable contract* — because in Canopy a responsibility is only real if discharging it produces something checkable.

Deliverable notation: **(A)** = Artifact, **(Att)** = ActionAttestation.

Roles are grouped by domain. Archetypes (see `archetypes.md`) compose their role palettes from these groups; formations (see `teams.md`) wire them into reusable subtrees.

---

## Leadership & Coordination

These roles are managers: they decompose intents, issue briefs and directives, declare dependencies, accept deliverables, and resolve gates. Any archetype's root is one of these.

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `chief-executive` | Chief Executive | Org root; owns the standing intent and delegates everything else | Decompose standing intent → child Assignments (A: DelegationPlan); accept subtree deliverables (Att: AcceptanceDecision); compile status → (A: StatusReport) |
| `general-manager` | General Manager | Runs a self-contained business unit against a P&L | Prioritize backlog → (A: PriorityList); resolve escalations (Att: EscalationResolution); budget oversight (Att: BudgetReview) |
| `team-lead` | Team Lead | First-line manager of a small delivery team | Decompose briefs → child Assignments (A: TaskBreakdown); review/accept work (Att: ReviewDecision); unblock reports (Att: GateResolution) |
| `program-manager` | Technical Program Manager | Cross-team sequencing and dependency management | Translate business intent → (A: FeatureBrief); declare dependency graphs (A: DependencyMap); track milestones → (A: MilestoneReport) |
| `chief-of-staff` | Chief of Staff | Aggregates upward reporting; runs the operating cadence | Compile subtree progress → (A: StatusReport); run cadences (Att: CadenceExecution); flag risks → (A: RiskRegister) |
| `coordinator` | Coordinator | General-purpose logistics and scheduling under any manager | Secure resources/bookings (Att: BookingConfirmation); maintain schedules → (A: Schedule) |

## Software Engineering

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `engineering-lead` | Engineering Lead | Technical decomposition and code quality for a pod | Break features into technical plans → (A: TechPlan); review code → (Att: ReviewDecision); own standards (A: EngineeringGuideline) |
| `backend-engineer` | Backend Engineer | Server-side implementation | Implement features → (A: PullRequest); fix defects → (A: PullRequest); write unit tests → (A: TestSuite) |
| `frontend-engineer` | Frontend Engineer | Client-side implementation | Implement UI from specs → (A: PullRequest); integrate APIs → (A: PullRequest) |
| `fullstack-engineer` | Full-Stack Engineer | End-to-end feature slices | Ship vertical slices → (A: PullRequest) |
| `mobile-engineer` | Mobile Engineer | iOS/Android implementation | Implement mobile features → (A: PullRequest); prepare releases → (A: ReleaseCandidate) |
| `qa-engineer` | QA Engineer | Verification and acceptance evidence | Write test plans → (A: TestPlan); execute verification → (A: TestReport); reproduce defects → (A: BugReport) |
| `code-reviewer` | Code Reviewer | Dedicated deep review (security, performance, correctness) | Review PRs → (A: ReviewReport) |
| `tech-writer` | Technical Writer | Developer-facing documentation | Write/maintain docs → (A: DocPage); write runbooks → (A: RunbookDoc) |

## Infrastructure, Security & Reliability

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `sre-lead` | SRE Lead | Reliability standards and infra spend oversight | Define SLOs → (A: SLODefinition); approve infra spend (Att: ApprovalDecision); run postmortem reviews (Att: ReviewDecision) |
| `cloud-architect` | Cloud Architect | Infrastructure design | Draft IaC blueprints → (A: InfraSpec); capacity planning → (A: CapacityPlan) |
| `platform-engineer` | Platform Engineer | Internal developer tooling and CI/CD | Build/maintain pipelines → (A: PullRequest); improve dev experience → (A: ToolingRelease) |
| `incident-responder` | Incident Responder | On-call triage and recovery | Triage alerts → (A: TriageNote); execute recovery (Att: RecoveryAttestation); draft postmortems → (A: IncidentPostmortem) |
| `security-engineer` | Security Engineer | Application and infra security | Threat-model designs → (A: ThreatModel); run security reviews → (A: SecurityReport); patch vulnerabilities → (A: PullRequest) |
| `security-analyst` | Security Analyst | Detection and monitoring | Investigate alerts → (A: InvestigationReport); tune detections → (A: DetectionRule) |

## Data & AI

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `data-engineer` | Data Engineer | Pipelines and data infrastructure | Build ETL pipelines → (A: PullRequest); maintain data quality → (A: DataQualityReport) |
| `data-analyst` | Data Analyst | Queries, dashboards, insight | Answer data questions → (A: AnalysisReport); build dashboards → (A: Dashboard) |
| `data-scientist` | Data Scientist | Statistical modeling and experimentation | Design experiments → (A: ExperimentDesign); run models → (A: DataModel); interpret results → (A: FindingsReport) |
| `ml-engineer` | ML Engineer | Model training, evaluation, deployment | Train models → (A: ModelCard); build eval harnesses → (A: EvalReport); productionize → (A: PullRequest) |

## Product & Design

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `product-manager` | Product Manager | What to build and why | Write specs → (A: ProductSpec); prioritize roadmap → (A: Roadmap); synthesize feedback → (A: InsightsReport) |
| `design-lead` | Design Lead | Design quality and system consistency | Review designs (Att: ReviewDecision); own design system → (A: DesignSystemUpdate) |
| `product-designer` | Product Designer | Flows, wireframes, high-fidelity UI | Design features → (A: DesignSpec); prototype → (A: Prototype) |
| `ux-researcher` | UX Researcher | User evidence | Plan studies → (A: ResearchPlan); run studies → (A: ResearchReport) |
| `content-designer` | Content Designer | In-product language | Write UX copy → (A: CopyDoc) |

## Marketing, Growth & Content

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `marketing-lead` | Marketing Lead | Campaign strategy and brand | Plan campaigns → (A: CampaignBrief); approve creative (Att: ApprovalDecision); report performance → (A: PerformanceReport) |
| `content-writer` | Content Writer | Long-form and short-form content | Draft content → (A: ContentPiece) |
| `editor` | Editor | Quality gate for published words | Edit drafts → (A: EditedDraft); enforce style (Att: ReviewDecision) |
| `growth-analyst` | Growth Analyst | Funnel measurement and experiments | Design growth experiments → (A: ExperimentDesign); analyze funnels → (A: FunnelReport) |
| `social-media-manager` | Social Media Manager | Distribution and engagement | Schedule/publish posts (Att: PublishAttestation); report engagement → (A: EngagementReport) |

## Sales & Customer

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `sales-director` | Sales Director | Targets, pricing authority, deal escalations | Set quotas → (A: QuotaPlan); resolve discount escalations (Att: EscalationResolution) |
| `sales-development-rep` | Sales Development Rep | Top-of-funnel outreach | Prospect and qualify → (A: QualifiedLead); log outreach (Att: OutreachAttestation) |
| `account-executive` | Account Executive | Pitch, negotiate, close | Run pitches (Att: MeetingAttestation); produce proposals → (A: Proposal); close → (A: SignedContract) |
| `solutions-engineer` | Solutions Engineer | Technical depth in the sales cycle | Run technical demos (Att: DemoAttestation); answer security questionnaires → (A: QuestionnaireResponse) |
| `support-agent` | Support Agent | Front-line ticket resolution | Resolve tickets (Att: ResolutionAttestation); escalate with context → (A: EscalationPackage) |
| `support-engineer` | Support Engineer | Deep technical escalations | Diagnose escalations → (A: DiagnosisReport); file product defects → (A: BugReport) |
| `knowledge-base-writer` | Knowledge Base Writer | Turn resolutions into reusable answers | Write KB articles → (A: KBArticle) |
| `customer-success-manager` | Customer Success Manager | Retention and account health | Run account reviews → (A: HealthReport); drive renewals → (A: RenewalPlan) |

## People & Recruiting

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `recruiter` | Recruiter | Own the hiring pipeline for open roles | Screen candidates → (A: ScreenNote); manage pipeline → (A: PipelineReport); extend offers → (A: OfferPacket) |
| `sourcer` | Sourcer | Fill the top of the hiring funnel | Source candidates → (A: CandidateList); log outreach (Att: OutreachAttestation) |
| `interview-coordinator` | Interview Coordinator | Loop logistics | Schedule loops (Att: BookingConfirmation); collect feedback → (A: FeedbackPacket) |

## Finance & Legal

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `finance-controller` | Controller | Accurate books and the monthly close | Run the close → (A: ClosePackage); review reconciliations (Att: ReviewDecision) |
| `staff-accountant` | Staff Accountant | Journal entries and reconciliation | Prepare journal entries → (A: JournalEntry); reconcile accounts → (A: Reconciliation) |
| `financial-analyst` | Financial Analyst | Variance and forecasting | Analyze variances → (A: VarianceReport); build forecasts → (A: Forecast) |
| `legal-counsel` | Legal Counsel | Contracts and risk judgment | Review contracts → (A: ContractRedline); assess risk → (A: RiskMemo); approve exceptions (Att: ApprovalDecision) |
| `contracts-analyst` | Contracts Analyst | Templated agreement throughput | Triage NDAs → (A: TriageNote); fill templates → (A: DraftAgreement) |
| `compliance-officer` | Compliance Officer | Regulatory adherence | Audit processes → (A: AuditReport); maintain policies → (A: PolicyDoc) |

## Physical Operations

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `store-manager` | Store Manager | Shift orchestration and exception handling | Staff/sequence shifts → (A: ShiftPlan); resolve floor exceptions (Att: InterventionResolution); manage inventory → (A: InventoryOrder) |
| `cashier` | Cashier / Teller | Customer-facing order capture | Take orders → (A: OrderTicket); handle payment (Att: PaymentAttestation) |
| `line-cook` | Line Cook (Station) | Execute one station to spec and tempo | Prepare station items (Att: StationAttestation); flag equipment failures (Att: FaultReport) |
| `expeditor` | Expeditor | Assemble and verify complete orders | Assemble orders (Att: OrderCompleteAttestation) |
| `general-contractor` | General Contractor | Sequence trades, hold the master budget | Sequence trades → (A: WorkSchedule); accept trade work (Att: AcceptanceDecision); procure materials → (A: PurchaseOrder) |
| `carpenter` | Carpenter | Structural build work | Build to blueprint (Att: BuildAttestation) |
| `electrician` | Electrician | Wiring to code | Wire to code (Att: WiringAttestation) |
| `site-inspector` | Site Inspector | Code compliance gate | Inspect work → (A: InspectionReport) |
| `warehouse-lead` | Warehouse Lead | Fulfillment throughput | Plan pick/pack waves → (A: WavePlan); resolve exceptions (Att: InterventionResolution) |
| `picker-packer` | Picker/Packer | Order fulfillment execution | Pick and pack orders (Att: FulfillmentAttestation) |
| `inventory-analyst` | Inventory Analyst | Stock accuracy and reordering | Cycle counts → (A: CountReport); reorder proposals → (A: ReorderProposal) |

## Healthcare (Clinic)

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `clinic-director` | Clinic Director | Care quality and clinic operations | Approve protocols (Att: ApprovalDecision); review outcomes → (A: OutcomesReport) |
| `physician` | Physician | Diagnosis and care decisions | Examine and diagnose → (A: CarePlan); order tests (Att: OrderAttestation) |
| `nurse` | Nurse | Patient intake and care execution | Intake patients → (A: IntakeNote); administer care (Att: CareAttestation) |
| `medical-scheduler` | Medical Scheduler | Patient flow | Book appointments (Att: BookingConfirmation); manage waitlists → (A: ScheduleReport) |

## Research & Education

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `principal-investigator` | Principal Investigator | Research direction and final review | Set research intent → (A: ResearchBrief); review findings (Att: ReviewDecision); secure funding → (A: GrantProposal) |
| `literature-analyst` | Literature Analyst | Survey existing knowledge | Review literature → (A: LitReview) |
| `research-assistant` | Research Assistant | Data collection and experiment execution | Run protocols (Att: ProtocolAttestation); collect data → (A: Dataset) |
| `manuscript-drafter` | Manuscript Drafter | Synthesis into publishable form | Draft manuscripts → (A: Manuscript); handle review responses → (A: RevisionMemo) |
| `curriculum-designer` | Curriculum Designer | Learning architecture | Design course outlines → (A: CourseOutline); define assessments → (A: AssessmentSpec) |
| `instructional-writer` | Instructional Writer | Lesson content | Write lesson modules → (A: LessonModule) |
| `assessment-reviewer` | Assessment Reviewer | Pedagogical quality gate | Review modules → (A: ReviewReport) |

## Media & Events

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `managing-editor` | Managing Editor | Editorial direction and standards | Assign stories → (A: StoryBrief); final publication approval (Att: ApprovalDecision) |
| `reporter` | Reporter | Investigation and drafting | Investigate → (A: InterviewNotes); draft stories → (A: StoryDraft) |
| `fact-checker` | Fact Checker | Verification gate | Verify claims → (A: FactCheckReport) |
| `event-producer` | Event Producer | Own an event end-to-end | Plan events → (A: EventRunSheet); accept vendor work (Att: AcceptanceDecision) |
| `stage-manager` | Stage Manager | Day-of execution | Run the show (Att: ShowAttestation); manage cues → (A: CueSheet) |
| `av-technician` | AV Technician | Sound, video, streaming | Set up and operate AV (Att: SetupAttestation); deliver recordings → (A: RecordingFile) |

## Professional Services

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `engagement-manager` | Engagement Manager | Client relationship and delivery quality | Scope engagements → (A: StatementOfWork); manage client escalations (Att: EscalationResolution) |
| `consultant` | Consultant | Analysis and recommendation | Analyze problems → (A: AnalysisDeck); interview stakeholders → (A: InterviewNotes) |
| `account-manager` | Account Manager (Agency) | Client servicing for agency work | Translate client asks → (A: CreativeBrief); manage feedback rounds → (A: FeedbackDigest) |
| `creative-director` | Creative Director | Creative quality gate | Review creative (Att: ReviewDecision); set direction → (A: CreativeDirection) |

## Nonprofit & Community

| Key | Title | Purpose | Responsibilities → Deliverables |
|---|---|---|---|
| `development-director` | Development Director | Fundraising strategy and donor stewardship | Plan campaigns → (A: FundraisingPlan); steward major donors (Att: MeetingAttestation) |
| `grant-writer` | Grant Writer | Institutional funding | Draft grant applications → (A: GrantProposal); track deadlines → (A: DeadlineCalendar) |
| `volunteer-coordinator` | Volunteer Coordinator | Mobilize and schedule people | Recruit volunteers → (A: VolunteerRoster); coordinate shifts (Att: ShiftConfirmation) |
| `community-lead` | Community Lead | Local presence and engagement | Run community events (Att: EventAttestation); publish updates → (A: Newsletter) |
