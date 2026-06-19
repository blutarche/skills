---
name: de-flaking-tests
description: "Makes flaky or unreliable tests deterministic — replaces fixed sleeps with condition-based polling, removes timing races, and kills tests that pass for the wrong reason (mock theater, test-only production methods, incomplete mocks, assertions that can't fail when logic changes). Use when the user mentions flaky tests, intermittent failures, tests that pass locally but fail in CI, or test reliability."
license: MIT
---

# De-Flaking Tests

A flaky test fails for one of two reasons: it races on timing, or it lies about what it verifies. Fix both. A test that passes intermittently is broken; a test that always passes but verifies nothing is worse.

> The code examples below are illustrative — adapt the syntax to your test runner and language. The principles are language-agnostic.

Route by symptom: a test that **fails intermittently** is a timing problem (Part 1); a test that **always passes but proves nothing** is an honesty problem (Part 2).

## Part 1 — Timing & Races

**Core principle:** Wait for the actual condition you care about, not a guess about how long it takes.

Fixed delays create races: the test passes on a fast machine and fails under load or in CI. A delay long enough to be reliable is also slow; a delay short enough to be fast is also flaky. There is no good fixed number.

### Replace the delay with a condition

```
// BEFORE: guessing at timing
sleep(50ms)
result = getResult()
assert result is defined

// AFTER: waiting for the condition
waitFor(() => getResult() is defined)
result = getResult()
assert result is defined
```

### Common conditions to wait for

| Scenario | Wait for |
|----------|----------|
| Event fired | `waitFor(() => events.some(e => e.type === 'DONE'))` |
| State reached | `waitFor(() => machine.state === 'ready')` |
| Count reached | `waitFor(() => items.length >= 5)` |
| File written | `waitFor(() => fileExists(path))` |
| Compound | `waitFor(() => obj.ready && obj.value > 10)` |

### A condition-poller, if your runner lacks one

Most test frameworks ship a `waitFor` / `eventually` / `until` helper — use theirs. If none exists, the shape is:

```
function waitFor(condition, description, timeoutMs = 5000):
    start = now()
    loop:
        result = condition()       // call the getter INSIDE the loop for fresh data
        if result: return result
        if now() - start > timeoutMs:
            fail("Timeout waiting for " + description + " after " + timeoutMs + "ms")
        sleep(10ms)                // poll interval; not 1ms
```

### Common mistakes

- **Polling too fast** (e.g. every 1ms) — wastes CPU. Poll around every 10ms.
- **No timeout** — loops forever when the condition never holds. Always bound it with a clear error.
- **Stale data** — capturing state once before the loop. Re-read inside the loop each iteration.

### When a fixed delay is correct

Only when you are testing timed behavior itself (debounce, throttle, a component that ticks on an interval). Then:

1. First wait for the triggering condition.
2. Base the delay on known timing, not a guess.
3. Comment why the number is what it is.

```
waitFor(() => toolStarted)   // 1. wait for the trigger
sleep(200ms)                 // 2. tool ticks every 100ms; 200ms = 2 ticks (documented)
```

---

## Part 2 — Honest Tests

A test that can't fail when the logic breaks gives false confidence. These patterns make tests pass for the wrong reason. Fix them so the test verifies real behavior.

**Core principle:** Test what the code does, not what the mocks do.

**Three rules:**
1. Never assert on mock behavior.
2. Never add test-only methods to production code.
3. Never mock without understanding what the real method does.

### Anti-pattern: testing the mock instead of the code

```
// BAD: asserts the mock is present, not that the component works
test('renders sidebar'):
    render(<Page />)
    assert getByTestId('sidebar-mock') is present
```

This passes when the mock is wired up and fails when it isn't — it tells you nothing about real behavior.

```
// GOOD: render the real Sidebar (unmock it) and assert on behavior it actually produces.
// If isolation forces a mock, assert on the page's OWN behavior given the sidebar slot —
// e.g. that a route renders or content loads — never on the mock's presence.
test('renders sidebar'):
    render(<Page />)        // real Sidebar, not the mock
    assert getByRole('navigation') is present
```

**Gate:** Before asserting on any mocked element, ask "Am I checking real behavior or just that the mock exists?" If the latter, delete the assertion or unmock the component.

### Anti-pattern: test-only methods in production code

```
// BAD: destroy() exists only so tests can clean up
class Session:
    destroy():               // looks like real API, but nothing in production calls it
        workspaceManager.destroyWorkspace(this.id)
```

This pollutes production with code that can be called by accident, and confuses object lifecycle with entity lifecycle.

```
// GOOD: cleanup lives in a test utility
// test-utils:
function cleanupSession(session):
    info = session.getWorkspaceInfo()
    if info: workspaceManager.destroyWorkspace(info.id)

// in tests:
afterEach(() => cleanupSession(session))
```

**Gate:** Before adding a method to a production class, ask "Is this only used by tests?" If yes, put it in test utilities. Then ask "Does this class actually own this resource's lifecycle?" If no, it's the wrong class.

### Anti-pattern: mocking without understanding dependencies

```
// BAD: the mocked method had a side effect the test depended on
test('detects duplicate server'):
    mock(ToolCatalog.discoverAndCacheTools).returns(nothing)  // also skips the config write!
    addServer(config)
    addServer(config)   // should throw on duplicate — but the config was never written, so it won't
```

Over-mocking "to be safe" removes behavior the test relies on. The test then passes for the wrong reason or fails mysteriously.

```
// GOOD: mock only the slow/external part, preserve the behavior under test
test('detects duplicate server'):
    mock(MCPServerManager)   // just the slow server startup
    addServer(config)        // config still written
    addServer(config)        // duplicate detected
```

**Gate:** Before mocking a method, ask: What side effects does the real method have? Does this test depend on any of them? If yes, mock at a lower level (the actual slow/external operation), not the high-level method the test needs. If you don't know what the test depends on, run it against the real implementation first, observe what must happen, then add minimal mocking.

### Anti-pattern: incomplete mocks

```
// BAD: only the fields you think you need
mockResponse = { status: 'success', data: { userId: '123', name: 'Alice' } }
// breaks later when code reads response.metadata.requestId
```

Partial mocks hide structural assumptions and fail silently when downstream code reads a field you omitted. The test proves nothing about real behavior.

```
// GOOD: mirror the complete real structure
mockResponse = {
    status: 'success',
    data: { userId: '123', name: 'Alice' },
    metadata: { requestId: 'req-789', timestamp: 1234567890 }
}
```

**Gate:** Before writing a mock object, ask: does it mirror the complete structure as it exists in reality, or only the fields my immediate assertion touches? Include every field the real API documents.

### When mocks get too complex

If mock setup is longer than the test logic, you're mocking everything to force a pass, or the test breaks whenever a mock changes — stop and ask whether you need the mock at all. An integration test with real components is often simpler and more honest than an elaborate mock.

---

## Confirm the Fix

A de-flaked test must:

1. **Pass repeatedly** — run it many times (and under load / in parallel) without intermittent failure.
2. **Still be able to fail** — break the production logic on purpose and confirm the test goes red. If it stays green, it was lying; fix the assertion, not the code.

## Red Flags

- Assertions that check for `*-mock` test IDs
- `sleep` / fixed delays in async tests
- Methods only ever called from test files
- Mock setup making up more than half the test
- A test that stays green when you delete the behavior it claims to verify
- "I'll mock this just to be safe"
