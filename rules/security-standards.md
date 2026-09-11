---
description: "Security standards covering input validation, Spring Security, CORS, and OWASP best practices."
globs:
  - "**/*.java"
  - "**/*.kt"
  - "**/application*.yml"
  - "**/application*.yaml"
---

# Security Standards

This document establishes security standards for Java 25 / Spring Boot 4 services, covering authentication/authorization patterns, input validation, CORS, and OWASP Top 10 mitigations.

> **Severity Levels**:
> - 🔴 **MUST**: Non-negotiable requirement. Violations will fail CI checks or block code review approval.
> - 🟡 **SHOULD**: Strongly recommended practice. Deviations require team consensus and documented rationale.
> - 🟢 **MAY**: Optional guideline or contextual optimization.

---

## 1. Authentication & Authorization Patterns 🔴 MUST

### 1.1 Security Filter Chain
- **Stateless sessions**: REST APIs MUST use stateless session management (`SessionCreationPolicy.STATELESS`). Never rely on server-side HTTP sessions for API authentication.
- **JWT-based authentication**: Use JWT tokens validated via a custom `OncePerRequestFilter` (e.g. `JwtAuthenticationFilter`).
- **Secure defaults**: Deny all requests by default. Explicitly permit only the required endpoints.

```java
// ✅ GOOD: Deny-by-default security configuration
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    return http
        .csrf(csrf -> csrf.disable()) // Stateless API — CSRF not applicable
        .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/api/v1/auth/login", "/api/v1/auth/refresh").permitAll()
            .requestMatchers("/actuator/health/**").permitAll()
            .anyRequest().authenticated()
        )
        .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)
        .build();
}

// ❌ BAD: Permit-all by default
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    return http
        .authorizeHttpRequests(auth -> auth.anyRequest().permitAll()) // VIOLATION — no security
        .build();
}
```

### 1.2 Authorization Levels
Apply authorization checks at multiple levels for defense in depth:

| Level | Mechanism | Purpose |
|---|---|---|
| **Transport** | `SecurityFilterChain` URL matchers | Coarse-grained endpoint access |
| **Method** | `@PreAuthorize` / `@Secured` | Fine-grained method-level authorization |
| **Domain** | `CurrentActor.canAccessScope()` | Business-rule-level access control |
| **Data** | Tenant-scoped queries | Row-level data isolation |

```java
// ✅ GOOD: Multi-level authorization
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {
    // Level 1: URL matcher in SecurityFilterChain → requires authentication
    // Level 2: Method-level role check
    @PreAuthorize("hasRole('ORDER_MANAGER')")
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID id) {
        // Level 3: Domain-level scope check inside use case
        // Level 4: Repository filters by tenantId
        deleteOrderUseCase.execute(id);
    }
}
```

---

## 2. Input Validation & Sanitization 🔴 MUST

### 2.1 Validation Layers
Input validation must happen at **two distinct layers**:

| Layer | What to Validate | How |
|---|---|---|
| **Controller/DTO** | Structural validity: required fields, format, length, range | Jakarta Bean Validation (`@Valid`, `@NotNull`, `@Size`, `@Pattern`) |
| **Domain** | Business invariants: uniqueness, referential integrity, business rules | Compact constructor checks, domain service validation |

### 2.2 Never Trust Client Input
- **Validate all inputs**: Every external input (request body, path variables, query parameters, headers) MUST be validated.
- **Parameterized queries**: ALWAYS use parameterized queries or Spring Data JPA methods. Never concatenate user input into SQL/JPQL strings.
- **Type-safe IDs**: Use typed value objects (e.g. `OrderId`, `UserId`) instead of raw `UUID` or `String` in domain logic to prevent ID confusion.

```java
// ❌ BAD: Concatenating user input into JPQL
@Query("SELECT u FROM UserJpaEntity u WHERE u.username = '" + username + "'")  // SQL INJECTION
List<UserJpaEntity> findByUsername(String username);

// ✅ GOOD: Parameterized query
@Query("SELECT u FROM UserJpaEntity u WHERE u.username = :username")
List<UserJpaEntity> findByUsername(@Param("username") String username);

// ✅ GOOD: Spring Data derived query (inherently parameterized)
List<UserJpaEntity> findByUsernameAndTenantId(String username, UUID tenantId);
```

### 2.3 Path Traversal & File Handling
- **Never use user input directly in file paths** without validation and sanitization.
- **Whitelist allowed file extensions** for upload endpoints.
- **Use `Path.normalize()`** and verify the resolved path stays within the expected directory.

---

## 3. CORS Configuration 🔴 MUST

### 3.1 Rules
- **No wildcards in production**: Never use `allowedOrigins("*")` in production. Explicitly list allowed origins.
- **Restrict methods**: Only allow the HTTP methods your API actually supports.
- **Restrict headers**: Only allow headers your API actually reads.
- **Credentials**: Set `allowCredentials(true)` only when cookies or Authorization headers must be sent cross-origin.

