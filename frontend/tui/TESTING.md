# TUI Testing Strategy

## Why We Missed the Bug

Our test suite was **unit-level only**:
- ✓ Component instantiation
- ✓ Type safety
- ✓ Linting
- ✗ Interactive streaming
- ✗ Message state accumulation
- ✗ Multiple consecutive responses

The bug only manifested when:
1. User types a message
2. Core streams multiple delta tokens
3. Multiple messages arrive in sequence

This requires **end-to-end testing** with a running backend.

## Test Pyramid (Current vs. Needed)

```
Current:
  Unit Tests (6)
  └─ Component instantiation
  └─ Interface validation
  └─ Mock provider setup

Needed:
  Integration Tests (E2E)
  └─ User types → message sent → response arrives
  └─ Multiple consecutive responses
  └─ Streaming tokens accumulate correctly
  └─ State doesn't get overwritten
```

## Testing Approach

### 1. Unit Tests ✓ (Already in place)

```bash
npm run test:run
```

Tests:
- CoreSubprocess interface (4 tests)
- Integration skeleton (2 tests)
- Streaming behavior (2 tests)

**Limitations**: Don't test actual streaming or state mutations.

### 2. Manual Integration Test (Required)

```bash
npm run dev
```

**Steps**:
1. Watch TUI initialize and show "Ready"
2. Type: "hello"
3. Verify: Response streams character-by-character
4. Type: "what is 2+2"
5. Verify: Previous response is intact, new one displays below
6. Type: "goodbye"
7. Verify: All three responses visible, none truncated/overwritten

**Why manual**: 
- Requires TTY (interactive terminal)
- Needs running backend
- Must observe visual streaming

### 3. Proposed: Automated Integration Test

For automated testing of streaming, we'd need:
- Mock CoreSubprocess that emits events sequentially
- Measure message state accumulation
- Verify no overwrites between runs

Example:
```typescript
it("should accumulate multiple streaming messages correctly", async () => {
  const messages = [];
  const handleMessage = (msg) => messages.push(msg.content);
  
  // Simulate 3 messages with streaming
  await core.start();
  await core.sendMessage("msg1");
  // Verify deltas accumulate into messages[0]
  await core.sendMessage("msg2");
  // Verify msg1 is intact, msg2 gets new content
  await core.sendMessage("msg3");
  // Verify all three are complete and separate
  
  expect(messages).toHaveLength(3);
});
```

## Bug Prevention

### What we should have tested:

1. **State isolation** — Each message should have its own ID
2. **Delta accumulation** — Tokens should append, not overwrite
3. **Sequential messages** — run_finish should clear state for next run
4. **Visual correctness** — No truncation or overwrites

### What we actually tested:

1. ✓ Type safety
2. ✓ Component mounting
3. ✓ Mock provider setup
4. ✗ Actual state mutation during streaming
5. ✗ Multiple sequential messages
6. ✗ Visual output

## Recommended Test Plan

### Before Shipping

- [ ] Manual E2E test (as documented above)
- [ ] 3+ consecutive messages with streaming
- [ ] Verify all messages visible and correct
- [ ] Test with real Claude (not mock)

### Before Major Changes

- [ ] Run manual E2E test again
- [ ] Verify no regressions

### CI/CD Integration

Since this is a TUI, we can't fully automate in CI (needs TTY). Instead:

```bash
# Run unit tests (CI)
npm run test:run

# Manual E2E instructions
npm run dev
# Then follow manual steps above
```

## Lessons Learned

1. **Unit tests ≠ integration tests**
   - We had good type checking but missed state bugs
   
2. **UI state is hard to test without running it**
   - Terminal UIs especially need manual verification
   
3. **Visual correctness requires observation**
   - Streaming effects only visible when running interactively

4. **Test the happy path end-to-end**
   - Type a message
   - See a response
   - Type another message
   - Verify both are visible

## Next Steps

1. ✓ Fixed the streaming bug
2. ✓ Added streaming.test.ts skeleton
3. [ ] Write backend streaming test utilities
4. [ ] Implement automated E2E test with mock events
5. [ ] Add manual test checklist to README

For now: **Run `npm run dev` and test manually** before shipping.
