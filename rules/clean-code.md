# Clean Code & Modern Java Standards

This document establishes clean code practices and coding standards for this repository (Java 25 / Spring Boot 4).

---

## 1. Immutability & Java Records

- **Default to Java `record`**: Use `record` for all Domain Entities, Value Objects, Commands, Events, and DTOs.
- **Fail-Fast with Compact Constructors**: Validate invariants directly inside the compact constructor to prevent instantiating invalid objects.
- **Immutable Collections**: Return unmodifiable copies (`List.of()`, `Set.of()`, `Map.copyOf()`) to prevent state mutations from leaking.

```java
// ✅ GOOD: Immutable record with compact constructor invariant checks
public record LoginCommand(AuthCredentials credentials, UUID tenantId) {
    public LoginCommand {
        Objects.requireNonNull(credentials, "AuthCredentials must not be null.");
        Objects.requireNonNull(tenantId, "TenantId must not be null.");
    }
}

// ❌ BAD: Mutable class with getters/setters and deferred validation
public class LoginCommand {
    private AuthCredentials credentials;
    private UUID tenantId;
    public AuthCredentials getCredentials() { return credentials; }
    public void setCredentials(AuthCredentials credentials) { this.credentials = credentials; }
}
```

---

## 2. Interface Segregation & Single-Purpose Ports

- **One Inbound Port = One Intention**: Avoid monolithic "god" service interfaces. Create single-purpose use case interfaces (`AuthenticateUserUseCase`, `ManageScopeUseCase`).
- **Encapsulate Arguments in Commands**: If a use case requires multiple inputs, encapsulate them into a strongly typed `*Command` record rather than passing long parameter lists.

```java
// ✅ GOOD: Focused, single-purpose Inbound Port
public interface AuthenticateUserUseCase {
    TokenResponse login(LoginCommand command);
    TokenResponse refreshToken(RefreshTokenCommand command);
    UserProfileResponse getMe(CurrentActor actor);
}

// ❌ BAD: Monolithic service interface with dozens of unrelated methods
public interface IamService {
    TokenResponse login(String username, String password);
    void resetPassword(UUID userId);
    void assignRole(UUID userId, UUID roleId);
    void deleteTenant(UUID tenantId);
}
```

---

## 3. Explicit Dependency Injection & Zero Magic

- **Constructor Injection with `final` Fields**: Always inject dependencies via constructors.
- **Lombok `@RequiredArgsConstructor`**: Permitted for clean constructor generation on services, adapters, and controllers.
- **Field Injection Strictly Prohibited**: Never use `@Autowired` on private fields.
- **No Spring in Domain/Application Services**: Never import `@Service`, `@Component`, `@Autowired`, or `@Value` inside pure domain packages or core application services. Bean wiring belongs in `AutoConfiguration`.

```java
// ✅ GOOD: Explicit dependencies via constructor, pure Java orchestration
public class AuthenticationService implements AuthenticateUserUseCase {
    private final AuthenticationProviderRouter authRouter;
    private final UserRepository userRepository;
    private final EffectiveAccessResolver effectiveAccessResolver;
    private final JwtTokenProvider jwtTokenProvider;

    public AuthenticationService(
            AuthenticationProviderRouter authRouter,
            UserRepository userRepository,
            EffectiveAccessResolver effectiveAccessResolver,
            JwtTokenProvider jwtTokenProvider) {
        this.authRouter = Objects.requireNonNull(authRouter, "AuthenticationProviderRouter must not be null.");
        this.userRepository = Objects.requireNonNull(userRepository, "UserRepository must not be null.");
        this.effectiveAccessResolver = Objects.requireNonNull(effectiveAccessResolver, "EffectiveAccessResolver must not be null.");
        this.jwtTokenProvider = Objects.requireNonNull(jwtTokenProvider, "JwtTokenProvider must not be null.");
    }
}
```

---

## 4. Null Safety & Clean Error Handling

- **Never Return `null`**:
  - Return `Optional<T>` from repository ports for single items that might not exist.
  - Return empty collections (`List.of()`, `Set.of()`) instead of `null` for list queries.
- **Domain Exceptions**:
  - Throw specific domain exceptions (e.g. `UserNotFoundException`, `AuthenticationException`, `AccessDeniedException`) instead of generic `RuntimeException` or returning error codes.
  - Domain exceptions must reside in `io.github.edmaputra.iam.domain.exception`.
- **Centralized REST Mapping**:
  - Catch domain exceptions in `adapter.rest` via `@ExceptionHandler` inside `IamExceptionHandler`. Translate them to standard HTTP status codes and structured problem responses.

```java
// ✅ GOOD: Idiomatic Optional transformation and domain exception
return userRepository.findByUsernameAndTenantId(username, tenantId)
    .orElseThrow(() -> new UserNotFoundException("User not found for tenant."));

// ❌ BAD: Returning null, nullable checks, and generic exception
User user = userRepository.find(username, tenantId);
if (user == null) {
    throw new RuntimeException("User not found");
}
```

