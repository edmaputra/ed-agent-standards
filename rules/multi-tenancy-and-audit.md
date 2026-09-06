# Multi-Tenancy & Audit Trail Rules

This document outlines the architectural requirements for multi-tenancy, security context propagation, and audit eventing in the `ed-iam` Spring Boot Starter.

---

## 1. Multi-Tenancy Architecture

Multi-tenancy is a foundational architectural pillar of `ed-iam`. The system operates on a **shared application, shared database, tenant discriminator column** model without tightly coupling to host application databases.

### 1.1 Pure Domain Tenancy Model
- **`TenantId`**: Pure domain value object wrapping RFC 9562 UUIDv7 (`TenantId.from(UUID)`).
- **`TenantOwned` Contract**: Domain entities belonging to a tenant implement `TenantOwned`:
  ```java
  public interface TenantOwned {
      TenantId tenantId();
  }
  ```
- **Zero Host Coupling**: Never hardcode foreign key constraints or foreign dependencies on host application tenant tables.

### 1.2 Pluggable Host Bridge (`TenantContextBridge`)
- Host applications manage their own tenancy context propagation (e.g. `ScopedValue`, `ThreadLocal`).
- `TenantContextBridge` provides a functional SPI hook invoked by `JwtAuthenticationFilter` during request dispatch:
  ```java
  public interface TenantContextBridge {
      <E extends Throwable> void runWithTenant(UUID tenantId, ThrowingRunnable<E> runnable) throws E;
  }
  ```
- If a host application registers a `TenantContextBridge` bean, the starter automatically delegates tenant scoping during HTTP filter execution.

### 1.3 Tenant-Aware Persistence
- **Table Namespacing**: All database tables managed by `ed-iam` use the `iam_*` prefix (`iam_user`, `iam_role`, `iam_group`, `iam_scope_node`, `iam_user_role_assignment`, etc.).
- **Query Scoping**: Repository adapters (`adapter.persistence`) MUST filter queries by `tenantId`. Never allow cross-tenant query leaks.
- **Isolated Migrations**: Module migrations run via `IamLiquibaseAutoConfiguration` using isolated changelogs (`db.changelog-iam.json`), executing after core migrations and before JPA entity manager initialization.

---

## 2. Security Context & Actor Propagation

### 2.1 Java 25 `ScopedValue` Context
- Context propagation uses Java 25 `ScopedValue` via `SecurityContextAccessor` implementing `CurrentActorProvider`.
- Virtual-thread friendly, non-blocking, and immutable across the request lifetime.
- **Fail-Fast**: Calling `currentActorProvider.requireCurrentActor()` when unauthenticated must throw `AccessDeniedException` immediately.

### 2.2 Hierarchical Organizational Scoping (`ScopeNode`)
- Scopes represent organizational hierarchies (e.g. Hospital -> Clinic -> Department -> Ward).
- Nodes use path-indexed hierarchy trees (e.g. `/root-id/clinic-id/dept-id/`).
- Scope checks must verify boundary access via `CurrentActor.canAccessScope(scopeNodeId)` or `ScopeSubtreeResolver`.

---

## 3. Audit Trail & Domain Events

Audit trailing is driven by structured domain events emitted upon state mutations.

### 3.1 Domain Events (`IamEvent`)
- Security and management use cases emit structured immutable domain events:
  - Event types declared in `IamEventTypes` (e.g. `USER_CREATED`, `USER_AUTHENTICATED`, `ROLE_ASSIGNED`, `SCOPE_NODE_CREATED`, `SCOPE_NODE_MOVED`).
  - Standard event structure:
    - `eventId`: UUIDv7 timestamp-ordered identifier.
    - `eventType`: Descriptive action string from `IamEventTypes`.
    - `tenantId`: Originating tenant.
    - `actorId`: Actor performing the operation.
    - `timestamp`: Instant of occurrence.
    - `payload`: Immutable state snapshot or delta.

### 3.2 Audit Invariants
- **Append-Only**: Audit records and domain event logs are strictly append-only.
- **Sensitive Data Redaction**: Passwords, hashed secrets, and raw JWT signatures must NEVER be emitted into event payloads or audit logs.
