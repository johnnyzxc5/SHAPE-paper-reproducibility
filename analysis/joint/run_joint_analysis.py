"""Descriptive joint stratification of frozen predictions. No inference or telemetry reads.

All output paths are confined to this separate audit directory. Source assets are
hashed before/after. Severity and excitation assignments are read, never refitted.
"""
from pathlib import Path
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent
FROZEN = Path(r'C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY')
TEX = Path(r'C:\Users\Johnny\Desktop\Git\Image Processing Project\Latex Report\Final_Report.tex')
SOURCE = FROZEN / 'derived' / 'canonical_e0_primary.parquet'
assert not OUT.is_relative_to(FROZEN.resolve())
assert OUT.name == 'KINOVA_JOINT_SEVERITY_EXCITATION_AUDIT'
OUT.mkdir(exist_ok=True)

METHODS = ['shape_cwt', 'torque_cwt', 'gmo_cwt', 'energy_cwt']
LABELS = dict(zip(METHODS, ['SHAPE', 'Torque', 'GMO', 'EO']))
SEEDS = [1729, 2027, 4099, 7919, 104729]
FAULTS = ['LoE', 'Friction', 'Vibration']
QS = ['Q1', 'Q2', 'Q3', 'Q4']
BINS = {
    'LoE': ['[0.02, 0.05)', '[0.05, 0.10)', '[0.10, 0.20)', '[0.20, 0.30]'],
    'Friction': ['[0.02, 0.10)', '[0.10, 0.30)', '[0.30, 0.75)', '[0.75, 1.50]'],
    'Vibration': ['[0.10, 0.50)', '[0.50, 1.00)', '[1.00, 1.75)', '[1.75, 2.50]'],
}
Y_LABELS = {'LoE': r'LoE severity, $s_{\mathrm{LoE}}$',
            'Friction': r'Dimensionless Friction severity, $s_F$',
            'Vibration': r'Vibration amplitude, $A_d$ (N m)'}
CLASSES = ['Nominal', 'LoE', 'Friction', 'Vibration']
GROUP = ['fault_class', 'severity_bin', 'excitation_quartile', 'representation']
SEED_GROUP = GROUP + ['seed']
TOL = 1e-12


def sha(p):
    digest = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def target(name):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_csv(frame, name):
    frame.to_csv(target(name), index=False, float_format='%.17g')


def write_report(name, text):
    target(name).write_text(text, encoding='utf-8')


