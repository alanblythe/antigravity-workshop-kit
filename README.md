# Antigravity Workshop Kit

> A modular CLI toolkit, templating engine, and agent skill for generating, verifying, and publishing customized Antigravity Google Cloud setup guides, rate limit guardrails, IAM configurations, and PDF assets for customer workshops.

---

## What This Is

When delivering Google Cloud Antigravity developer workshops, customer environments vary across two major dimensions:
1. **Licensing Model:**
   * **Gemini Enterprise:** Assigned subscription seat licenses managed via Google Admin Console / Gemini Platform.
   * **Vertex AI API (Pay-As-You-Go):** Direct project-billed model inference via Vertex AI without seat licenses, requiring `roles/serviceusage.serviceUsageConsumer`, Dynamic Shared Quota (DSQ) budget alerts, and regional online prediction overrides.
2. **Infrastructure Scope:**
   * Teams requiring workload creation (Cloud Run, Cloud Storage, Artifact Registry, Cloud Build) vs. model inference only.
   * Single or multi-project topologies (e.g. 5 dedicated team projects with zero-padded groups: `agy-workshop-team01`..`agy-workshop-team05`).

`antigravity-workshop-kit` codifies this setup workflow into a deterministic, testable Python toolkit and agent skill that eliminates human error in `gcloud` scripts and client authentication instructions.

---

## Workflow & Quickstart

```bash
# 1. Configure workshop parameters (writes .workshop-config.json)
antigravity-workshop-kit configure \
  --organization="Acme" \
  --auth-mode=vertex_paygo \
  --teams=5 \
  --prefix="acme-workshop-team" \
  --billing-account="01ABCD-2EF345-67890A"

# 2. Generate customized Markdown setup guide
antigravity-workshop-kit generate

# 3. Test and validate all bash snippets & best practices in the guide
antigravity-workshop-kit test

# 4. Export to polished, print-styled PDF via headless Chrome
antigravity-workshop-kit export-pdf

# Or run the entire pipeline in one shot:
antigravity-workshop-kit run-all --organization="Acme" --auth-mode=vertex_paygo --teams=5
```

---

## Project Structure

```
antigravity-workshop-kit/
├── workshop-config.example.json # Workshop configuration template
├── README.md                   # Project overview & documentation
├── SPEC.md                     # Engineering specification & testing requirements
├── pyproject.toml              # Python packaging & CLI entrypoint
├── requirements.txt            # Python dependencies (jinja2, markdown)
├── src/
│   └── antigravity_workshop_kit/
│       ├── __init__.py
│       ├── cli.py              # CLI entrypoint
│       ├── config.py           # Configuration schema & state management
│       ├── generator.py        # Jinja2 template rendering engine
│       ├── tester.py           # Bash syntax extractor, static rule auditor & GCP smoke tester
│       ├── exporter.py         # Headless Chrome PDF compiler
│       └── templates/
│           └── setup_guide.md.j2
├── .agents/
│   └── skills/
│       └── antigravity-workshop-guide/
│           └── SKILL.md        # Agent skill definition
└── tests/
    └── test_kit.py             # Hermetic unit tests
```

---

## License

Apache-2.0
