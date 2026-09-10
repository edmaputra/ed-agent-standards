---
description: "Hexagonal Architecture (Ports and Adapters) rules with strict layered dependency flow."
globs:
  - "**/*.java"
  - "**/*.kt"
---

# Hexagonal Architecture Rules

This project follows **Hexagonal Architecture (Ports and Adapters)** with **Domain-Driven Design (DDD)** in Java 25 and Spring Boot 4.

> **Notation**: `{base-package}` refers to the project's root package (e.g. `io.github.edmaputra.iam`). `{Module}` refers to the project's module name used as a class prefix (e.g. `Iam`, `Order`). `{module}` refers to the lowercase version used in table prefixes and config namespaces.

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
- **Packages**: `{base-package}.domain.*`
- **Contents**:
  - **Domain Entities & Value Objects**: Immutable Java `record`s enforcing business invariants.
  - **Security & Tenancy Abstractions**: e.g. `CurrentActor`, `CurrentActorProvider`, `TenantId`, `TenantOwned`, `TenantContextBridge`.
  - **Outbound Ports (Repository Interfaces)**: Pure repository interfaces (e.g. `UserRepository`, `OrderRepository`).
  - **Domain Events**: Records representing state changes (e.g. `{Module}Event`, `{Module}EventTypes`).
  - **Domain Exceptions**: Specific domain exceptions (e.g. `EntityNotFoundException`, `AccessDeniedException`, `AuthenticationException`).
  - **Platform Contexts**: e.g. `OperationContext`.

```java
// ❌ BAD: Domain class importing Spring
package com.example.myapp.domain.model;

import org.springframework.stereotype.Component; // VIOLATION
import jakarta.persistence.Entity;               // VIOLATION

@Entity    // VIOLATION — JPA annotation in domain
@Component // VIOLATION — Spring annotation in domain
public class Order { ... }

// ✅ GOOD: Pure domain record, no framework dependencies
package com.example.myapp.domain.model;

public record Order(OrderId id, TenantId tenantId, List<LineItem> items, Money total) {
    public Order {
        Objects.requireNonNull(id, "OrderId must not be null.");
        Objects.requireNonNull(tenantId, "TenantId must not be null.");
        items = List.copyOf(items);
    }
}
```

### 1.2 `application` (Use Cases & Application Orchestration)
- **Framework-Agnostic Orchestration**: Pure Java logic depending only on `domain`.
- **No Spring Annotations in Services**: Do NOT use Spring `@Service`, `@Component`, or `@Autowired` in core application services. Bean instantiation is managed by Starter Auto-Configurations.
- **Packages**: `{base-package}.application.*`
- **Contents**:
  - **Inbound Ports (`port.in`)**: Single-purpose use-case interfaces and command records (e.g. `AuthenticateUserUseCase`, `PlaceOrderUseCase`, `LoginCommand`, `CreateOrderCommand`).
  - **Outbound SPI Ports (`port.out`)**: Extensible SPI interfaces (e.g. `AuthenticationProvider`, `PaymentGateway`, `PasswordEncoderPort`).
  - **Application Services (`service`)**: Orchestrators implementing inbound ports (e.g. `AuthenticationService`, `OrderProcessingService`).
  - **Application Models (`model`)**: Output transfer objects (e.g. `TokenResponse`, `OrderSummary`).

```java
// ❌ BAD: Spring annotation in application service
package com.example.myapp.application.service;

import org.springframework.stereotype.Service;

@Service // VIOLATION — bean wiring belongs in AutoConfiguration
public class OrderProcessingService implements PlaceOrderUseCase { ... }

// ✅ GOOD: Pure application service, wired via AutoConfiguration
package com.example.myapp.application.service;

public class OrderProcessingService implements PlaceOrderUseCase {
    private final OrderRepository orderRepository;
    private final PaymentGateway paymentGateway;

    public OrderProcessingService(OrderRepository orderRepository, PaymentGateway paymentGateway) {
        this.orderRepository = Objects.requireNonNull(orderRepository);
        this.paymentGateway = Objects.requireNonNull(paymentGateway);
    }
}
```

### 1.3 `adapter.rest` (Driving / Inbound REST Adapter)
- **HTTP Transport Layer**: Exposes REST endpoints.
- **Packages**: `{base-package}.adapter.rest.*`
- **Contents**:
  - `@RestController` classes (e.g. `AuthController`, `OrderController`).
  - Request/Response DTO records and mappings (e.g. `LoginRequest`, `CreateOrderRequest`).
  - Centralized exception mapping (`{Module}ExceptionHandler`) returning RFC 9457 problem details.
