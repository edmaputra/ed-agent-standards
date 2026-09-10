# ed-agent-standards

Central repository for AI agent rules, coding standards, architectural constraints, and engineering guidelines across projects.

---

## 1. Overview

This repository acts as the single source of truth for agent-enforced coding standards, architectural patterns, and quality gates for projects maintained by `@edmaputra`.

All rules target **Java 25 / Spring Boot 4** as the minimum baseline.

### Current Standards

| Rule File | Focus Area | Key Highlights |
|---|---|---|
| [`rules/clean-code.md`](rules/clean-code.md) | Modern Java & Clean Code | Immutability via Java `record`s, compact constructors for fail-fast invariant checks, single-purpose ports, constructor injection with zero magic, mandatory `@author {maintainer}` & `@since <version>` type-level Javadoc standards. |
| [`rules/hexagonal-architecture.md`](rules/hexagonal-architecture.md) | Architectural Boundaries | Ports & Adapters (Hexagonal Architecture) with strict inward dependency flow: `domain` (zero framework dependencies) ◄ `application` (use cases & orchestration) ◄ `adapter` (driving REST & driven persistence adapters). Includes ✅/❌ examples for every layer violation. |
| [`rules/multi-tenancy-and-audit.md`](rules/multi-tenancy-and-audit.md) | Multi-Tenancy & Security | Pure domain tenancy representation via `TenantId` (RFC 9562 UUIDv7), pluggable host `TenantContextBridge` SPI, Java 25 `ScopedValue` context propagation, and structured immutable domain events. |
| [`rules/logging-and-observability.md`](rules/logging-and-observability.md) | Logging & Observability | SLF4J structured logging, log level conventions, MDC context propagation (`traceId`, `tenantId`, `actorId`), sensitive data prohibition, Micrometer metrics naming, OpenTelemetry tracing, and Spring Actuator health endpoints. |
| [`rules/api-conventions.md`](rules/api-conventions.md) | API Design & Error Handling | RESTful resource naming, HTTP method/status code standards, RFC 9457 Problem Details error responses, pagination conventions, Bean Validation for request DTOs, content negotiation, and API versioning strategy. |

---

## 2. Usage in Downstream Projects

### Option A: As a Git Submodule (Recommended for Team Projects)

Add this repository as a Git submodule mapped directly to `.agents` in your project root. Antigravity automatically discovers all rule files located in `.agents/rules/*.md`:

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
# Symlink rules directory into Antigravity global configuration
ln -s ~/Projects/ed-agent-standards/rules ~/.gemini/config/rules
```

---

## 3. Contributing & Updating Rules

1. Update or add rule documents inside the `rules/` directory.
2. Ensure markdown documents are structured clearly with good/bad examples and clear rationale.
3. Include YAML frontmatter with `description` and `globs` for Antigravity file-type filtering.
4. Commit and push changes to `main`.
5. Downstream projects can update to the latest revision using `git submodule update --remote`.
