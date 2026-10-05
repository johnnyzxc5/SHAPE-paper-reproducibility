# 01_FINAL_SCIENTIFIC_DATA_GENERATOR_CONTRACT: Master Scientific Specification for the SHAPE Benchmark Data Generator

**Document ID:** `docs/codex_active/01_FINAL_SCIENTIFIC_DATA_GENERATOR_CONTRACT.md`  
**Governing Authority:** SHAPE Benchmark Governance Team & Antigravity  
**Target Platform:** Kinova Gen3 Ultra-Lightweight 6-DOF Industrial Manipulator  
**Status:** **`FORMALLY RATIFIED & BINDING TIER-0 SPECIFICATION`**  

---

## 1. Physical Manipulator Model & Hardware Limits

The equations of motion for the Kinova Gen3 6-DOF rigid manipulator are:
$$M_{\mathrm{total}}(q)\ddot{q} + C(q, \dot{q})\dot{q} + g(q) + \tau_f(\dot{q}) = \tau_{\mathrm{applied}}$$
where:
* $M_{\mathrm{total}}(q) = M_{\mathrm{geo}}(q) + J_{\mathrm{rotors}}$ is the total effective manipulator inertia matrix.
* Constant reflected actuator rotor inertia:
  $$J_{\mathrm{rotors}} = \operatorname{diag}([0.172,\; 0.172,\; 0.172,\; 0.089,\; 0.089,\; 0.089])\,\mathrm{kg\cdot m^2}$$
* Coriolis and centrifugal matrix $C(q, \dot{q})$ satisfies the Christoffel antisymmetry property: $\dot{M} - 2C = -(\dot{M} - 2C)^T$.
* Gravitational torque vector $g(q)$ with $g_0 = 9.80665\,\mathrm{m/s^2}$ along $-Z$.
* Nominal friction model: $\tau_{f,\mathrm{nom}, j}(\dot{q}_j) = F_{c,\mathrm{nom}, j}\tanh(50\dot{q}_j) + F_{v,\mathrm{nom}, j}\dot{q}_j$ with $F_{c,\mathrm{nom}, 2} = 2.15\,\mathrm{N\cdot m}$.

### Fixed Hardware Continuous Operating Limits:
* **Joints 1–3 (Base, Shoulder, Elbow):** $\tau_{\max} = 39.0\,\mathrm{N\cdot m}$, $\dot{q}_{\max} = 1.3962634016\,\mathrm{rad/s}$ ($80.0^\circ/\mathrm{s}$), $P_{\mathrm{ref}} = 54.4543\,\mathrm{W}$.
* **Joints 4–6 (Wrist 1, 2, 3):** $\tau_{\max} = 9.0\,\mathrm{N\cdot m}$, $\dot{q}_{\max} = 1.2217304764\,\mathrm{rad/s}$ ($70.0^\circ/\mathrm{s}$), $P_{\mathrm{ref}} = 10.9956\,\mathrm{W}$.
* **Total Articulated Robot Capacity:** $P_{\mathrm{robot\_ref}} = 3(54.4543) + 3(10.9956) = 196.3495\,\mathrm{W}$.

---

## 2. Flatness-MPC Trajectory Generation & Simulation Semantics

1. **Trajectory Window:** Strictly $T_{\mathrm{window}} = 10.0\,\mathrm{s}$, $F_s = 1000\,\mathrm{Hz}$ ($T_s = 1.0\,\mathrm{ms}$), exactly $N_t = 10{,}001$ timesteps ($t \in [0.000, 10.000]\,\mathrm{s}$).
2. **Knot Modes:** $K_{\mathrm{segments}} \in \{2, 3\}$. Trajectory mode strictly balanced $50/50$ fly/stop per partition ($1{,}750/1{,}750$ Train, $375/375$ Val, $375/375$ Test). Sibling runs inherit parent mode.
3. **Solver Coupling:** Continuous variable-step `ode45` solver, `SampleTime = -1`, `ChartUpdate = 'INHERITED'` in Simulink. Active QP solver is MATLAB `quadprog` with preallocated options. Zero artificial discrete MPC aliasing.
4. **Planning Margins:** Trajectory optimization enforces $85\%$ margins against hardware limits.

---

## 3. Paired Counterfactual Campaign Architecture

