# Final Integrated Production Regression

This harness executes a disposable, isolated regression of the frozen production stack. It does not authorize production and never writes into the future production dataset root or the frozen trajectory registry.

The runner performs a fail-closed preflight, prints the exact deterministic parent selection, starts an eight-process pool, executes the 72 selected physical records once, then dispatches the same records a second time through the canonical `shape.run_record` resume path. The second phase must execute zero physical simulations and leave every HDF5 SHA-256 unchanged.

Run exactly:

```powershell
Set-Location 'C:\Users\Johnny\Desktop\Git\Image Processing Project'; & matlab -batch "addpath('Code_Image'); result = run_final_integrated_production_regression();" 2>&1 | Tee-Object -FilePath 'docs\codex_final_integrated_production_regression\console.log'
```

Return these files for independent review:

- `docs/codex_final_integrated_production_regression/FINAL_INTEGRATED_PRODUCTION_REGRESSION_RECEIPT.json`
- `docs/codex_final_integrated_production_regression/console.log`

Regression HDF5 files are written beneath a unique timestamped directory in `outputs_integrated_production_regression/`.

