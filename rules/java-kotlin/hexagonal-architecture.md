---
description: "Hexagonal Architecture (Ports and Adapters) rules with strict layered dependency flow."
globs:
  - "**/*.java"
  - "**/*.kt"
---

# Hexagonal Architecture Rules

This project follows **Hexagonal Architecture (Ports and Adapters)** with **Domain-Driven Design (DDD)** in Java 25 and Spring Boot 4.

> **Notation**: `{base-package}` refers to the project's root package (e.g. `io.github.edmaputra.iam`). `{Module}` refers to the project's module name used as a class prefix (e.g. `Iam`, `Order`). `{module}` refers to the lowercase version used in table prefixes and config namespaces.
>
> **Severity Levels**:
> - 🔴 **MUST**: Non-negotiable requirement. Violations will fail CI checks or block code review approval.
> - 🟡 **SHOULD**: Strongly recommended practice. Deviations require team consensus and documented rationale.
> - 🟢 **MAY**: Optional guideline or contextual optimization.

---

## 1. Package Layout & Architectural Layers 🔴 MUST

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

## 2. Transaction Boundaries 🔴 MUST

Transaction management is a common source of subtle bugs. These rules ensure consistency.

### 2.1 `@Transactional` Placement
- **Repository Adapters (`adapter.persistence`)**: `@Transactional` belongs on repository adapter methods that perform write operations. This is the **primary** location for transaction demarcation.
- **Application Services**: Application services MAY use `@Transactional` when a use case must orchestrate **multiple** repository writes as a single atomic operation. In this case, the `@Transactional` annotation is applied at the application service method level, and the service is wired in AutoConfiguration (not annotated with `@Service`).
- **Domain Layer**: NEVER place `@Transactional` in the domain layer. The domain must remain framework-agnostic.
- **Controllers**: NEVER place `@Transactional` on REST controllers or controller methods.

```java
// ❌ BAD: @Transactional on controller
@RestController
public class OrderController {
    @Transactional // VIOLATION — transaction management does not belong in the transport layer
    @PostMapping("/api/v1/orders")
    public OrderSummary create(@RequestBody CreateOrderRequest request) { ... }
}

// ❌ BAD: @Transactional on domain class
package com.example.myapp.domain.model;
@Transactional // VIOLATION — domain must be framework-agnostic
public record Order(...) { ... }

// ✅ GOOD: @Transactional on repository adapter (single-repo write)
public class OrderRepositoryAdapter implements OrderRepository {
    @Override
    @Transactional
    public Order save(Order order) {
        var entity = OrderMapper.toJpa(order);
        return OrderMapper.toDomain(jpaRepository.save(entity));
    }
}

// ✅ GOOD: @Transactional on application service (multi-repo atomic operation)
public class PlaceOrderService implements PlaceOrderUseCase {
    private final OrderRepository orderRepository;
    private final InventoryPort inventoryPort;

    @Override
    @Transactional
    public OrderSummary execute(CreateOrderCommand command) {
        inventoryPort.reserve(command.productId(), command.quantity());
        var order = Order.create(command);
        orderRepository.save(order);
        return OrderSummary.from(order);
    }
}
```

### 2.2 Read-Only Transactions
- Use `@Transactional(readOnly = true)` for query-only operations to enable database-level optimizations (e.g. no dirty checking, replica routing).

```java
// ✅ GOOD: Read-only transaction for queries
public class OrderRepositoryAdapter implements OrderRepository {
    @Override
    @Transactional(readOnly = true)
    public Optional<Order> findById(OrderId id) {
        return jpaRepository.findById(id.value()).map(OrderMapper::toDomain);
    }
}
```

### 2.3 Transaction Propagation
- **Default propagation (`REQUIRED`)**: Suitable for most cases. Joins an existing transaction or creates a new one.
- **`REQUIRES_NEW`**: Use sparingly and only when an operation must commit independently (e.g. audit log persistence that must not roll back with the main transaction).
- **Document non-default propagation**: Any use of `REQUIRES_NEW`, `NESTED`, or `NOT_SUPPORTED` must include a comment explaining why.

---

## 3. Layer Mapping Strategy 🟡 SHOULD

Mapping between architectural layers (domain ↔ JPA entity ↔ DTO) requires clear conventions.

### 3.1 Mapping Approaches (in order of preference)
1. **Record-to-Record constructors / static factory methods**: Preferred for simple mappings. Keep mapping logic co-located.
2. **Dedicated `*Mapper` utility classes**: For complex mappings with conditional logic, computed fields, or collection transformations. Use `static` methods in a non-instantiable class.
3. **MapStruct**: Permitted for large-scale projects with many entities, but only in `adapter` packages. Never generate mappers into domain.

