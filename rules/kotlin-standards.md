---
description: "Kotlin coding standards, Spring Boot 4 integration, coroutines, and idiomatic practices for Kotlin projects."
globs:
  - "**/*.kt"
  - "**/*.kts"
---

# Kotlin Coding Standards & Spring Boot 4 Integration

This document establishes coding conventions, architectural guidelines, and idiomatic practices for projects written in Kotlin targeting **Spring Boot 4** and **Java 25**.

> **Notation**: `{base-package}` refers to the project's root package. `{maintainer}` refers to the project's primary author or team identifier.
>
> **Severity Levels**:
> - 🔴 **MUST**: Non-negotiable requirement. Violations break builds, cause runtime bugs, or fail architectural gates.
> - 🟡 **SHOULD**: Strongly recommended best practice. Deviations require documented rationale.
> - 🟢 **MAY**: Optional stylistic guideline or situational preference.

---

## 1. Kotlin & Spring Boot 4 Baseline 🔴 MUST

- 🔴 **MUST**: Target Kotlin **2.0+** with JVM bytecode target set to **Java 25**.
- 🔴 **MUST**: Configure compiler flag `-Xjsr305=strict` to enforce Spring Framework null-safety annotations (`@NonNull`, `@Nullable`) at compile time.
- 🔴 **MUST**: Enable `-Werror` in CI to treat compiler warnings as build-breaking errors.

```kotlin
// ✅ GOOD: build.gradle.kts Kotlin compiler configuration
kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_25)
        freeCompilerArgs.addAll(
            "-Xjsr305=strict",
            "-opt-in=kotlinx.coroutines.ExperimentalCoroutinesApi"
        )
    }
}
```

---

## 2. Immutability & Data Classes 🔴 MUST

Kotlin's `data class` provides structural equality, copying, and `toString()` generation, making it the idiomatic choice for immutable data structures.

- 🔴 **MUST**: Use `data class` with read-only properties (`val`) for Domain Commands, Events, Value Objects, and API DTOs.
- 🔴 **MUST**: Provide default values or constructor validation (`init` block) to protect domain invariants.
- 🔴 **MUST NOT**: Use `data class` for JPA `@Entity` classes. JPA requires a no-arg constructor, mutable state for proxies, and stable identity for `equals()` and `hashCode()` that does not trigger lazy loading. Use standard `open class` or regular class for JPA entities.

```kotlin
// ✅ GOOD: Immutable Domain Value Object using data class
data class TenantId(val value: UUID) {
    init {
        require(value.version() == 7) { "TenantId must be an RFC 9562 UUIDv7" }
    }
}

// ✅ GOOD: API Request DTO
data class CreateUserRequest(
    @field:NotBlank val username: String,
    @field:Email val email: String,
    @field:NotNull val role: UserRole
)

// ❌ BAD: Using data class for JPA Entity (triggers N+1 / lazy load crashes in equals/hashCode)
@Entity
@Table(name = "users")
data class UserEntity(
    @Id val id: UUID,
    var username: String,
    @OneToMany(mappedBy = "user", fetch = FetchType.LAZY)
    val roles: Set<RoleEntity> // will cause stack overflow or LazyInitializationException in toString/equals
)

// ✅ GOOD: JPA Entity as a standard class with explicit ID-based equals/hashCode
@Entity
@Table(name = "users")
class UserEntity(
    @Id
    val id: UUID = UUID.randomUUID(),

    @Column(nullable = false)
    var username: String,

    @OneToMany(mappedBy = "user", fetch = FetchType.LAZY)
    var roles: MutableSet<RoleEntity> = mutableSetOf()
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is UserEntity) return false
        return id == other.id
    }

    override fun hashCode(): Int = id.hashCode()
    override fun toString(): String = "UserEntity(id=$id, username='$username')"
}
```

---

## 3. Null Safety & Java Interop 🔴 MUST

Kotlin's type system distinguishes between nullable (`T?`) and non-nullable (`T`) references at compile time.

- 🔴 **MUST NOT**: Use the `!!` (double-bang) non-null assertion operator in production code. Use `?:`, `checkNotNull()`, or `requireNotNull()` with descriptive error messages instead.
- 🔴 **MUST**: Handle Java platform types (`T!`) explicitly by typing variables as nullable or asserting non-null at the boundary.
- 🟡 **SHOULD**: Use the safe-call operator (`?.`) combined with the Elvis operator (`?:`) for fallbacks.

```kotlin
// ✅ GOOD: Safe call with explicit validation
val tenantId = request.headers["X-Tenant-Id"]?.firstOrNull()
    ?.let { UUID.fromString(it) }
    ?: throw MissingTenantException("Header X-Tenant-Id is required")

// ❌ BAD: Double-bang operator throwing cryptic NullPointerException
val tenantId = UUID.fromString(request.headers["X-Tenant-Id"]!!.first()!!)
```

---

## 4. Coroutines & Reactive Flow with Spring 🔴 MUST

Spring Boot 4 / WebFlux natively supports Kotlin Coroutines and `Flow`.

- 🔴 **MUST**: Use `suspend` functions for asynchronous controller actions and service calls instead of raw Reactor `Mono<T>`.
- 🔴 **MUST**: Return `Flow<T>` instead of `Flux<T>` for streaming endpoints.
- 🔴 **MUST NOT**: Block a coroutine dispatcher thread with blocking I/O (e.g. `Thread.sleep()`, synchronous JDBC). If calling legacy blocking code, explicitly dispatch to `Dispatchers.IO` using `withContext`.
- 🔴 **MUST**: Propagate MDC context (traceId, tenantId) across coroutine suspension points using `MDCContext()`.

