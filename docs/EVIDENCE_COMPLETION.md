# Evidence completion — 2026-10-05

This addition completes the specifically identified evidence omissions in the local paper package. It does not declare the full scientific campaign independently reproduced or the repository published. The original assembly report and its test results remain historical records.

## Frozen predictions now included

The three canonical E0 Primary, E2-B and E4 Parquet tables, plus the three E0 per-seed summary CSVs, are under `evidence/final/predictions/`. All six copies match the hashes already recorded in the original external analysis inventory. They support inspection of the saved prediction evidence without running the CNN. No predictions, statistics or plots were recomputed. Parquet inspection was limited to schemas.

## Solver evidence now included

| File | Role |
|---|---|
| `docs/codex_pilot24_v2/08_SOLVER_SUBSTUDY.md` | Historical matched comparison of the 1-ms maximum-step configuration and the automatic alternative |
| `docs/codex_pilot24_v2/solver_substudy/solver_substudy_metrics.csv` | Existing numerical comparison table used by that report |
| `docs/codex_postpilot_p5/P5_SOLVER_RATIFICATION_RECEIPT.json` | Later assessment of the existing solver evidence and execution semantics |
| `docs/codex_postpilot_p5/P5_SOLVER_FREEZE_RECEIPT.json` | Subsequent recorded ratification/freeze transition |

The substudy's final OPEN wording is a historical status, not the final configuration decision. Read it with the later ratification and freeze receipts. Those records retain `ode45`, `RelTol=1e-6`, `AbsTol=1e-8`, `MaxStep=0.001`, inherited/continuous controller execution and an internal MPC prediction grid of 0.05 s. The grid is not a periodic controller-update schedule.

The original comparison found differences in commanded torque and diagnostic residuals under the automatic-step alternative. Its records support retaining the reported configuration; they do not establish step-refinement convergence or invariance of classifier predictions. No solver was run during this addition. Other historical paths named inside the receipts are retained as provenance and are not all included; this is a selected evidence package, not the complete development history.

## Validation and scope

- The existing 669-file seal was verified before copying any evidence.
- Ten added source files were copied without edits; source and destination SHA-256 values match.
- Frozen scientific code, original data and `Final_Report.tex` were not modified.
- The source-origin index, paper map, reproduction guide and package seal were updated for this addition.
- No new simulations, training, inference, metric recalculation or runtime benchmarking occurred. The original 16 safe tests were not rerun because no executable code changed.

Machine-readable provenance is in `provenance/evidence_completion_20261005.json`. Run `python tools/verify_repository.py` for the current byte seal.

## Remaining release and execution requirements

This is a local addition; no remote, public release, DOI or project license was created. The author still needs to decide licensing/distribution and public access. Large trajectories, HDF5 inputs and checkpoints remain external; E4 tensor restaging and host qualification are still required before a new evaluation. The preserved analysis scripts need reviewed path adaptation and their remaining inputs before reaggregation. These execution boundaries are not removed by including frozen predictions.
