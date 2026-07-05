# Canopy Organization Archetypes: Blueprints for Democratized Scale

The beauty of Canopy is that it treats organizational structure as a living, programmable tapestry. By defining roles, establishing strict reporting chains, and routing immutable artifacts, a single individual can orchestrate massive, synchronized efforts. The framework democratizes capitalism by allowing anyone to spin up the exact human machinery required to solve complex problems—tangible or intangible.

Below is a foundational document enumerating a variety of organizational archetypes, exploring their internal roles, the problems they solve, and the structural dynamics that make them work.

**How to read an archetype.** An archetype is an `OrganizationType` in domain-model terms: it defines the role palette a user can drag from when building a chart of that type, and it suggests default formations (see `teams.md`). Roles are referenced by key from `roles.md`. Every archetype has a stable kebab-case key for serialization. Archetypes nest: a large company is a parent org (`saas-company`) with children (`customer-support-center`, `finance-back-office`) mounted at reporting points — the Corporate Chassis section exists precisely to be nested under any parent.

---

## 1. The Tech Enterprise: Building the Digital World

Large software companies are not single entities; they are federations of highly specialized, nested teams. Canopy handles this gracefully by nesting specific `OrganizationTypes` under a massive corporate umbrella.

### Archetype 1A: Core Product Engineering

**Key:** `product-engineering` · **Formations:** `product-engineering-pod`, `design-studio-cell`

**The Problem:** Translating ambiguous market requirements into shipped, stable, and highly performant code.
**Example Intent:** "Release the new multi-tenant billing microservice to production by Q3."

**Roles & Responsibilities:**

* **Technical Product Manager** (`program-manager`): The root node for the engagement. Translates standing business intents into structured feature briefs and manages cross-team dependencies.
* **Engineering Lead** (`engineering-lead`): Receives the brief from the TPM and decomposes it into an ordered `Plan` of technical `Assignments` for the developers.
* **Backend Engineer** (`backend-engineer`): Executes code-writing assignments, producing immutable `PullRequest` artifacts.
* **QA Automation Engineer** (`qa-engineer`): Writes end-to-end (E2E) test suites to debug complex race conditions, consuming the `PullRequest` to discharge a `TestReport` artifact.

**The Dynamic:** The Engineering Lead fans out an Intent into parallel assignments. The QA Engineer sits completely idle behind a `DependencyGate`, waiting for the Backend Engineer's `PullRequest` artifact to be accepted. If the E2E test suite fails, the QA Engineer's `TestReport` becomes the brief for a rework cycle, hitting the Backend Engineer's original `BudgetMeter`.

### Archetype 1B: Site Reliability & Infrastructure (SRE)

**Key:** `site-reliability` · **Formations:** `incident-response-squad`, `platform-pod`

**The Problem:** Maintaining high availability and scaling infrastructure to meet user demand without manual intervention.
**Example Intent:** "Migrate the primary database cluster to a multi-region active-active setup."

**Roles & Responsibilities:**

* **SRE Director** (`sre-lead`): Monitors the overall `BudgetMeter` for cloud compute spend and defines the standing reliability intent.
* **Cloud Architect** (`cloud-architect`): Drafts the infrastructure-as-code (IaC) blueprints.
* **Incident Responder** (`incident-responder`): A specialized role that operates primarily on `InterventionGates` and automated alerts, attesting to system recoveries.

**The Dynamic:** This team operates heavily on `Cadences` rather than episodic intents. A daily cadence triggers the Cloud Architect to review server loads. When infrastructure changes require spending real money to spin up new clusters, the Architect hits an `ApprovalGate`, requiring the SRE Director's explicit consent before the consequential action occurs.

### Archetype 1C: Go-to-Market (GTM) & Enterprise Sales

**Key:** `enterprise-sales` · **Formations:** `sales-pod`

**The Problem:** Identifying targets, qualifying leads, and closing high-value software contracts.
**Example Intent:** "Close $500k in new enterprise annual recurring revenue (ARR) this quarter."

**Roles & Responsibilities:**

* **Sales Director** (`sales-director`): Sets the strategic targets and resolves `EscalationGates` regarding contract discounts.
* **Sales Development Rep** (`sales-development-rep`): Conducts cold outreach and produces a `QualifiedLead` artifact.
* **Account Executive** (`account-executive`): Consumes the lead artifact, runs the pitch, and produces a `SignedContract`.

**The Dynamic:** The SDR operates almost entirely on `ActionAttestations`—logging that an email was sent or a phone call was made. When an AE is stuck negotiating a massive deal, they open an `EscalationGate`. The Sales Director can either resolve it with an answer ("offer a 10% discount") or grant a temporary **brokered channel**, introducing the AE directly to a Cloud Architect from the SRE team to answer complex technical security questions for the client.

