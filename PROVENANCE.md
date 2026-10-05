# Provenance and assembly boundary

Assembled locally on 2026-10-05. Original repositories, manuscript, production data, portables and frozen evidence were read only. The destination did not contain pre-existing work. The source Git object store was not repaired, reset, fetched or changed.

## Source selection

| Component | Selected source | Basis |
|---|---|---|
| Simulation/runtime closure | `C:\KinovaProductionBundleComplete\KINOVA_PRODUCTION_RELEASE_OPERATIONAL_HOST_CONCURRENCY_5b4d099` | All 10,218 manifest entries verified. Manifest SHA-256 `30aa2f51cfe238b33134d17e3f5daf3b69731af471c5b882c5d09353ade5f435`; host-portable verification copy has same manifest and also verifies |
| Scientific protected files | Same portable and `production_spec.m` | 12 protected source/binary SHA checks retained; source/manifest identity established, runtime not executed |
| Generator | Portable sequential generator | Six source hashes and canonical composite hash match the frozen qualification receipt; readable scientific commit instead contains an older generator |
| MEX builder/generation supplements and missing contracts | Readable scientific blobs where available, otherwise individually hashed historical working files | Per-file source kind in `provenance/source_files.json`; no claim that absent files came from the commit |
| AI | Historical `Fault_Diagnosis/shape_ai` working tree | Complete later E4 bridge retained. Text-normalized training/model/config sources agree with f7f183f; later data/evaluator changes and new E4 code are explicitly compared |
| E4 MATLAB bridge | Historical `Code_Image/+shape` working files | Runtime calls inspected; same shared residual/representation backend preserved. Exact historical execution tree not completely recoverable |
| Frozen results | `KINOVA_FINAL_ANALYSIS_ANTIGRAVITY` | Selected scientific CSVs and final PDFs copied without recalculation |
| Later regional analysis | `KINOVA_JOINT_SEVERITY_EXCITATION_AUDIT` | Both main script hashes match their recorded receipts; full GMO-inclusive tables/maps retained |
| Paper-specific graphics | Five existing PDFs referenced by `Final_Report.tex` | Byte-copy export only; no manuscript or LaTeX copied |

## Scientific versus operational differences

`provenance/simulation_comparison.json` compares 146 portable Code_Image/docs files with readable objects at `5b4d099...`: 120 byte-identical, 12 byte-different, 14 absent. Some differences are line endings, explicitly distinguished by normalized comparison. Portable additions change worker-local Simulink file-generation, host identity/exact concurrency receipts, environment detection and qualification policy. Protected residual, CWT, plant RHS, controller and serializer bytes remain unchanged.

The generator discrepancy is scientific source recovery, not merely a portability patch: the commit blob implements an older 5-second trajectory interface; the portable implements the qualified 10-second sequential distribution. Its receipt-bound identity is verified in `generator_identity.json`. Several contracts and builder helpers are absent at the declared commit and supplied from the working tree with that limitation recorded. The COMPLETE portable has 10,210 payload entries; the selected operational portable has 10,218. Both verify against their own manifests. Names/dates did not determine the selection.

`provenance/ai_comparison.json` and `ai_diff.txt` distinguish line-ending differences from semantic changes after `f7f183f`. Added E4 code uses persistent MATLAB staging and accepted evaluator batch boundaries; `data.py` adds optional batch samplers and `evaluate.py` accepts prepared loaders. Training metadata does not contain a per-file execution-source hash manifest. Checkpoint/config/index links are verified; full source-at-run identity remains only partially established. The calibration's `f86ad963...` object is unreadable.

## Packaging adaptations

No copied scientific code was refactored, renamed or edited. Root `Code_Image`, `Fault_Diagnosis/shape_ai` and executable `docs` paths are kept. New documentation and `tools/` are separate. `prepare_ai_config.py` changes only paths in a new derived configuration. `.gitattributes` disables line-ending conversion so Git preserves source bytes. Original absolute paths remain in immutable provenance/config records for traceability and require review before eventual public distribution. No credentials were intentionally copied; static scanning scope and results are recorded separately.

Large trajectories, Pilot fixtures, HDF5 and checkpoints stay external, with byte sizes and SHA-256 inventories. Canonical prediction tables are included by the evidence addition described below. The upstream full-payload manifest is preserved under `provenance/upstream/`; it is not a claim that its entire payload is included in Git. Venvs, caches, generated compilation trees (except the frozen observer binary), legacy notebooks, draft reports, TeX and internal editorial notes were excluded.

`provenance/source_files.json` records copied-file origins; `provenance/SHA256SUMS.txt` seals the delivered tracked payload, excluding itself and ignored runtime directories. Its companion source-preservation report hashes copied local originals again and checks the manuscript and sampled Git administrative files. This is scoped verification, not a claim to hash every unrelated byte of the historical repository.

## Evidence addition — 2026-10-05

Ten existing evidence files were copied without recalculation: four historical solver records from the original project and six frozen prediction/summary files from the final analysis workspace. Exact origins, sizes, hashes and inspected Parquet column names are in `provenance/evidence_completion_20261005.json`; `source_files.json` includes the new origins. The solver files are attributed to their inspected historical files, not automatically to commit `5b4d099`. The original solver substudy's OPEN status predates the later P5 ratification and freeze. The addition documents this sequence without editing any historical record. It does not recover the entire historical execution tree or claim a new solver-convergence result.
