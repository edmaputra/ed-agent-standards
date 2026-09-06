# Hexagonal Architecture Rules

This project follows **Hexagonal Architecture (Ports and Adapters)** with **Domain-Driven Design (DDD)** in Java 25 and Spring Boot 4 for the `ed-iam` Spring Boot Starter.

---

## 1. Package Layout & Architectural Layers

The codebase is structured into strict architectural layers where dependencies must flow **inward**.

```
adapter.rest (Driving Adapter)       adapter.persistence (Driven Adapter)
         \                                    /
          \                                  /
           --->   domain (Core Kernel)   <---
                        ^
                        |
            application (Use Cases & SPIs)
                        ^
                        |
        AutoConfiguration (Starter Auto-Wiring)
```

### 1.1 `domain` (Domain Model, Contracts & Ports)
- **Framework-Agnostic**: Pure Java 25 only. Strictly NO Spring, JPA, Hibernate, or Web dependencies.
- **Packages**: `io.github.edmaputra.iam.domain.*`
- **Contents**:
  - **Domain Entities & Value Objects**: Immutable Java `record`s enforcing business invariants (e.g. `User`, `Role`, `Group`, `ScopeNode`, `TenantId`, `UserId`).
  - **Security & Tenancy Abstractions**: `CurrentActor`, `CurrentActorProvider`, `TenantId`, `TenantOwned`, `TenantContextBridge`.
  - **Outbound Ports (Repository Interfaces)**: Pure repository interfaces (e.g. `UserRepository`, `RoleRepository`, `GroupRepository`, `ScopeNodeRepository`).
  - **Domain Events**: Records representing state changes (e.g. `IamEvent`, `IamEventTypes`).
  - **Domain Exceptions**: Specific domain exceptions (e.g. `UserNotFoundException`, `AccessDeniedException`, `AuthenticationException`).
  - **Platform Contexts**: `OperationContext`.

### 1.2 `application` (Use Cases & Application Orchestration)
- **Framework-Agnostic Orchestration**: Pure Java logic depending only on `domain`.
- **No Spring Annotations in Services**: Do NOT use Spring `@Service`, `@Component`, or `@Autowired` in core application services. Bean instantiation is managed by Starter Auto-Configurations.
- **Packages**: `io.github.edmaputra.iam.application.*`
- **Contents**:
  - **Inbound Ports (`port.in`)**: Single-purpose use-case interfaces and command records (e.g. `AuthenticateUserUseCase`, `ManageScopeUseCase`, `LoginCommand`, `RefreshTokenCommand`, `CreateScopeNodeCommand`).
  - **Outbound SPI Ports (`port.out`)**: Extensible SPI interfaces (e.g. `AuthenticationProvider`, `AuthenticationProviderRouter`, `PasswordEncoderPort`, `ApiKeyValidatorPort`).
  - **Application Services (`service`)**: Orchestrators implementing inbound ports (e.g. `AuthenticationService`, `EffectiveAccessResolver`, `ScopeHierarchyService`, `ScopeSubtreeResolver`, `FederatedIdentityService`).
  - **Application Models (`model`)**: Output transfer objects (e.g. `TokenResponse`, `UserProfileResponse`, `EffectiveAccess`, `ScopeTreeNode`).

### 1.3 `adapter.rest` (Driving / Inbound REST Adapter)
- **HTTP Transport Layer**: Exposes identity and authentication endpoints.
- **Packages**: `io.github.edmaputra.iam.adapter.rest.*`
- **Contents**:
  - `@RestController` classes (e.g. `AuthController` exposing `/api/v1/auth/*`).
  - Request/Response DTO records and mappings (e.g. `LoginRequest`, `RefreshTokenRequest`).
  - Centralized exception mapping (`IamExceptionHandler`) returning RFC 7807 problem details or structured error envelopes.
- **Rule**: Controllers MUST only invoke Inbound Port interfaces (`*UseCase`). They must never interact directly with repositories or persistence entities.

### 1.4 `adapter.persistence` (Driven / Outbound JPA Adapter)
- **Database & Data Access**: Implements domain repository ports using Spring Data JPA.
- **Packages**: `io.github.edmaputra.iam.adapter.persistence.*`
- **Contents**:
  - JPA entities with `iam_*` table mappings (e.g. `UserJpaEntity`, `RoleJpaEntity`, `ScopeNodeEntity`).
  - Spring Data JPA repositories (e.g. `UserJpaRepository`, `RoleJpaRepository`).
  - Repository adapters bridging domain repository interfaces (e.g. `UserRepositoryAdapter implements UserRepository`).
- **Rules**:
  - JPA entities must remain private to this adapter. Always map cleanly between JPA entities and domain records.
  - Never let database entity mutations leak outside repository adapters.

### 1.5 `adapter.security` (Security & Token Adapter)
- **Security Infrastructure**: Implements token management, cryptographic adapters, and HTTP security filters.
- **Packages**: `io.github.edmaputra.iam.adapter.security.*`
- **Contents**:
  - HMAC-SHA256 JWT generation and validation (`JwtTokenProvider`).
  - Java 25 `ScopedValue`-backed security context propagation (`SecurityContextAccessor`).
  - Non-blocking HTTP filter (`JwtAuthenticationFilter`) binding `CurrentActor` and bridging `TenantContextBridge`.
  - Authentication provider implementations (e.g. `LocalPasswordAuthProvider`, `OidcAuthProvider`).
  - Password hashing adapter (`BCryptPasswordEncoderAdapter implements PasswordEncoderPort`).

### 1.6 AutoConfiguration Layer (Starter Bootstrap & Wiring)
- **Auto-Configuration Root**: Registers beans with `@ConditionalOnMissingBean` so host applications can override any component or SPI.
- **Classes**:
  - `IamSecurityAutoConfiguration`: Auto-configures auth providers, token engine, JPA repository adapters, and security filters.
  - `IamScopeAutoConfiguration`: Auto-configures hierarchical scope services and repositories.
  - `IamLiquibaseAutoConfiguration`: Configures isolated `iam_*` Liquibase migrations with proper execution ordering before JPA entity manager initialization.

---

## 2. Dependency Check List

When adding or modifying code, verify:
- [ ] Does `domain` contain any Spring, JPA, or Web imports? (Must be **NONE**)
- [ ] Do application use-case services contain Spring annotations (`@Service`, `@Component`, `@Autowired`)? (Must be **NONE** - wired in AutoConfiguration)
- [ ] Do REST controllers call repositories directly? (Must **ONLY** call Inbound Port interfaces)
- [ ] Are JPA entities leaking into domain or REST layers? (Must remain inside `adapter.persistence`)
- [ ] Are starter beans declared with `@ConditionalOnMissingBean` to preserve pluggability?
