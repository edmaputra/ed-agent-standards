---
description: "Database schema conventions, migration standards, and persistence best practices."
globs:
  - "**/*.java"
  - "**/*.kt"
  - "**/*.sql"
  - "**/*.xml"
  - "**/*.json"
  - "**/db/changelog/**"
---

# Database & Migration Standards

This document establishes database schema conventions, migration management, and persistence best practices for Java 25 / Spring Boot 4 services.

> **Notation**: `{module}` refers to the project's module name in lowercase (e.g. `iam`, `order`, `billing`).
>
> **Severity Levels**:
> - 🔴 **MUST**: Non-negotiable requirement. Violations will fail CI checks or block code review approval.
> - 🟡 **SHOULD**: Strongly recommended practice. Deviations require team consensus and documented rationale.
> - 🟢 **MAY**: Optional guideline or contextual optimization.

---

## 1. Table & Column Naming Conventions 🔴 MUST

### 1.1 Table Names
- **Prefix with module name**: All tables MUST use the `{module}_` prefix to prevent collisions in shared-database deployments (e.g. `iam_user`, `order_line_item`).
- **Lowercase snake_case**: Always use lowercase `snake_case` for table names.
- **Plural nouns**: Tables represent collections — use plural names (e.g. `iam_users`, `order_items`).

```sql
-- ✅ GOOD: Prefixed, snake_case, plural
CREATE TABLE iam_users (...)
CREATE TABLE iam_roles (...)
CREATE TABLE order_line_items (...)

-- ❌ BAD: No prefix, camelCase, singular
CREATE TABLE User (...)
CREATE TABLE OrderLineItem (...)
CREATE TABLE users (...)  -- Missing module prefix
```

### 1.2 Column Names
- **Lowercase snake_case**: All column names MUST be lowercase `snake_case`.
- **No abbreviations**: Use full, descriptive names (e.g. `created_at` not `crt_at`, `tenant_id` not `tid`).
- **Boolean columns**: Prefix with `is_` or `has_` (e.g. `is_active`, `has_verified_email`).
- **Foreign key columns**: Use `{referenced_entity}_id` pattern (e.g. `user_id`, `tenant_id`).

```sql
-- ✅ GOOD: Clear, descriptive column names
CREATE TABLE iam_users (
    id              UUID            PRIMARY KEY,
    tenant_id       UUID            NOT NULL,
    username        VARCHAR(255)    NOT NULL,
    email           VARCHAR(255),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by      UUID,
    updated_by      UUID
);

-- ❌ BAD: Abbreviations, inconsistent naming
CREATE TABLE iam_users (
    ID              UUID PRIMARY KEY,   -- VIOLATION: uppercase
    tid             UUID NOT NULL,      -- VIOLATION: abbreviation
    uname           VARCHAR(255),       -- VIOLATION: abbreviation
    active          BOOLEAN,            -- VIOLATION: missing is_ prefix
    crtDt           TIMESTAMP           -- VIOLATION: camelCase + abbreviation
);
```

### 1.3 Index & Constraint Naming
- **Indexes**: `idx_{table}_{column(s)}` (e.g. `idx_iam_users_tenant_id`, `idx_iam_users_username_tenant_id`)
- **Unique constraints**: `uq_{table}_{column(s)}` (e.g. `uq_iam_users_username_tenant_id`)
- **Foreign keys**: `fk_{table}_{referenced_table}` (e.g. `fk_iam_user_roles_iam_users`)
- **Check constraints**: `chk_{table}_{description}` (e.g. `chk_order_items_quantity_positive`)

---

## 2. Audit Columns 🔴 MUST

### 2.1 Required Audit Columns
Every table MUST include the following audit columns:

| Column | Type | Purpose |
|---|---|---|
| `created_at` | `TIMESTAMPTZ` | Timestamp of row creation. Set once, never updated. |
| `updated_at` | `TIMESTAMPTZ` | Timestamp of last modification. Updated on every write. |
| `created_by` | `UUID` (nullable) | Actor ID who created the record. Nullable for system-generated records. |
| `updated_by` | `UUID` (nullable) | Actor ID who last modified the record. |

### 2.2 JPA Audit Mapping
Use Spring Data JPA's `@EntityListeners(AuditingEntityListener.class)` or a shared `@MappedSuperclass` to populate audit columns automatically:

```java
// ✅ GOOD: Shared auditable base entity
@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class AuditableEntity {
    @CreatedDate
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @LastModifiedDate
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @CreatedBy
    @Column(name = "created_by", updatable = false)
    private UUID createdBy;

    @LastModifiedBy
    @Column(name = "updated_by")
    private UUID updatedBy;
}
```

---

## 3. Soft Delete vs Hard Delete 🟡 SHOULD

- **Default: Soft Delete** for business entities that may need recovery or audit trails. Add an `is_deleted` boolean column and a `deleted_at` timestamp.
- **Hard Delete** is permitted for:
  - Join/association tables (e.g. `iam_user_role_assignments`)
  - Temporary or ephemeral data (e.g. OTP codes, session tokens)
  - When regulations require actual data removal (e.g. GDPR right to erasure)
- **Query Discipline**: When using soft delete, ALL queries MUST include `WHERE is_deleted = FALSE` unless explicitly querying deleted records for audit/recovery.

