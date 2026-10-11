# Preserved analysis sources

These are selected original final analysis/plotting scripts. They were copied, statically parsed and never imported/executed. The two joint/regional main scripts have verified execution-provenance hashes. Consult `docs/PAPER_MAP.md` for inputs and existing outputs.

Historical roots, folder-name assertions, manuscript integrity checks and top-level output creation remain unchanged. Their presence is not permission to write to original workspaces. The core E0–E4 adapter below uses a separate new analysis workspace; historical report/layout adaptations remain separate. Do not use preserved scripts as install/import hooks. Existing E0/E1/E2/E3/E4 results can be inspected without running any script.

The canonical E0 Primary, E2-B and E4 prediction tables are included in `evidence/final/predictions/`. They were copied byte for byte, not produced by running these scripts during assembly. Review all additional inputs and output destinations before any future reaggregation; the presence of the Parquet files alone does not make the original scripts runnable in this layout.

# Portable prospective analysis

`tools/reproduce_tables.py` adapts copied E0–E4 scripts to a newly generated campaign's predictions and fits new E3 train quartiles. It preserves the original files and calculations, writes new core tables/figures and joint numerical summaries, and executes only with `--execute`. Default planning and source checks were tested; aggregation was NOT_RUN. See [FROM_SEEDS](../docs/FROM_SEEDS.md). Historical report/layout scripts remain separate from this route.
