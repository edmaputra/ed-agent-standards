---
description: "Project directory structures, agent discovery metadata, AGENTS.md manifests, and automated structure scanning across Java, Kotlin, Flutter, and Angular."
globs:
  - "**/*"
---

# Project Structure & Agent Discovery Standards

This document establishes standardized repository layouts, directory structures, and AI agent discovery mechanisms across **Java & Kotlin**, **Flutter & Dart**, and **Angular & TypeScript** projects.

> **Severity Levels**:
> - 🔴 **MUST**: Non-negotiable requirement. Violations break build gates, fail architectural tests, or block code review approval.
> - 🟡 **SHOULD**: Strongly recommended practice. Deviations require team consensus and documented rationale.
> - 🟢 **MAY**: Optional guideline or contextual optimization.

---

## 1. Universal Agent Discovery Mechanism 🔴 MUST

To enable AI agents (such as Antigravity) to navigate repositories deterministically without expensive, repetitive exploratory searches:

- 🔴 **MUST**: Every project repository must maintain an `AGENTS.md` file in its root directory.
- 🔴 **MUST**: Automated structure scans generate a cached `project-structure.json` map that must be ignored by Git (`.gitignore`).
- 🔴 **MUST**: Directory structures must follow the canonical architectural pattern designated for that technology stack.
- 🟡 **SHOULD**: Projects should include the Antigravity `PreInvocation` hook (`hooks.json`) to automatically refresh `project-structure.json` on session startup if missing.

### 1.1 Discovery Workflow

```
Session Start (Antigravity)
       │
       ▼
PreInvocation Hook (hooks.json)
       │
       ├───> Does project-structure.json exist?
       │        ├── YES ──> Continue instantly (0ms overhead)
       │        └── NO  ──> Execute scripts/scan-structure.py
       │                        │
       │                        ▼
       │                   Generate project-structure.json
       │                   Emit ephemeral notice to Agent
       ▼
Agent reads AGENTS.md + project-structure.json
       │
       ▼
Instant Direct Navigation (zero exploratory tool calls)
```

---

## 2. Java & Kotlin Standards (Hexagonal Architecture) 🔴 MUST

All Java and Kotlin microservices and libraries follow **Hexagonal Architecture (Ports and Adapters)** with **Domain-Driven Design (DDD)**.

### 2.1 Package Layout

Dependencies flow **strictly inward**: `adapter` ➔ `application` ➔ `domain`.

```
{base-package}/
├── domain/                      # Core business model (Pure Java/Kotlin, zero framework)
│   ├── model/                  # Domain Entities & Value Objects (Java records)
│   ├── port/                   # SPI contracts: repository and external service interfaces
│   ├── event/                  # Domain event records
│   └── exception/              # Domain-specific exceptions
├── application/                 # Use cases and orchestration
│   ├── port/
│   │   ├── in/                 # Primary/Driving port interfaces (Use Cases)
│   │   └── out/                # Secondary/Driven port interfaces (SPIs)
│   └── service/                # Use case implementations (@Service)
├── adapter/                     # Infrastructure and transport adapters
│   ├── in/                     # Driving adapters
│   │   ├── rest/               # Spring Web MVC / WebFlux controllers, DTOs, mappers
│   │   └── messaging/          # Kafka / RabbitMQ message consumers
│   └── out/                    # Driven adapters
│       ├── persistence/        # Spring Data JPA / R2DBC repositories, entities, mappers
│       └── client/             # HTTP clients (RestClient, Feign, WebClient)
└── config/                      # Spring Boot configuration, SecurityFilterChain, Beans
```

### 2.2 Rules & Constraints

- 🔴 **MUST**: `domain` package must have zero dependencies on Spring, Hibernate, JPA, or Web libraries.
- 🔴 **MUST**: Outbound ports (repository interfaces) reside in `domain/port/` or `application/port/out/`. Implementations reside exclusively in `adapter/out/persistence/`.
- 🔴 **MUST**: Inbound driving controllers reside exclusively in `adapter/in/rest/` or `adapter/in/{protocol}/`.
- 🔴 **MUST**: Request/Response DTOs belong to `adapter/in/rest/dto/` and must never leak into `domain`.
- 🟡 **SHOULD**: Multi-module Gradle/Maven builds should preserve this package hierarchy within each subproject (e.g. `services/order-service/src/main/java/...`).

---

## 3. Flutter & Dart Standards (Feature-First Clean Architecture) 🔴 MUST

Flutter applications use a **feature-first folder structure** under `lib/`. Each feature encapsulates its own `presentation/`, `domain/`, and `data/` layers.

### 3.1 Directory Layout

