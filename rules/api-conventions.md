---
description: "RESTful API design conventions, error handling, pagination, and request validation standards."
globs:
  - "**/*.java"
  - "**/*.kt"
  - "**/application*.yml"
  - "**/application*.yaml"
---

# API Conventions & Error Handling Standards

This document establishes RESTful API design conventions, error response formats, pagination, and request validation standards for Java 25 / Spring Boot 4 services.

---

## 1. RESTful Resource Naming

- **Plural Nouns**: Use plural nouns for resource collections (e.g. `/orders`, `/users`, `/user-profiles`).
- **Kebab-Case**: Use lowercase kebab-case for multi-word resource names (e.g. `/user-profiles`, NOT `/userProfiles` or `/user_profiles`).
- **URI Path Versioning**: All API endpoints MUST be prefixed with `/api/v{N}/` (e.g. `/api/v1/orders`).
- **No Verbs in URIs**: Use HTTP methods to express actions, not URL segments.

```
✅ GOOD:
GET    /api/v1/orders
GET    /api/v1/orders/{id}
POST   /api/v1/orders
PUT    /api/v1/orders/{id}
PATCH  /api/v1/orders/{id}
DELETE /api/v1/orders/{id}
GET    /api/v1/orders/{id}/line-items

❌ BAD:
GET    /api/v1/getOrders          ← verb in URI
POST   /api/v1/createOrder        ← verb in URI
GET    /api/v1/order              ← singular resource name
GET    /api/v1/userProfiles       ← camelCase
GET    /orders                    ← missing version prefix
```

---

## 2. HTTP Method Semantics

Use HTTP methods strictly according to their defined semantics:

| Method | Semantics | Idempotent | Request Body | Success Status |
|---|---|---|---|---|
| `GET` | Retrieve resource(s). MUST be side-effect free. | ✅ Yes | None | `200 OK` |
| `POST` | Create a new resource or trigger an action. | ❌ No | Required | `201 Created` |
| `PUT` | Full replacement of an existing resource. | ✅ Yes | Required | `200 OK` |
| `PATCH` | Partial update of an existing resource. | ❌ No | Required | `200 OK` |
| `DELETE` | Remove a resource. | ✅ Yes | None | `204 No Content` |

```java
// ✅ GOOD: Correct method-to-action mapping
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {
    private final PlaceOrderUseCase placeOrder;
    private final GetOrderUseCase getOrder;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public OrderSummary create(@Valid @RequestBody CreateOrderRequest request) {
        return placeOrder.execute(request.toCommand());
    }

    @GetMapping("/{id}")
    public OrderSummary getById(@PathVariable UUID id) {
        return getOrder.getById(id);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID id) {
        deleteOrder.execute(id);
    }
}
```

---

## 3. HTTP Status Code Standards

### Success Codes

| Code | When to Use |
|---|---|
| `200 OK` | Successful GET, PUT, or PATCH returning a response body. |
| `201 Created` | Successful POST that created a new resource. Include `Location` header. |
| `204 No Content` | Successful DELETE or action that returns no body. |

### Client Error Codes

| Code | When to Use |
|---|---|
| `400 Bad Request` | Malformed request syntax, invalid JSON, or type mismatch. |
| `401 Unauthorized` | Request lacks valid authentication credentials. |
| `403 Forbidden` | Authenticated but lacks permission for the requested action. |
| `404 Not Found` | Resource does not exist (or caller lacks visibility). |
| `409 Conflict` | Request conflicts with current resource state (e.g. duplicate creation, concurrent modification). |
| `422 Unprocessable Entity` | Request is syntactically valid but fails domain/business validation (e.g. invalid field values, business rule violations). |

### Server Error Codes

| Code | When to Use |
|---|---|
| `500 Internal Server Error` | Unhandled server-side failure. **Never expose stack traces or internal details.** |
| `502 Bad Gateway` | Upstream service returned an invalid response. |
| `503 Service Unavailable` | Service is temporarily overloaded or under maintenance. |

> **`400` vs `422` Decision Rule**: Use `400` when the request cannot be parsed or is structurally invalid. Use `422` when the request is well-formed but violates business/domain rules.

---

## 4. Error Response Format — RFC 9457 Problem Details

All error responses MUST follow the [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457) format. Spring Boot 4 supports this natively via `ProblemDetail`.

