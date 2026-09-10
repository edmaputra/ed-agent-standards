---
description: "Logging, observability, and monitoring standards for production-grade Java services."
globs:
  - "**/*.java"
  - "**/*.kt"
  - "**/application*.yml"
  - "**/application*.yaml"
  - "**/logback*.xml"
---

# Logging & Observability Standards

This document establishes logging, tracing, metrics, and health-check standards for Java 25 / Spring Boot 4 services.

---

## 1. Logger Declaration

- **Use SLF4J**: All logging MUST go through the SLF4J API (`org.slf4j.Logger`).
- **Allowed Declarations**:
  - Explicit factory: `private static final Logger log = LoggerFactory.getLogger(MyClass.class);`
  - Lombok shortcut: `@Slf4j` on the class.
- **Strictly Prohibited**:
  - `System.out.println()` / `System.err.println()` — not structured, not filterable.
  - `e.printStackTrace()` — writes to stderr, bypasses log framework.
  - Direct use of `java.util.logging` or Log4j2 API — use SLF4J facade only.

```java
// ✅ GOOD: SLF4J logger
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class OrderProcessingService {
    private static final Logger log = LoggerFactory.getLogger(OrderProcessingService.class);
}

// ✅ GOOD: Lombok shortcut
@Slf4j
public class OrderProcessingService { ... }

// ❌ BAD: System.out and printStackTrace
public class OrderProcessingService {
    public void process(Order order) {
        System.out.println("Processing order: " + order.id()); // VIOLATION
        try { ... } catch (Exception e) {
            e.printStackTrace(); // VIOLATION
        }
    }
}
```

---

## 2. Log Level Conventions

Use log levels consistently across all services. Misuse of levels makes alerting and log filtering unreliable.

| Level | When to Use | Examples |
|---|---|---|
| `ERROR` | System is broken, requires immediate attention. Triggers alerts. | Unhandled exceptions, failed database connections, integration failures with no fallback |
| `WARN` | Unexpected but recoverable. Warrants investigation but not an emergency. | Retry attempts, deprecated API usage, fallback logic triggered, approaching resource limits |
| `INFO` | Business-significant events. Tells the "story" of what the system is doing. | User authenticated, order placed, payment processed, deployment started, application startup/shutdown |
| `DEBUG` | Diagnostic detail for troubleshooting. Disabled in production by default. | Method entry/exit with parameters, intermediate computation state, cache hit/miss |
| `TRACE` | Ultra-verbose detail. Rarely enabled outside of active debugging sessions. | Full request/response payloads, loop iterations, detailed algorithm steps |

```java
// ✅ GOOD: Correct level usage
log.info("Order placed successfully. orderId={}, tenantId={}", order.id(), order.tenantId());
log.warn("Payment gateway timeout, retrying. orderId={}, attempt={}", orderId, attemptCount);
log.error("Failed to persist order after all retries. orderId={}", orderId, exception);
log.debug("Resolving effective access for actor. actorId={}, scopeId={}", actorId, scopeId);

// ❌ BAD: Misused log levels
log.error("User not found");            // Not a system error — use WARN or throw domain exception
log.info("Entering method process()");   // Diagnostic noise — use DEBUG
log.debug("Order placed: {}", orderId);  // Business event — use INFO
```

---

## 3. Structured Logging

- **Production Format**: JSON structured output (via Logback `JsonLayout` or `logstash-logback-encoder`) for machine parsing by log aggregation systems (ELK, Loki, Datadog, etc.).
- **Development Format**: Human-readable pattern layout for local development.
- **Key-Value Parameters**: Use SLF4J parameterized messages (`{}` placeholders) — never string concatenation.
- **MDC (Mapped Diagnostic Context)**: Enrich all log lines with contextual identifiers set at the request boundary.

### Required MDC Fields

| MDC Key | Source | Purpose |
|---|---|---|
| `traceId` | Micrometer Tracing / OpenTelemetry (auto-populated) | Distributed trace correlation |
| `spanId` | Micrometer Tracing / OpenTelemetry (auto-populated) | Span-level correlation |
| `tenantId` | `JwtAuthenticationFilter` or `TenantContextBridge` | Tenant isolation in logs |
| `actorId` | `CurrentActor` from security context | Identify who performed the action |
| `requestId` | Generated per incoming HTTP request (e.g. `X-Request-Id` header) | Request-level grouping |

```java
// ✅ GOOD: MDC enrichment at request boundary (e.g. in a filter)
MDC.put("tenantId", tenantId.toString());
MDC.put("actorId", actor.id().toString());
try {
    filterChain.doFilter(request, response);
} finally {
    MDC.clear(); // Always clear to prevent context leaks in pooled threads
}

// ✅ GOOD: Parameterized logging (SLF4J auto-includes MDC fields in structured output)
log.info("Order created. orderId={}, total={}", order.id(), order.total());

// ❌ BAD: String concatenation in log messages
log.info("Order created. orderId=" + order.id() + ", total=" + order.total()); // VIOLATION
```

---

## 4. Sensitive Data Prohibition

Passwords, tokens, PII, and secrets must **NEVER** appear in logs. This rule has no exceptions.