```kotlin
// ✅ GOOD: Idiomatic Spring WebFlux controller using coroutines and Flow
@RestController
@RequestMapping("/api/v1/orders")
class OrderController(
    private val orderService: OrderService
) {

    @GetMapping("/{id}")
    suspend fun getOrderById(@PathVariable id: UUID): OrderResponse {
        return orderService.findById(id)
            ?: throw ResourceNotFoundException("Order $id not found")
    }

    @GetMapping(produces = [MediaType.TEXT_EVENT_STREAM_VALUE])
    fun streamActiveOrders(): Flow<OrderResponse> {
        return orderService.streamOrders()
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    suspend fun createOrder(
        @Valid @RequestBody request: CreateOrderRequest
    ): OrderResponse {
        // MDC context preserved across suspend calls with MDCContext
        return withContext(Dispatchers.Default + MDCContext()) {
            orderService.createOrder(request)
        }
    }
}
```

```kotlin
// ❌ BAD: Blocking coroutine thread with Thread.sleep or synchronous database calls
suspend fun fetchExternalData(): String {
    Thread.sleep(5000) // blocks the underlying coroutine worker thread!
    return "result"
}

// ✅ GOOD: Non-blocking delay or offloading to Dispatchers.IO
suspend fun fetchExternalData(): String {
    delay(5000) // non-blocking delay
    return "result"
}
```

---

## 5. Domain Modeling with Sealed Interfaces 🟡 SHOULD

- 🟡 **SHOULD**: Use `sealed interface` or `sealed class` to represent closed type hierarchies (Algebraic Data Types / Sum Types) such as domain events, operation results, and business states.
- 🔴 **MUST**: Handle sealed hierarchies using exhaustive `when` expressions **without an `else` branch**. This forces the compiler to warn when a new subtype is added.

```kotlin
// ✅ GOOD: Sealed interface modeling business operation outcome
sealed interface PaymentResult {
    data class Success(val transactionId: String, val amount: BigDecimal) : PaymentResult
    data class Declined(val reason: String, val retryable: Boolean) : PaymentResult
    data class Error(val cause: Throwable) : PaymentResult
}

// ✅ GOOD: Exhaustive when expression — compiler breaks if a new outcome is added
fun handlePayment(result: PaymentResult): ResponseEntity<Any> = when (result) {
    is PaymentResult.Success -> ResponseEntity.ok(result)
    is PaymentResult.Declined -> ResponseEntity.status(HttpStatus.PAYMENT_REQUIRED).body(result)
    is PaymentResult.Error -> ResponseEntity.internalServerError().body(ProblemDetail.forStatus(500))
    // Note: NO "else" branch — allows compiler exhaustiveness checking!
}
```

---

## 6. Extension Functions & Scope Functions 🟡 SHOULD

### Extension Functions

- 🟡 **SHOULD**: Use extension functions to add utility methods or domain-specific conversions without polluting the original class definition.
- 🔴 **MUST**: Keep extension functions scoped to the package or module where they are needed. Avoid declaring global extensions on generic types like `Any`, `String?`, or `List<T>`.
- 🔴 **MUST**: Ensure extension functions are pure and side-effect-free.

```kotlin
// ✅ GOOD: Focused mapper extension function in the adapter layer
fun UserEntity.toDomain(): User = User(
    id = this.id,
    username = this.username,
    email = this.email
)

// ❌ BAD: Overly broad extension polluting the global String namespace
fun String.makeImportant(): String = "*** $this ***"
```

### Scope Functions (`let`, `apply`, `also`, `run`)

- 🟡 **SHOULD**: Follow standard Kotlin scoping semantics:
  - `apply`: Object configuration (returns the receiver `this`).
  - `let`: Null-checking or transforming an expression (returns the lambda result).
  - `also`: Additional side effects such as logging or validation without modifying the object (returns the receiver `this`).
  - `run`: Computing a result with a scoped receiver.
- 🔴 **MUST NOT**: Nest scope functions deeply or chain more than 2-3 scope functions together. It destroys readability and creates variable shadowing (`it`).

```kotlin
// ✅ GOOD: Clear, readable usage of scope functions
val client = HttpClient().apply {
    connectTimeout = Duration.ofSeconds(5)
    readTimeout = Duration.ofSeconds(10)
}

val formattedEmail = user.email
    ?.trim()
    ?.lowercase()
    ?.let { Email(it) }

// ❌ BAD: Convoluted nested scope functions with confusing context
user.let { u ->
    u.address?.let { a ->
        a.city.run {
            toUpperCase().also { println(it) }
        }
    }
}
```

---

## 7. Idiomatic Clean Code Practices 🔴 MUST

- 🔴 **MUST**: Prefer `val` (read-only) over `var` (mutable). Treat `var` as a code smell; restrict its usage to local loops or performance-critical algorithms.
- 🔴 **MUST**: Use constructor injection with `val` parameters in Spring components. Never use field injection (`@Autowired lateinit var`).
- 🟡 **SHOULD**: Use expression body syntax for single-line functions where the return type is obvious.
- 🔴 **MUST**: Include `@author {maintainer}` and `@since <version>` in class-level KDoc metadata, matching current project conventions.

```kotlin
// ✅ GOOD: Clean, idiomatic Spring Service
/**
 * Application service managing user authentication and profile retrieval.
 *
 * @author {maintainer}
 * @since 1.0.0
 */
@Service
class DefaultAuthenticationService(
    private val userRepository: UserRepository,
    private val tokenProvider: JwtTokenProvider
) : AuthenticateUserUseCase {

    override suspend fun authenticate(command: LoginCommand): TokenResponse {
        val user = userRepository.findByEmail(command.email)
            ?: throw InvalidCredentialsException("Invalid email or password")

        val token = tokenProvider.generateToken(user)
        return TokenResponse(accessToken = token, expiresIn = 3600)
    }
}
```
