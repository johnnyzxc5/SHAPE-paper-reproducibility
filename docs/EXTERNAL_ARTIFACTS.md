# External artifacts and distribution

The large artifact groups in the following table remain at their original local locations. No public download URL, release, upload, LFS configuration or asset archive was created. Sizes below are measured bytes, with decimal GB for comparison.

| Group | File count | Bytes | GB |
|---|---:|---:|---:|
| Pilot fixtures | 6 | 40,133,263 | 0.040 |
| production qualification JSON | 5,030 | 12,104,623 | 0.012 |
| production MAT | 5,030 | 9,436,587,887 | 9.437 |
| PRIMARY | 20,000 | 361,518,853,632 | 361.519 |
| E2B | 300 | 5,422,858,712 | 5.423 |
| checkpoints | 30 | 205,279,244 | 0.205 |
| E4_stage | 0 | 0 | 0.000 |

`provenance/external_portable_inventory.json` records each portable fixture's exact relative restore path, local source, bytes and SHA-256. All bytes were verified against the manifest in all three candidate portable directories. `provenance/external_production_files.csv` contains fresh SHA-256 hashes of all 20,300 PRIMARY/E2B HDF5 files and 30 best checkpoints, read as bytes only. No tensor values or metrics were recalculated. These are selected canonical artifacts, not every duplicate, cache, last checkpoint or benchmark in production storage.

`provenance/external_analysis_inventory.json` is the original inventory of prediction tables and analysis inputs, preserved unchanged. Six of its entries are now also included under `evidence/final/predictions/`: the three canonical prediction tables and the three E0 per-seed summary CSVs. Their delivered paths and hashes are recorded in `provenance/evidence_completion_20261005.json`. Other inventory entries remain external; their presence in the inventory is not a download link. The retained aggregate tables and PDFs remain available for level A viewing.

## Local access / restoration

For simulation, restore `data/trajectory_registry/production/`, the Pilot MAT/JSON pairs and `pilot24_outputs/` according to the portable inventory, under a disposable execution copy. Use a copy tool that refuses conflicts and verify hashes before any qualification. Do not rename the bound manifest or fixture paths. The upstream `PORTABLE_RELEASE_MANIFEST.json` describes the full original payload; it is preserved as evidence under `provenance/upstream`, not used as the new repository inventory.

For AI, the original index already references local HDF5 under `C:\KinovaProduction`; the 30 best checkpoints live under its `AI/runs` subtree. New results must use separate writable paths. No external file was altered or linked into the new tree. For another machine, arrange access/download and resolve path binding as described in `AI.md`. E4's final index preserves identities, not permanent staged tensor paths; zero stage HDF5 files remain in the canonical stage directory. Restaging is pending scientific work, not a missing published asset link.

## Hosting constraints checked 2026-10-05

GitHub blocks ordinary Git files larger than 100 MiB and recommends small repositories, ideally below 1 GB and strongly below 5 GB. The report's blanket 2 GB repository limit is not the stated rule. [Official large-file guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).

The dedicated releases documentation states up to 1,000 assets per release and each asset under 2 GiB. A single approximately 9 GB trajectory archive would violate that documented per-asset limit. The large-file page separately refers to plan-dependent LFS maximums; use the conservative dedicated release limit and recheck the chosen hosting account before publishing. [Official release constraints](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

Potential distribution therefore requires independently verifiable split assets below the confirmed provider limit or a research data host. The author must choose hosting, redistribution rights, dataset/checkpoint scope, retention and any DOI policy. No scheme has been implemented and no download links are invented. The complete campaign is hundreds of GB; do not infer transfer/storage feasibility from trajectory size alone.