* **Total Physical Campaign:** Exactly **$5{,}030$ unique physical parents** generating **$20{,}300$ physical runs** in MATLAB/Simulink:
  * **Primary Benchmark ($20,000$ runs):** $5{,}000$ unique parent geometries (disjoint IDs $1\dots5000$) $\times$ 4 physical classes (Nominal, LoE, Friction, Vibration). Grouped 70/15/15 by `parent_trajectory_id` ($14{,}000$ Train, $3{,}000$ Val, $3{,}000$ Test). Zero parent leakage.
  * **E2-B Frequency Supplement ($300$ runs):** Fixed amplitude $A_d = 1.0\,\mathrm{N\cdot m}$, exactly $30$ unique paired parent geometries (disjoint IDs $5001\dots5030$; $15$ fly / $15$ stop) $\times$ 10 discrete frequencies $\{2, 5, 8, 11, 14, 17, 20, 23, 26, 30\}\,\mathrm{Hz}$ per parent ($30 \times 10 = 300$ runs). All 10 frequency siblings inherit parent geometry, mode, and parameters.
  * **Combined Campaign Accounting Summary:**
    * Primary: $5{,}000$ unique parents ($20{,}000$ physical runs)
    * Paired E2-B: $30$ unique parents ($300$ physical runs)
    * Scientific Total: **$5{,}030$ unique physical parents**, **$20{,}300$ physical runs**.

---

## 4. Fault Injection Physics (Strictly Joint 2)

* **Onset Timing:** $t_{\mathrm{fault}} \sim \mathcal{U}(2.0, 5.0)\,\mathrm{s}$ sampled once per parent and shared across fault siblings. Pre-fault $[0, t_{\mathrm{fault}})$ is strictly nominal.
* **Class 0 (Nominal):** $\tau_{\mathrm{applied}} = \tau_{\mathrm{cmd}}$.
* **Class 1 (LoE):** $\tau_{\mathrm{applied}, 2}(t) = (1 - s_{\mathrm{LoE}})\tau_{\mathrm{cmd}, 2}(t)$ for $t \ge t_{\mathrm{fault}}$ with $s_{\mathrm{LoE}} \in [0.02, 0.30]$ ($\alpha = 1 - s_{\mathrm{LoE}} \in [0.70, 0.98]$).
* **Class 2 (Coulomb Friction):** $\tau_{\mathrm{applied}, 2}(t) = \tau_{\mathrm{cmd}, 2}(t) - \Delta F_c \tanh(50\dot{q}_2(t))$ for $t \ge t_{\mathrm{fault}}$ with $s_F \in [0.02, 1.50]$, $\Delta F_c = s_F \cdot F_{c,\mathrm{nom}, 2} \in [0.043, 3.225]\,\mathrm{N\cdot m}$.
* **Class 3 (Harmonic Vibration):** $\tau_{\mathrm{applied}, 2}(t) = \tau_{\mathrm{cmd}, 2}(t) + A_d \sin(2\pi f_d t + \phi_d)$ for $t \ge t_{\mathrm{fault}}$ with $A_d \in [0.1, 2.5]\,\mathrm{N\cdot m}$, $f_d \in [2.0, 30.0]\,\mathrm{Hz}$, $\phi_d \sim \mathcal{U}(0, 2\pi)\,\mathrm{rad}$.

---

## 5. The Four Physical Diagnostic Residuals

### R1 — SHAPE Port-Hamiltonian Power Residual ($r_{\mathrm{SHAPE}}$)
$$P_{\mathrm{cmd}, j}(t) = \tau_{\mathrm{cmd}, j}(t) \cdot \dot{q}_{\mathrm{meas}, j}(t)$$
$$P_{\mathrm{nom}, j}(t) = \tau_{\mathrm{nom}, j}(t) \cdot \dot{q}_{\mathrm{ref}, j}(t)$$
$$r_{\mathrm{SHAPE}, j}(t) \triangleq P_{\mathrm{cmd}, j}(t) - P_{\mathrm{nom}, j}(t), \quad j=1,\dots,6$$
* **Domain & Shape:** Watts ($\mathrm{W}$), array $[6, 10001]$ `float32`.
* **Properties:** Purely algebraic, instantaneous. **Zero acceleration dependency.**

### R2 — Inverse Dynamics Torque Parity Residual ($r_\tau$)
$$r_\tau(t) \triangleq \tau_{\mathrm{cmd}}(t) - \tau_{\mathrm{nom}}(t)$$
$$\tau_{\mathrm{nom}}(t) = \mathrm{ID}_{\mathrm{nom}}\big(q_{\mathrm{ref}}(t), \dot{q}_{\mathrm{ref}}(t), \ddot{q}_{\mathrm{ref}}(t)\big)$$
* **Domain & Shape:** $\mathrm{N\cdot m}$, array $[6, 10001]$ `float32`.
* **Properties:** Reference feedforward parity. **Zero measured state dependency** ($q_{\mathrm{meas}}, \dot{q}_{\mathrm{meas}}, \ddot{q}_{\mathrm{meas}}$).

