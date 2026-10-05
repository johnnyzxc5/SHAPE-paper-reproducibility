# 09_PHYSICAL_NORMALIZATION_CONTRACT: Continuous Hardware Normalization Specification

**Document ID:** `docs/codex_active/09_PHYSICAL_NORMALIZATION_CONTRACT.md`  

---

## 1. Fundamental Scientific Rationale
Physical normalization is executed **generator-side BEFORE Continuous Wavelet Transformation**.
* **Preservation of Relative Fault Severity:** Multiplying a fault by factor $a$ produces an exact vertical additive decibel shift $\Delta X_{\log} \approx 20\log_{10}(a)\,\mathrm{dB}$ in log-power.
* **Zero Data Leakage:** Scaling constants are fixed hardware parameters known *a priori*. They do not depend on realized sample distributions or dataset statistics.
* **Prohibition:** Sample-wise normalization (`mat2gray`, per-sample min-max) is strictly forbidden.

---

## 2. Exact Normalization Constants

| Physical Channel | Normalization Parameter | Numerical Constant | Dimensionless Scaled Residual |
|:---|:---|:---:|:---|
| **SHAPE Joints 1–3** | Peak Power $P_{\mathrm{ref}, 1..3} = \tau_{\max, 1} \dot{q}_{\max, 1}$ | **$54.45427\,\mathrm{W}$** | $r_{\mathrm{SHAPE}, j} / 54.45427$ |
| **SHAPE Joints 4–6** | Peak Power $P_{\mathrm{ref}, 4..6} = \tau_{\max, 4} \dot{q}_{\max, 4}$ | **$10.99557\,\mathrm{W}$** | $r_{\mathrm{SHAPE}, j} / 10.99557$ |
| **Torque Joints 1–3** | Peak Continuous Torque $\tau_{\max, 1..3}$ | **$39.0\,\mathrm{N\cdot m}$** | $r_{\tau, j} / 39.0$ |
| **Torque Joints 4–6** | Peak Continuous Torque $\tau_{\max, 4..6}$ | **$9.0\,\mathrm{N\cdot m}$** | $r_{\tau, j} / 9.0$ |
| **GMO Joints 1–3** | Peak Continuous Torque $\tau_{\max, 1..3}$ | **$39.0\,\mathrm{N\cdot m}$** | $r_{\mathrm{GMO}, j} / 39.0$ |
| **GMO Joints 4–6** | Peak Continuous Torque $\tau_{\max, 4..6}$ | **$9.0\,\mathrm{N\cdot m}$** | $r_{\mathrm{GMO}, j} / 9.0$ |
| **Energy Observer** | Total Articulated Robot Power $P_{\mathrm{robot\_ref}}$ | **$196.3495\,\mathrm{W}$** | $r_E / 196.3495$ |

---

## 3. Boundary with Nico-Side Standardization
* **Generator:** Delivers unquantized float32 tensors with fixed physical normalization.
* **Nico Team:** If statistical standardization (mean zero, variance unit) is desired for neural network training, parameters $\mu, \sigma$ must be computed **strictly on the Train partition** and applied frozen to Val and Test.