### Standard Error Response

```json
{
  "type": "https://api.example.com/problems/order-not-found",
  "title": "Order Not Found",
  "status": 404,
  "detail": "No order found with ID '550e8400-e29b-41d4-a716-446655440000' for the current tenant.",
  "instance": "/api/v1/orders/550e8400-e29b-41d4-a716-446655440000"
}
```

### Validation Error Response (with field-level errors)

For `422 Unprocessable Entity` responses, include an `errors` extension array with field-level details:

```json
{
  "type": "https://api.example.com/problems/validation-error",
  "title": "Validation Failed",
  "status": 422,
  "detail": "Request contains 2 validation errors.",
  "instance": "/api/v1/orders",
  "errors": [
    {
      "field": "quantity",
      "message": "must be greater than 0",
      "rejectedValue": -1
    },
    {
      "field": "shippingAddress.zipCode",
      "message": "must not be blank",
      "rejectedValue": null
    }
  ]
}
```

### Centralized Exception Handler

```java
// ✅ GOOD: Centralized exception handler producing RFC 9457 responses
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(EntityNotFoundException.class)
    public ProblemDetail handleNotFound(EntityNotFoundException ex, HttpServletRequest request) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
        problem.setTitle("Resource Not Found");
        problem.setType(URI.create("https://api.example.com/problems/not-found"));
        problem.setInstance(URI.create(request.getRequestURI()));
        return problem;
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ProblemDetail handleForbidden(AccessDeniedException ex, HttpServletRequest request) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.FORBIDDEN, ex.getMessage());
        problem.setTitle("Access Denied");
        problem.setType(URI.create("https://api.example.com/problems/access-denied"));
        problem.setInstance(URI.create(request.getRequestURI()));
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail handleValidation(MethodArgumentNotValidException ex, HttpServletRequest request) {
        List<Map<String, Object>> fieldErrors = ex.getBindingResult().getFieldErrors().stream()
            .map(fe -> Map.<String, Object>of(
                "field", fe.getField(),
                "message", fe.getDefaultMessage(),
                "rejectedValue", fe.getRejectedValue() != null ? fe.getRejectedValue() : "null"
            ))
            .toList();

        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
            HttpStatus.UNPROCESSABLE_ENTITY,
            "Request contains %d validation errors.".formatted(fieldErrors.size())
        );
        problem.setTitle("Validation Failed");
        problem.setType(URI.create("https://api.example.com/problems/validation-error"));
        problem.setInstance(URI.create(request.getRequestURI()));
        problem.setProperty("errors", fieldErrors);
        return problem;
    }
}

// ❌ BAD: Inconsistent ad-hoc error responses
@GetMapping("/{id}")
public ResponseEntity<?> getOrder(@PathVariable UUID id) {
    var order = orderRepository.findById(id);
    if (order == null) {
        return ResponseEntity.status(404).body(Map.of("error", "not found")); // VIOLATION
    }
    return ResponseEntity.ok(order);
}
```

---

## 5. Success Response Conventions

### Single Resource

Return the resource directly as the response body. Do NOT wrap in an envelope.

```java
// ✅ GOOD: Direct resource response
@GetMapping("/{id}")
public OrderSummary getById(@PathVariable UUID id) {
    return getOrderUseCase.getById(id);
}
// Response: { "id": "...", "status": "PLACED", "total": 99.99 }

// ❌ BAD: Unnecessary wrapper
@GetMapping("/{id}")
public Map<String, Object> getById(@PathVariable UUID id) {
    return Map.of("success", true, "data", getOrderUseCase.getById(id)); // VIOLATION
}
```

### Collections (Paginated)

Return a page wrapper with pagination metadata. Use Spring's `Page<T>` or a custom page record.

```java
// ✅ GOOD: Paginated response
@GetMapping
public Page<OrderSummary> list(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size) {
    return listOrdersUseCase.list(PageRequest.of(page, size));
}
```

Response shape:
```json
{
  "content": [ { "id": "...", "status": "PLACED" }, ... ],
  "page": {
    "size": 20,
    "number": 0,
    "totalElements": 142,
    "totalPages": 8
  }
}
```

---

## 6. Pagination Standards