### Archetype 1D: Platform Engineering

**Key:** `platform-engineering` · **Formations:** `platform-pod`

**The Problem:** Product teams reinventing infrastructure badly; slow builds, flaky deploys, inconsistent tooling.
**Example Intent:** "Cut median CI time to under 8 minutes and give every pod one-command preview environments."

**Roles:** `engineering-lead`, `platform-engineer`, `cloud-architect`, `security-engineer`.

**The Dynamic:** The customer is internal. Requests arrive as `EscalationGates` from peer pods, resolved via brokered channels — and channel telemetry matters doubly here: if every pod keeps getting introduced to platform, that's the signal to grow the pod, exactly Conway's law read as tooling demand.

### Archetype 1E: Security Operations

**Key:** `security-operations` · **Formations:** `incident-response-squad` (security-flavored)

**The Problem:** Finding vulnerabilities before attackers do, and responding when they find them first.
**Example Intent:** "Complete the quarterly threat review of the payments path and close all criticals."

**Roles:** `security-engineer`, `security-analyst`, `incident-responder`, reporting to an `sre-lead` or dedicated security lead.

**The Dynamic:** Two rhythms coexist: cadence-driven reviews (`ThreatModel`, `SecurityReport` on a schedule) and alert-driven investigation (`InvestigationReport` on demand). Disclosure and patching of production systems are governed actions — an `ApprovalGate` stands between finding and touching.

### Archetype 1F: Data & Analytics

**Key:** `data-analytics` · **Formations:** `data-insights-cell`

**The Problem:** Decisions being made on vibes because the data is scattered, stale, or wrong.
**Example Intent:** "Stand up the retention dashboard and tell me whether January's pricing change actually worked."

**Roles:** `team-lead`, `data-engineer`, `data-analyst`, `data-scientist`.

**The Dynamic:** Question-shaped intents decompose into pipeline work (engineer), descriptive answers (analyst), and causal answers (scientist). The scientist's `FindingsReport` frequently contradicts the asker's hopes — which routes upward as a deliverable, not a diplomatic problem, because acceptance is contract-based.

### Archetype 1G: Applied ML

**Key:** `applied-ml` · **Formations:** `ml-delivery-pod`

**The Problem:** Shipping models that are actually better than the heuristic they replace, with evidence.
**Example Intent:** "Replace the rules-based fraud filter with a model at equal recall and half the false-positive rate."

**Roles:** `engineering-lead`, `ml-engineer`, `data-engineer`, `data-scientist`, `qa-engineer`.

**The Dynamic:** The `EvalReport` is structurally load-bearing: deployment assignments depend on an accepted eval, so "we'll evaluate after launch" is unrepresentable. Training runs are where `BudgetMeters` earn their keep — a hyperparameter search that eats triple its envelope glows on the chart mid-run, not on the monthly bill.

### Archetype 1H: Product Design Studio

**Key:** `product-design` · **Formations:** `design-studio-cell`

**The Problem:** Building the wrong thing beautifully, or the right thing unusably.
**Example Intent:** "Redesign onboarding so activation hits 40%, with research to prove it."

**Roles:** `design-lead`, `product-designer`, `ux-researcher`, `content-designer`, often paired with a `product-manager`.

**The Dynamic:** Research gates design: the `DesignSpec` assignment depends on an accepted `ResearchReport`, making "we skipped research" a visible, deliberate act by the manager rather than a quiet default.

### Archetype 1I: Growth Marketing

**Key:** `growth-marketing` · **Formations:** `content-machine`

**The Problem:** Nobody knows the product exists; or they know and don't convert.
**Example Intent:** "Launch the Q3 content campaign and grow organic signups 25%."

**Roles:** `marketing-lead`, `content-writer`, `editor`, `social-media-manager`, `growth-analyst`.

**The Dynamic:** Cadence-heavy (posting schedules, weekly newsletters) with episodic campaign intents layered on. Publishing to owned channels is a governed action with manager-level approval authority; the `EngagementReport` closes the loop so the next `CampaignBrief` is written against measured reality.

### Archetype 1J: Customer Support Center

**Key:** `customer-support-center` · **Formations:** `support-tier`

**The Problem:** High ticket volume, wildly varying difficulty, and institutional amnesia about past fixes.
**Example Intent:** "Hold first-response under 2 hours this quarter while cutting repeat-issue tickets 30%."