```
lib/
├── core/                        # Cross-cutting foundational modules
│   ├── di/                      # Riverpod provider definitions or service locator
│   ├── navigation/              # GoRouter route declarations and guards
│   ├── network/                 # Dio / HTTP client wrapper, interceptors
│   ├── theme/                   # ThemeData, color schemes, typography
│   └── utils/                   # Shared formatters, validators, extensions
├── features/
│   └── {feature_name}/          # Bounded feature (e.g. auth, checkout, profile)
│       ├── data/                # Data layer
│       │   ├── datasources/     # Remote (API) and local (cache/database) datasources
│       │   ├── models/          # JSON-serializable DTO models (`freezed` or manual)
│       │   └── repositories/    # Repository implementations (implements domain contract)
│       ├── domain/              # Domain layer (Pure Dart)
│       │   ├── entities/        # Core business objects
│       │   ├── repositories/    # Abstract repository interfaces
│       │   └── usecases/        # Single-purpose use cases (Callable classes)
│       └── presentation/        # UI layer
│           ├── pages/           # Route destination screens (`*Page`, `*Screen`)
│           ├── widgets/         # Feature-specific dumb and smart widgets
│           └── providers/       # StateNotifier, AsyncNotifier, or Cubit/Bloc
└── main.dart                    # Application bootstrap & entry point
```

### 3.2 Rules & Constraints

- 🔴 **MUST**: Feature directories under `lib/features/` must be named in `snake_case` (e.g. `user_management`, `shopping_cart`).
- 🔴 **MUST**: Presentation widgets must not import data sources directly; all interactions must pass through presentation providers/state controllers and use cases.
- 🔴 **MUST**: Files must use `snake_case` and end with their role:
  - Pages: `*_page.dart`
  - Providers: `*_provider.dart`
  - Models: `*_model.dart`
  - Entities: `*_entity.dart`
  - Repositories: `*_repository.dart` or `*_repository_impl.dart`
- 🟡 **SHOULD**: Pure domain code in `domain/` must have zero Flutter UI dependencies (`dart:ui`, `package:flutter/material.dart`).

---

## 4. Angular & TypeScript Standards (Feature-First Standalone) 🔴 MUST

Angular projects (v17+) use a **feature-first architecture** with **standalone components**, eliminating `NgModule`s for modern modularity.

### 4.1 Directory Layout

```
src/
├── app/
│   ├── core/                    # Singleton services, interceptors, shell layouts
│   │   ├── guards/              # CanActivateFn, CanDeactivateFn functional guards
│   │   ├── interceptors/        # HttpInterceptorFn functional interceptors
│   │   ├── services/            # Global singletons (AuthService, LoggingService)
│   │   └── layout/              # Header, sidebar, footer, shell navigation
│   ├── shared/                  # Reusable presentation utilities across features
│   │   ├── components/          # Dumb/Presentational UI components (buttons, tables)
│   │   ├── directives/          # Shared attribute/structural directives
│   │   ├── pipes/               # Formatting pipes
│   │   └── models/              # Shared interfaces and TypeScript types
│   └── features/
│       └── {feature-name}/      # Self-contained feature module
│           ├── components/      # Smart & dumb components for the feature
│           ├── services/        # Feature-specific business logic and API services
│           ├── store/           # NgRx SignalStore or actions/reducers/selectors
│           ├── models/          # Feature-specific types, DTOs, and view models
│           └── {feature}.routes.ts # Lazy-loaded route definitions
├── main.ts                      # bootstrapApplication entry point
└── index.html                   # HTML host template
```

### 4.2 Rules & Constraints

- 🔴 **MUST**: All components, directives, and pipes must be `standalone: true`.
- 🔴 **MUST**: Every feature must provide a `{feature}.routes.ts` file loaded via `loadChildren: () => import(...)` for route-level code splitting.
- 🔴 **MUST**: Component files must be co-located in their own folder:
  - `{name}.component.ts`
  - `{name}.component.html`
  - `{name}.component.scss`
  - `{name}.component.spec.ts`
- 🟡 **SHOULD**: Feature folders under `src/app/features/` must use kebab-case (e.g. `order-history`, `user-profile`).

---

## 5. Automated Scanner & Structure Map (`project-structure.json`) 🔴 MUST

Downstream projects adopting these standards include the scanner script and `hooks.json`.

### 5.1 Scanner Script Specification

The scanner script (`scripts/scan-structure.py`) performs intelligent architectural analysis:
1. **Stack Identification**: Identifies Java/Kotlin, Flutter, and Angular markers (`pom.xml`, `build.gradle.kts`, `pubspec.yaml`, `angular.json`).
2. **Layer Classification**: Groups files into their architectural roles (Hexagonal layers, Flutter clean architecture subdirectories, Angular feature stores/components).
3. **Artifact Exclusion**: Filters all build and temporary directories (`build/`, `target/`, `node_modules/`, `.dart_tool/`, `.angular/`, `.git/`).

### 5.2 JSON Output Schema Reference