- **Rule**: Controllers MUST only invoke Inbound Port interfaces (`*UseCase`). They must never interact directly with repositories or persistence entities.

```java
// ❌ BAD: Controller calling repository directly
@RestController
public class OrderController {
    private final OrderJpaRepository jpaRepo; // VIOLATION — bypasses use case ports

    @GetMapping("/api/v1/orders/{id}")
    public OrderJpaEntity getOrder(@PathVariable UUID id) {
        return jpaRepo.findById(id).orElseThrow(); // VIOLATION — leaking JPA entity
    }
}

// ✅ GOOD: Controller delegates to inbound port
@RestController
public class OrderController {
    private final GetOrderUseCase getOrderUseCase;

    @GetMapping("/api/v1/orders/{id}")
    public OrderSummary getOrder(@PathVariable UUID id) {
        return getOrderUseCase.getById(id);
    }
}
```

### 1.4 `adapter.persistence` (Driven / Outbound JPA Adapter)
- **Database & Data Access**: Implements domain repository ports using Spring Data JPA.
- **Packages**: `{base-package}.adapter.persistence.*`
- **Contents**:
  - JPA entities with `{module}_*` table mappings (e.g. `OrderJpaEntity`, `ProductJpaEntity`).
  - Spring Data JPA repositories (e.g. `OrderJpaRepository`, `ProductJpaRepository`).
  - Repository adapters bridging domain repository interfaces (e.g. `OrderRepositoryAdapter implements OrderRepository`).
- **Rules**:
  - JPA entities must remain private to this adapter. Always map cleanly between JPA entities and domain records.
  - Never let database entity mutations leak outside repository adapters.

```java
// ❌ BAD: Returning JPA entity from adapter
public class OrderRepositoryAdapter implements OrderRepository {
    public OrderJpaEntity findById(UUID id) { ... } // VIOLATION — leaking JPA entity
}

// ✅ GOOD: Mapping JPA entity to domain record
public class OrderRepositoryAdapter implements OrderRepository {
    private final OrderJpaRepository jpaRepository;

    @Override
    public Optional<Order> findById(OrderId id) {
        return jpaRepository.findById(id.value()).map(OrderMapper::toDomain);
    }
}
```

### 1.5 `adapter.security` (Security & Token Adapter)
- **Security Infrastructure**: Implements token management, cryptographic adapters, and HTTP security filters.
- **Packages**: `{base-package}.adapter.security.*`
- **Contents**:
  - JWT generation and validation (`JwtTokenProvider`).
  - Java 25 `ScopedValue`-backed security context propagation (`SecurityContextAccessor`).
  - Non-blocking HTTP filter (`JwtAuthenticationFilter`) binding `CurrentActor` and bridging `TenantContextBridge`.
  - Authentication provider implementations (e.g. `LocalPasswordAuthProvider`, `OidcAuthProvider`).
  - Password hashing adapter (e.g. `BCryptPasswordEncoderAdapter implements PasswordEncoderPort`).

### 1.6 AutoConfiguration Layer (Starter Bootstrap & Wiring)
- **Auto-Configuration Root**: Registers beans with `@ConditionalOnMissingBean` so host applications can override any component or SPI.
- **Classes** (examples):
  - `{Module}SecurityAutoConfiguration`: Auto-configures auth providers, token engine, JPA repository adapters, and security filters.
  - `{Module}LiquibaseAutoConfiguration`: Configures isolated `{module}_*` Liquibase migrations with proper execution ordering before JPA entity manager initialization.

---

## 2. Dependency Check List

When adding or modifying code, verify:
- [ ] Does `domain` contain any Spring, JPA, or Web imports? (Must be **NONE**)
- [ ] Do application use-case services contain Spring annotations (`@Service`, `@Component`, `@Autowired`)? (Must be **NONE** — wired in AutoConfiguration)
- [ ] Do REST controllers call repositories directly? (Must **ONLY** call Inbound Port interfaces)
- [ ] Are JPA entities leaking into domain or REST layers? (Must remain inside `adapter.persistence`)
- [ ] Are starter beans declared with `@ConditionalOnMissingBean` to preserve pluggability?
