# Release notes — draft for the accepted StudyHub Planner

**Status:** prepared after the clean-copy checks; no tag or GitHub Release has been created.

## Included

- Persistent task management through the console CLI.
- JSON storage with restart recovery and legacy records without `tags`.
- Regression checks for CLI effects, storage errors, and service restart.
- Windows PowerShell instructions for setup, tests, and a persistence walkthrough.

## Verification to record with the accepted revision

- Python 3.12.10.
- Install development checks from `requirements-dev.txt`.
- Run `python -m pytest -q` in a clean clone.
- Exercise add/done, exit, and list/stats in a second process.
- Record the exact accepted commit with `git rev-parse HEAD`.

## Known limits

JSON snapshots are written without transaction or atomic-replacement guarantees. Concurrent writers are not coordinated. Model and MemoryStorage unit coverage from the skipped earlier lesson steps remains incomplete in this checkout and is called out in `test-matrix.md`.
