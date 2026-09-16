---
description: "Flutter and Dart coding standards, widget architecture, state management, navigation, and testing conventions."
globs:
  - "**/*.dart"
  - "**/pubspec.yaml"
  - "**/analysis_options.yaml"
---

# Flutter & Dart Coding Standards

This document establishes coding conventions, architectural guidelines, and idiomatic practices for projects written in **Flutter** using **Dart 3.x**.

> **Notation**: `{feature}` refers to a bounded feature area (e.g. `auth`, `orders`, `profile`). `{maintainer}` refers to the project's primary author or team identifier.
>
> **Severity Levels**:
> - 🔴 **MUST**: Non-negotiable requirement. Violations break builds, cause runtime bugs, or fail code review gates.
> - 🟡 **SHOULD**: Strongly recommended best practice. Deviations require documented rationale.
> - 🟢 **MAY**: Optional stylistic guideline or situational preference.

---

## 1. Dart & SDK Baseline 🔴 MUST

- 🔴 **MUST**: Target **Dart 3.x** with **Flutter stable channel** as the minimum baseline.
- 🔴 **MUST**: Enable **sound null safety** — do not use `// ignore: null_safety` suppressions in production code.
- 🔴 **MUST**: Enforce static analysis via `analysis_options.yaml` using the `flutter_lints` package as the baseline rule set. Extend with stricter rules as needed.
- 🔴 **MUST**: Treat all analysis warnings as errors in CI (`--fatal-infos`, `--fatal-warnings` flags on `flutter analyze`).

```yaml
# ✅ GOOD: analysis_options.yaml
include: package:flutter_lints/flutter.yaml

analyzer:
  errors:
    missing_required_param: error
    missing_return: error
    dead_code: warning
  strong-mode:
    implicit-casts: false
    implicit-dynamic: false

linter:
  rules:
    - always_declare_return_types
    - avoid_dynamic_calls
    - avoid_print
    - prefer_const_constructors
    - prefer_final_fields
    - prefer_final_locals
    - unawaited_futures
```

---

## 2. Project & Feature Structure 🔴 MUST

- 🔴 **MUST**: Use a **feature-first** folder structure under `lib/`. Each feature is self-contained with its own `data/`, `domain/`, and `presentation/` layers, mirroring the hexagonal/clean architecture principle.
- 🔴 **MUST NOT**: Place business logic inside widget files. Widgets must only handle rendering and user interaction delegation.
- 🟡 **SHOULD**: Place shared utilities, theme, routing, and DI configuration in a `lib/core/` directory.

```
lib/
├── core/
│   ├── di/                  # Dependency injection setup (e.g. Riverpod providers)
│   ├── navigation/          # GoRouter configuration
│   ├── theme/               # ThemeData, color tokens, text styles
│   └── utils/               # Shared utilities (formatters, extensions)
├── features/
│   └── {feature}/
│       ├── data/
│       │   ├── datasources/ # Remote and local data sources
│       │   ├── models/      # JSON-serialisable data models
│       │   └── repositories/# Repository implementations
│       ├── domain/
│       │   ├── entities/    # Pure Dart domain entities
│       │   ├── repositories/# Repository interfaces (abstract classes)
│       │   └── usecases/    # Single-responsibility use case classes
│       └── presentation/
│           ├── pages/       # Full-screen route destinations
│           ├── widgets/     # Feature-specific reusable widgets
│           └── providers/   # Riverpod providers / Bloc cubit
└── main.dart
```

---

## 3. Naming & File Conventions 🔴 MUST

- 🔴 **MUST**: Use `UpperCamelCase` for class, enum, and widget names.
- 🔴 **MUST**: Use `lowerCamelCase` for variables, parameters, and method names.
- 🔴 **MUST**: Use `snake_case` for file and directory names (e.g. `user_profile_page.dart`).
- 🔴 **MUST**: Use `SCREAMING_SNAKE_CASE` for top-level and class-level constants.
- 🔴 **MUST NOT**: Abbreviate names unless the abbreviation is universally understood (e.g. `id`, `url`).
- 🟡 **SHOULD**: Suffix widget classes with their type: `Page`, `Screen`, `Widget`, `Dialog`, `Button`.