**Roles:** `team-lead`, `support-agent`, `support-engineer`, `knowledge-base-writer`.

**The Dynamic:** A standing intent absorbs an endless stream of micro-engagements. Escalation is literally the `EscalationPackage` artifact moving up a tier, and every accepted `DiagnosisReport` spawns a dependent KB assignment — the org is structurally incapable of solving the same problem twice without writing it down.

---

## 2. The Physical World: Service, Craft, & Retail

Canopy is not limited to digital products. Agents can orchestrate, sequence, and manage physical labor by relying on `ActionAttestations` rather than digital files.

### Archetype 2A: The High-Volume Franchise Operation

**Key:** `franchise-operation` · **Formations:** `franchise-shift`

**The Problem:** Executing high-throughput, standardized physical service delivery within strict time and safety tolerances.
**Example Intent:** "Serve a 200-car lunch rush while maintaining a sub-3-minute average ticket time."

**Roles & Responsibilities:**

* **Store Manager** (`store-manager`): The orchestrator. Resolves on-the-floor exceptions and manages inventory budgets.
* **Front-of-House / Teller** (`cashier`): Interacts directly with the customer to generate an `OrderTicket` artifact.
* **Grill Station** (`line-cook`): Reads the ticket and cooks the primary protein.
* **Fry Station** (`line-cook`): Synchronizes side items with the main protein completion.

**The Dynamic:** This is an ultra-fast, highly parallel structure. The Teller's `OrderTicket` immediately fans out assignments to both the Grill and Fry stations. If the fry vat malfunctions, the Fry Station agent stalls, triggering an `InterventionGate` to the Store Manager to repair the physical equipment so the queue can resume.

Franchising itself is the nesting mechanism: one parent org, N identical child orgs instantiated from the same blueprint, each mounted under a regional manager.

### Archetype 2B: General Contracting & Construction

**Key:** `general-contracting` · **Formations:** `build-crew`

**The Problem:** Coordinating physical materials, specialized labor, and strict safety codes into a durable structure.
**Example Intent:** "Build a custom 8x4 cedar lumber planter garden and wire the adjacent exterior electrical outlets."

**Roles & Responsibilities:**

* **General Contractor** (`general-contractor`): Holds the master blueprint, manages the `BudgetMeter` for materials, and sequences the trades.
* **Lead Carpenter** (`carpenter`): Measures, cuts, and assembles the structural cedar lumber, filing an `ActionAttestation` upon completion.
* **Electrician** (`electrician`): Runs conduit and wires the electrical outlets, ensuring safe routing to the breaker panel.
* **Site Inspector** (`site-inspector`): A specialized QA role that operates on strict code compliance.

**The Dynamic:** Dependencies in construction are immutable physical realities. The Electrician sits behind a strict `DependencyGate`; they cannot wire the outlet until the Lead Carpenter has built the wooden framework. Once both are done, the Site Inspector must complete a review, acting as an `ApprovalGate` before the GC can accept the final deliverable and close the root assignment.

### Archetype 2C: E-commerce Fulfillment

**Key:** `ecommerce-fulfillment` · **Formations:** `franchise-shift` (warehouse-flavored), `data-insights-cell`

**The Problem:** Orders in, correct boxes out, at volume, with inventory that never lies.
**Example Intent:** "Clear the Black Friday backlog within 48 hours at under 0.5% mis-pick rate."

**Roles:** `warehouse-lead`, `picker-packer`, `inventory-analyst`, `support-agent` for order exceptions.

**The Dynamic:** Structurally the franchise pattern at warehouse scale — huge volumes of small Assignment trees, `FulfillmentAttestation` as the workhorse deliverable, and the `inventory-analyst`'s `ReorderProposal`s hitting `ApprovalGates` because reordering spends real money.

### Archetype 2D: Outpatient Medical Clinic

**Key:** `medical-clinic` · **Formations:** custom (director → physicians → nurses/schedulers)

**The Problem:** Patient flow, care quality, and documentation under regulatory constraint.
**Example Intent:** "Run today's schedule of 40 appointments with complete intake notes and zero missed follow-ups."

**Roles:** `clinic-director`, `physician`, `nurse`, `medical-scheduler`.

**The Dynamic:** The strictest governance profile in the catalog: care decisions are physician-owned (`CarePlan` artifacts), consequential orders are governed actions, and everything is evidenced — the attestation trail *is* the medical record's shadow. A good stress test for whether Canopy's approval/audit machinery is trustworthy where stakes are real.

### Archetype 2E: Event Production

**Key:** `event-production` · **Formations:** `event-crew`

