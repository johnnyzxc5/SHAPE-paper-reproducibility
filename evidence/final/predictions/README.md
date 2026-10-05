# Frozen prediction evidence

These files are byte-for-byte copies of previously verified final-analysis outputs. No simulation, training, inference, metric aggregation or figure generation was performed to include them.

| File | Scope |
|---|---|
| `canonical_e0_primary.parquet` | Frozen clean Primary test predictions for the six evaluated pipelines and five training seeds |
| `canonical_e2b.parquet` | Frozen predictions for the controlled E2-B frequency sweep |
| `canonical_e4.parquet` | Frozen predictions under the ten E4 offline perturbation conditions |
| `e0_metrics_by_seed.csv` | Existing E0 overall metrics by training seed |
| `e0_per_class_by_seed.csv` | Existing E0 per-class summaries by training seed |
| `e0_binary_by_seed.csv` | Existing E0 binary diagnostic summaries by training seed |

The prediction files contain existing true/predicted class labels, probabilities, identifiers and stratification fields. E4 also records the perturbation condition and clean-run identity. A prediction row is a seed-run evaluation, not a new independent simulated trajectory; E4 also repeats trajectories across conditions. Use the appropriate pipeline, seed, condition and run identity when aligning records. Preserve parent-group relationships for any separately authorized statistical work.

Historical `path`, `checkpoint` and E4 `clean_path` columns are retained as provenance; they are not portable download locations. Do not rewrite frozen bytes to update paths. No sensor records of people are involved; these are simulated robot trajectories. The schema inspection does not constitute a general privacy or redistribution-rights certification.

`provenance/evidence_completion_20261005.json` records source paths, exact bytes, hashes and column names. The six files match the corresponding original `provenance/external_analysis_inventory.json` hashes, which is preserved as an assembly-time inventory. The three Parquet files total 61,514,904 bytes. The original files remain unchanged at their source locations.

Viewing these records does not require model checkpoints. Running frozen classifiers still requires external checkpoints and HDF5 inputs. The original analysis scripts retain additional inputs, absolute paths and output side effects: see `analysis/README.md` before attempting reaggregation in a separate writable workspace.