```dart
// ✅ GOOD
class UserProfilePage extends StatelessWidget { ... }
class PrimaryActionButton extends StatelessWidget { ... }
const double kDefaultPadding = 16.0;

// ❌ BAD
class usrPrfPg extends StatelessWidget { ... }  // abbreviation + wrong case
class MyWidget1 extends StatelessWidget { ... }  // meaningless name
```

---

## 4. Widget Architecture 🔴 MUST

- 🔴 **MUST**: Default to `StatelessWidget`. Only use `StatefulWidget` for purely local, ephemeral UI state (e.g. animation controllers, focus nodes) that has no business meaning.
- 🔴 **MUST NOT**: Place business logic, API calls, or data transformations inside `build()` methods.
- 🟡 **SHOULD**: Extract complex subtrees into named private widget classes (`_HeaderSection`, `_ItemCard`) rather than inlining deep widget trees in a single `build()`.
- 🔴 **MUST**: Use `const` constructors wherever possible to enable Flutter's widget diffing optimisation.

```dart
// ✅ GOOD: StatelessWidget with const constructor, no logic in build()
class OrderSummaryCard extends StatelessWidget {
  const OrderSummaryCard({
    super.key,
    required this.order,
    required this.onTap,
  });

  final Order order;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: _CardContent(order: order),
    );
  }
}

class _CardContent extends StatelessWidget {
  const _CardContent({required this.order});
  final Order order;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(order.id, style: Theme.of(context).textTheme.titleMedium),
        Text(order.status.label),
      ],
    );
  }
}

// ❌ BAD: Business logic and API calls inside build()
@override
Widget build(BuildContext context) {
  final data = apiService.fetchOrders(); // ❌ blocking call in build
  return ListView(children: data.map((o) => Text(o.id)).toList());
}
```

---

## 5. State Management 🔴 MUST

- 🔴 **MUST**: Use **Riverpod** (preferred) or **Bloc/Cubit** for all feature-level and application-level state. Justify any deviation in the project ADR.
- 🔴 **MUST NOT**: Use raw `setState()` outside of truly local, ephemeral UI micro-state (e.g. expanding/collapsing an accordion). Never use it to drive business logic or cross-widget communication.
- 🔴 **MUST NOT**: Use `InheritedWidget` or manual `ChangeNotifier` propagation for new code. Use Riverpod providers instead.
- 🟡 **SHOULD**: Name Riverpod providers descriptively with a `Provider` suffix: `currentUserProvider`, `ordersListProvider`.

```dart
// ✅ GOOD: Riverpod AsyncNotifier for server-driven state
@riverpod
class OrdersList extends _$OrdersList {
  @override
  Future<List<Order>> build() async {
    return ref.watch(orderRepositoryProvider).fetchAll();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => ref.read(orderRepositoryProvider).fetchAll());
  }
}

// ✅ GOOD: Consuming state in a widget
class OrdersPage extends ConsumerWidget {
  const OrdersPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(ordersListProvider);
    return ordersAsync.when(
      loading: () => const CircularProgressIndicator(),
      error: (e, _) => ErrorView(message: e.toString()),
      data: (orders) => OrderListView(orders: orders),
    );
  }
}
```

---

## 6. Navigation 🔴 MUST