def md_table(frame):
    headings = [str(c) for c in frame.columns]
    rows = [['' if pd.isna(v) else str(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    return '\n'.join(['| ' + ' | '.join(headings) + ' |',
                      '| ' + ' | '.join(['---'] * len(headings)) + ' |'] +
                     ['| ' + ' | '.join(row) + ' |' for row in rows])


def ordered(frame):
    frame = frame.copy()
    frame['_fault'] = frame.fault_class.map({f: n for n, f in enumerate(FAULTS)})
    frame['_severity'] = [BINS[f].index(b) for f, b in zip(frame.fault_class, frame.severity_bin)]
    if 'excitation_quartile' in frame:
        frame['_q'] = frame.excitation_quartile.map({q: n for n, q in enumerate(QS)})
    if 'representation' in frame:
        frame['_rep'] = frame.representation.map({r: n for n, r in enumerate(METHODS)})
    keys = [k for k in ['_fault', '_severity', '_q', '_rep', 'seed'] if k in frame]
    return frame.sort_values(keys).drop(columns=[k for k in frame if k.startswith('_')]).reset_index(drop=True)


before = {str(p.relative_to(FROZEN)): sha(p) for p in sorted(FROZEN.rglob('*')) if p.is_file()}
tex_before = sha(TEX)
authority = json.loads((FROZEN / 'audit' / 'analysis_manifest.json').read_text())
assert sha(SOURCE) == authority['derived']['canonical_e0_primary.parquet']['sha256']
for name in ['T06_E1_severity.csv', 'T09_E3_excitation.csv']:
    assert sha(FROZEN / 'tables' / name) == authority['tables'][name]['sha256']

full = pd.read_parquet(SOURCE)
df = full[(full['cohort'] == 'PRIMARY') & (full['split'] == 'test') &
          full['fault_class'].isin(FAULTS) & full['representation'].isin(METHODS)].copy()
errors = []
if len(df) != 45000:
    errors.append(f'Expected 45000 rows, got {len(df)}')
if df.groupby('fault_class').run_uid.nunique().to_dict() != {'Friction': 750, 'LoE': 750, 'Vibration': 750}:
    errors.append('Unique runs per fault class differ from 750')
if df.duplicated(['run_uid', 'representation', 'seed']).any():
    errors.append('Duplicate prediction keys')
if set(df.seed) != set(SEEDS) or set(df.representation) != set(METHODS):
    errors.append('Method/seed set mismatch')
if not df.groupby('run_uid').size().eq(20).all():
    errors.append('Incomplete method/seed coverage')
required = ['run_uid', 'parent_trajectory_id', 'fault_class', 'severity_bin',
            'dq2_rms_post', 'excitation_quartile', 'label', 'prediction',
            'prediction_class', 'is_correct_multiclass', 'is_correct_binary']
if df[required].isna().any().any():
    errors.append('Missing required fields')
meta_cols = ['parent_trajectory_id', 'fault_class', 'severity_bin', 'dq2_rms_post',
             'excitation_quartile', 's_LoE', 's_Friction', 'A_d', 'label']
if (df.groupby('run_uid')[meta_cols].nunique(dropna=False) > 1).any().any():
    errors.append('Run metadata differ across method/seed evaluations')
for fault in FAULTS:
    part = df[df.fault_class == fault]
    if set(part.severity_bin) != set(BINS[fault]) or set(part.excitation_quartile) != set(QS):
        errors.append(f'Missing/unknown strata for {fault}')
if not ((df.prediction == df.label).astype(int) == df.is_correct_multiclass).all():
    errors.append('Multiclass correctness flag mismatch')
if not ((df.prediction != 0).astype(int) == df.is_correct_binary).all():
    errors.append('Binary correctness flag mismatch on faulty runs')
if not (df.prediction.map(dict(enumerate(CLASSES))) == df.prediction_class).all():
    errors.append('Prediction-class mapping mismatch')

integrity = {
    'status': 'FAIL' if errors else 'PASS', 'errors': errors,
    'prediction_rows': len(df), 'unique_runs': int(df.run_uid.nunique()),
    'runs_by_fault': df.groupby('fault_class').run_uid.nunique().to_dict(),
    'methods': METHODS, 'seeds': SEEDS,
    'frozen_workspace_files_hashed': len(before), 'source_sha256': sha(SOURCE),
}
write_report('01_population_integrity_report.md',
             '# Population integrity\n\n```json\n' + json.dumps(integrity, indent=2) + '\n```\n\n'
             'Population: PRIMARY/test faulty runs only, common CWT formulations. '
             'A physical denominator is a unique simulated run_uid; seeds do not multiply that denominator.\n')
if errors:
    raise RuntimeError('STOP: population discrepancy: ' + '; '.join(errors))

# Cell counts use run_uid exactly once, independently of predictions.
physical = df.drop_duplicates('run_uid')
counts = physical.groupby(GROUP[:3], sort=False).run_uid.nunique().rename('N_unique_runs').reset_index()
assert len(counts) == 48 and counts.N_unique_runs.gt(0).all()
counts['Severity_Total'] = counts.groupby(['fault_class', 'severity_bin']).N_unique_runs.transform('sum')
counts['Quartile_Total'] = counts.groupby(['fault_class', 'excitation_quartile']).N_unique_runs.transform('sum')
counts['Fault_Total'] = counts.groupby('fault_class').N_unique_runs.transform('sum')
counts = ordered(counts)
save_csv(counts, '02_cell_counts.csv')
count_stats = []
for fault in FAULTS:
    c = counts[counts.fault_class == fault]
    matrix = c.pivot(index='severity_bin', columns='excitation_quartile', values='N_unique_runs').reindex(index=BINS[fault], columns=QS)
    with_totals = matrix.copy()
    with_totals['Total'] = with_totals.sum(axis=1)
    with_totals.loc['Total'] = with_totals.sum(axis=0)
    save_csv(with_totals.reset_index(), f'02_{fault}_count_matrix.csv')
    count_stats.append({'fault_class': fault, 'min_N': int(c.N_unique_runs.min()),
                        'max_N': int(c.N_unique_runs.max()), 'median_N': float(c.N_unique_runs.median()),
                        'N_lt_10_cells': int(c.N_unique_runs.lt(10).sum()),
                        'N_lt_20_cells': int(c.N_unique_runs.lt(20).sum()),
                        'N_lt_30_cells': int(c.N_unique_runs.lt(30).sum())})
save_csv(pd.DataFrame(count_stats), '02_cell_support_summary.csv')

# Seed-specific metrics first; no seed pooling for reported means or SDs.
for code, name in enumerate(CLASSES):
    df[f'pred_fraction_{name}'] = (df.prediction == code).astype(float)
aggregations = {
    'N_unique_runs': ('run_uid', 'nunique'),
    'Recall': ('is_correct_multiclass', 'mean'),
    'Detection': ('is_correct_binary', 'mean'),
}
for name in CLASSES:
    aggregations[f'Fraction_{name}'] = (f'pred_fraction_{name}', 'mean')
seed_metrics = df.groupby(SEED_GROUP, sort=False).agg(**aggregations).reset_index()
seed_metrics = ordered(seed_metrics)
assert len(seed_metrics) == 960
assert seed_metrics[[f'Fraction_{c}' for c in CLASSES]].sum(axis=1).sub(1).abs().max() < TOL
save_csv(seed_metrics, '03_joint_metrics_by_seed.csv')

summary_agg = {'N_unique_runs': ('N_unique_runs', 'first'), 'Seeds': ('seed', 'nunique')}
for metric in ['Recall', 'Detection'] + [f'Fraction_{name}' for name in CLASSES]:
    summary_agg[metric + '_Mean'] = (metric, 'mean')
    summary_agg[metric + '_SD'] = (metric, 'std')  # pandas sample SD, ddof=1
summary = ordered(seed_metrics.groupby(GROUP, sort=False).agg(**summary_agg).reset_index())
assert summary.Seeds.eq(5).all()
assert summary[[f'Fraction_{c}_Mean' for c in CLASSES]].sum(axis=1).sub(1).abs().max() < TOL
save_csv(summary[GROUP + ['N_unique_runs', 'Recall_Mean', 'Recall_SD']], '03_joint_multiclass_recall.csv')
save_csv(summary[GROUP + ['N_unique_runs', 'Detection_Mean', 'Detection_SD']], '04_joint_binary_detection.csv')
save_csv(summary[GROUP + ['N_unique_runs'] + [f'Fraction_{c}_{stat}' for c in CLASSES for stat in ['Mean', 'SD']]],
         '05_joint_confusion_destinations.csv')
summary['Detection_minus_Identification_pp'] = 100 * (summary.Detection_Mean - summary.Recall_Mean)
save_csv(summary[GROUP + ['N_unique_runs', 'Recall_Mean', 'Detection_Mean', 'Detection_minus_Identification_pp']],
         '05_detection_identification_gaps.csv')

composition = counts[['fault_class', 'excitation_quartile', 'severity_bin', 'N_unique_runs', 'Quartile_Total']].copy()
composition['Severity_Fraction_Within_Q'] = composition.N_unique_runs / composition.Quartile_Total
composition['Severity_Percent_Within_Q'] = 100 * composition.Severity_Fraction_Within_Q
save_csv(composition, '06_severity_composition_by_Q.csv')


def reconstruct(group_columns, metric):
    temp = seed_metrics.copy()
    temp['numerator'] = temp[metric] * temp.N_unique_runs
    by_seed = temp.groupby(group_columns + ['seed'], sort=False).agg(numerator=('numerator', 'sum'), denominator=('N_unique_runs', 'sum')).reset_index()
    by_seed['value'] = by_seed.numerator / by_seed.denominator
    return by_seed.groupby(group_columns, sort=False).value.agg(['mean', 'std']).reset_index()


# Reconstruct seed-level marginals with physical-run weighting, then aggregate seeds.
t06 = pd.read_csv(FROZEN / 'tables' / 'T06_E1_severity.csv')
t09 = pd.read_csv(FROZEN / 'tables' / 'T09_E3_excitation.csv')
checks = []
for metric, stem in [('Recall', 'Multiclass_Recall'), ('Detection', 'Binary_Detection')]:
    reconstructed = reconstruct(['fault_class', 'severity_bin', 'representation'], metric)
    for row in reconstructed.itertuples(index=False):
        ref = t06[(t06.Fault_Class == row.fault_class) & (t06.Severity_Bin == row.severity_bin) & (t06.rep_key == row.representation)].iloc[0]
        for suffix, value in [('Mean', row.mean), ('SD', row.std)]:
            frozen_value = float(ref[stem + '_' + suffix])
            checks.append({'source_table': 'T06', 'field': stem + '_' + suffix,
                           'fault_class': row.fault_class, 'severity_bin': row.severity_bin,
                           'excitation_quartile': '', 'representation': row.representation,
                           'Reconstructed': value, 'Frozen': frozen_value,
                           'Absolute_Discrepancy': abs(value-frozen_value)})
reconstructed = reconstruct(['fault_class', 'excitation_quartile', 'representation'], 'Recall')
for row in reconstructed.itertuples(index=False):
    ref = t09[(t09.Excitation_Quartile == row.excitation_quartile) & (t09.rep_key == row.representation)].iloc[0]
    for suffix, value in [('Mean', row.mean), ('SD', row.std)]:
        frozen_value = float(ref[row.fault_class + '_Recall_' + suffix])
        checks.append({'source_table': 'T09', 'field': row.fault_class + '_Recall_' + suffix,
                       'fault_class': row.fault_class, 'severity_bin': '',
                       'excitation_quartile': row.excitation_quartile, 'representation': row.representation,
                       'Reconstructed': value, 'Frozen': frozen_value,
                       'Absolute_Discrepancy': abs(value-frozen_value)})
reconstructed = reconstruct(['excitation_quartile', 'representation'], 'Detection')
for row in reconstructed.itertuples(index=False):
    ref = t09[(t09.Excitation_Quartile == row.excitation_quartile) & (t09.rep_key == row.representation)].iloc[0]
    for suffix, value in [('Mean', row.mean), ('SD', row.std)]:
        frozen_value = float(ref['Fault_Detection_' + suffix])
        checks.append({'source_table': 'T09', 'field': 'Fault_Detection_' + suffix,
                       'fault_class': 'ALL_FAULTS', 'severity_bin': '',
                       'excitation_quartile': row.excitation_quartile, 'representation': row.representation,
                       'Reconstructed': value, 'Frozen': frozen_value,
                       'Absolute_Discrepancy': abs(value-frozen_value)})
check_frame = pd.DataFrame(checks)
check_frame['PASS'] = check_frame.Absolute_Discrepancy <= TOL
save_csv(check_frame, '07_marginal_reconstruction_check.csv')
if not check_frame.PASS.all():
    raise RuntimeError('STOP: marginal reconstruction differs from frozen tables')

# Transparent descriptive labels of observed mean shape; no test/equivalence claim.
def trajectory_label(values):
    pp = np.asarray(values) * 100
    if np.ptp(pp) <= 3.0 + 1e-12:
        return 'approximately flat'
    if np.all(np.diff(pp) >= -1e-12):
        return 'generally increasing'
    if np.all(np.diff(pp) <= 1e-12):
        return 'generally decreasing'
    return 'non-monotonic'


trajectory_rows = []
for fault in FAULTS:
    for severity in BINS[fault]:
        for rep in METHODS:
            part = summary[(summary.fault_class == fault) & (summary.severity_bin == severity) & (summary.representation == rep)].set_index('excitation_quartile').loc[QS]
            row = {'fault_class': fault, 'severity_bin': severity, 'representation': rep}
            for q in QS:
                row[q + '_Recall_Mean'] = float(part.loc[q, 'Recall_Mean'])
                row[q + '_Recall_SD'] = float(part.loc[q, 'Recall_SD'])
                row[q + '_N_unique_runs'] = int(part.loc[q, 'N_unique_runs'])
            row['Q4_minus_Q1_pp'] = 100 * (part.loc['Q4', 'Recall_Mean'] - part.loc['Q1', 'Recall_Mean'])
            row['Observed_Trajectory'] = trajectory_label(part.Recall_Mean)
            trajectory_rows.append(row)
trajectories = ordered(pd.DataFrame(trajectory_rows))
save_csv(trajectories, '08_within_severity_Q_deltas.csv')

# Exact symmetric arithmetic accounting of endpoint marginal change.
# Delta = sum(mean(w1,w4)*(r4-r1)) + sum((w4-w1)*mean(r1,r4)).
# This is descriptive bookkeeping, not adjustment or causal attribution.
accounting = []
for fault in FAULTS:
    support = counts[counts.fault_class == fault].pivot(index='severity_bin', columns='excitation_quartile', values='N_unique_runs').reindex(index=BINS[fault], columns=QS)
    w1 = (support.Q1 / support.Q1.sum()).to_numpy()
    w4 = (support.Q4 / support.Q4.sum()).to_numpy()
    for rep in METHODS:
        r = summary[(summary.fault_class == fault) & (summary.representation == rep)].pivot(index='severity_bin', columns='excitation_quartile', values='Recall_Mean').reindex(index=BINS[fault], columns=QS)
        r1, r4 = r.Q1.to_numpy(), r.Q4.to_numpy()
        marginal = 100 * (np.dot(w4, r4) - np.dot(w1, r1))
        within = 100 * np.dot((w1+w4)/2, r4-r1)
        comp = 100 * np.dot(w4-w1, (r1+r4)/2)
        assert abs(marginal-within-comp) < 1e-10
        accounting.append({'fault_class': fault, 'representation': rep,
                           'Marginal_Q4_minus_Q1_pp': marginal,
                           'Within_Severity_Term_pp': within,
                           'Composition_Term_pp': comp,
                           'Accounting_Residual_pp': marginal-within-comp})
accounting = pd.DataFrame(accounting)
save_csv(accounting, '10_descriptive_composition_accounting.csv')

plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'],
                     'font.size': 9, 'axes.labelsize': 9, 'axes.titlesize': 9.5,
                     'xtick.labelsize': 8.5, 'ytick.labelsize': 8,
                     'mathtext.fontset': 'stix', 'pdf.fonttype': 42,
                     'axes.linewidth': 0.6})
styles = [('SHAPE', '#1f77b4', 'o', '-'), ('Torque', '#ff7f0e', 's', '--'),
          ('GMO', '#2ca02c', '^', '-.'), ('EO', '#d62728', 'D', ':')]


def export_figure(fig, name):
    fig.savefig(target('figures/' + name + '.pdf'), metadata={
        'Title': name, 'Subject': 'Joint observational stratification of frozen PRIMARY/test predictions; five-seed mean',
        'Author': 'Johnny Garcia'})
    fig.savefig(target('figures/' + name + '.png'), dpi=300)
    plt.close(fig)


for fault in FAULTS:
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 6.15))
    fig.subplots_adjust(left=0.16, right=0.87, bottom=0.14, top=0.87, wspace=0.62, hspace=0.38)
    for ax, rep in zip(axes.flat, METHODS):
        data = summary[(summary.fault_class == fault) & (summary.representation == rep)].pivot(index='severity_bin', columns='excitation_quartile', values='Recall_Mean').reindex(index=BINS[fault], columns=QS) * 100
        # pcolormesh keeps cells vector-based in the PDF.
        image = ax.pcolormesh(np.arange(5)-0.5, np.arange(5)-0.5, data.to_numpy(),
                              cmap='viridis', vmin=0, vmax=100, shading='flat',
                              edgecolors='white', linewidth=0.7, rasterized=False)
        ax.set_xlim(-0.5, 3.5); ax.set_ylim(3.5, -0.5)
        ax.set_xticks(np.arange(4), QS)
        ax.set_yticks(np.arange(4), [b.replace(', ', ',') for b in BINS[fault]])
        ax.tick_params(length=0, pad=4)
        ax.set_title(LABELS[rep], pad=6)
        for iy in range(4):
            for ix in range(4):
                value = data.iloc[iy, ix]
                ax.text(ix, iy, f'{value:.1f}%', ha='center', va='center', fontsize=8.5,
                        color='white' if value < 55 else 'black')
    cax = fig.add_axes([0.92, 0.20, 0.019, 0.60])
    cb = fig.colorbar(image, cax=cax, ticks=np.arange(0, 101, 20))
    cb.set_label('Multiclass recall (%)', fontsize=9)
    fig.suptitle(f'{fault} identification across severity and excitation strata', fontsize=10.5, y=0.97)
    fig.text(0.022, 0.50, Y_LABELS[fault], rotation=90, va='center', ha='center', fontsize=9)
    fig.text(0.52, 0.075, 'Excitation stratum', ha='center', fontsize=9)
    fig.text(0.52, 0.030, 'Five-seed means; unique-run support in companion count matrix.', ha='center', fontsize=7.8)
    export_figure(fig, fault + '_joint_recall')

    support = counts[counts.fault_class == fault].pivot(index='severity_bin', columns='excitation_quartile', values='N_unique_runs').reindex(index=BINS[fault], columns=QS)
    fig, ax = plt.subplots(figsize=(3.58, 3.35))
    fig.subplots_adjust(left=0.29, right=0.84, bottom=0.20, top=0.83)
    im = ax.pcolormesh(np.arange(5)-0.5, np.arange(5)-0.5, support.to_numpy(), cmap='Blues', vmin=0, vmax=85,
                       edgecolors='white', linewidth=0.7, shading='flat', rasterized=False)
    ax.set_xlim(-0.5, 3.5); ax.set_ylim(3.5, -0.5)
    ax.set_xticks(np.arange(4), QS); ax.set_yticks(np.arange(4), [b.replace(', ', ',') for b in BINS[fault]])
    ax.tick_params(length=0, pad=3)
    for iy in range(4):
        for ix in range(4):
            val = int(support.iloc[iy, ix])
            ax.text(ix, iy, str(val), ha='center', va='center', fontsize=9, color='white' if val > 55 else 'black')
    ax.set_xlabel('Excitation stratum', labelpad=6)
    fig.suptitle(f'{fault}: unique simulated test runs', fontsize=10, y=0.96)
    fig.text(0.035, 0.50, Y_LABELS[fault], rotation=90, va='center', ha='center', fontsize=8.5)
    cax = fig.add_axes([0.90, 0.20, 0.03, 0.63])
    fig.colorbar(im, cax=cax, ticks=[0, 20, 40, 60, 80])
    fig.text(0.5, 0.05, 'Counts are shared across methods and seeds.', ha='center', fontsize=7.5)
    export_figure(fig, fault + '_counts')