---

## 5. Guard Clauses & Flat Code

- **Guard Clauses**: Validate preconditions early and exit/throw immediately to avoid nested `if-else` blocks (arrow anti-pattern).
- **Pattern Matching (Java 25)**: Use pattern matching for `instanceof` and `switch` expressions over chained condition ladders.

```java
// ✅ GOOD: Flat guard clauses
public void validateScope(ScopeNode node) {
    if (node == null) {
        throw new IllegalArgumentException("ScopeNode must not be null.");
    }
    if (node.name().isBlank()) {
        throw new IllegalArgumentException("ScopeNode name must not be blank.");
    }
    // Happy path proceeds with no indentation
}

// ❌ BAD: Deeply nested indentation
public void validateScope(ScopeNode node) {
    if (node != null) {
        if (!node.name().isBlank()) {
            // Happy path buried deep
        } else {
            throw new IllegalArgumentException("ScopeNode name must not be blank.");
        }
    } else {
        throw new IllegalArgumentException("ScopeNode must not be null.");
    }
}
```

---

## 6. Naming & Language Conventions

- **English Only**: Use standard English naming for all classes, methods, variables, database tables, and REST endpoints.
- **Intention-Revealing Names**:
  - Use Cases: Verb phrases (e.g., `AuthenticateUserUseCase`, `ManageScopeUseCase`).
  - Domain Models: Noun phrases (e.g., `User`, `Role`, `Group`, `ScopeNode`).
  - Outbound Ports: Repository or Provider nouns (e.g., `UserRepository`, `AuthenticationProvider`).
  - Controllers: Resource nouns (e.g., `AuthController`).
- **REST Endpoints**: Lowercase, plural kebab-case under `/api/v1/auth` (e.g., `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/me`).

---

## 7. Testing Standards

- **Integration-First Testing Tier (`*IT.java`)**:
  - Primary verification tier using `@SpringBootTest(webEnvironment = RANDOM_PORT)` with Testcontainers PostgreSQL.
  - Use `org.springframework.test.web.reactive.server.WebTestClient` bound to the live embedded server (`WebTestClient.bindToServer().baseUrl("http://localhost:" + port)...`) for HTTP API testing, verifying actual network calls, servlet filters, security headers, and JSON responses. Do NOT use `MockMvc`.
  - **JSON Payloads & Lenient Assertions**: Send HTTP request bodies using direct JSON text blocks (`"""..."""`) via `.bodyValue(jsonString)` and assert JSON responses directly using `.expectBody().json(expectedJson, JsonCompareMode.LENIENT)` for declarative, readable verification.
- **Pure Unit Tests Tier (`*Test.java`)**:
  - Reserved strictly for isolated domain invariants, value object validation, tree algorithms, and compact constructor null guards. Fast, pure Java execution without Spring context.
- **Elimination of Mock Slice Tests**:
  - Avoid mock-heavy slice tests (`@WebMvcTest`, mocked repository adapters) that drift from production runtime behavior.
- **Arrange-Act-Assert**: Write clean, expressive tests with clear expectations and descriptive method names:
  ```java
  @Test
  void login_withValidCredentials_returnsTokenResponse() {
      // Arrange
      // Act
      // Assert
  }
  ```

---

## 8. Comprehensive Javadoc Documentation Standards

- **Mandatory Type-Level Javadoc (Class, Interface, Record, Enum)**:
  - Every Java class, interface, `record`, and `enum` MUST have a descriptive Javadoc block summarizing its purpose, domain context, and architectural role.
  - **Required Type-Level Tags**:
    ```java
    /**
     * Short one-sentence summary of the class purpose.
     * <p>
     * Detailed explanation of responsibilities, design decisions,
     * or architectural placement (e.g. Hexagonal SPI port).
     *
     * @author edmaputra
     * @since 1.0.0
     */
    ```
  - **`@author edmaputra`**: Required on all top-level types to identify maintainer attribution.
  - **`@since <version>`**: Required on all top-level types (e.g. `@since 1.0.0`) to document when the API or component was introduced.
  - **Do NOT Use `@version`**: Avoid file-level `@version` tags. Git commits, tags, and `pom.xml` manage release versioning; `@since` documents API introduction without version drift.

- **Public & Protected Methods Documentation**:
  - All public and protected methods across interfaces, ports, domain services, and adapters must be documented with:
    - `@param <name>`: Purpose and constraints of each parameter.
    - `@return`: Description of return value (omitted on `void` and constructors).
    - `@throws <ExceptionClass>`: Conditions under which checked or runtime domain exceptions are thrown.
    - `@see <reference>`: Links to related types or specifications where relevant.
    - `@deprecated`: Explanation of deprecation and replacement reference (paired with `@Deprecated`).

- **Record & Domain Invariants**:
  - Document compact constructor invariant constraints, validation rules, and structural behaviors.

- **Concise & Meaningful**:
  - Avoid empty or tautological comments. Provide real context on intent, behavior, and lifecycle.