### 3.2 Mapping Rules
- **JPA ↔ Domain mapping** lives in `adapter.persistence` (e.g. `OrderMapper.toDomain()`, `OrderMapper.toJpa()`).
- **Domain ↔ DTO mapping** lives in `adapter.rest` (e.g. request `toCommand()` methods, response `from()` factory methods).
- **Never pass JPA entities across layer boundaries**. Always map to domain records at the adapter boundary.
- **Never pass request/response DTOs into application or domain services**. Map to commands/domain objects at the controller.

```java
// ✅ GOOD: Mapper in adapter.persistence
package com.example.myapp.adapter.persistence;

public final class OrderMapper {
    private OrderMapper() {} // Non-instantiable

    public static Order toDomain(OrderJpaEntity entity) {
        return new Order(
            new OrderId(entity.getId()),
            new TenantId(entity.getTenantId()),
            entity.getItems().stream().map(LineItemMapper::toDomain).toList(),
            Money.of(entity.getTotalAmount(), entity.getCurrency())
        );
    }

    public static OrderJpaEntity toJpa(Order order) {
        var entity = new OrderJpaEntity();
        entity.setId(order.id().value());
        entity.setTenantId(order.tenantId().value());
        entity.setTotalAmount(order.total().amount());
        entity.setCurrency(order.total().currency());
        return entity;
    }
}

// ✅ GOOD: DTO with toCommand() in adapter.rest
package com.example.myapp.adapter.rest;

public record CreateOrderRequest(
    @NotNull UUID productId,
    @Min(1) int quantity
) {
    public CreateOrderCommand toCommand() {
        return new CreateOrderCommand(productId, quantity);
    }
}

// ✅ GOOD: Response with static factory in adapter.rest
package com.example.myapp.adapter.rest;

public record OrderResponse(UUID id, String status, BigDecimal total) {
    public static OrderResponse from(OrderSummary summary) {
        return new OrderResponse(summary.id(), summary.status().name(), summary.total());
    }
}
```

---

## 4. ArchUnit Enforcement 🔴 MUST

Use [ArchUnit](https://www.archunit.org/) to automatically verify architectural layer boundaries in your test suite. This prevents layer violations from slipping in via code reviews.

### 4.1 Required ArchUnit Tests

Every project following these architecture rules SHOULD include an `ArchitectureTest` class in the test source set:

```java
package com.example.myapp;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

@AnalyzeClasses(
    packages = "com.example.myapp",
    importOptions = ImportOption.DoNotIncludeTests.class
)
class ArchitectureTest {

    // --- Domain layer must have ZERO framework dependencies ---

    @ArchTest
    static final ArchRule domain_must_not_depend_on_spring =
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("org.springframework..");

    @ArchTest
    static final ArchRule domain_must_not_depend_on_jpa =
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("jakarta.persistence..", "org.hibernate..");

    // --- Domain must not depend on application or adapter ---

    @ArchTest
    static final ArchRule domain_must_not_depend_on_application =
        noClasses().that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..application..", "..adapter..");

    // --- Application must not depend on adapters ---

    @ArchTest
    static final ArchRule application_must_not_depend_on_adapters =
        noClasses().that().resideInAPackage("..application..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..adapter..");

    // --- Adapters must not depend on each other ---

    @ArchTest
    static final ArchRule adapters_must_not_depend_on_each_other =
        slices().matching("..adapter.(*)..")
            .should().notDependOnEachOther();

    // --- Controllers must not access repositories directly ---

    @ArchTest
    static final ArchRule controllers_must_not_access_persistence =
        noClasses().that().resideInAPackage("..adapter.rest..")
            .should().dependOnClassesThat()
            .resideInAPackage("..adapter.persistence..");
}
```

### 4.2 Dependency Setup

Add ArchUnit to your test dependencies:

```xml
<!-- Maven (pom.xml) -->
<dependency>
    <groupId>com.tngtech.archunit</groupId>
    <artifactId>archunit-junit5</artifactId>
    <version>1.4.0</version>
    <scope>test</scope>
</dependency>
```

```kotlin
// Gradle (build.gradle.kts)
testImplementation("com.tngtech.archunit:archunit-junit5:1.4.0")
```

---

## 5. Dependency Check List 🔴 MUST

When adding or modifying code, verify:
- [ ] Does `domain` contain any Spring, JPA, or Web imports? (Must be **NONE**)
- [ ] Do application use-case services contain Spring annotations (`@Service`, `@Component`, `@Autowired`)? (Must be **NONE** — wired in AutoConfiguration)
- [ ] Do REST controllers call repositories directly? (Must **ONLY** call Inbound Port interfaces)
- [ ] Are JPA entities leaking into domain or REST layers? (Must remain inside `adapter.persistence`)
- [ ] Are starter beans declared with `@ConditionalOnMissingBean` to preserve pluggability?
- [ ] Is `@Transactional` placed correctly? (Adapter or application service — **NEVER** domain or controller)
- [ ] Are layer mappings co-located in the correct adapter package?
- [ ] Do ArchUnit tests pass after the change?
