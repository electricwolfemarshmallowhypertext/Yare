# RELEASE_CHECKLIST

## Yare v0.2.0 RC

- [ ] Run local syntax check:
  - `python -m py_compile cli/yare.py`
- [ ] Run local CLI tests:
  - `python -m pytest -q tests/yare/test_yare_cli.py`
- [ ] Run demo proof script:
  - `.\scripts\demo-lead-compile.ps1`
- [ ] Verify GitHub Actions workflow run is green:
  - `Yare Lead Demo` (`.github/workflows/yare-lead-demo.yml`)
- [ ] Verify workflow artifact upload contains:
  - `.sticky/current-state.json`
  - `.sticky/current-state.md`
  - `.sticky/receipts/*.jsonl`
- [ ] Confirm clean git status:
  - `git status --short`
- [ ] Create tag only after CI pass:
  - `git tag v0.2.0`
