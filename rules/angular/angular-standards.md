---
description: "Angular and TypeScript coding standards, component architecture, RxJS patterns, state management, and testing conventions."
globs:
  - "**/*.ts"
  - "**/*.html"
  - "**/*.scss"
  - "**/*.css"
  - "**/angular.json"
  - "**/tsconfig*.json"
---

# Angular & TypeScript Coding Standards

This document establishes coding conventions, architectural guidelines, and idiomatic practices for projects written in **Angular 17+** with **TypeScript 5.x**.

> **Notation**: `{feature}` refers to a bounded feature area (e.g. `auth`, `orders`, `profile`). `{maintainer}` refers to the project's primary author or team identifier.
>
> **Severity Levels**:
> - 🔴 **MUST**: Non-negotiable requirement. Violations break builds, cause runtime bugs, or fail code review gates.
> - 🟡 **SHOULD**: Strongly recommended best practice. Deviations require documented rationale.
> - 🟢 **MAY**: Optional stylistic guideline or situational preference.

---

## 1. TypeScript Baseline 🔴 MUST

- 🔴 **MUST**: Enable `"strict": true` in `tsconfig.json`. This activates `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, and `strictPropertyInitialization`.
- 🔴 **MUST NOT**: Use the `any` type in production code. Use `unknown` and perform explicit type narrowing, or define proper interfaces/types.
- 🔴 **MUST NOT**: Use `@ts-ignore` or `@ts-nocheck` directives in production code.
- 🔴 **MUST**: Enforce code style via **ESLint** (`@angular-eslint`) and **Prettier**. Both must run as CI checks.
- 🟡 **SHOULD**: Use TypeScript `type` aliases for union/intersection types and `interface` for object shapes that may be extended.

```json
// ✅ GOOD: tsconfig.json strict baseline
{
  "compilerOptions": {
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitOverride": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true
  }
}
```

```typescript
// ✅ GOOD: Explicit typing with unknown narrowing
function parseApiResponse(raw: unknown): Order {
  if (!isOrder(raw)) throw new Error('Invalid Order payload');
  return raw;
}

// ❌ BAD: any type hiding real typing issues
function parseApiResponse(raw: any): Order {
  return raw as Order; // ❌ bypasses type system entirely
}
```

---

## 2. Project & Feature Structure 🔴 MUST

- 🔴 **MUST**: Use a **feature-first** folder structure. Each feature encapsulates its own components, services, store, and models.
- 🟡 **SHOULD**: Place application-wide concerns (guards, interceptors, core services, shell layout) in `src/app/core/`.
- 🟡 **SHOULD**: Place globally reusable, dumb UI components in `src/app/shared/`.

```
src/app/
├── core/
│   ├── guards/              # Route guards
│   ├── interceptors/        # HTTP interceptors
│   ├── services/            # Singleton application services (auth, logging)
│   └── layout/              # Shell/layout components
├── shared/
│   ├── components/          # Generic, reusable UI components
│   ├── directives/          # Shared directives
│   ├── pipes/               # Shared pipes
│   └── models/              # Shared interfaces/types
└── features/
    └── {feature}/
        ├── components/      # Feature-specific smart & dumb components
        ├── services/        # Feature-scoped services
        ├── store/           # NgRx store: actions, reducers, selectors, effects
        ├── models/          # Feature-specific types and interfaces
        └── {feature}.routes.ts  # Lazy-loaded route config
```

---

## 3. Component Architecture 🔴 MUST

- 🔴 **MUST**: Use **standalone components** (Angular 17+) by default. Do not create `NgModule` declarations for new code.
- 🔴 **MUST**: Set `changeDetection: ChangeDetectionStrategy.OnPush` on every component. Avoid `Default` change detection.
- 🔴 **MUST**: Separate **smart (container) components** from **dumb (presentational) components**:
  - **Smart**: Injects services/store, dispatches actions, subscribes to state. Has minimal template logic.
  - **Dumb**: Accepts data via `@Input()`, emits events via `@Output()`. Has zero store or service dependencies.
- 🟡 **SHOULD**: Prefer Angular **Signals** (`signal()`, `computed()`, `effect()`) over manual `BehaviorSubject` wiring for component-local reactive state (Angular 16+).

```typescript
// ✅ GOOD: Standalone component with OnPush and Signals
@Component({
  selector: 'app-order-detail',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, OrderSummaryComponent],
  template: `
    @if (order()) {
      <app-order-summary [order]="order()!" />
    } @else {
      <app-loading-spinner />
    }
  `,
})
export class OrderDetailComponent implements OnInit {
  private readonly orderService = inject(OrderService);
  private readonly route = inject(ActivatedRoute);

