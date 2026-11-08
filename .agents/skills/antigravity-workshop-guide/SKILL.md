---
name: antigravity-workshop-guide
description: Generates, validates, and exports customized Google Cloud project and client setup guides (Markdown and print-styled PDF) for Antigravity workshops across Vertex AI Pay-As-You-Go and Gemini Enterprise licensing modes.
---

# Antigravity Workshop Setup Guide Skill (`antigravity-workshop-guide`)

Use this skill when a user asks to create, customize, test, or export a Google Cloud setup guide or attendee pre-work document for an Antigravity workshop.

## User Experience Principles

1. **Set Expectations First:** Never dump a raw list of configuration questions. Start by explaining what the setup process produces, what defaults are used, and ask if the user wants to proceed or customize.
2. **Interactive UI Selection:** When configuration inputs are needed, use structured multiple-choice questions (e.g., Antigravity `ask_question` tool) with recommended choices marked `(Recommended)` and allow free-form inputs only where required (such as organization names or custom prefixes).
3. **Validation & Polish:** Always run static syntax checks (`bash -n`) and render print-ready PDFs.

---

## Workflow

### 1. Set Expectations & Confirm Intent
Inspect current settings dynamically:
```bash
antigravity-workshop-kit configure --dump-options
```

Present a clear summary of what will be generated:
* **Purpose:** Configures multi-team GCP environments, IAM roles, and attendee onboarding guides for Antigravity workshops.
* **Deliverables:**
  1. `antigravity_setup_guide.md`: Admin GCP provisioning script and attendee onboarding guide (pre-validated with `bash -n`).
  2. `antigravity_setup_guide.pdf`: Print-ready, professionally styled PDF.
  3. `.workshop-config.json`: Persisted settings for repeatable generation.
* **Default Profile:** 5 team projects (`workshop-team1`..`5`), Vertex AI Pay-As-You-Go licensing, and Cloud Run / Storage deployment guides included.

Ask the user if they want to proceed with the defaults or customize the setup.

### 2. Interactive Configuration (Structured Selection)
If the user chooses to customize, prompt them using structured multiple-choice questions:

* **Question 1: Licensing / Auth Model**
  - `(Recommended) Vertex AI API Pay-As-You-Go (vertex_paygo)` — Pay-per-token usage with budget alerts and prediction caps.
  - `Gemini Enterprise Subscription (gemini_enterprise)` — Fixed subscription seat licenses (`roles/cloudaicompanion.user`).

* **Question 2: Cloud Workload Scope**
  - `(Recommended) Include Cloud Resources (Cloud Run, Cloud Storage, Artifact Registry, Cloud Build)`
  - `Antigravity CLI / IDE Only (No Cloud Deployments)`

* **Question 3: Custom Parameters (Optional)**
  - Organization Name (default: `Workshop`)
  - Team Count (default: `5`)
  - Project ID Prefix (default: `workshop-team`)
  - Billing Account ID (placeholder if not known)

### 3. Execute Full Pipeline (Generate, Validate & Export)
Run `run-all` with the resolved options:
```bash
antigravity-workshop-kit run-all \
  --organization="<ORGANIZATION>" \
  --auth-mode="<vertex_paygo|gemini_enterprise>" \
  --teams=<N> \
  --prefix="<PROJECT_PREFIX>"
```

### 4. Return Verified Deliverables
Provide clickable links to both the verified Markdown file (`antigravity_setup_guide.md`) and compiled PDF (`antigravity_setup_guide.pdf`).
