# Agent Guide: ed-agent-standards

Central repository for AI agent rules, coding standards, architectural constraints, and engineering guidelines across projects maintained by `@edmaputra`.

---

## 1. Repository Purpose & Architecture

This repository acts as the source of truth for agent-enforced engineering guidelines across multiple tech stacks. Downstream projects consume this repository via Git submodule mapped to `.agents` or machine-level symlink.

### Directory Layout

```
ed-agent-standards/
├── .gitignore                   # Ignores agent runtime artifacts (project-structure.json, cache)
├── hooks.json                   # Antigravity PreInvocation lifecycle hook configuration
├── AGENTS.md                    # Root agent navigation guide (this file)
├── README.md                    # Public documentation and standards directory
├── scripts/
│   ├── scan-structure.py        # Python scanner for Java/Kotlin, Flutter, and Angular projects
│   └── ensure-structure.sh      # Shell wrapper for Antigravity PreInvocation hook
└── rules/                       # Stack-specific engineering guidelines
    ├── shared/                  # Universal standards (Git, CI, Project Structure)
    │   ├── git-and-ci-standards.md
    │   └── project-structure-standards.md
    ├── java-kotlin/             # Java 25, Kotlin 2.x, Spring Boot 4, Hexagonal Architecture
    │   ├── clean-code.md
    │   ├── hexagonal-architecture.md
    │   ├── multi-tenancy-and-audit.md
    │   ├── logging-and-observability.md
    │   ├── api-conventions.md
    │   ├── database-standards.md
    │   ├── security-standards.md
    │   └── kotlin-standards.md
    ├── flutter/                 # Flutter, Dart 3.x, Riverpod, Feature-first Clean Architecture
    │   └── flutter-standards.md
    └── angular/                 # Angular 17+, TypeScript 5.x, Standalone, NgRx, Signals
        └── angular-standards.md
```

---

## 2. Rule Authoring & Contribution Guidelines 🔴 MUST

When modifying or creating rules in this repository:

1. **YAML Frontmatter**: Every markdown document in `rules/` must include frontmatter:
   ```yaml
   ---
   description: "Brief summary of standard scope and applicability."
   globs:
     - "**/*.ext"
   ---
   ```
2. **Severity Hierarchy**: Use standard badges:
   - 🔴 **MUST**: Non-negotiable requirement.
   - 🟡 **SHOULD**: Strongly recommended practice.
   - 🟢 **MAY**: Optional guideline or optimization.
3. **Examples**: Provide explicit `// ✅ GOOD` and `// ❌ BAD` code blocks with explanatory comments for every standard.
4. **Notation Consistency**: Use `{base-package}`, `{Module}`, `{module}`, `{feature}`, `{maintainer}` placeholders.
5. **Sync with README.md**: Whenever adding or renaming a rule, update the standards table in `README.md`.

---

## 3. Automated Structure Scanning

- The scanner script is located at `scripts/scan-structure.py`.
- Running `python3 scripts/scan-structure.py` will generate `project-structure.json`.
- The output file `project-structure.json` is git-ignored and used by agents for 0-latency workspace discovery.
- Use `--force` to re-scan after creating new directories or modules.