line_part = summary[summary.fault_class.isin(['LoE', 'Friction'])]
line_lower = min(0, 5*np.floor(100*(line_part.Recall_Mean-line_part.Recall_SD).min()/5))
line_upper = max(100, 5*np.ceil(100*(line_part.Recall_Mean+line_part.Recall_SD).max()/5))
for fault in ['LoE', 'Friction']:
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 5.25))
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.12, top=0.82, hspace=0.44, wspace=0.22)
    for ax, severity in zip(axes.flat, BINS[fault]):
        for rep, (label, color, marker, linestyle) in zip(METHODS, styles):
            part = summary[(summary.fault_class == fault) & (summary.severity_bin == severity) & (summary.representation == rep)].set_index('excitation_quartile').loc[QS]
            ax.errorbar(np.arange(4), part.Recall_Mean*100, yerr=part.Recall_SD*100,
                        color=color, marker=marker, linestyle=linestyle, linewidth=1.05,
                        markerfacecolor='white', markersize=4, capsize=2.2, elinewidth=0.8)
        ax.set_title(severity, loc='left', pad=5)
        ax.set_ylim(line_lower, line_upper); ax.set_yticks(np.arange(0, 101, 20))
        ax.set_xlim(-0.15, 3.15); ax.set_xticks(np.arange(4), QS)
        ax.set_axisbelow(True); ax.grid(axis='y', color='#dddddd', linewidth=0.5)
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    handles = [Line2D([], [], color=c, marker=m, linestyle=l, markerfacecolor='white', label=n) for n,c,m,l in styles]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.54, 0.94), ncol=4, frameon=False, fontsize=8.8)
    fig.suptitle(f'{fault}: recall across Q within each severity bin', fontsize=10.5, y=0.995)
    fig.text(0.025, 0.48, 'Multiclass recall (%)', rotation=90, ha='center', va='center', fontsize=9)
    fig.text(0.54, 0.035, 'Excitation stratum; error bars show five-seed sample SD', ha='center', fontsize=8.5)
    export_figure(fig, fault + '_within_severity_Q')

