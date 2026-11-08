# Antigravity Workshop Kit: Technical Specification

## 1. Overview & Objectives

`antigravity-workshop-kit` provides a testable CLI toolkit, templating engine, and agent skill to automate the generation, validation, and export of Google Cloud setup guides for Antigravity workshops.

### Key Goals:
1. **Model Parameterization:** Support both **Gemini Enterprise** (subscriptions) and **Vertex AI API Pay-As-You-Go** (`roles/serviceusage.serviceUsageConsumer`, DSQ billing budget alerts, regional prediction caps).
2. **Project Topology:** Default to 5 dedicated team projects with zero-padded groups (`agy-workshop-team01`..`agy-workshop-team05`) and configurable overrides.
3. **Rigorous Testability:** Automatically extract and validate all bash snippets using `bash -n` and static best-practice rules (enforcing public allowlisted Google Cloud APIs and valid regional endpoints).
4. **PDF Compilation:** Headless Chrome rendering with print styling, table layouts, and syntax-highlighted code blocks.
5. **Agent Skill Discovery:** Expose an options inspection interface (`--dump-options`) so agent skills can discover and prompt for configurable parameters dynamically.

---

## 2. Configuration Schema (`.workshop-config.json`)

The state is stored in `.workshop-config.json` at the repository root.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `organization` | `string` | `"Workshop"` | Organization name. |
| `auth_mode` | `"vertex_paygo"` \| `"gemini_enterprise"` | `"vertex_paygo"` | Licensing/auth model. |
| `team_count` | `integer` | `5` | Number of team projects to provision. |
| `project_prefix` | `string` | `"workshop-team"` | GCP project ID prefix. |
| `billing_account_id` | `string` | `"<BILLING_ACCOUNT_ID>"` | Google Cloud Billing Account ID. |
| `folder_id` | `string` | `""` | Optional parent GCP Folder ID. |
| `region` | `string` | `"global"` | Antigravity client auth region (must be `"global"`). |
| `compute_region` | `string` | `"us-central1"` | Default region for Cloud Run workloads. |
| `budget_alert_usd` | `integer` | `250` | Cloud Billing budget alert threshold per team. |
| `rate_limit_rpm` | `integer` | `150` | Target rate limit RPM for prediction overrides. |
| `group_email_pattern`| `string` | `"agy-workshop-team{NN}@example.com"` | Zero-padded team group email pattern. |
| `enable_cloud_resources` | `boolean` | `true` | Include Cloud Run / Storage / Artifact Registry setup. |
| `output_filename` | `string` | `"antigravity_setup_guide.md"` | Output Markdown filename. |

### Formatting Patterns:
* `{N}`: Unpadded team number (e.g. `1`, `2`, `10`).
* `{NN}`: 2-digit zero-padded team number (e.g. `01`, `02`, `10`).

---

## 3. CLI Command Specifications

The CLI entrypoint `antigravity-workshop-kit` provides five subcommands:

### `configure`
* Updates or initializes `.workshop-config.json`.
* Flags: `--organization`, `--auth-mode`, `--teams`, `--prefix`, `--billing-account`, `--folder-id`, `--budget-alert`, `--rate-limit`, `--output`.
* **Discovery Flag:** `--dump-options` prints JSON metadata describing each option, type, default, and description.

### `generate`
* Loads `.workshop-config.json` (or accepts ad-hoc CLI flag overrides).
* Renders `src/antigravity_workshop_kit/templates/setup_guide.md.j2`.
* Outputs to `output_filename` (default: `antigravity_setup_guide.md`).

### `test`
* Extracts all ````bash ... ```` blocks from the generated guide.
* Performs:
  1. **Syntax Check:** Runs `bash -n` on all code snippets (with placeholders mocked).
  2. **Static Allowlist Audits:**
     * Asserts only allowlisted public `*.googleapis.com` service APIs are referenced.
     * Asserts client region is instructed as `Global` / `global`.
     * Asserts `gcloud auth login --update-adc` is present for single-step browser authentication.
     * For `vertex_paygo`, asserts both `roles/aiplatform.user` and `roles/serviceusage.serviceUsageConsumer` are granted.
  3. **Live GCP Smoke Test (Optional via `--live-project=<ID>`):** Verifies project reachability and API status.

### `export-pdf`
* Converts Markdown to styled HTML using Python `markdown` with `tables` and `fenced_code`.
* Runs headless Chrome: `google-chrome --headless=new --disable-gpu --no-sandbox --no-pdf-header-footer --print-to-pdf=<out.pdf>`.

### `run-all`
* Runs `configure` $\rightarrow$ `generate` $\rightarrow$ `test` $\rightarrow$ `export-pdf` sequentially.
* Fails fast if any test fails.

---

## 4. Agent Skill Specification (`.agents/skills/antigravity-workshop-guide`)

* **Location:** `.agents/skills/antigravity-workshop-guide/`
* **Entrypoint:** `SKILL.md` (checked directly into the repository)
* **Agent Behavior:**
  1. Calls `antigravity-workshop-kit configure --dump-options` to introspect available options.
  2. Prompts user conversationally for any specific overrides (e.g. organization name, Gemini Enterprise vs Vertex PAYGO, team count).
  3. Executes `antigravity-workshop-kit run-all` to generate, test, and export.
  4. Returns the verified Markdown and PDF links.

---

## 5. Acceptance Criteria

1. `antigravity-workshop-kit --help` and all 5 subcommands execute cleanly.
2. `test` passes with 0 syntax errors and 0 static rule violations on both `vertex_paygo` and `gemini_enterprise` output guides.
3. Zero internal codenames, internal workstation paths, or internal usernames in the repository.
4. Clean packaging with `pip install -e .` and runnable unit tests via `pytest` or `unittest`.
