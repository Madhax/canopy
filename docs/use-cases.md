# Canopy Out-of-the-Box Use Cases

The use cases Canopy supports on day one, without the user authoring any custom roles or archetypes. Each row is a recipe: the thing a user wants, phrased as they'd phrase it, mapped to the intent they'd submit, the formation/archetype that absorbs it, and the deliverables that come back.

This list is the acceptance suite for the catalog: if a use case here can't be expressed with the shipped roles (`roles.md`), formations (`teams.md`), and archetypes (`archetypes.md`), the catalog — not the user — is wrong.

## Software delivery

| # | I want to… | Example intent | Formation / Archetype | Comes back as |
|---|---|---|---|---|
| 1 | Ship a feature end-to-end | "Add CSV export to the reports page" | `product-engineering-pod` | PullRequest + TestReport, accepted up the chain |
| 2 | Fix a production incident and learn from it | "Checkout is 500ing — restore and postmortem" | `incident-response-squad` | RecoveryAttestation → IncidentPostmortem → RunbookDoc |
| 3 | Get a codebase reviewed before merge | "Review this PR for security and perf" | `code-reviewer` under any lead | ReviewReport |
| 4 | Harden and speed up CI/CD | "One-command preview envs for every pod" | `platform-pod` | InfraSpec → ToolingRelease |
| 5 | Run a security review | "Threat-model the payments path, close criticals" | `security-operations` | ThreatModel + SecurityReport + patch PRs |
| 6 | Build a dashboard / answer a data question | "Did January's pricing change work?" | `data-insights-cell` | Dashboard + FindingsReport |
| 7 | Train and ship an ML model with evidence | "Beat the rules-based fraud filter" | `ml-delivery-pod` | ModelCard + EvalReport gating a deploy PR |
| 8 | Design a feature with research backing | "Redesign onboarding for 40% activation" | `design-studio-cell` | ResearchReport → DesignSpec + Prototype |
| 9 | Document a system | "Write the runbook and API docs for billing" | `tech-writer` under any lead | DocPage + RunbookDoc |

## Go-to-market & customer

| # | I want to… | Example intent | Formation / Archetype | Comes back as |
|---|---|---|---|---|
| 10 | Run outbound sales on a territory | "Close $500k ARR this quarter" | `sales-pod` | QualifiedLeads → Proposals → SignedContracts |
| 11 | Launch a content campaign | "Q3 campaign, +25% organic signups" | `content-machine` | CampaignBrief → ContentPieces → EngagementReport |
| 12 | Publish on a cadence | "Weekly newsletter, every Thursday" | `content-machine` (Cadence) | EditedDraft → PublishAttestation, weekly |
| 13 | Run a support desk | "First response < 2h, repeat tickets −30%" | `support-tier` | ResolutionAttestations + KBArticles |
| 14 | Keep key accounts healthy | "Quarterly reviews for top 20 accounts" | `customer-success-manager` (Cadence) | HealthReports + RenewalPlans |

## Operations & back office

| # | I want to… | Example intent | Formation / Archetype | Comes back as |
|---|---|---|---|---|
| 15 | Hire for open roles | "Fill three senior engineering roles" | `recruiting-loop` | ScreenNotes → FeedbackPackets → OfferPacket (gated) |
| 16 | Close the monthly books | "Close March by business day 5" | `finance-back-office` (Cadence) | JournalEntries → Reconciliations → ClosePackage |
| 17 | Triage and redline contracts | "Every NDA triaged in 24h" | `legal-compliance-desk` | TriageNotes + ContractRedlines |
| 18 | Run a compliance audit | "Quarterly SOC2 process audit" | `compliance-officer` (Cadence) | AuditReport |

## Knowledge & content production

| # | I want to… | Example intent | Formation / Archetype | Comes back as |
|---|---|---|---|---|
| 19 | Produce a research paper | "Paper on carbon-capture efficiency drop" | `research-cell` | LitReview + DataModel → Manuscript |
| 20 | Investigate and publish a story | "Procurement records — publish if it holds" | `newsdesk` | StoryDraft + FactCheckReport → gated publication |
| 21 | Build a course | "6-week intro-to-data-analysis course" | `curriculum-studio` | CourseOutline → LessonModules → ReviewReports |
| 22 | Get a strategic recommendation | "Should we enter the Brazilian market?" | `management-consultancy` case team | InterviewNotes + AnalysisDecks → recommendation |

## Physical-world coordination

| # | I want to… | Example intent | Formation / Archetype | Comes back as |
|---|---|---|---|---|
| 23 | Run a service shift | "200-car lunch rush, sub-3-min tickets" | `franchise-shift` | OrderTickets → StationAttestations at tempo |
| 24 | Sequence a small construction job | "Cedar planter + exterior outlets" | `build-crew` | BuildAttestation → WiringAttestation → InspectionReport |
| 25 | Clear a fulfillment backlog | "Black Friday backlog in 48h, <0.5% mis-picks" | `ecommerce-fulfillment` | FulfillmentAttestations + exception reports |
| 26 | Produce an event | "300-person launch conference Oct 12" | `event-crew` | EventRunSheet → bookings (gated) → ShowAttestation + RecordingFile |
| 27 | Mobilize a community event | "Synchronized workout at the high school field" | `community-organization` | Permit (gated) → EventAttestation → Newsletter |
| 28 | Run a fundraising year | "$250k across grants and spring campaign" | `fundraising-office` | GrantProposals + donor attestations → StatusReports |

## Meta / demonstrative

| # | I want to… | Example intent | Formation / Archetype | Comes back as |
|---|---|---|---|---|
| 29 | Instruct only the CEO and watch delegation | "Ship a landing page for the new product" | any archetype root | full Assignment tree, artifacts routing up |
| 30 | Get a daily status of everything | standing Cadence on the root | `chief-of-staff` / root | daily StatusReport rolled up from the subtree |
| 31 | Clone a working org | "Another store like store #4" | nested org from blueprint (future: Blueprints) | new child org mounted under the parent |
