# 13_OBSERVER_CTDQ_BACKEND_AUTHORITY

Human promotion decision: `finite_difference_batch_mex`, version `p1b-fd-central-h1e-6-v1`, is approved as numerically equivalent to the unchanged `finite_difference_gold` algorithm inside the qualified environment below. It is the preferred backend only when the complete environment check and startup self-test pass.

Qualified boundary:

- Windows `win64`
- MATLAB `26.1.0.3312084 (R2026a) Update 4`
- MATLAB Coder `26.1`
- MinGW64 Compiler (C++) `14.2.0`
- source SHA-256 `b99e2a6b3185a6af0f4f8db7b720fe5dfa4f90b4bb45c4c6b28b978c6d7e13c0`
- qualified MEX SHA-256 `9dda22245d4f649854c9f3b7f9ad04527e288a2342ef5468c5a70020ddf12f5c`
- qualification boundary: 24/24 Pilot V2 parents, 1,440,144 scalar comparisons, maximum error `2.220446049e-9 N*m`, global RMSE `1.121612074e-10 N*m`, GMO/EO GATE-03 PASS, and downstream M03/M04 PASS.

Outside that boundary, or when hash/load/version/self-test validation fails, execution must use `finite_difference_gold`. Fallback must be explicit in output provenance and must never be silent. `finite_difference_gold` remains the scientific oracle. This promotion changes no GMO/EO equation or gain.

Every future output records requested/actual backend, backend/source version, MEX and source hashes, self-test status, and fallback status/reason. The single historical MATLAB teardown access violation after completed P1B receipt generation is an `ENGINEERING_WATCH_ITEM`, not a scientific failure; recurrence must be logged by future benchmark runners.
