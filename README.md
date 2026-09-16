# ed-agent-standards

Central repository for AI agent rules, coding standards, architectural constraints, and engineering guidelines across projects.

---

## 1. Overview

This repository acts as the single source of truth for agent-enforced coding standards, architectural patterns, and quality gates for projects maintained by `@edmaputra`.

Standards are organised by **technology stack** under the `rules/` directory. New stacks can be added by creating a new subdirectory with a `*-standards.md` file.

### Severity Classification

Every standard and rule across this repository is classified under one of three severity tiers:

- 🔴 **MUST**: Non-negotiable requirements. Violations break CI builds, fail architectural tests, or block PR approval.
- 🟡 **SHOULD**: Strongly recommended best practices. Deviations require documented justification and team consensus.
- 🟢 **MAY**: Optional guidelines or stylistic preferences.

### Current Standards

#### 🟠 Shared (All Stacks)

| Rule File | Focus Area | Key Highlights |
|---|---|---|
| [`rules/shared/git-and-ci-standards.md`](rules/shared/git-and-ci-standards.md) | Git, CI/CD & Containers | Conventional Commits standard, structured branch naming conventions, atomic PR quality gates, multi-stage non-root Docker images, and automated CI pipeline checks. |

#### ☕ Java / Kotlin

| Rule File | Focus Area | Key Highlights |
|---|---|---|
| [`rules/java-kotlin/clean-code.md`](rules/java-kotlin/clean-code.md) | Modern Java & Clean Code | Immutability via Java `record`s, compact constructors for fail-fast invariant checks, single-purpose ports, constructor injection with zero magic, mandatory `@author {maintainer}` & `@since <version>` type-level Javadoc standards. |
| [`rules/java-kotlin/hexagonal-architecture.md`](rules/java-kotlin/hexagonal-architecture.md) | Architectural Boundaries | Ports & Adapters (Hexagonal Architecture) with strict inward dependency flow, transaction boundary rules, layer mapping strategy, and ArchUnit enforcement tests. Includes ✅/❌ examples for every layer violation. |
| [`rules/java-kotlin/multi-tenancy-and-audit.md`](rules/java-kotlin/multi-tenancy-and-audit.md) | Multi-Tenancy & Security | Pure domain tenancy representation via `TenantId` (RFC 9562 UUIDv7), pluggable host `TenantContextBridge` SPI, Java 25 `ScopedValue` context propagation, and structured immutable domain events. |
| [`rules/java-kotlin/logging-and-observability.md`](rules/java-kotlin/logging-and-observability.md) | Logging & Observability | SLF4J structured logging, log level conventions, MDC context propagation (`traceId`, `tenantId`, `actorId`), sensitive data prohibition, Micrometer metrics naming, OpenTelemetry tracing, and Spring Actuator health endpoints. |
| [`rules/java-kotlin/api-conventions.md`](rules/java-kotlin/api-conventions.md) | API Design & Error Handling | RESTful resource naming, HTTP method/status code standards, RFC 9457 Problem Details error responses, pagination conventions, Bean Validation for request DTOs, content negotiation, and API versioning strategy. |
| [`rules/java-kotlin/database-standards.md`](rules/java-kotlin/database-standards.md) | Database & Migrations | Table/column naming conventions, audit columns, soft delete vs hard delete, optimistic locking with `@Version`, Liquibase migration standards, and connection pool/query performance guidelines. |
| [`rules/java-kotlin/security-standards.md`](rules/java-kotlin/security-standards.md) | Security | Deny-by-default Spring Security filter chains, multi-level authorization, input validation & parameterized queries, CORS configuration, secrets management, rate limiting, OWASP Top 10 checklist, and dependency vulnerability management. |
| [`rules/java-kotlin/kotlin-standards.md`](rules/java-kotlin/kotlin-standards.md) | Kotlin & Spring Boot 4 | Idiomatic Kotlin 2.x practices, compiler null-safety flags, `data class` vs JPA entity separation, Coroutines & `Flow` in WebFlux, sealed interface domain modeling, and extension function rules. |

#### 🐦 Flutter / Dart

| Rule File | Focus Area | Key Highlights |
|---|---|---|
| [`rules/flutter/flutter-standards.md`](rules/flutter/flutter-standards.md) | Flutter & Dart | Dart 3.x null safety, feature-first project structure, `StatelessWidget`-first architecture, Riverpod state management, GoRouter navigation, repository pattern, and 80% test coverage gate. |

#### 🅰️ Angular / TypeScript

| Rule File | Focus Area | Key Highlights |
|---|---|---|
| [`rules/angular/angular-standards.md`](rules/angular/angular-standards.md) | Angular & TypeScript | TypeScript strict mode, standalone components with `OnPush`, RxJS best practices (`async` pipe, `takeUntilDestroyed`), NgRx for global state, typed HTTP error handling, lazy loading, and 80% test coverage gate. |

---

## 2. Usage in Downstream Projects

### Option A: As a Git Submodule (Recommended for Team Projects)

Add this repository as a Git submodule mapped directly to `.agents` in your project root. Antigravity automatically discovers all rule files matching `rules/**/*.md` within `.agents`:

```bash
# In the root of your target project:
git submodule add git@github.com:edmaputra/ed-agent-standards.git .agents
git commit -m "chore: add ed-agent-standards submodule under .agents"
```

#### Pulling the Latest Standards in Downstream Projects

When standards in this repository are updated, downstream projects can pull the latest rules with:

```bash
git submodule update --remote .agents
git add .agents
git commit -m "chore: update ed-agent-standards to latest"
```

#### Cloning a Project with the Submodule

When cloning a project that uses this submodule:

```bash
git clone --recurse-submodules <project-url>
# Or if already cloned:
git submodule update --init --recursive
```

---

### Option B: As a Machine-Level Global Configuration

If you want these standards to apply automatically across all workspaces on your workstation without committing submodules to individual repositories:

```bash
# Symlink the entire rules directory into Antigravity global configuration
ln -s ~/Projects/ed-agent-standards/rules ~/.gemini/config/rules
```

> **Note**: Antigravity discovers rules via `rules/**/*.md`, so the recursive symlink covers all stack subdirectories automatically.

---

## 3. Adding a New Stack

1. Create a new subdirectory under `rules/` named after the stack (e.g. `rules/react/`).
2. Add a `*-standards.md` file inside it with YAML frontmatter (`description`, `globs`) targeting the relevant file extensions.
3. Update this `README.md` with a new row in the standards table.
4. Commit and push to `main`.

---

## 4. Contributing & Updating Rules

1. Update or add rule documents inside the appropriate `rules/<stack>/` subdirectory.
2. Ensure markdown documents are structured clearly with good/bad examples and clear rationale.
3. Include YAML frontmatter with `description` and `globs` for Antigravity file-type filtering.
4. Commit and push changes to `main`.
5. Downstream projects can update to the latest revision using `git submodule update --remote`.