### Exact Tracking-Power Bridge:
$$r_{\mathrm{SHAPE}, j}(t) = \dot{q}_{\mathrm{meas}, j}(t) \cdot r_{\tau, j}(t) + \big(\dot{q}_{\mathrm{meas}, j}(t) - \dot{q}_{\mathrm{ref}, j}(t)\big) \cdot \tau_{\mathrm{nom}, j}(t)$$
* Tracking-power term $(\dot{q}_{\mathrm{meas}} - \dot{q}_{\mathrm{ref}})\tau_{\mathrm{nom}}$ is mandatory; collapsing SHAPE to $r_\tau \odot \dot{q}$ is strictly forbidden.

### R3 — Generalized Momentum Observer Residual ($r_{\mathrm{GMO}}$)
$$\dot{\xi}(t) = -K_O \xi(t) + K_O M_{\mathrm{total}}(q)\dot{q} + \tau_{\mathrm{cmd}} - g_{\mathrm{nom}}(q) + C_{\mathrm{nom}}^T(q, \dot{q})\dot{q} - \tau_{f,\mathrm{nom}}(\dot{q})$$
$$r_{\mathrm{GMO}}(t) = K_O \big(M_{\mathrm{total}}(q)\dot{q} - \xi(t)\big)$$
* **Gain:** $K_O = 100.0\,\mathrm{s}^{-1}$ ($f_c = 15.9155\,\mathrm{Hz}$).
* **Discretization:** Trapezoidal / Tustin update on state $\xi$.
* **Domain & Shape:** $\mathrm{N\cdot m}$, array $[6, 10001]$ `float32`. Initial condition $r(0) = 0$.

### R4 — Energy Observer Residual ($r_E$)
$$\dot{\xi}_E(t) = -k_O \xi_E(t) + k_O \big(\frac{1}{2}\dot{q}^T M_{\mathrm{total}}(q)\dot{q}\big) + \dot{q}^T \big(\tau_{\mathrm{cmd}} - g_{\mathrm{nom}}(q) - \tau_{f,\mathrm{nom}}(\dot{q})\big)$$
$$r_E(t) = k_O \big(\frac{1}{2}\dot{q}^T M_{\mathrm{total}}(q)\dot{q} - \xi_E(t)\big)$$
* **Gain:** $k_O = 100.0\,\mathrm{s}^{-1}$ ($f_c = 15.9155\,\mathrm{Hz}$).
* **Discretization:** Trapezoidal / Tustin update on scalar state $\xi_E$.
* **Domain & Shape:** Watts ($\mathrm{W}$), **strictly scalar** array $[1, 10001]$ `float32`. Initial condition $r_E(0) = 0$.

---

## 6. Continuous Wavelet Transform & Representation Pipeline

1. **Physical Pre-Scaling:** Joint-wise normalized by continuous hardware limits BEFORE CWT: SHAPE by $P_{\mathrm{ref}, j}$, Torque and GMO by $\tau_{\max, j}$, EO by $P_{\mathrm{robot\_ref}}$.
2. **CWT Engine:** MATLAB Wavelet Toolbox GPU engine (`DEC-21`), mother wavelet `'amor'`, $VoicesPerOctave = 32$, $f \in [1.0, 100.0]\,\mathrm{Hz}$ ($N_{\mathrm{freq\_native}} = 213$ native scales).
3. **COI Treatment:** Valid-only aggregation with threshold $\Gamma_{\mathrm{COI}} = 0.80$. Neutral COI fill: **$-100.0\,\mathrm{dB}$** for log-power; **$0.0$** for A1 magnitude.
4. **2D Conservative Rebinning:** Area-power aggregation to compatibility grid $224 \times 448$ `float32` conserving continuous energy $\iint P(f,t)\,df\,dt$.
5. **Main Log-Power:** $X_{\log}(f, t) = 10\log_{10}(P(f, t) + 10^{-10})$ with floor at $-100.0\,\mathrm{dB}$.
6. **Paired Ablations:**
   * **A1 Magnitude:** $X_{\mathrm{mag}} = |W(f, t)|$ generated **DIRECTLY pre-log** (never invert float32 log-power).
   * **A2 Raw Time:** Continuous physical residuals $[6, 1, 10001]$ and $[1, 1, 10001]$ `float32`.
   * **A3 1D Spectrum:** Truncated FFT spectrum ($f \le 100\,\mathrm{Hz}$, $N=10001$, symmetric Hann, DC retained).