# Full trajectory table requested for scientific inspection, with support and SD.
trajectory_report = ['# Within-severity excitation trajectories', '',
                     'All values are recall percentages, five-seed mean +/- sample SD. '
                     'Labels describe means only: approximately flat means a Q1-Q4 range <= 3 pp; '
                     'otherwise generally increasing/decreasing requires no reversal in successive means; '
                     'remaining trajectories are non-monotonic. These are editorial descriptions, not tests or equivalence statements.', '']
for fault in FAULTS:
    trajectory_report += ['## ' + fault, '']
    formatted = []
    for r in trajectories[trajectories.fault_class == fault].to_dict('records'):
        row = {'Severity bin': r['severity_bin'], 'Method': LABELS[r['representation']]}
        for q in QS:
            row[q] = f"{100*r[q+'_Recall_Mean']:.2f} +/- {100*r[q+'_Recall_SD']:.2f} (N={r[q+'_N_unique_runs']})"
        row['Q4-Q1 (pp)'] = f"{r['Q4_minus_Q1_pp']:+.2f}"
        row['Description'] = r['Observed_Trajectory']
        formatted.append(row)
    trajectory_report += [md_table(pd.DataFrame(formatted)), '']
write_report('08_within_severity_Q_trajectories.md', '\n'.join(trajectory_report))

