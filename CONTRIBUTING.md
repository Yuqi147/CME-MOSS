# Contributing to CME-MOSS

Thanks for considering a contribution. This is a research software project:
the scientific models and their defaults matter more than style, so changes
that affect physics must stay auditable.

## Getting started

```bash
pip install -e ".[dev]"
pytest          # the whole suite must pass (60 tests, offline)
```

## Before you open a pull request

- **Run the tests**: `pytest` must pass. If you change physics or encounter
  logic, add or update tests for the changed behaviour (see `tests/`
  naming: `test_wavefront.py`, `test_encounter_pipeline.py`, ...).
- **Keep the layers clean**: imports point downward only
  (`data -> preprocess -> physics -> analysis -> visualization -> app`).
  The GUI and CLI must not contain scientific logic.
- **Document any numerical change**: if a change can alter results, note it
  in `docs/MIGRATION_SCIENCE.md` so conclusions stay traceable.
- **No generated artefacts in commits**: `.venv/`, caches and build outputs
  are ignored by `.gitignore`; keep them out of the repository.

## Reporting issues

Include the version (`cmemoss.__version__`), the exact command or GUI inputs,
the full traceback, and (if relevant) the expected vs. actual result.
