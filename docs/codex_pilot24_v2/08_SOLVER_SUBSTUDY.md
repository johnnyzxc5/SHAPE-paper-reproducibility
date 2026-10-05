# Solver matched substudy

Eight representative alternatives covered Nominal, LoE, Friction, Vibration, fly, stop, K=2, and K=3. Canonical A used MaxStep 1 ms; alternative B used MaxStep auto. Alternatives were stored separately.

- Mean Simulink time: 314.787102 s (1 ms) versus 60.987042 s (auto).
- Mean profiled total: 570.520641 s versus 193.642938 s.
- Worst `q`: max error `5.62966e-5 rad`, RMSE `9.18216e-6`, min correlation `0.999999999968394`.
- Worst `dq`: max error `0.00145304 rad/s`, RMSE `7.01939e-5`, min correlation `0.999999968885238`.
- Worst `tau_cmd`: max error `2.61843 Nm`, RMSE `0.0608074`, min correlation `0.999983921413365`.
- Worst SHAPE/Torque: `1.67255 W` / `2.61843 Nm` max error.
- Worst GMO/EO: `0.913382 Nm` / `1.05041 W` max error.

Production status: **retain the conservative 1-ms candidate; auto is rejected as a drop-in replacement. Final production solver authority remains OPEN.**