**The Problem:** A hard deadline that cannot slip, dozens of vendors, and a day-of execution window measured in minutes.
**Example Intent:** "Produce the 300-person launch conference on Oct 12, from venue to recap video."

**Roles:** `event-producer`, `coordinator`, `stage-manager`, `av-technician`, `content-writer`.

**The Dynamic:** Milestones dominate — the target date is immovable, so `at_risk` derivation runs backward from the event date. Deposits and permits are `ApprovalGates` (real money, real commitments); day-of execution is almost pure attestation at high tempo.

---

## 3. Knowledge, Discovery, & Community

These structures exist to synthesize information, mobilize groups, and push the boundaries of human understanding.

### Archetype 3A: The Academic Research Lab

**Key:** `research-lab` · **Formations:** `research-cell`

**The Problem:** Expanding the boundary of human knowledge through rigorous testing, data modeling, and peer-reviewed publication.
**Example Intent:** "Draft and publish a paper solving the atmospheric carbon-capture efficiency drop."

**Roles & Responsibilities:**

* **Principal Investigator** (`principal-investigator`): Sets the standing research intent, secures university funding (salary top-ups), and acts as the final reviewer.
* **Literature Analyst** (`literature-analyst`): Scours existing scientific journals to produce a `LitReview` artifact.
* **Data Scientist** (`data-scientist`): Runs Python-based simulations and outputs a `DataModel` artifact.
* **Lead Drafter** (`manuscript-drafter`): Synthesizes the literature and the data into a final `Manuscript` artifact.

**The Dynamic:** The PI issues the intent. The Literature Analyst and Data Scientist execute their plans in parallel. If the Data Scientist's model generates an anomaly that contradicts the hypothesis, they open an `EscalationGate` requesting guidance from the PI. Only when both the `LitReview` and `DataModel` are accepted does the `DependencyGate` open for the Lead Drafter to begin writing.

### Archetype 3B: Grassroots Community Organization

**Key:** `community-organization` · **Formations:** `event-crew` (lightweight), `fundraising-office`

**The Problem:** Mobilizing local participants, securing resources, and synchronizing outdoor community events for a shared purpose.
**Example Intent:** "Design and execute a 45-minute synchronized community fitness workout across a local high school football field."

**Roles & Responsibilities:**

* **Regional Lead** (`community-lead`): Holds the standing intent of community growth and health.
* **Event Quarterback** (`event-producer`): Designs the specific routines, station rotations, and music triggers.
* **Logistics Coordinator** (`coordinator`): Secures the physical space, permits, and necessary equipment.
* **Communications Lead** (`content-writer`): Drafts the post-event summary, logs attendance, and publishes the community newsletter.

**The Dynamic:** The Event Quarterback issues a `Plan` for the workout structure. Because the event requires public space, the Logistics Coordinator must pass an `ApprovalGate` governed by the Regional Lead before submitting a permit application (spending real money). Once the physical event is executed and verified via `ActionAttestation`, the Communications Lead digests the data into a final published artifact for the community.

### Archetype 3C: The Newsroom

**Key:** `newsroom` · **Formations:** `newsdesk`

**The Problem:** Publishing stories fast enough to matter and verified enough to defend.
**Example Intent:** "Investigate the city procurement records and publish by Friday if the story holds."

**Roles:** `managing-editor`, `reporter`, `fact-checker`, `editor`.

**The Dynamic:** The conditional intent is the interesting part — "publish *if it holds*" means the fact-checker's `FactCheckReport` can legitimately kill the root assignment, and that's success, not failure. Publication is a governed action only the managing editor can approve; the fact-check dependency cannot be waived silently.

### Archetype 3D: Curriculum Studio

**Key:** `curriculum-studio` · **Formations:** custom (designer → writers → reviewer)

**The Problem:** Turning expertise into teachable, assessable learning material.
**Example Intent:** "Build the 6-week 'Intro to Data Analysis' course: outline, twelve modules, assessments."

**Roles:** `curriculum-designer`, `instructional-writer`, `assessment-reviewer`.

**The Dynamic:** The `CourseOutline` is the decomposition artifact — each module becomes a parallel writing assignment, each gated on the outline's acceptance, each followed by a dependent review. A clean example of one artifact *becoming* the delegation plan.

### Archetype 3E: Nonprofit Development Office

**Key:** `nonprofit-fundraising` · **Formations:** `fundraising-office`

**The Problem:** Funding a mission from grants, donors, and volunteers, with radical accountability for where money goes.
**Example Intent:** "Raise $250k this fiscal year across grants and the spring donor campaign."

