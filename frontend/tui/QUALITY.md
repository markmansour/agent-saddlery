# Frontend TUI — Quality & Testing

This frontend is held to the same quality standards as the backend.

## Quality Checks

All commands require zero violations:

```bash
npm run type-check  # TypeScript strict type checking
npm run build       # Compile to JavaScript
npm run lint        # ESLint with max-warnings=0
npm run test:run    # Run tests (CI mode)
npm run format      # Prettier code formatting (optional)
```

### Type Checking

**Command:** `npm run type-check` (TypeScript in noEmit mode)

Verifies:
- ✓ All imports resolve correctly
- ✓ Type safety across components
- ✓ React prop types
- ✓ Test framework types (Vitest)

**Pass requirement:** 0 errors

### Build

**Command:** `npm run build` (TypeScript compiler)

Outputs to `dist/` directory:
- ✓ JavaScript bundles for all components
- ✓ Type declarations (.d.ts) for consumption by other projects
- ✓ ESM (ECMAScript Modules) format

**Pass requirement:** 0 errors

### Linting

**Command:** `npm run lint` (ESLint with max-warnings=0)

Enforces:
- ✓ No unused variables
- ✓ No undefined globals (process, NodeJS, setTimeout, etc.)
- ✓ React best practices
- ✓ TypeScript type safety
- ✓ Consistent code style (via Prettier config)

**Pass requirement:** 0 errors, 0 warnings

### Testing

**Command:** `npm run test` (watch mode) or `npm run test:run` (CI mode)

Test framework: **Vitest** (compatible with Jest syntax)

**Unit tests:**
- CoreSubprocess interface validation (4 tests)
- Event emitter setup

**Integration tests:**
- Skeleton for end-to-end testing (commented out)
- Requires: Python backend available

See `src/__tests__/` for test files.

**Pass requirement:** All tests passing, 100% of unit tests included

## Configuration Files

### `tsconfig.json`
- Target: ES2020, module: ES2020
- JSX: react-jsx
- moduleResolution: bundler (for Node.js ESM)
- Strict: false (Ink has some loose types)
- Includes: vitest/globals types

### `eslint.config.js`
- ESLint 9 with flat config
- @typescript-eslint/parser and @typescript-eslint/eslint-plugin
- eslint-plugin-react for JSX rules
- eslint-config-prettier to disable formatting rules
- Node.js globals: process, NodeJS, setTimeout, clearTimeout

### `.prettierrc.json`
- printWidth: 100 (match backend convention)
- semi: true
- singleQuote: false
- trailingComma: es5
- tabWidth: 2

### `vitest.config.ts`
- environment: node
- globals: true (use `describe`, `it`, `expect` without imports)
- Coverage provider: v8

### `.npmrc`
- legacy-peer-deps=true (ESLint 9 ↔ TypeScript ESLint 7 compatibility)

## Before Commit

Ensure this command passes:

```bash
npm run type-check && npm run build && npm run lint && npm run test:run
```

All four must pass with zero errors/warnings.

## Development Workflow

1. **Local development:** `npm run dev` (compiles and runs TUI with backend)
2. **Watch tests:** `npm run test` (Vitest watch mode while coding)
3. **Pre-commit:** Run all four checks above
4. **CI:** Same four checks run automatically

## Common Issues

| Issue | Solution |
|-------|----------|
| `Cannot find module 'keypress'` | Run `npm install --legacy-peer-deps` |
| ESLint errors on `process` | Already configured in eslint.config.js globals |
| TypeScript errors on Vitest functions | Already included via `"types": ["node", "vitest/globals"]` |
| Build fails with unknown .tsx extension | Update tsconfig.json moduleResolution to "bundler" |
| Tests don't run | Ensure vitest is installed and test files match `**/*.test.ts` pattern |

## Future Work

- Add integration tests (requires Python backend mocking or real backend available)
- Add component snapshot tests
- Add E2E tests (full TUI interaction)
- Coverage reporting (currently v8 configured but not enforced)
- Vitest UI for visual test running

## Related

- Backend quality checks: `backend/QUALITY.md`
- TUI architecture: `README.md`
- Integration with core: `src/core/subprocess.ts`