```json
{
  "schemaVersion": "1.0.0",
  "generatedAt": "2026-09-17T06:12:00Z",
  "workspaceName": "my-service",
  "workspaceRoot": "/path/to/my-service",
  "detectedStacks": ["java-kotlin"],
  "stackDetails": {
    "java-kotlin": {
      "architecture": "hexagonal",
      "modules": {
        "root": {
          "domain": {
            "models": ["src/main/java/com/example/domain/model/User.java"],
            "ports": ["src/main/java/com/example/domain/port/UserRepository.java"],
            "events": ["src/main/java/com/example/domain/event/UserRegisteredEvent.java"]
          },
          "application": {
            "usecases": ["src/main/java/com/example/application/service/RegisterUserService.java"]
          },
          "adapter": {
            "inbound": {
              "rest": ["src/main/java/com/example/adapter/in/rest/UserController.java"]
            },
            "outbound": {
              "persistence": ["src/main/java/com/example/adapter/out/persistence/UserJpaAdapter.java"]
            }
          },
          "config": ["src/main/java/com/example/config/SecurityConfig.java"]
        }
      }
    }
  },
  "rootSummary": {
    "topLevelDirectories": ["src", "gradle"],
    "topLevelFiles": ["build.gradle.kts", "settings.gradle.kts", "README.md", "AGENTS.md"]
  }
}
```

### 5.3 Manual Execution & Refresh

Developers or agents can manually refresh the structure map at any time:

```bash
# Refresh map in current workspace
python3 .agents/scripts/scan-structure.py --force

# Output to stdout without writing
python3 .agents/scripts/scan-structure.py --stdout
```

---

## 6. Downstream `AGENTS.md` Starter Templates

Copy the appropriate template into the root of your downstream repository as `AGENTS.md`.

### Template A: Java / Kotlin (Spring Boot & Hexagonal Architecture)

```markdown
# Agent Guide: {project-name}

## Stack & Versions
- **Language**: Java 25 / Kotlin 2.x
- **Framework**: Spring Boot 4.x
- **Build Tool**: Gradle (`./gradlew`) or Maven (`./mvnw`)
- **Standards**: Inherited from `.agents/rules/java-kotlin/`

## Architecture: Hexagonal (Ports & Adapters)
- `domain/model/` -> Entities and value objects (Java records)
- `domain/port/` -> Outbound repository & SPI contracts
- `application/service/` -> Use case implementations
- `adapter/in/rest/` -> REST controllers & HTTP request/response DTOs
- `adapter/out/persistence/` -> Spring Data JPA / Liquibase persistence adapters

## Key Commands
- Build: `./gradlew build`
- Unit Tests: `./gradlew test`
- Verification / Lint: `./gradlew check`

## Agent Guidelines
- Check `.agents/project-structure.json` for immediate directory mapping.
- If missing, run: `python3 .agents/scripts/scan-structure.py`.
- Strict rule: NEVER import Spring, JPA, or Web dependencies inside `domain/`.
```

### Template B: Flutter (Feature-First Clean Architecture)

```markdown
# Agent Guide: {project-name}

## Stack & Versions
- **Framework**: Flutter (Stable channel)
- **Language**: Dart 3.x with sound null safety
- **State Management**: Riverpod (`flutter_riverpod`)
- **Routing**: GoRouter (`go_router`)
- **Standards**: Inherited from `.agents/rules/flutter/`

## Architecture: Feature-First Clean Architecture
- `lib/core/` -> Shared theme, navigation, DI, network, and utilities
- `lib/features/{feature}/presentation/` -> Pages, reusable widgets, Riverpod providers
- `lib/features/{feature}/domain/` -> Pure entities, repository interfaces, use cases
- `lib/features/{feature}/data/` -> Models (freezed/json), remote datasources, repository impls

## Key Commands
- Run Analysis: `flutter analyze --fatal-infos --fatal-warnings`
- Run Tests: `flutter test --coverage`
- Code Generation: `dart run build_runner build --delete-conflicting-outputs`

## Agent Guidelines
- Check `.agents/project-structure.json` for feature mapping.
- If missing, run: `python3 .agents/scripts/scan-structure.py`.
- Strict rule: NEVER import Flutter UI packages inside `domain/`.
```

### Template C: Angular (Feature-First Standalone)

```markdown
# Agent Guide: {project-name}

## Stack & Versions
- **Framework**: Angular 17+ (Standalone Components)
- **Language**: TypeScript 5.x (`strict: true`)
- **State Management**: NgRx / Angular Signals
- **Standards**: Inherited from `.agents/rules/angular/`

## Architecture: Feature-First Standalone
- `src/app/core/` -> Singleton services, HTTP interceptors, route guards, layout shell
- `src/app/shared/` -> Presentational dumb UI components, directives, pipes
- `src/app/features/{feature}/` -> Components, services, store, models, routes

## Key Commands
- Lint: `npm run lint`
- Test: `npm run test`
- Build: `npm run build`

## Agent Guidelines
- Check `.agents/project-structure.json` for component and store locations.
- If missing, run: `python3 .agents/scripts/scan-structure.py`.
- Strict rule: All components MUST be standalone with `ChangeDetectionStrategy.OnPush`.
```