- **Default Strategy**: Offset-based pagination using `page` (zero-indexed) and `size` parameters.
- **Default Page Size**: `20`. Maximum page size: `100`. Requests exceeding the max MUST be clamped, not rejected.
- **Cursor-Based Alternative**: For large datasets or real-time feeds, use cursor-based pagination with an opaque `cursor` token and `limit` parameter.
- **Always Include Metadata**: Every paginated response MUST include `totalElements`, `totalPages`, `size`, and current `number` (page index).

```java
// ✅ GOOD: Page size clamping
@GetMapping
public Page<OrderSummary> list(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size) {
    int clampedSize = Math.min(size, 100); // Clamp to max
    return listOrdersUseCase.list(PageRequest.of(page, clampedSize));
}
```

---

## 7. Request Validation

- **Bean Validation**: Use Jakarta Bean Validation (`@Valid`, `@NotNull`, `@NotBlank`, `@Size`, `@Min`, `@Max`, `@Pattern`) on controller `@RequestBody` parameters.
- **Validated Groups**: Use validation groups for context-specific rules (e.g. `OnCreate` vs `OnUpdate`).
- **Custom Validators**: Implement `ConstraintValidator` for domain-specific validation rules that cannot be expressed via standard annotations.
- **Validation Location**: Structural validation (format, required fields) belongs in the controller/DTO layer via Bean Validation. Domain invariant validation belongs in domain record compact constructors.

```java
// ✅ GOOD: Request DTO with Bean Validation
public record CreateOrderRequest(
    @NotNull(message = "Product ID is required")
    UUID productId,

    @Min(value = 1, message = "Quantity must be at least 1")
    int quantity,

    @NotBlank(message = "Shipping address is required")
    @Size(max = 500, message = "Shipping address must not exceed 500 characters")
    String shippingAddress
) {
    /**
     * Maps this validated request to a domain command.
     */
    public CreateOrderCommand toCommand() {
        return new CreateOrderCommand(productId, quantity, shippingAddress);
    }
}

// ✅ GOOD: Controller applying validation
@PostMapping
@ResponseStatus(HttpStatus.CREATED)
public OrderSummary create(@Valid @RequestBody CreateOrderRequest request) {
    return placeOrderUseCase.execute(request.toCommand());
}

// ❌ BAD: Manual validation in controller
@PostMapping
public OrderSummary create(@RequestBody CreateOrderRequest request) {
    if (request.productId() == null) {
        throw new IllegalArgumentException("Product ID is required"); // VIOLATION — use @Valid
    }
    if (request.quantity() < 1) {
        throw new IllegalArgumentException("Quantity must be at least 1"); // VIOLATION — use @Min
    }
    return placeOrderUseCase.execute(request.toCommand());
}
```

---

## 8. Content Negotiation & Headers

- **Default Content Type**: `application/json` for both request and response bodies.
- **`Content-Type` Header**: All POST/PUT/PATCH requests MUST set `Content-Type: application/json`.
- **`Accept` Header**: Clients SHOULD set `Accept: application/json`. Services MUST respond with JSON by default.
- **Error Content Type**: Error responses (RFC 9457) use `application/problem+json`.
- **`Location` Header**: `201 Created` responses MUST include a `Location` header pointing to the newly created resource.

```java
// ✅ GOOD: Location header on resource creation
@PostMapping
public ResponseEntity<OrderSummary> create(@Valid @RequestBody CreateOrderRequest request) {
    OrderSummary created = placeOrderUseCase.execute(request.toCommand());
    URI location = URI.create("/api/v1/orders/" + created.id());
    return ResponseEntity.created(location).body(created);
}
```

---

## 9. API Versioning Strategy

- **URI Path Versioning** (default): `/api/v1/`, `/api/v2/`. Simple, explicit, and easily routable.
- **Version Lifecycle**:
  1. New versions are introduced when breaking changes are unavoidable.
  2. Previous versions are marked `@Deprecated` with a sunset date communicated via API documentation and response headers (`Sunset`, `Deprecation`).
  3. Deprecated versions run in parallel for a defined migration period before removal.
- **Non-Breaking Changes** (do NOT require a new version):
  - Adding new optional fields to responses.
  - Adding new endpoints.
  - Adding new optional query parameters.
- **Breaking Changes** (require a new version):
  - Removing or renaming fields in responses.
  - Changing field types.
  - Removing endpoints.
  - Changing authentication/authorization requirements.