```java
// ✅ GOOD: Soft delete in repository adapter
public class UserRepositoryAdapter implements UserRepository {
    @Override
    @Transactional(readOnly = true)
    public Optional<User> findById(UserId id) {
        return jpaRepository.findByIdAndIsDeletedFalse(id.value())
            .map(UserMapper::toDomain);
    }

    @Override
    @Transactional
    public void delete(UserId id) {
        jpaRepository.findById(id.value()).ifPresent(entity -> {
            entity.setDeleted(true);
            entity.setDeletedAt(Instant.now());
        });
    }
}

// ❌ BAD: Hard delete without justification
public void delete(UserId id) {
    jpaRepository.deleteById(id.value()); // VIOLATION — use soft delete for business entities
}
```

---

## 4. Optimistic Locking 🔴 MUST

- **Use `@Version`** on JPA entities that support concurrent modification (e.g. orders, user profiles, configuration records).
- The `version` column prevents lost updates without requiring pessimistic database locks.
- Handle `OptimisticLockException` / `StaleObjectStateException` gracefully — translate to HTTP `409 Conflict`.

```java
// ✅ GOOD: Optimistic locking on JPA entity
@Entity
@Table(name = "order_orders")
public class OrderJpaEntity extends AuditableEntity {
    @Id
    private UUID id;

    @Version
    @Column(name = "version", nullable = false)
    private Long version;

    // ... other fields
}
```

```java
// ✅ GOOD: Handling optimistic lock failure in exception handler
@ExceptionHandler(OptimisticLockingFailureException.class)
public ProblemDetail handleConflict(OptimisticLockingFailureException ex, HttpServletRequest request) {
    ProblemDetail problem = ProblemDetail.forStatusAndDetail(
        HttpStatus.CONFLICT,
        "Resource was modified by another request. Please refresh and retry."
    );
    problem.setTitle("Concurrent Modification Conflict");
    problem.setInstance(URI.create(request.getRequestURI()));
    return problem;
}
```

---

## 5. Migration Standards (Liquibase) 🔴 MUST

### 5.1 Changelog Organization
- **Changelog format**: JSON or YAML (not XML) for readability and consistency.
- **Master changelog**: One master file per module (e.g. `db/changelog/db.changelog-{module}.json`).
- **Individual changesets**: One changeset per logical change. Never combine unrelated schema changes in a single changeset.
- **File naming**: `YYYY-MM-DD-NNN-{description}.json` (e.g. `2025-01-15-001-create-users-table.json`).

```
src/main/resources/
└── db/
    └── changelog/
        ├── db.changelog-iam.json              ← Master changelog
        ├── 2025-01-15-001-create-users-table.json
        ├── 2025-01-15-002-create-roles-table.json
        ├── 2025-02-01-001-add-user-email-column.json
        └── 2025-03-10-001-create-scope-nodes-table.json
```

### 5.2 Changeset Rules
- **Immutable changesets**: Once a changeset has been applied to any environment, NEVER modify it. Create a new changeset for corrections.
- **Unique IDs**: Use `{author}:{YYYYMMDD}-{NNN}` format (e.g. `edmaputra:20250115-001`).
- **Rollback support**: Every changeset that creates or alters tables MUST include a `rollback` section.
- **Context tags**: Use context tags for environment-specific changesets (e.g. `context: "!production"` for test data seeding).

### 5.3 Migration Safety
- **No destructive changes in production**: Never drop columns or tables directly. Instead:
  1. Mark as deprecated in the application
  2. Stop reading/writing the column
  3. Drop in a future release after verifying no access
- **Additive-first**: Prefer adding new nullable columns over modifying existing columns.
- **Large table migrations**: For large tables, use Liquibase's `splitStatements` or run migrations outside of application startup to avoid long lock times.

---

## 6. Connection Pool & Performance 🔴 MUST

### 6.1 Connection Pool (HikariCP)
- **Spring Boot default**: HikariCP is auto-configured. Do not replace without justification.
- **Pool sizing**: Follow the formula: `connections = (core_count * 2) + effective_spindle_count`. For most cloud services, start with `maximumPoolSize = 10` and tune based on load testing.
- **Leak detection**: Enable `spring.datasource.hikari.leak-detection-threshold=30000` (30s) in non-production environments.

### 6.2 Query Performance
- **Avoid N+1 queries**: Use `JOIN FETCH`, `@EntityGraph`, or batch fetching (`@BatchSize`) for associated collections.
- **Pagination**: Always paginate large result sets. Never fetch unbounded collections.
- **Projections**: Use interface projections or DTO projections for read-heavy queries that don't need full entity loading.

```java
// ❌ BAD: N+1 query — each order triggers a separate query for line items
List<OrderJpaEntity> orders = jpaRepository.findAll();
orders.forEach(o -> o.getLineItems().size()); // VIOLATION — lazy load per order

// ✅ GOOD: JOIN FETCH to load in a single query
@Query("SELECT o FROM OrderJpaEntity o JOIN FETCH o.lineItems WHERE o.tenantId = :tenantId")
List<OrderJpaEntity> findAllWithItemsByTenantId(@Param("tenantId") UUID tenantId);
```
