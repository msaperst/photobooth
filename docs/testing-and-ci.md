# Testing & Continuous Integration

This project prioritizes **correctness, safety, and repeatability** over speed.  
Before hardware is introduced (camera, printer), all core logic is validated through automated tests and enforced via
CI.

The goal is to catch regressions **before events**, not during them.

---

## Testing Philosophy

- Business logic is tested **before** hardware integration
- Hardware access is isolated behind abstractions
- Tests are:
    - Deterministic
    - Fast
    - Runnable locally without special setup
- Regressions should be caught by CI, not in production

---

## What Is Tested

Current test coverage includes:

- Controller logic
    - State transitions
    - Busy vs idle behavior
    - Command handling
- Web API behavior
    - `/status` response shape
    - `/start-session` success and rejection logic
- Boundary conditions (e.g. rejecting concurrent sessions)

What is **not** tested yet:

- Camera hardware (gphoto2)
- Printer hardware (CUPS)
- Frontend JavaScript
- Timing-sensitive threading behavior

These areas will be added incrementally as abstractions are introduced.

---

## Running Tests Locally

Before opening a pull request, tests **must** be run locally.

From the project root:

```bash
pytest --cov=controller --cov=web --cov-report=term-missing
```

This will:

- Run all unit tests
- Display coverage information
- Highlight untested lines

To enforce the same coverage threshold as CI:

```bash
pytest --cov=controller --cov=web --cov-fail-under=80
```

If this command fails locally, CI will fail as well.

---

## Continuous Integration (GitHub Actions)

All pushes and pull requests trigger CI.

CI performs the following steps:

1. Checks out the repository
2. Sets up Python (currently Python 3.12)
3. Installs dependencies from requirements.txt
4. Runs all unit tests
5. Fails if:

- Any test fails
- Coverage drops below the enforced threshold

No code should be merged unless CI is fully green.

---

## Development Workflow

The expected workflow for changes is:

1. Create a feature branch
2. Make changes
3. Run tests locally
4. Open a pull request
5. Ensure all CI checks pass
6. Merge only when green

This workflow applies to:

- Code changes
- Refactors
- Infrastructure changes
- Behavior changes

---

## Documentation Discipline

Testing and CI workflows are considered **part of the system design.**

If any of the following change:

- Test strategy
- Coverage thresholds
- CI tooling
- Supported Python versions

Then this document **must be updated** accordingly.

Documentation should reflect reality, not intention.

---

## Why This Matters

Photobooths fail in the real world for unexpected reasons:

- Power issues
- USB flakiness
- Hardware quirks
- Human behavior

The goal of testing and CI is to ensure:

- When something breaks, it’s not the logic
- Rebuilds and refactors are safe
- Confidence remains high as features are added