| Category | Examples | Log Instead |
|---|---|---|
| Credentials | Passwords, API keys, client secrets | `"authMethod=LOCAL"`, `"apiKeyPrefix=sk-...ab3"` |
| Tokens | JWT access/refresh tokens, session IDs | `"tokenType=ACCESS"`, `"jti=<uuid>"` |
| PII | Email addresses, phone numbers, SSNs | `"userId=<uuid>"`, `"userRef=USR-12345"` |
| Financial | Credit card numbers, bank accounts | `"last4=1234"`, `"paymentMethodId=<uuid>"` |

```java
// ❌ BAD: Logging sensitive data
log.info("User login. username={}, password={}", username, password);       // VIOLATION
log.debug("Token issued: {}", jwtToken);                                    // VIOLATION
log.info("Processing payment for card: {}", creditCardNumber);              // VIOLATION

// ✅ GOOD: Log identifiers only
log.info("User login successful. username={}, authMethod={}", username, "LOCAL");
log.debug("Token issued. jti={}, expiresIn={}s", tokenId, expiresInSeconds);
log.info("Processing payment. paymentMethodId={}, last4={}", paymentMethodId, last4);
```

---

## 5. Correlation & Distributed Tracing

- **Micrometer Tracing with OpenTelemetry**: Use Spring Boot 4's auto-configured Micrometer Tracing with OpenTelemetry bridge for automatic `traceId`/`spanId` propagation.
- **W3C Trace Context**: Use W3C `traceparent` header propagation (Spring Boot 4 default) for inter-service calls.
- **Custom Spans**: Create meaningful spans around significant operations (external API calls, database-heavy operations, message processing).

```java
// ✅ GOOD: Custom observation for significant operation
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;

public class PaymentGatewayAdapter implements PaymentGateway {
    private final PaymentClient client;
    private final ObservationRegistry observationRegistry;

    @Override
    public PaymentResult charge(PaymentRequest request) {
        return Observation.createNotStarted("payment.charge", observationRegistry)
            .lowCardinalityKeyValue("payment.method", request.method().name())
            .observe(() -> client.charge(request));
    }
}
```

---

## 6. Metrics Naming Conventions

- **Framework**: Micrometer (auto-configured by Spring Boot 4 Actuator).
- **Naming**: Lowercase, dot-separated, following Micrometer conventions.
  - Format: `{domain}.{entity}.{action}` or `{domain}.{operation}.{metric}`
  - Examples: `orders.created.count`, `payment.charge.duration`, `auth.login.failures`
- **Tag/Label Cardinality**: Keep tag values low-cardinality. Never use user IDs, order IDs, or other high-cardinality identifiers as metric tags.
- **Standard Spring Boot Metrics**: Always expose the default Spring Boot Actuator metrics (`http.server.requests`, `jvm.*`, `system.*`, `db.*`).

```java
// ✅ GOOD: Custom counter with low-cardinality tags
meterRegistry.counter("orders.created.count",
    "channel", order.channel().name(),
    "region", order.region().name()
).increment();

// ❌ BAD: High-cardinality tag
meterRegistry.counter("orders.created.count",
    "orderId", order.id().toString()  // VIOLATION — unique per order, causes metric explosion
).increment();
```

---

## 7. Health & Readiness Endpoints

- **Spring Boot Actuator**: Always include `spring-boot-starter-actuator` dependency.
- **Required Endpoints** (exposed for orchestration/monitoring):
  - `/actuator/health` — overall health (liveness)
  - `/actuator/health/readiness` — readiness probe (Kubernetes `readinessProbe`)
  - `/actuator/health/liveness` — liveness probe (Kubernetes `livenessProbe`)
  - `/actuator/info` — application metadata
  - `/actuator/prometheus` or `/actuator/metrics` — metrics export
- **Custom Health Indicators**: Implement `HealthIndicator` for critical external dependencies (database, message broker, external APIs).

```java
// ✅ GOOD: Custom health indicator for critical dependency
@Component
public class PaymentGatewayHealthIndicator implements HealthIndicator {
    private final PaymentClient paymentClient;

    @Override
    public Health health() {
        try {
            paymentClient.ping();
            return Health.up().withDetail("gateway", "reachable").build();
        } catch (Exception e) {
            return Health.down(e).withDetail("gateway", "unreachable").build();
        }
    }
}
```

---

## 8. Performance Logging Guidelines

- **Never Log in Hot Loops**: Avoid logging inside tight loops or high-frequency methods. Use counters/metrics instead.
- **Log External Call Latency**: Log duration of external service calls, database queries over a threshold, and message processing times at `INFO` or `DEBUG` level.
- **Lazy Evaluation**: Use SLF4J `{}` placeholders or `Supplier`-based logging for expensive `toString()` calls.

```java
// ✅ GOOD: Log external call duration
long start = System.nanoTime();
var result = paymentGateway.charge(request);
long durationMs = (System.nanoTime() - start) / 1_000_000;
log.info("Payment gateway call completed. durationMs={}, status={}", durationMs, result.status());

// ❌ BAD: Logging inside a hot loop
for (var item : items) {
    log.debug("Processing item: {}", item); // VIOLATION — may produce millions of log lines
    process(item);
}

// ✅ GOOD: Log summary after loop
log.debug("Processed {} items for orderId={}", items.size(), orderId);
```
