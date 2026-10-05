# SHAPE paper reproducibility — local assembly

Companion code and frozen evidence for *Energy-Based Fault Detection and Isolation Framework for Flat Port-Hamiltonian Mechanical Systems*. This independently initialized repository was assembled on 2026-10-05 and delivered to a private GitHub repository. No public release or DOI has been issued. The author has not selected a project license.

Start with [reproduction scope](docs/REPRODUCTION.md) and the [paper-to-artifact map](docs/PAPER_MAP.md).

| Level | Available in this repository | Boundary |
|---|---|---|
| A — inspect frozen results | Canonical E0/E2-B/E4 predictions, selected CSVs, final PDFs, full regional maps including GMO, run/configuration metadata | Available now; no numerical recomputation required. Reaggregating metrics is a separate analysis step |
| B — evaluate frozen models | Evaluator and verified checkpoint identities | Checkpoints and HDF5 inputs exist locally outside Git; restore/access them first. E4 tensors were temporary and must be restaged offline. Evaluation is NOT_RUN in this assembly |
| C — regenerate and train | Simulation, trajectory generator, qualification, residual/representation code, six AI pipelines | Requires external trajectories/Pilot fixtures, licensed MATLAB, qualified host and substantial compute. NOT_RUN; no claim of cross-host bit identity or fixed runtime |

```text
Code_Image/                  canonical MATLAB/Simulink layout, +shape, mr, MEX
Fault_Diagnosis/shape_ai/    current package, original configs/scripts/tests
docs/                       user guides + selected executable upstream contracts
metadata/AI/                frozen resolved configs, environment/evaluation records, indexes
evidence/                   frozen predictions, final CSVs, regional PDFs and paper figures
analysis/                   identified original analysis/figure scripts (not executed)
provenance/                 source comparisons, external inventories, validation records
tools/                      safe byte-integrity check and path-only config adapter
third_party/                recovered upstream Modern Robotics notice
```

Safe, standard-library-only entry point from the repository root:

```powershell
python tools/verify_repository.py
```

This checks packaged bytes only. It does not run MATLAB, infer predictions or recalculate metrics. See [simulation](docs/SIMULATION.md), [AI](docs/AI.md), [environment](docs/ENVIRONMENT.md), [external artifacts](docs/EXTERNAL_ARTIFACTS.md), [provenance](PROVENANCE.md), and [validation](docs/VALIDATION.md).

Frozen code is preserved byte for byte. Historical path defaults and upstream host guides remain inside it; use the new guides before invoking an upstream launcher. Installing the Python package does not start a campaign. Original analysis scripts may execute work on import and contain absolute paths: do not import/run them unchanged.

The [evidence completion note](docs/EVIDENCE_COMPLETION.md) documents the added canonical predictions and historical solver comparison/ratification records. The original assembly report remains a dated record; this addition does not qualify a new host or claim that the scientific campaign has been rerun.
