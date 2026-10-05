# 08_OBSERVER_GAIN_AUTHORITY: Mathematical & Empirical Provenance for GMO and EO Observer Gains

**Document ID:** `docs/codex_active/08_OBSERVER_GAIN_AUTHORITY.md`  
**Frozen Parameters:** $K_O = 100.0\,\mathrm{s}^{-1}$ (GMO), $k_O = 100.0\,\mathrm{s}^{-1}$ (EO-A)  

---

## 1. Generalized Momentum Observer ($K_O = 100.0\,\mathrm{s}^{-1}$)
* **Role & Filter Dynamics:** GMO is a first-order low-pass estimator: $H(s) = \frac{K_O}{s + K_O}$ with cutoff frequency $f_c = \frac{K_O}{2\pi} = 15.9155\,\mathrm{Hz}$ and time constant $\tau = 10.0\,\mathrm{ms}$.
* **Candidate Gain Sweep:** Evaluated across $K_O \in \{10, 25, 35, 50, 75, 100, 150, 200\}\,\mathrm{s}^{-1}$ in `OBSERVER_GAIN_SWEEP.csv`.
* **Selection Criteria:**
  1. **E2 Vibration Transmission:** At low gains ($35	ext{--}50\,\mathrm{s}^{-1}$), high-frequency vibration harmonics ($25	ext{--}30\,\mathrm{Hz}$) suffer severe attenuation ($-10.36$ to $-14.77\,\mathrm{dB}$), wiping out up to $93.7\%$ of spectral energy in the CWT scalogram.
  2. **E4 Noise Amplification:** At high gains ($150	ext{--}200\,\mathrm{s}^{-1}$), encoder derivative noise is amplified, producing severe startup spikes ($> 52.79\,\mathrm{Nm}$).
  3. **Optimal Compromise:** $K_O = 100\,\mathrm{s}^{-1}$ limits attenuation to $< 2.2\,\mathrm{dB}$ at $15\,\mathrm{Hz}$ and $< 5.7\,\mathrm{dB}$ at $30\,\mathrm{Hz}$, while holding startup transient to $25.15\,\mathrm{Nm}$.

---

## 2. Energy Observer ($k_O = 100.0\,\mathrm{s}^{-1}$)
* **Role & Filter Dynamics:** EO monitors scalar kinetic energy balance.
* **Formulation:** EO-A kinetic balance (Haddadin et al. 2017 Eq. 28) eliminates potential energy computation.
* **Selection Criteria:** Evaluated independently across $k_O \in \{10\dots200\}\,\mathrm{s}^{-1}$. $k_O = 100\,\mathrm{s}^{-1}$ matches the first-order observer bandwidth ($15.92\,\mathrm{Hz}$), providing balanced sensitivity across all 4 fault classes without derivative jitter on total power.
* **Independent Verification:** Both gains were frozen *a priori* by Johnny (`DEC-25`) based on continuous control theory, strictly independent of downstream CNN accuracy.
