---
description: "Multi-tenancy architecture, security context propagation, and audit eventing standards."
globs:
  - "**/*.java"
  - "**/*.kt"
---

# Multi-Tenancy & Audit Trail Rules

This document outlines the architectural requirements for multi-tenancy, security context propagation, and audit eventing.

> **Notation**: `{Module}` refers to the project's module name used as a class prefix (e.g. `Iam`, `Order`). `{module}` refers to the lowercase version used in table prefixes and config namespaces.
>
> **Severity Levels**:
> - 🔴 **MUST**: Non-negotiable requirement. Violations will fail CI checks or block code review approval.
> - 🟡 **SHOULD**: Strongly recommended practice. Deviations require team consensus and documented rationale.
> - 🟢 **MAY**: Optional guideline or contextual optimization.

---

## 1. Multi-Tenancy Architecture 🔴 MUST

Multi-tenancy is a foundational architectural pillar. The system operates on a **shared application, shared database, tenant discriminator column** model without tightly coupling to host application databases.

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
- **Table Namespacing**: All database tables managed by a module use a consistent `{module}_*` prefix (e.g. `iam_user`, `order_item`).
- **Query Scoping**: Repository adapters (`adapter.persistence`) MUST filter queries by `tenantId`. Never allow cross-tenant query leaks.
- **Isolated Migrations**: Module migrations run via `{Module}LiquibaseAutoConfiguration` using isolated changelogs, executing after core migrations and before JPA entity manager initialization.

```java
// ❌ BAD: Repository query without tenant scoping
public interface OrderJpaRepository extends JpaRepository<OrderJpaEntity, UUID> {
    List<OrderJpaEntity> findByStatus(String status); // VIOLATION — no tenant filter
}

// ✅ GOOD: All queries scoped by tenant
public interface OrderJpaRepository extends JpaRepository<OrderJpaEntity, UUID> {
    List<OrderJpaEntity> findByTenantIdAndStatus(UUID tenantId, String status);
    Optional<OrderJpaEntity> findByIdAndTenantId(UUID id, UUID tenantId);
}
```

---

## 2. Security Context & Actor Propagation 🔴 MUST

### 2.1 Java 25 `ScopedValue` Context
- Context propagation uses Java 25 `ScopedValue` via `SecurityContextAccessor` implementing `CurrentActorProvider`.
- Virtual-thread friendly, non-blocking, and immutable across the request lifetime.
- **Fail-Fast**: Calling `currentActorProvider.requireCurrentActor()` when unauthenticated must throw `AccessDeniedException` immediately.

```java
// ❌ BAD: ThreadLocal-based context (not virtual-thread safe)
public class SecurityContext {
    private static final ThreadLocal<CurrentActor> holder = new ThreadLocal<>();
    public static void set(CurrentActor actor) { holder.set(actor); }
    public static CurrentActor get() { return holder.get(); } // may return null silently
}

// ✅ GOOD: ScopedValue-based context (virtual-thread friendly, fail-fast)
public class SecurityContextAccessor implements CurrentActorProvider {
    private static final ScopedValue<CurrentActor> CURRENT_ACTOR = ScopedValue.newInstance();

    @Override
    public CurrentActor requireCurrentActor() {
        return CURRENT_ACTOR.orElseThrow(() -> new AccessDeniedException("No authenticated actor in scope."));
    }
}
```

### 2.2 Hierarchical Organizational Scoping
- Scopes represent organizational hierarchies (e.g. Hospital -> Clinic -> Department -> Ward, or Company -> Division -> Team).
- Nodes use path-indexed hierarchy trees (e.g. `/root-id/clinic-id/dept-id/`).
- Scope checks must verify boundary access via `CurrentActor.canAccessScope(scopeNodeId)` or a `ScopeSubtreeResolver`.

---

## 3. Audit Trail & Domain Events 🔴 MUST

Audit trailing is driven by structured domain events emitted upon state mutations.

### 3.1 Domain Events (`{Module}Event`)
- Security and management use cases emit structured immutable domain events:
  - Event types declared in `{Module}EventTypes` (e.g. `USER_CREATED`, `ORDER_PLACED`, `ROLE_ASSIGNED`).
  - Standard event structure:
    - `eventId`: UUIDv7 timestamp-ordered identifier.
    - `eventType`: Descriptive action string from `{Module}EventTypes`.
    - `tenantId`: Originating tenant.
    - `actorId`: Actor performing the operation.
    - `timestamp`: Instant of occurrence.
    - `payload`: Immutable state snapshot or delta.

```java
// ✅ GOOD: Structured immutable domain event
public record OrderEvent(
    UUID eventId,
    String eventType,
    UUID tenantId,
    UUID actorId,
    Instant timestamp,
    Map<String, Object> payload
) {
    public OrderEvent {
        Objects.requireNonNull(eventId, "eventId must not be null.");
        Objects.requireNonNull(eventType, "eventType must not be null.");
        Objects.requireNonNull(tenantId, "tenantId must not be null.");
        Objects.requireNonNull(timestamp, "timestamp must not be null.");
        payload = payload == null ? Map.of() : Map.copyOf(payload);
    }
}
```

### 3.2 Audit Invariants
- **Append-Only**: Audit records and domain event logs are strictly append-only. Never update or delete audit entries.
- **Sensitive Data Redaction**: Passwords, hashed secrets, and raw JWT signatures must NEVER be emitted into event payloads or audit logs.

```java
// ❌ BAD: Sensitive data in event payload
var event = new OrderEvent(eventId, "USER_AUTHENTICATED", tenantId, actorId, now,
    Map.of("username", username, "password", rawPassword)); // VIOLATION — password in payload

// ✅ GOOD: Only safe identifiers in event payload
var event = new OrderEvent(eventId, "USER_AUTHENTICATED", tenantId, actorId, now,
    Map.of("username", username, "authMethod", "LOCAL"));
```