- 🔴 **MUST**: Use **GoRouter** for all application routing. No imperative `Navigator.push()` / `Navigator.pushNamed()` calls across feature boundaries.
- 🔴 **MUST**: Define all routes centrally in `lib/core/navigation/app_router.dart`.
- 🟡 **SHOULD**: Use typed route classes (GoRouter's `TypedGoRoute`) for compile-time safe route parameters.
- 🔴 **MUST NOT**: Pass complex domain objects as route arguments. Pass only primitive IDs and load data in the destination screen via its provider.

```dart
// ✅ GOOD: Centralised GoRouter with typed routes
final appRouter = GoRouter(
  initialLocation: '/home',
  routes: [
    GoRoute(
      path: '/home',
      builder: (context, state) => const HomePage(),
    ),
    GoRoute(
      path: '/orders/:orderId',
      builder: (context, state) {
        final orderId = state.pathParameters['orderId']!;
        return OrderDetailPage(orderId: orderId); // ✅ only pass ID
      },
    ),
  ],
);

// ❌ BAD: Passing full domain objects via route arguments
context.push('/order-detail', extra: orderObject); // ❌ breaks deep linking and serialisation
```

---

## 7. Data Layer & Repository Pattern 🟡 SHOULD

- 🟡 **SHOULD**: Define repository **interfaces** (abstract classes) in `domain/repositories/` and their implementations in `data/repositories/`.
- 🔴 **MUST**: All network models (`data/models/`) must be distinct from domain entities (`domain/entities/`). Use a `toDomain()` / `fromDomain()` mapping method.
- 🟡 **SHOULD**: Use `json_serializable` for JSON model generation. Do not write manual `fromJson`/`toJson` in production code.
- 🔴 **MUST**: Handle all remote errors at the repository boundary. Convert HTTP errors and exceptions into typed domain `Failure` or `Result` objects before they reach the presentation layer.

```dart
// ✅ GOOD: Typed failure result from repository
sealed class OrderFailure {
  const OrderFailure();
}
class NetworkOrderFailure extends OrderFailure { const NetworkOrderFailure(); }
class NotFoundOrderFailure extends OrderFailure { const NotFoundOrderFailure(this.orderId); final String orderId; }

abstract interface class OrderRepository {
  Future<Either<OrderFailure, Order>> findById(String orderId);
}
```

---

## 8. Testing 🔴 MUST

- 🔴 **MUST**: Write **unit tests** for all use case classes, repository implementations, and pure Dart business logic in `test/`.
- 🟡 **SHOULD**: Write **widget tests** for key UI components and page flows using `flutter_test`.
- 🟢 **MAY**: Write **integration tests** using `integration_test` for critical user journeys (login, checkout, etc.).
- 🔴 **MUST**: Maintain a minimum of **80% line coverage** on `domain/` and `data/` layers. Enforce via CI (`flutter test --coverage`).
- 🟡 **SHOULD**: Use `mocktail` (preferred) or `mockito` for mocking dependencies in unit tests.

```dart
// ✅ GOOD: Unit test for a use case
void main() {
  late MockOrderRepository mockRepository;
  late GetOrderById useCase;

  setUp(() {
    mockRepository = MockOrderRepository();
    useCase = GetOrderById(repository: mockRepository);
  });

  test('returns Order when repository succeeds', () async {
    final expected = Order(id: '123', status: OrderStatus.pending);
    when(() => mockRepository.findById('123'))
        .thenAnswer((_) async => Right(expected));

    final result = await useCase.execute('123');

    expect(result, Right(expected));
  });

  test('returns NotFoundOrderFailure when order does not exist', () async {
    when(() => mockRepository.findById('999'))
        .thenAnswer((_) async => const Left(NotFoundOrderFailure('999')));

    final result = await useCase.execute('999');

    expect(result, const Left(NotFoundOrderFailure('999')));
  });
}
```

---

## 9. Async & Error Handling 🔴 MUST

- 🔴 **MUST NOT**: Use `print()` in production code. Use a structured logging package (e.g. `logger`, `talker`).
- 🔴 **MUST NOT**: Swallow exceptions silently with empty `catch` blocks.
- 🔴 **MUST**: Always `await` `Future`s. Never fire-and-forget without deliberate justification and a comment.
- 🟡 **SHOULD**: Prefer `async`/`await` over raw `.then()` chaining for readability.

```dart
// ✅ GOOD: Explicit error handling with structured logging
Future<void> submitOrder(Order order) async {
  try {
    await orderRepository.save(order);
  } on NetworkException catch (e, stackTrace) {
    logger.e('Failed to submit order', error: e, stackTrace: stackTrace);
    rethrow;
  }
}

// ❌ BAD: Silent catch, fire-and-forget, and print()
void submitOrder(Order order) {
  orderRepository.save(order).then((_) {}).catchError((e) {
    print(e); // ❌ use structured logger
  });
}
```

---

## 10. Assets & Platform Conventions 🟡 SHOULD

- 🟡 **SHOULD**: Organise assets under `assets/images/`, `assets/icons/`, `assets/fonts/`, `assets/i18n/`.
- 🟡 **SHOULD**: Use `flutter_gen` for type-safe asset access instead of raw string paths.
- 🔴 **MUST**: Name platform channel method channels using reverse domain notation: `com.{org}.{app}/{feature}` (e.g. `com.example.myapp/camera`).
- 🟡 **SHOULD**: Wrap all platform channel calls in a dedicated service class within the `data/datasources/` layer to isolate platform coupling.