```java
// ✅ GOOD: Restrictive CORS configuration
@Bean
public CorsConfigurationSource corsConfigurationSource() {
    var config = new CorsConfiguration();
    config.setAllowedOrigins(List.of(
        "https://app.example.com",
        "https://admin.example.com"
    ));
    config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE"));
    config.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-Request-Id"));
    config.setAllowCredentials(true);
    config.setMaxAge(3600L);

    var source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/api/**", config);
    return source;
}

// ❌ BAD: Wide-open CORS
@Bean
public CorsConfigurationSource corsConfigurationSource() {
    var config = new CorsConfiguration();
    config.setAllowedOrigins(List.of("*"));            // VIOLATION — allows any origin
    config.setAllowedMethods(List.of("*"));            // VIOLATION — allows any method
    config.setAllowedHeaders(List.of("*"));            // VIOLATION — allows any header
    var source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/**", config);   // VIOLATION — applies to all paths
    return source;
}
```

---

## 4. Secrets Management 🔴 MUST

### 4.1 Rules
- **Never commit secrets**: Passwords, API keys, JWT signing keys, and database credentials MUST NEVER be committed to source control.
- **Environment variables or vault**: Inject secrets via environment variables, Kubernetes secrets, or a secrets manager (e.g. HashiCorp Vault, AWS Secrets Manager).
- **Spring externalized config**: Use `${ENV_VAR}` placeholders in `application.yml` for secret values.
- **`.gitignore`**: Ensure `application-local.yml`, `.env`, and any file containing secrets is in `.gitignore`.

```yaml
# ✅ GOOD: Secrets injected via environment variables
spring:
  datasource:
    url: ${DATABASE_URL}
    username: ${DATABASE_USERNAME}
    password: ${DATABASE_PASSWORD}
  
app:
  jwt:
    signing-key: ${JWT_SIGNING_KEY}
```

```yaml
# ❌ BAD: Hardcoded secrets in application.yml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/mydb
    username: admin
    password: super-secret-password    # VIOLATION — hardcoded secret
```

### 4.2 Secret Rotation
- Design systems to support secret rotation without downtime (e.g. accept multiple valid JWT signing keys during rotation period).
- Log secret rotation events at `INFO` level (log the *event*, never the *secret*).

---

## 5. Rate Limiting 🟡 SHOULD

### 5.1 Rules
- **Authentication endpoints**: Login, registration, and password reset endpoints MUST be rate-limited to prevent brute-force attacks.
- **API endpoints**: Apply rate limiting on a per-tenant or per-client basis to prevent abuse.
- **429 Too Many Requests**: Rate-limited responses MUST return HTTP `429` with a `Retry-After` header indicating when the client can retry.

```java
// ✅ GOOD: Rate limit response with Retry-After header
@ExceptionHandler(RateLimitExceededException.class)
public ResponseEntity<ProblemDetail> handleRateLimit(RateLimitExceededException ex) {
    ProblemDetail problem = ProblemDetail.forStatusAndDetail(
        HttpStatus.TOO_MANY_REQUESTS,
        "Rate limit exceeded. Please retry after the specified time."
    );
    problem.setTitle("Too Many Requests");
    return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
        .header("Retry-After", String.valueOf(ex.getRetryAfterSeconds()))
        .body(problem);
}
```

---

## 6. OWASP Top 10 Considerations 🔴 MUST

### 6.1 Checklist

| OWASP Risk | Mitigation in This Stack |
|---|---|
| **A01: Broken Access Control** | Multi-level authorization (§1.2), tenant-scoped queries, `CurrentActor` scope checks |
| **A02: Cryptographic Failures** | BCrypt for passwords, HMAC-SHA256+ for JWTs, TLS for transport, no secrets in logs |
| **A03: Injection** | Parameterized queries (§2.2), Bean Validation, no string concatenation in SQL |
| **A04: Insecure Design** | Hexagonal architecture, domain invariants in compact constructors, fail-fast guards |
| **A05: Security Misconfiguration** | Deny-by-default filter chain (§1.1), restrictive CORS (§3), no stack traces in responses |
| **A06: Vulnerable Components** | Dependency scanning (Dependabot/Snyk), regular updates, BOM version management |
| **A07: Auth Failures** | Stateless JWT, rate limiting on login (§5), fail-fast `requireCurrentActor()` |
| **A08: Data Integrity Failures** | Signed JWTs, optimistic locking, append-only audit trail |
| **A09: Logging & Monitoring** | Structured logging, MDC correlation, sensitive data redaction (see `logging-and-observability.md`) |
| **A10: SSRF** | Validate and whitelist outbound URLs, never forward user-supplied URLs to backend services without validation |

### 6.2 Response Headers
Configure Spring Security to include protective response headers:

```java
// ✅ GOOD: Security response headers (most are Spring Boot defaults)
http.headers(headers -> headers
    .contentTypeOptions(Customizer.withDefaults())          // X-Content-Type-Options: nosniff
    .frameOptions(frame -> frame.deny())                     // X-Frame-Options: DENY
    .httpStrictTransportSecurity(hsts -> hsts               // Strict-Transport-Security
        .includeSubDomains(true)
        .maxAgeInSeconds(31536000))
    .cacheControl(Customizer.withDefaults())                 // Cache-Control: no-cache, no-store
);
```

---

## 7. Dependency Vulnerability Management 🔴 MUST

- **Automated scanning**: Enable Dependabot (GitHub) or Snyk for continuous dependency vulnerability detection.
- **Spring Boot BOM**: Always inherit dependency versions from the Spring Boot BOM to get coordinated security patches.
- **Update cadence**: Review and apply dependency security updates at least monthly. Critical vulnerabilities must be patched within 48 hours.
- **Suppression documentation**: If a vulnerability is suppressed (false positive or mitigated), document the justification in a `dependency-suppressions.xml` or equivalent file.