  protected readonly order = signal<Order | null>(null);

  ngOnInit(): void {
    const orderId = this.route.snapshot.paramMap.get('orderId')!;
    this.orderService.getById(orderId).subscribe(o => this.order.set(o));
  }
}

// ❌ BAD: NgModule-based component with Default change detection
@Component({ selector: 'app-foo', template: '...' }) // ❌ missing standalone, OnPush
export class FooComponent {
  constructor(private store: Store, private service: DataService) {} // ❌ old-style injection
}
```

---

## 4. RxJS Patterns 🔴 MUST

- 🔴 **MUST**: Prefer the **`async` pipe** in templates over manual `.subscribe()` calls in component classes. The `async` pipe handles subscription teardown automatically.
- 🔴 **MUST**: When `.subscribe()` is unavoidable in a component class, use `takeUntilDestroyed()` (Angular 16+) to prevent memory leaks.
- 🔴 **MUST NOT**: Nest `.subscribe()` inside another `.subscribe()`. Use `switchMap`, `mergeMap`, or `concatMap` instead.
- 🟡 **SHOULD**: Use `shareReplay(1)` for HTTP observables that are consumed by multiple subscribers.
- 🔴 **MUST NOT**: Use `subscribe()` to drive side effects in services without proper teardown. Expose observables and let consumers subscribe.

```typescript
// ✅ GOOD: async pipe in template — no manual subscription
@Component({
  template: `
    @for (order of orders$ | async; track order.id) {
      <app-order-card [order]="order" />
    }
  `,
})
export class OrdersListComponent {
  protected readonly orders$ = inject(OrderService).getAll();
}

// ✅ GOOD: takeUntilDestroyed() when subscribe is necessary
export class OrderDetailComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.orderService.getById(this.orderId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(order => this.order.set(order));
  }
}

// ❌ BAD: Nested subscribes
this.userService.getUser().subscribe(user => {
  this.orderService.getOrders(user.id).subscribe(orders => { // ❌ nested subscribe
    this.orders = orders;
  });
});

// ✅ GOOD: Flattened with switchMap
this.userService.getUser().pipe(
  switchMap(user => this.orderService.getOrders(user.id))
).subscribe(orders => this.orders = orders);
```

---

## 5. State Management 🔴 MUST

- 🔴 **MUST**: Use **NgRx** (Store + Effects + Selectors) for application-wide shared state (authentication, cart, notifications). Justify any alternative in the project ADR.
- 🟡 **SHOULD**: Use **Angular Signals** or a simple service with `signal()` for feature-scoped or component-local state that does not need to be shared across features.
- 🔴 **MUST**: Define actions using `createAction` with typed `props<>()`. Never dispatch raw action objects.
- 🔴 **MUST**: Selectors must be created with `createSelector` and `createFeatureSelector` for memoisation. Never access `store.select(state => state.feature.data)` inline.
- 🔴 **MUST NOT**: Perform side effects (HTTP calls, navigation) inside reducers. Use NgRx Effects for all side effects.

```typescript
// ✅ GOOD: Typed NgRx action, reducer, selector
// actions
export const loadOrders = createAction('[Orders] Load Orders');
export const loadOrdersSuccess = createAction(
  '[Orders] Load Orders Success',
  props<{ orders: Order[] }>()
);
export const loadOrdersFailure = createAction(
  '[Orders] Load Orders Failure',
  props<{ error: string }>()
);

// selectors
export const selectOrdersFeature = createFeatureSelector<OrdersState>('orders');
export const selectAllOrders = createSelector(selectOrdersFeature, s => s.orders);
export const selectOrdersLoading = createSelector(selectOrdersFeature, s => s.loading);

// effect
@Injectable()
export class OrdersEffects {
  private readonly actions$ = inject(Actions);
  private readonly orderService = inject(OrderService);