protocol = '''# Joint descriptive analysis protocol

Source: frozen canonical_e0_primary.parquet. Use stored severity_bin and excitation_quartile without refitting, joins, telemetry processing, simulation, training, or inference.

Population: PRIMARY/test; LoE, Friction, Vibration; shape_cwt, torque_cwt, gmo_cwt, energy_cwt; seeds 1729, 2027, 4099, 7919, 104729.

For each cell and seed: recall = mean(is_correct_multiclass); detection = mean(is_correct_binary) on true faulty runs; destination fractions = mean(prediction == class code). Then calculate five-seed mean and sample SD (ddof=1). Unique simulated runs are the physical denominator. Fractions are stored on 0-1 scale; figures show percentages.

Marginal reconstruction: first collapse seed-specific cell rates using N_unique_runs weights; then calculate seed mean and SD. Compare E1 recall/detection with T06 and E3 class-specific recall/aggregate fault detection with T09. Tolerance = 1e-12 in proportion units. Overall Accuracy is not reconstructed from a fault-only population.

Composition: N(severity,Q)/N(Q) within each fault class. No quartile refitting.

Optional endpoint accounting is an exact symmetric arithmetic identity. With severity weights w1,w4 and seed-mean recalls r1,r4:

Delta = sum(((w1+w4)/2)*(r4-r1)) + sum((w4-w1)*((r1+r4)/2)).

The first term describes within-severity changes; the second describes differing severity weights under this symmetric convention. Their sum equals the marginal endpoint difference. This is not causal adjustment or attribution; another accounting convention can allocate terms differently. No percentage-of-effect interpretation is used.

Trajectory descriptions: approximately flat when the observed mean range is <=3 pp; otherwise generally increasing/decreasing when successive means do not reverse; non-monotonic otherwise. These descriptive labels are not statistical tests, equivalence claims, detection thresholds, or deployment rules.

Heatmaps: common 0-100% recall scale, means only. Sample SDs are provided in CSVs, trajectory tables, and supplementary line views. Count maps show unique simulated runs. No p-values or bootstrap intervals are calculated.

Scientific scope: observational, non-factorial joint stratification. dq2_rms_post is measured post-fault and can covary with severity, trajectory, closed-loop response and other variables. No causal interaction, independent excitation effect, optimal region, universal threshold, or deployment recommendation is established.
'''
write_report('00_analysis_protocol.md', protocol)

