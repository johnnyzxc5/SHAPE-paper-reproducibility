# Reproduction levels

## A — inspect the paper evidence now

Open `evidence/final/tables/T02_E0_overall.csv`, the adjacent class/stratification tables, `evidence/joint/10_regional_master_table.csv` and `evidence/joint/figures/regional/`. All four CWT methods, including GMO, are present. `evidence/paper_figures/` contains the five PDFs referenced by the current manuscript, exported without TeX. No values were recalculated. Individual final evaluation metrics, original index and resolved configurations are under `metadata/AI/`.

`evidence/final/predictions/` now contains the canonical E0 Primary, E2-B and E4 prediction tables, including labels, probabilities and existing stratification fields, plus three frozen E0 per-seed summaries. These permit inspection of the inputs behind the reported aggregates without rerunning a classifier. The same trajectories recur across training seeds and, for E4, conditions; prediction rows are not independent physical runs. See the directory README before interpreting identities and paths.

## B — frozen model evaluation, conditional

The source and model identities are included, but checkpoints and HDF5 inputs are external. Their local existence/bytes are recorded in inventories. PRIMARY/E2B evaluation can be attempted after these inputs and a compatible environment are available. This assembly proves file identity and metadata links, not equivalent inference on a new host. E4 additionally requires offline tensor restaging and its frozen calibration/index agreement. No frozen-model evaluation was run here.

## C — complete regeneration/training, conditional

**2026-10-11 addition:** [FROM_SEEDS.md](FROM_SEEDS.md) describes a new standalone route that generates production/Pilot trajectories from packaged seeds and uses numerical fingerprints instead of external Pilot HDF5. It prepares all 30 recorded training configurations, new E4 calibration and core analysis paths. Static checks passed; no scientific stage was executed. The restoration instructions below describe the preserved historical launchers, which remain available separately.

Restore trajectories and Pilot fixtures, qualify the host, verify manifests/binding, run the clean campaign, index outputs, train the 30 configurations, evaluate and perform the offline E4 stage. See simulation and AI guides. Source supplements for generation are included, but prospective regeneration must use a new writable copy because it writes binding/receipts. Frozen trajectories are the reliable replay inputs; seeds alone do not guarantee identical files or acceptance on another environment. No universal hardware, runtime, or bit-for-bit guarantee is made.

## Analysis scripts

The subsequent joint/regional analysis is outside the original AI package. Its two main scripts match the hashes recorded in their provenance receipts. Original plotting sources and source-to-output tables are retained, including the representation comparison tables. `analysis/` contains original source, not an automatic pipeline: scripts have hard-coded historical input/output roots, manuscript hash checks, directory-name assertions, and some top-level execution. They must be staged in a separate writable analysis workspace with reviewed path-only changes before reuse. Do not import them or direct their outputs to frozen evidence. No figure regeneration or statistical aggregation was executed here.

The three canonical prediction tables and E0 per-seed summaries are included in this repository. Other original analysis inputs remain externally inventoried. Analysis-path adaptation is still pending: copying predictions does not make the preserved scripts portable or remove their additional input requirements. Viewing already frozen outputs requires no adaptation or recomputation. Historical solver comparison and ratification evidence is listed in `docs/EVIDENCE_COMPLETION.md`; it documents the reported configuration, not a new numerical-convergence experiment.