  loadOrders$ = createEffect(() =>
    this.actions$.pipe(
      ofType(loadOrders),
      switchMap(() =>
        this.orderService.getAll().pipe(
          map(orders => loadOrdersSuccess({ orders })),
          catchError(err => of(loadOrdersFailure({ error: err.message })))
        )
      )
    )
  );
}
```

---

## 6. HTTP & Error Handling 🔴 MUST

- 🔴 **MUST**: All HTTP calls must go through `HttpClient`. Never use the browser's raw `fetch` API.
- 🔴 **MUST**: Register a global **HTTP interceptor** to handle authentication headers, request correlation IDs, and error mapping. Do not scatter these concerns across individual services.
- 🔴 **MUST**: Map all HTTP errors to **typed error models** at the service boundary. The component or store should receive a typed error, not a raw `HttpErrorResponse`.
- 🔴 **MUST NOT**: Use `console.error()` or `console.log()` in production code. Use a structured logging service.

```typescript
// ✅ GOOD: Centralised error-mapping interceptor
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      const appError = mapHttpErrorToAppError(error); // typed mapping
      return throwError(() => appError);
    })
  );
};

// ✅ GOOD: Typed error model
export class AppError {
  constructor(
    public readonly code: string,
    public readonly message: string,
    public readonly retryable: boolean,
  ) {}
}

// ❌ BAD: Raw error handling in a component
this.http.get('/api/orders').subscribe({
  error: (e) => console.error('Error', e) // ❌ raw HttpErrorResponse, console.error
});
```

---

## 7. Naming & Style Conventions 🔴 MUST

- 🔴 **MUST**: Use `PascalCase` for class, interface, enum, and type names.
- 🔴 **MUST**: Use `camelCase` for variables, methods, and properties.
- 🔴 **MUST**: Use `kebab-case` for file names and Angular component selectors.
- 🔴 **MUST**: Use Angular CLI naming conventions — suffix files with their type:
  - Components: `user-profile.component.ts`
  - Services: `order.service.ts`
  - Guards: `auth.guard.ts`
  - Pipes: `currency-format.pipe.ts`
  - Interceptors: `auth.interceptor.ts`
- 🟡 **SHOULD**: Prefix component selectors with a project/org abbreviation to avoid collisions: `app-`, `ed-`, etc.

```typescript
// ✅ GOOD
@Component({ selector: 'app-user-profile', ... })
export class UserProfileComponent { ... }

export interface OrderSummary { id: string; total: number; }

// ❌ BAD
@Component({ selector: 'UserProfile', ... }) // ❌ PascalCase selector
export class userProfile { ... }             // ❌ camelCase class name
```

---

## 8. Testing 🔴 MUST

- 🔴 **MUST**: Write **unit tests** for all services, pipes, guards, and NgRx effects using **Jest**.
- 🟡 **SHOULD**: Write **component tests** using **Angular Testing Library** (`@testing-library/angular`) for behaviour-driven UI testing. Avoid testing implementation details (internal component properties/methods).
- 🟢 **MAY**: Write **E2E tests** using **Playwright** for critical user journeys.
- 🔴 **MUST**: Maintain a minimum of **80% line coverage** on services and store logic. Enforce via CI (`npm test -- --coverage`) using the shared parser `python3 .agents/scripts/coverage/generate-lcov-summary.py` and template `templates/github-actions/ci-angular.yml`.
- 🔴 **MUST**: Mock all external dependencies (HTTP, services, NgRx store) in unit and component tests.

```typescript
// ✅ GOOD: Service unit test with Jest
describe('OrderService', () => {
  let service: OrderService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [OrderService],
    });
    service = TestBed.inject(OrderService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('should return orders on getAll()', () => {
    const expected: Order[] = [{ id: '1', status: 'pending' }];
    service.getAll().subscribe(orders => expect(orders).toEqual(expected));
    httpMock.expectOne('/api/orders').flush(expected);
  });
});
```

---

## 9. Routing & Lazy Loading 🟡 SHOULD

- 🟡 **SHOULD**: Lazy-load all feature modules/routes using `loadComponent` or `loadChildren` to keep the initial bundle small.
- 🔴 **MUST**: Use route-level **guards** (`CanActivate`, `CanMatch`) for access control. Never implement auth checks inside component `ngOnInit`.
- 🟡 **SHOULD**: Use route-level **resolvers** to pre-fetch required data before the component renders, avoiding loading spinners inside components for initial data.

```typescript
// ✅ GOOD: Lazy-loaded feature route with guard and resolver
export const APP_ROUTES: Routes = [
  {
    path: 'orders',
    canMatch: [authGuard],
    loadChildren: () => import('./features/orders/orders.routes'),
  },
  {
    path: 'orders/:id',
    resolve: { order: orderDetailResolver },
    loadComponent: () =>
      import('./features/orders/components/order-detail.component')
        .then(m => m.OrderDetailComponent),
  },
];
```
