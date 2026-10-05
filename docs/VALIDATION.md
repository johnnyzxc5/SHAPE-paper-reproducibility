# Validation record — 2026-10-05

| Check | Result | Exact scope |
|---|---|---|
| Three portable manifests | PASS | 10,210 COMPLETE and 10,218 entries in each operational copy; all files rehashed; zero mismatches |
| Frozen protected authorities | PASS | 12 exact source/binary hashes from production_spec |
| Generator binding | PASS | Six source hashes plus canonical composite hash match receipt; all 5,030 qualification JSONs identify that generator and PASS |
| MATLAB package closure | PASS (static scope) | No unresolved `shape.function(...)` calls in included MATLAB and executable docs; not a full MATLAB dependency analyzer |
| Scientific metadata | PASS | 20,000 PRIMARY + 300 E2B manifest rows; 5,030 binding rows; original index paths exist; E4 index and calibration membership/hash inspected |
| Checkpoint links | PASS | 30 best checkpoints match PRIMARY/E2B evaluation metadata; applicable 20 match E4; no deserialization/inference |
| Main joint/regional script identity | PASS | Both files match their respective recorded execution SHA-256 |
| Python syntax and text scan | PASS | AST only; static_review.json records scope; no known credential-pattern hits |
| Safe unit tests | PASS | 16 passed, 2 deselected in the selected files, 17.07 s; three model-forward tests not selected |
| Source preservation | PASS | Copied local source files, manuscript and sampled Git administrative files rehashed; no changes; scientific copies byte-identical |
| MATLAB STATIC / MEX self-test / Q1 | NOT_RUN | Requires runtime/numerical execution; this assembly uses byte and source checks only |
| PHYSICAL / Q2 / production / trajectory regeneration | NOT_RUN | Explicitly outside authorized validation scope |
| Training / frozen inference / E4 restaging / scientific postprocessing | NOT_RUN | No new numerical results requested or produced |

Safe tests inspected before execution: contracts, lazy indexing, synthetic calibration membership/identity, E4 job bookkeeping and mocked MATLAB/evaluation paths. `test_models.py` (three forward passes), `test_reused_loader_matches_ordinary_evaluator` (actual model inference), and `test_partial_worker_stage_is_removed_before_resume` (possible real MATLAB startup despite mocked staging) were NOT_RUN. Thus the old “21 passed” report is not claimed as a fresh full-suite result.

The first safe-test attempt failed during fixture setup because the new temporary parent directory was absent (5 tests passed, 11 fixture errors). Creating that directory and rerunning produced the passing result above; no scientific implementation was changed. Test logs are in `provenance/safe_tests.txt`. The existing environment was used read only with bytecode/cache disabled, imported package source pointed to the new copy, and test fixture writes confined to the new repository's ignored work directory.

Re-run the safe subset from a prepared environment with `PYTHONPATH` pointing to `Fault_Diagnosis/shape_ai/src`, `PYTHONDONTWRITEBYTECODE=1`, and an existing `work` parent:

```powershell
python -B -m pytest -ra -p no:cacheprovider Fault_Diagnosis/shape_ai/tests/test_contracts.py Fault_Diagnosis/shape_ai/tests/test_indexing.py Fault_Diagnosis/shape_ai/tests/test_e4_production.py -k 'not reused_loader_matches_ordinary_evaluator and not partial_worker_stage_is_removed_before_resume' --basetemp work/pytest_safe_new
```

Use a fresh temporary path. A test pass does not qualify a host or reproduce paper metrics. `python tools/verify_repository.py` is the standard-library-only check of delivered bytes. No scientific check was disabled to achieve a preflight pass.

The Git whitespace check reports retained source whitespace (and CRLF when CR-at-EOL is not recognized). This is not a scientific or byte-integrity failure. Frozen files were not reformatted to satisfy a whitespace lint rule; their exact upstream bytes take precedence.

## Evidence-completion validation — 2026-10-05

The 669-file baseline seal passed before the addition. Ten files were copied byte for byte: four existing solver records and six frozen prediction/summary tables. The six prediction/summary hashes agree with the assembly-time external analysis inventory. Source and destination hashes are recorded in `provenance/evidence_completion_20261005.json`; only Parquet schemas were inspected, with no metric aggregation. The package seal was refreshed for the added evidence and documentation and is checked by the same standard-library verifier. Original scientific files and manuscript were preserved. No executable code changed, so the 16 historical safe-test passes were not rerun or relabeled as fresh tests. See `docs/EVIDENCE_COMPLETION.md` for remaining publication and execution boundaries.