after = {str(p.relative_to(FROZEN)): sha(p) for p in sorted(FROZEN.rglob('*')) if p.is_file()}
changed = [name for name in before if after.get(name) != before[name]]
added = [name for name in after if name not in before]
assert not changed and not added, {'changed': changed, 'added': added}
assert sha(TEX) == tex_before, 'Final_Report.tex changed during this run'
provenance = {
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'source': str(SOURCE), 'source_sha256': sha(SOURCE),
    'output_directory': str(OUT), 'script': str(Path(__file__).resolve()), 'script_sha256': sha(Path(__file__)),
    'python': sys.executable, 'versions': {'python': platform.python_version(), 'pandas': pd.__version__, 'numpy': np.__version__, 'matplotlib': matplotlib.__version__},
    'scientific_authority_record': authority['scientific_authority_commit'],
    'frozen_files_checked': len(before), 'frozen_changed_files': changed, 'frozen_added_files': added,
    'final_report_sha256_before': tex_before, 'final_report_sha256_after': sha(TEX),
    'marginal_max_absolute_discrepancy_proportion': float(check_frame.Absolute_Discrepancy.max()),
    'marginal_tolerance': TOL, 'confusion_fraction_sum_max_error': float(summary[[f'Fraction_{c}_Mean' for c in CLASSES]].sum(axis=1).sub(1).abs().max()),
    'integrity': integrity, 'count_support': count_stats,
}
target('00_source_and_output_provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
write_report('01_population_integrity_report.md',
             '# Population integrity\n\n```json\n' + json.dumps(integrity, indent=2) + '\n```\n\n'
             f'Frozen-workspace hash audit: PASS across {len(before)} files; zero added or changed files. Final_Report.tex hash is unchanged.\n\n'
             'All 48 cells are populated, and every run has all 20 method/seed evaluations. '
             'No missing values, duplicate keys, conflicting metadata or inconsistent correctness flags were found.\n')
print(json.dumps({'status': 'PASS', 'output': str(OUT), 'count_support': count_stats,
                  'marginal_max_discrepancy': provenance['marginal_max_absolute_discrepancy_proportion'],
                  'confusion_sum_error': provenance['confusion_fraction_sum_max_error'],
                  'frozen_files_unchanged': len(before)}, indent=2))
print('ENDPOINT ACCOUNTING')
print(accounting.to_csv(index=False))
print('WITHIN-SEVERITY ENDPOINTS')
print(trajectories[['fault_class', 'severity_bin', 'representation', 'Q4_minus_Q1_pp', 'Observed_Trajectory']].to_csv(index=False))