**Roles:** `development-director`, `grant-writer`, `volunteer-coordinator`, `content-writer`, `community-lead`.

**The Dynamic:** Long-horizon standing intent with deadline-driven bursts (grant cycles). The spend side is unusually visible — donors effectively demand what Canopy's provenance chain already provides: every dollar of effort traceable from `SpendEvent` up to the mission intent.

---

## 4. Professional & Client Services

Organizations whose product is *the engagement itself* — a client brings the intent, the org supplies the machinery.

### Archetype 4A: Marketing / Creative Agency

**Key:** `creative-agency` · **Formations:** `content-machine` + `account-manager` front-end

**The Problem:** Delivering creative work that satisfies a client who changes their mind, on retainer economics.
**Example Intent:** "Deliver the full rebrand package for Client X: identity, site copy, launch assets."

**Roles:** `account-manager`, `creative-director`, `content-writer`, `product-designer`, `editor`.

**The Dynamic:** The client is an external intent source proxied through the `account-manager`, whose `CreativeBrief` is the internal contract. Client feedback rounds are brief *revisions* — which, under the rework-funding rule, makes scope creep financially visible on the account rather than silently absorbed by the creatives. Agencies are where per-client budget meters most resemble actual invoices.

### Archetype 4B: Management Consultancy

**Key:** `management-consultancy` · **Formations:** custom case team (engagement manager → consultants)

**The Problem:** Answering a high-stakes strategic question with rigor, on a deadline, for someone else.
**Example Intent:** "Should Client Y enter the Brazilian market? Recommendation deck in six weeks."

**Roles:** `engagement-manager`, `consultant` ×N, `data-analyst`.

**The Dynamic:** The classic hypothesis-driven decomposition: the engagement manager's issue tree becomes the assignment tree one-to-one. Interview `InterviewNotes` and analysis `AnalysisDeck`s roll up into the final recommendation, and milestone pressure (the six-week clock) drives `at_risk` signaling throughout.

### Archetype 4C: Law Practice

**Key:** `law-practice` · **Formations:** custom (counsel → contracts analysts)

**The Problem:** Legal throughput — contracts, redlines, filings — where errors are expensive and everything needs review.
**Example Intent:** "Clear the M&A due-diligence document room by the 15th, flagging every change-of-control clause."

**Roles:** `legal-counsel`, `contracts-analyst` ×N, `compliance-officer`.

**The Dynamic:** A pyramid of review: analysts produce volume (`TriageNote`, `DraftAgreement`), counsel reviews everything (acceptance is genuinely the product), and anything filed externally or signed is a governed action. The strictest "consented, then evidenced" archetype outside the clinic.

---

## 5. The Corporate Chassis

The internal support functions every sufficiently large parent org nests, regardless of what the org actually does. These are designed to be mounted as child organizations under any parent archetype.

### Archetype 5A: Talent Acquisition

**Key:** `talent-acquisition` · **Formations:** `recruiting-loop`

**The Problem:** Filling open roles with signal, not luck, at pipeline scale.
**Example Intent:** "Fill the three open senior engineering roles this quarter."

**Roles:** `recruiter`, `sourcer`, `interview-coordinator`.

**The Dynamic:** Pure pipeline: `CandidateList` → `ScreenNote` → loop logistics → `FeedbackPacket` → `OfferPacket`, with offer extension as the governed action. When Canopy orgs can propose their own hires someday, this is the archetype the proposal routes through.

### Archetype 5B: Finance Back Office

**Key:** `finance-back-office` · **Formations:** custom (controller → accountants/analysts)

**The Problem:** Books that close on time and survive audit.
**Example Intent:** "Close March by the 5th business day with all reconciliations reviewed."

**Roles:** `finance-controller`, `staff-accountant`, `financial-analyst`.

**The Dynamic:** The most cadence-shaped archetype in the catalog — the monthly close *is* a recurring Intent with a fixed internal dependency graph (entries → reconciliations → review → `ClosePackage`). Ideal early candidate for validating Cadence + Dependency machinery together.

### Archetype 5C: Legal & Compliance Desk

**Key:** `legal-compliance-desk` · **Formations:** custom (counsel → analysts)

**The Problem:** Contract review and regulatory adherence as an internal service.
**Example Intent:** "Every inbound NDA triaged within 24 hours; quarterly compliance audit complete by the 20th."

**Roles:** `legal-counsel`, `contracts-analyst`, `compliance-officer`.

**The Dynamic:** A service desk shaped like support (`support-tier`'s pattern with legal deliverables): standing intent, stream of micro-engagements, tiered escalation from analyst to counsel, external commitments behind approval gates.
