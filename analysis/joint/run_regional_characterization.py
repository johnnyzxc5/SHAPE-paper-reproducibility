"""Regional characterization of existing joint summaries, without new inference.

All scientific sources and previous outputs are read-only. New destinations must
not exist. Exact empirical outcome dominance is used without arbitrary cutoffs.
"""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
FROZEN = Path(r'C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY')
SOURCE = FROZEN / 'derived' / 'canonical_e0_primary.parquet'
TEX = Path(r'C:\Users\Johnny\Desktop\Git\Image Processing Project\Latex Report\Final_Report.tex')
FIG = OUT / 'figures' / 'regional'
assert OUT.name == 'KINOVA_JOINT_SEVERITY_EXCITATION_AUDIT'
assert not OUT.is_relative_to(FROZEN)
METHODS = ['SHAPE', 'Torque', 'GMO', 'EO']
REPS = dict(zip(['shape_cwt', 'torque_cwt', 'gmo_cwt', 'energy_cwt'], METHODS))
FAULTS = ['LoE', 'Friction', 'Vibration']
QS = ['Q1', 'Q2', 'Q3', 'Q4']
BINS = {
    'LoE': ['[0.02, 0.05)', '[0.05, 0.10)', '[0.10, 0.20)', '[0.20, 0.30]'],
    'Friction': ['[0.02, 0.10)', '[0.10, 0.30)', '[0.30, 0.75)', '[0.75, 1.50]'],
    'Vibration': ['[0.10, 0.50)', '[0.50, 1.00)', '[1.00, 1.75)', '[1.75, 2.50]']}
Y_LABELS = {'LoE': r'LoE severity, $s_{\mathrm{LoE}}$',
            'Friction': r'Dimensionless Friction severity, $s_F$',
            'Vibration': r'Vibration amplitude, $A_d$ (N m)'}
KEYS = ['fault_class', 'severity_bin', 'excitation_quartile', 'representation', 'N_unique_runs']
TOL = 1e-12


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def new_path(name):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    if p.exists():
        raise FileExistsError('Refusing to overwrite: ' + str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def csv(frame, name):
    frame.to_csv(new_path(name), index=False, float_format='%.17g')


def write(name, text):
    new_path(name).write_text(text, encoding='utf-8')


def md(frame):
    return '\n'.join(['| ' + ' | '.join(map(str, frame.columns)) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(str(x) for x in row) + ' |'
                      for row in frame.itertuples(index=False, name=None)])


def sort(frame):
    z = frame.copy()
    z['_f'] = z.fault_class.map({v: i for i, v in enumerate(FAULTS)})
    z['_s'] = [BINS[f].index(s) for f, s in zip(z.fault_class, z.severity_bin)]
    z['_q'] = z.excitation_quartile.map({v: i for i, v in enumerate(QS)})
    z['_m'] = z.method.map({v: i for i, v in enumerate(METHODS)})
    return z.sort_values(['_f', '_s', '_q', '_m']).drop(columns=['_f', '_s', '_q', '_m']).reset_index(drop=True)


before_frozen = {str(p): sha(p) for p in FROZEN.rglob('*') if p.is_file()}
before_previous = {str(p): sha(p) for p in OUT.rglob('*') if p.is_file()}
tex_before = sha(TEX)
prior = json.loads((OUT / '00_source_and_output_provenance.json').read_text())
assert sha(SOURCE) == prior['source_sha256']
old_manifest = json.loads((OUT / '12_output_manifest.json').read_text())
for item in old_manifest['outputs']:
    assert sha(OUT / item['file']) == item['sha256'], item['file']

# Existing seed and cell summaries are the numerical source. Canonical rows are
# read only to check keys, run support and the correct class-code interpretation.
r = pd.read_csv(OUT / '03_joint_multiclass_recall.csv')
d = pd.read_csv(OUT / '04_joint_binary_detection.csv')
c = pd.read_csv(OUT / '05_joint_confusion_destinations.csv')
s = pd.read_csv(OUT / '03_joint_metrics_by_seed.csv')
z = r.merge(d, on=KEYS, validate='one_to_one').merge(c, on=KEYS, validate='one_to_one')
assert len(z) == 192 and len(s) == 960
canonical = pd.read_parquet(SOURCE, columns=['cohort', 'split', 'fault_class', 'severity_bin',
    'excitation_quartile', 'representation', 'seed', 'run_uid', 'label', 'prediction',
    'prediction_class', 'true_binary', 'predicted_binary', 'is_correct_multiclass', 'is_correct_binary'])
canonical = canonical[(canonical.cohort == 'PRIMARY') & (canonical.split == 'test') &
    canonical.fault_class.isin(FAULTS) & canonical.representation.isin(REPS)].copy()
assert len(canonical) == 45000 and canonical.run_uid.nunique() == 2250
assert not canonical.duplicated(['run_uid', 'representation', 'seed']).any()
assert canonical.groupby('run_uid').size().eq(20).all()
assert sorted(canonical.seed.unique().tolist()) == [1729, 2027, 4099, 7919, 104729]
assert (canonical.prediction.eq(canonical.label) == canonical.is_correct_multiclass).all()
assert (canonical.prediction.ne(0) == canonical.is_correct_binary).all()
assert (canonical.prediction.ne(0) == canonical.predicted_binary).all()
physical = canonical.drop_duplicates('run_uid')
counts = physical.groupby(KEYS[:3]).run_uid.nunique().rename('Canonical_N').reset_index()
check = z.merge(counts, on=KEYS[:3], validate='many_to_one')
assert (check.N_unique_runs == check.Canonical_N).all()
for f in FAULTS:
    assert physical[physical.fault_class == f].run_uid.nunique() == 750
    assert set(physical[physical.fault_class == f].severity_bin) == set(BINS[f])
    assert set(physical[physical.fault_class == f].excitation_quartile) == set(QS)

z = z.rename(columns={'representation': 'representation_source', 'Recall_Mean': 'Identification_Mean',
    'Recall_SD': 'Identification_SD', **{f'Fraction_{f}_Mean': f'{f}_Prediction_Mean'
                                       for f in ['Nominal'] + FAULTS}})
z['method'] = z.representation_source.map(REPS)
z['Missed_Detection_Mean'] = z.Nominal_Prediction_Mean
z['Missed_Detection_SD'] = z.Fraction_Nominal_SD
z['Wrong_Fault_Type_Mean'] = [sum(row[f'{f}_Prediction_Mean'] for f in FAULTS if f != row.fault_class)
                            for _, row in z.iterrows()]
z['Identification_Detection_Gap'] = z.Detection_Mean - z.Identification_Mean
s['Wrong'] = s.Detection - s.Recall
wrong_sd = s.groupby(KEYS[:-1]).Wrong.std(ddof=1).rename('Wrong_Fault_Type_SD').reset_index()
wrong_sd = wrong_sd.rename(columns={'representation': 'representation_source'})
z = z.merge(wrong_sd, on=KEYS[:-1][:-1] + ['representation_source'], validate='one_to_one')
errors = {
    'outcome_sum_error': float((z.Identification_Mean+z.Wrong_Fault_Type_Mean+z.Missed_Detection_Mean-1).abs().max()),
    'destination_sum_error': float((z[[f'{f}_Prediction_Mean' for f in ['Nominal']+FAULTS]].sum(axis=1)-1).abs().max()),
    'wrong_equals_gap_error': float((z.Wrong_Fault_Type_Mean-z.Identification_Detection_Gap).abs().max()),
    'detection_equals_one_minus_nominal_error': float((z.Detection_Mean+z.Missed_Detection_Mean-1).abs().max()),
    'identification_equals_true_class_fraction_error': max(abs(row.Identification_Mean-row[f'{row.fault_class}_Prediction_Mean']) for _, row in z.iterrows())}
assert max(errors.values()) <= TOL
for col in ['Identification_Mean', 'Detection_Mean', 'Missed_Detection_Mean', 'Wrong_Fault_Type_Mean']:
    assert z[col].between(-TOL, 1+TOL).all()

# Empirical descriptions without a high/low score cutoff. Outcome dominance means
# largest of the three mutually exclusive outcome fractions, not significance.
I, W, M = z.Identification_Mean, z.Wrong_Fault_Type_Mean, z.Missed_Detection_Mean
z['Empirical_Ceiling'] = np.isclose(I, 1, atol=TOL, rtol=0)
z['Wrong_Type_Dominates_Outcomes'] = (W > I+TOL) & (W > M+TOL)
z['Missed_Detection_Dominates_Outcomes'] = (M > I+TOL) & (M > W+TOL)
z['Wrong_Type_Dominates_Errors'] = W > M+TOL
z['Region_Description'] = np.select([z.Empirical_Ceiling, z.Wrong_Type_Dominates_Outcomes,
    z.Missed_Detection_Dominates_Outcomes, (I > W+TOL) & (I > M+TOL)],
    ['EXACT_EMPIRICAL_CEILING', 'CORE_DETECTABLE_BUT_AMBIGUOUS', 'MISSED_DETECTION_DOMINANT',
     'IDENTIFICATION_DOMINANT_WITH_RESIDUAL_ERRORS'], default='MIXED_OR_TIED')
base = ['fault_class', 'severity_bin', 'excitation_quartile', 'method', 'N_unique_runs',
    'Identification_Mean', 'Identification_SD', 'Detection_Mean', 'Detection_SD',
    'Nominal_Prediction_Mean', 'LoE_Prediction_Mean', 'Friction_Prediction_Mean', 'Vibration_Prediction_Mean',
    'Missed_Detection_Mean', 'Wrong_Fault_Type_Mean', 'Identification_Detection_Gap']
extra = ['Missed_Detection_SD', 'Wrong_Fault_Type_SD', 'Empirical_Ceiling', 'Region_Description',
         'Wrong_Type_Dominates_Outcomes', 'Missed_Detection_Dominates_Outcomes', 'Wrong_Type_Dominates_Errors']
master = sort(z[base+extra])
csv(master, '10_regional_master_table.csv')
for n, method in enumerate(METHODS, 11):
    csv(master[master.method == method], f'{n:02d}_{method.lower()}_regional_profile.csv')

adjacency, maxima_records = [], []
for method in METHODS:
    for fault in FAULTS:
        block = master[(master.method == method)&(master.fault_class == fault)]
        arr = block.pivot(index='severity_bin', columns='excitation_quartile', values='Identification_Mean').reindex(index=BINS[fault], columns=QS).to_numpy()
        peak = arr.max()
        coords = set(map(tuple, np.argwhere(np.abs(arr-peak) <= TOL)))
        remaining = coords.copy(); comps = []
        while remaining:
            first = remaining.pop(); component = {first}; stack = [first]
            while stack:
                i,j = stack.pop()
                for neighbor in [(i-1,j),(i+1,j),(i,j-1),(i,j+1)]:
                    if neighbor in remaining:
                        remaining.remove(neighbor); component.add(neighbor); stack.append(neighbor)
            comps.append(component)
        boundary = set()
        for i,j in coords:
            boundary.update((a,b) for a,b in [(i-1,j),(i+1,j),(i,j-1),(i,j+1)]
                            if 0<=a<4 and 0<=b<4 and (a,b) not in coords)
        near = [arr[i,j] for i,j in boundary]
        peaks = block[abs(block.Identification_Mean-peak) <= TOL]
        adjacency.append({'method':method,'fault_class':fault,'Max_Identification_Mean':peak,
            'Max_Cell_Count':len(coords),'Max_Cells':'; '.join(f'{BINS[fault][i]} {QS[j]}' for i,j in sorted(coords)),
            'Max_Cells_Min_N':int(peaks.N_unique_runs.min()),'Max_Cells_Max_N':int(peaks.N_unique_runs.max()),
            'Max_Cells_Detection_Min':float(peaks.Detection_Mean.min()),'Max_Cells_Detection_Max':float(peaks.Detection_Mean.max()),
            'Largest_Connected_Exact_Maximum_Component':max(map(len,comps)),
            'Adjacent_Nonmaximum_Min':min(near) if near else np.nan,
            'Adjacent_Nonmaximum_Max':max(near) if near else np.nan,
            'Largest_Local_Drop_From_Maximum':peak-min(near) if near else 0,
            'Selection_Basis':'Exact within-method/fault maxima; grid adjacency describes continuity, not causal optimality'})
        for _, row in peaks.iterrows():
            item = row.to_dict()
            i,j = BINS[fault].index(row.severity_bin), QS.index(row.excitation_quartile)
            item['Connected_Exact_Maximum_Component_Size'] = next(len(x) for x in comps if (i,j) in x)
            item['Maximal_Cell_Only_Not_Validated_Region'] = True
            maxima_records.append(item)
csv(pd.DataFrame(maxima_records), '15_high_performing_regions.csv')
csv(master[master.Wrong_Type_Dominates_Outcomes], '16_ambiguous_regions.csv')
csv(master[master.Missed_Detection_Dominates_Outcomes], '17_weak_observability_regions.csv')
csv(master[base+['Wrong_Fault_Type_SD', 'Missed_Detection_SD', 'Wrong_Type_Dominates_Errors']], '18_regional_error_destinations.csv')
csv(pd.DataFrame(adjacency), '24_maximum_adjacency_audit.csv')
csv(master[(master.method == 'GMO') & ~master.Empirical_Ceiling], '25_gmo_ceiling_departures.csv')
csv(master[master.Wrong_Type_Dominates_Errors], '26_wrong_type_dominant_errors.csv')

# Complete Q1-Q4 trajectories for all four diagnostic outcomes, mean and SD.
trajectory_rows = []
metrics = [('Identification','Identification_Mean','Identification_SD'),
           ('Detection','Detection_Mean','Detection_SD'),
           ('Missed detection','Missed_Detection_Mean','Missed_Detection_SD'),
           ('Wrong fault type','Wrong_Fault_Type_Mean','Wrong_Fault_Type_SD')]
for method in METHODS:
    for fault in FAULTS:
        for severity in BINS[fault]:
            b = master[(master.method==method)&(master.fault_class==fault)&(master.severity_bin==severity)].set_index('excitation_quartile').loc[QS]
            for title, mean, sd in metrics:
                item = {'method':method,'fault_class':fault,'severity_bin':severity,'metric':title}
                for q in QS:
                    item[q+'_Mean'] = float(b.loc[q,mean]); item[q+'_SD'] = float(b.loc[q,sd]); item[q+'_N_unique_runs'] = int(b.loc[q,'N_unique_runs'])
                trajectory_rows.append(item)
tr = pd.DataFrame(trajectory_rows)
csv(tr, '20_full_regional_Q_trajectories.csv')
parts = ['# Complete regional Q1-Q4 trajectories',
    'Every percentage is a five-seed mean +/- sample SD. N denotes unique simulated runs, shared across methods/seeds. No trend testing or smoothing.']
for method in METHODS:
    for fault in FAULTS:
        b = tr[(tr.method==method)&(tr.fault_class==fault)]
        pretty = b[['severity_bin','metric']].copy()
        for q in QS:
            pretty[q] = [f'{100*row[q+"_Mean"]:.2f} +/- {100*row[q+"_SD"]:.2f} (N={row[q+"_N_unique_runs"]})'
                         for _, row in b.iterrows()]
        parts += [f'## {method}: {fault}', md(pretty)]
trajectory_md = '\n\n'.join(parts)+'\n'
write('21_full_regional_Q_trajectories.md', trajectory_md)

distribution_columns = ['Identification_Mean','Detection_Mean','Identification_Detection_Gap','Missed_Detection_Mean','Wrong_Fault_Type_Mean']
dist = master[distribution_columns].quantile([0,.05,.1,.25,.5,.75,.9,.95,1]).reset_index(names='Quantile')
csv(dist, '22_regional_distribution_audit.csv')
cross = []
for (fault, severity, q), b in master.groupby(['fault_class','severity_bin','excitation_quartile'],sort=False):
    item = {'fault_class':fault,'severity_bin':severity,'excitation_quartile':q,'N_unique_runs':int(b.N_unique_runs.iloc[0])}
    for _,row in b.iterrows():
        for col in ['Identification_Mean','Detection_Mean','Missed_Detection_Mean','Wrong_Fault_Type_Mean']:
            item[row.method+'_'+col] = row[col]
    item['All_Methods_Exact_Ceiling'] = bool(b.Empirical_Ceiling.all())
    item['Identification_Min_Across_Methods'] = b.Identification_Mean.min()
    item['Identification_Max_Across_Methods'] = b.Identification_Mean.max()
    item['Detection_Min_Across_Methods'] = b.Detection_Mean.min()
    item['Detection_Max_Across_Methods'] = b.Detection_Mean.max()
    cross.append(item)
csv(pd.DataFrame(cross), '23_cross_method_regional_comparison.csv')

# Publication-sized, fully vector candidate figures, with shared 0-100 scales.
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
    'font.size':9,'axes.labelsize':9,'axes.titlesize':9.5,'xtick.labelsize':8.5,'ytick.labelsize':8,
    'pdf.fonttype':42,'ps.fonttype':42,'savefig.dpi':220,'mathtext.fontset':'stix'})


def matrix(method, fault, metric):
    b = master[(master.method==method)&(master.fault_class==fault)]
    return b.pivot(index='severity_bin', columns='excitation_quartile', values=metric).reindex(index=BINS[fault], columns=QS).to_numpy()*100


def heat(ax, method, fault, metric, title):
    a = matrix(method,fault,metric)
    im = ax.pcolormesh(np.arange(5),np.arange(5),a,cmap='viridis',vmin=0,vmax=100,
                      edgecolors='white',linewidth=.65,rasterized=False,shading='flat')
    ax.set_xlim(0,4); ax.set_ylim(4,0)
    ax.set_xticks(np.arange(4)+.5,QS)
    ax.set_yticks(np.arange(4)+.5,[s.replace(' ','') for s in BINS[fault]])
    ax.set_xlabel('Excitation stratum'); ax.set_ylabel(Y_LABELS[fault],labelpad=4)
    ax.set_title(title,loc='left',pad=6)
    ax.tick_params(length=0,pad=3)
    for i in range(4):
        for j in range(4):
            ax.text(j+.5,i+.5,f'{a[i,j]:.1f}',ha='center',va='center',fontsize=8.5,
                    color='white' if a[i,j]<55 else 'black')
    for spine in ax.spines.values(): spine.set_visible(False)
    return im


def save_fig(fig, im, name, title):
    cbax = fig.add_axes([.914,.20,.019,.62])
    cb = fig.colorbar(im,cax=cbax,ticks=[0,20,40,60,80,100])
    cb.set_label('Five-seed mean (%)',fontsize=9,labelpad=7)
    cb.ax.tick_params(labelsize=8,length=2)
    cb.solids.set_rasterized(False)
    fig.suptitle(title,fontsize=10.5,y=.977)
    fig.text(.49,.017,'Observational strata; unique-run counts are in the companion table.',
             ha='center',fontsize=7.2)
    pdf = new_path('figures/regional/'+name+'.pdf')
    png = new_path('figures/regional/'+name+'.png')
    fig.savefig(pdf,metadata={'Title':title,'Subject':'Existing frozen joint summaries; observational descriptive characterization',
                             'Creator':'run_regional_characterization.py'})
    fig.savefig(png)
    plt.close(fig)


for method in METHODS:
    fig, axes = plt.subplots(2,2,figsize=(7.16,6.25))
    fig.subplots_adjust(left=.135,right=.872,bottom=.12,top=.895,wspace=.59,hspace=.60)
    for ax, fault, metric, letter in zip(axes.flat,['LoE','Friction','LoE','Friction'],
         ['Identification_Mean','Identification_Mean','Detection_Mean','Detection_Mean'],'abcd'):
        title = f'({letter}) {fault} '+('identification' if metric=='Identification_Mean' else 'detection')
        im = heat(ax,method,fault,metric,title)
    save_fig(fig,im,method+'_regional_dashboard',method+' regional diagnostic profile')
for fault in FAULTS:
    fig,axes = plt.subplots(2,2,figsize=(7.16,6.25))
    fig.subplots_adjust(left=.135,right=.872,bottom=.12,top=.895,wspace=.59,hspace=.60)
    for ax,method,letter in zip(axes.flat,METHODS,'abcd'):
        im = heat(ax,method,fault,'Identification_Mean',f'({letter}) {method}')
    save_fig(fig,im,fault+'_regional_comparison',fault+' identification across severity and excitation strata')

# Evidence-led narrative. All complete maps and trajectories are appended.
story = '''# Regional diagnostic characterization

## Integrity, units and descriptive conventions

PASS: 192 method/fault/severity/Q cells; 48 unique-run cells, all populated. Each run retains all four common-CWT methods and five training seeds. Source metrics are the existing joint-analysis CSVs, checked against canonical run keys and counts. All requested identities pass at 1e-12 tolerance. Fractions in CSVs use 0-1 units; report/figure values use percent, and identification-detection gaps are percentage points. Seed SD is sample SD and does not quantify run-sampling uncertainty. Friction bins remain dimensionless s_F, with Delta F_c = 2.15 s_F N m.

The distribution has a large ceiling mass (64 exact identification-ceiling cells and 91 exact detection-ceiling cells). No clear universal separator defines near-ceiling versus transitional identification. We therefore impose no fixed identification/detection cutoff and no forced favorable/ambiguous/weak partition of every cell.

Region indexes have explicit, reproducible meanings:
- 15_high_performing_regions.csv records exact within-method/fault maximum cells and connected exact-maximum components. It is a peak index, not certification that an isolated maximum is a broad favorable region. Neighbor ranges and local drops are in 24_maximum_adjacency_audit.csv.
- 16_ambiguous_regions.csv records the four strongest ambiguity cases where wrong fault type is the largest of identification, wrong type and missed detection. This is outcome plurality, not a significance test or universal detection threshold. Other meaningful but less extreme gaps remain in the master/error tables and 26_wrong_type_dominant_errors.csv.
- 17_weak_observability_regions.csv records the 16 cells where predicted Nominal is the largest outcome; twelve have a strict Nominal majority, while four have a Nominal plurality. These are empirically missed-detection-dominant cells.
- Other cells remain numerically characterized, with residual-error dominance noted. A high-identification cell with its few errors mostly wrong-type is not automatically labeled ambiguous.

## 1. SHAPE DIAGNOSTIC ENVELOPE

LoE: the weakest severity band has identification 50.42-55.12% across Q and detection 66.27-76.67%. Both missed detection and wrong-fault confusion remain appreciable. At Q3, identification is 50.42%, detection 76.67%, missed detection 23.33% and wrong type 26.25%. Higher-Q advantages are apparent in stronger bands, especially the strongest trajectory 85.33 -> 92.20 -> 95.43 -> 97.53%; the second band reverses after Q3 (68.95 -> 78.87 -> 90.00 -> 82.80%). These are observed patterns, not independent excitation effects.

Friction: the weakest evaluated bin remains poor at every Q: identification 11.20-22.79%, detection 22.80-31.05%, with 68.95-77.20% predicted Nominal. The strongest bin forms a broad observed high-identification region: 94.93 -> 98.95 -> 98.49 -> 99.31%, accompanied by detection 98.51 -> 100.00 -> 100.00 -> 99.31%. The Q4 maximum has N=29, but its adjacent Q cells are also high; the plateau claim does not rest on that one maximum. At intermediate severity, detection can substantially exceed identification, e.g. [0.10,0.30) Q2: 74.29% versus 57.71%, with 16.57% assigned another fault class.

Vibration: a broad plateau spans the map, with identification 94.76-100%. The lowest-amplitude Q4 departure is predominantly missed detection (5.24%), while higher-amplitude cells are almost all at ceiling.

## 2. TORQUE DIAGNOSTIC ENVELOPE

LoE: the weakest band remains approximately flat in identification (35.83 -> 37.07 -> 35.83 -> 37.65%), while detection changes non-monotonically (57.08 -> 70.24 -> 58.33 -> 57.65%). Nominal predictions dominate the outcomes at Q1/Q3/Q4; at Q2 the 33.17 pp detection-identification gap accompanies both wrong-class confusion and missed detection. The second severity bin increases throughout Q (51.58 -> 68.68 -> 78.70 -> 80.80%); the third is non-monotonic, and the strongest increases (85.33 -> 91.22 -> 92.57 -> 98.27%).

Friction: no severity band establishes a consistent universal Q relationship. The weakest and second bands reverse, the third stays within 89.73-92.67%, and the strongest is high but non-monotonic (91.04 -> 94.74 -> 93.58 -> 95.86%). The weakest bin has 73.68-88.42% missed detection, much greater than its wrong-type fraction (1.05-6.40%). Intermediate [0.10,0.30) also has substantial missed detection (31.70-42.86%).

Vibration: the main weakness is localized to the lowest amplitude, increasingly apparent at Q3/Q4: identification 89.13 -> 88.75 -> 76.86 -> 72.86%, detection 90.43 -> 89.58 -> 79.61 -> 76.67%. At Q4, 23.33% are predicted Nominal and 3.81% another fault. Higher amplitudes have 96.08-100% identification apart from a very small third-bin Q3 departure. The exact ceiling component is therefore broad at higher amplitude but not uniform across the whole amplitude/Q map.

## 3. GMO DIAGNOSTIC ENVELOPE

Vibration is exactly 100% identified and detected in all 16 cells. LoE is 96.59-100% in the three stronger severity bands, with 100% detection there; non-ceiling errors in those stronger bands are wrong-class assignments. Weakest LoE has identification 96.67 -> 97.56 -> 95.83 -> 91.37% and detection 99.17 -> 97.56 -> 98.33 -> 96.86%. At Q4 its 8.63% total identification error comprises 3.14% missed detection and 5.49% wrong type.

The principal non-ceiling Friction region is the weakest bin: identification 48.40 -> 61.86 -> 74.74 -> 76.84%, detection 50.00 -> 66.98 -> 76.14 -> 78.42%. Missed detection dominates its errors at every Q (50.00 -> 33.02 -> 23.86 -> 21.58%), rather than broad class confusion. The second Friction bin remains 94.29-100%; the strongest two remain 99.67-100%. Exact departures from ceiling are tabulated in 25_gmo_ceiling_departures.csv and below. Ceiling departure has no temporal meaning: these are unordered observational cells.

## 4. EO DIAGNOSTIC ENVELOPE

Weakest LoE provides the clearest detection/identification separation. Identification increases 21.67 -> 31.71 -> 40.42 -> 43.53%, while detection is 71.67 -> 84.88 -> 84.58 -> 70.59%. The destination Friction fractions are 50.00 -> 53.17 -> 44.17 -> 26.27%; Nominal fractions are 28.33 -> 15.12 -> 15.42 -> 29.41%. Vibration receives zero predictions in Q1-Q3 and 0.78% in Q4. Thus Q4 identification is higher despite lower detection than Q2/Q3; a binary metric alone misses this difference. In the second LoE bin at Q1, 38.95% identification accompanies 88.42% detection, with 49.47% assigned Friction. Even third-bin Q1 detection is 97.83% versus 66.96% identification. Strongest-bin Q2-Q4 identification reaches 95.61-98.52% with 100% detection, forming a neighboring-cell high-identification region rather than merely a detection region.

Friction: improvement is broad in endpoint direction but not uniformly monotonic. Weakest-bin identification is 16.40 -> 32.09 -> 37.19 -> 35.79%; second-bin identification increases throughout (54.34 -> 63.43 -> 68.09 -> 83.46%). The third increases from 83.33% to around 95% after Q1; the strongest remains 93.43-97.36%. Weakest-bin errors are mostly Nominal; at third-bin Q1, 97.67% detection versus 83.33% identification instead leaves 14.33% wrong-type predictions and only 2.33% missed detection. The strongest-bin maximum at Q3 (97.36%, N=53) has neighboring Q2/Q4 values of 95.79/95.86%, supporting a broad observed plateau.

Vibration: identification is 100% in 14 cells and 99.61% in one; lowest-amplitude Q1 is 91.74%, comprising 6.09% missed detection and 2.17% wrong type. This is a broad high-identification profile with one localized qualification.

## 5. LOE REGIONS

Weakest LoE is not a common failure region for all methods. SHAPE/Torque/EO have differing mixtures of misses and wrong-type errors, while GMO remains much higher in identification. Strongest LoE Q3/Q4 is a shared favorable observed region: all four have at least 92.57% identification in those cells and at least 99.43% detection. At strongest-bin Q1, detection is already 96-100% across methods but identification spans 82.67-100%, so much of the difference concerns fault type rather than detecting abnormality. Full four-method regional comparisons are in 23_cross_method_regional_comparison.csv.

## 6. FRICTION REGIONS

Weakest Friction is the shared vulnerability: Q1 identification spans 10.00-48.40% and detection 16.40-50.00%. GMO improves across Q but remains below its stronger-bin ceiling profile. SHAPE/Torque/EO remain missed-detection dominated in every weakest-bin cell. In the strongest Friction bin, all methods have identification at least 91.04% across all Q and detection at least 96.42%; this broad favorable observed region survives adjacent-Q examination. Its Q4 count is 29 for every method and should remain explicit.

At second-bin Q2, methods differ substantially in missed detection: SHAPE 25.71%, Torque 42.86%, GMO 2.29%, EO 24.57%. At third-bin Q1, detection is 96.33-100% while identification is 83.33-99.67%; remaining differences are predominantly wrong-type assignments for SHAPE/Torque/EO and a very small wrong-type fraction for GMO. These distinguish lack of detection from lack of correct fault-type identification.

## 7. VIBRATION REGIONS

GMO is at ceiling everywhere; SHAPE/EO remain high except localized lowest-amplitude qualifications. Torque's lowest-amplitude Q3/Q4 cells supply the meaningful contrast: most of its error there is missed detection. The strongest two amplitude bins form a broad near-ceiling region across all four formulations, with minimum identification 99.18%. No amplitude-frequency inference is introduced here.

## 8. DETECTABLE-BUT-AMBIGUOUS REGIONS

Four cells have wrong fault type as the largest outcome: EO weakest LoE Q1/Q2/Q3 and EO second-bin LoE Q1. Their detection means span 71.67-88.42%, identification 21.67-40.42%, and wrong-type fractions 44.17-53.17%. The largest observed gap is EO weakest LoE Q2, 53.17 pp. These provide the most distinct core ambiguity pattern without imposing arbitrary score cutoffs.

Less extreme, still meaningful examples include EO third-bin LoE Q1 (gap 30.87 pp, detection 97.83%), SHAPE second-bin LoE Q1 (22.63 pp, detection 91.58%), Torque second-bin LoE Q1 (31.05 pp, detection 82.63%), and EO third-bin Friction Q1 (14.33 pp, detection 97.67%). Such cases remain fully quantified even when wrong-type fraction is not the largest overall outcome. In total, 74 cells have more wrong-type errors than misses, but many are high-identification cells with very few errors and must not all be called ambiguous.

## 9. WEAK-OBSERVABILITY REGIONS

The 16 Nominal-plurality cells comprise all twelve weakest-Frict ion cells for SHAPE/Torque/EO, GMO weakest Friction Q1, and Torque weakest LoE Q1/Q3/Q4. (The spelling of Friction is retained normally in all data tables.) Twelve are strict Nominal-majority cases. Most severe observed examples are weakest Friction Torque Q4 (88.42% missed, 11.58% detection) and Q1 (83.60% missed, 16.40% detection), and SHAPE Q1 (77.20% missed, 22.80% detection). This category describes empirical diagnostic detection capability, not formal system-theoretic observability.

## 10. BROAD HIGH-IDENTIFICATION REGIONS

Supported plateaus include SHAPE/EO Vibration; GMO Vibration and stronger LoE/Friction; SHAPE strongest Friction across all Q; EO strongest Friction across all Q; Torque stronger Vibration and strongest Friction. Strongest LoE high-Q cells are favorable for all four, while Q1 is less uniformly high for SHAPE/Torque/EO. Favorable observed regions must be described with their actual ranges, counts and adjacent cells, rather than inferred from a single maximum.

Exact-maximum topology can differ from practical continuity. For example, SHAPE's strongest Friction Q4 is its single maximum (99.31%) but its same-band neighboring Q values remain 94.93-98.95%; conversely, Torque Vibration exact maxima adjoin lowest-bin Q3 identification of 76.86%, so its plateau must be restricted to stronger amplitudes rather than expanded to the whole grid. No statistical robustness claim follows from neighboring high means.

## 11. WHICH RESULTS ARE STRONG ENOUGH FOR V.C

Scientifically clear descriptive additions: LoE's severity-specific identification and error-mode differences; Friction's within-bin/marginal distinction and broad strongest-bin versus weakest-bin contrast; EO weak-LoE confusion destinations; and Torque's lowest-amplitude Vibration missed-detection localization. Retain selected numerical anchors and count support. Identification and detection answer different questions and should not be collapsed into one favorable/poor score. The profiles support V.C observations, not inferential or causal claims.

## 12. WHICH RESULTS BELONG ONLY IN APPENDIX/V.G

Complete 192-cell master tables, all 192 four-point outcome trajectories, seven full dashboards/comparisons and exact ceiling-departure lists belong in supporting material unless a specific panel is selected for main text. Method-wide envelopes and broad cross-experiment interpretation belong in V.G; the present analysis establishes only local E3 joint descriptive profiles. The Vibration full map is mostly ceiling cells and remains secondary. Counts and seed SDs must remain available alongside any selected main evidence.

## Claim boundaries and numerical interpretation

These are observational severity-excitation strata, with post-fault measured Joint-2 velocity RMS. No quartiles or severity bins were changed. No causal excitation effect, controlled interaction, causal mechanism, optimal operating region, significance/equivalence claim, deployment recommendation or global winner is established. Adjacency indicates neighboring observed means, not validation under new trajectories or sensors. The descriptive region files are indexes of specific observed patterns, not an exhaustive threshold-based classifier. All 48 unique-run cells are populated; the only N<30 cell is strongest Friction Q4 (N=29). Across-seed SD can be appreciable in low-identification regions (e.g. EO weakest LoE Q3 identification SD 13.23 pp) and should not be mistaken for a confidence interval.
'''
story = story.replace('weakest-Frict ion','weakest-Friction').replace(' (The spelling of Friction is retained normally in all data tables.)','')

dist_pretty = dist.copy()
for col in distribution_columns: dist_pretty[col] = (100*dist_pretty[col]).map(lambda v:f'{v:.2f}')
story += '\n## Distribution audit (percent; gap in pp)\n\n'+md(dist_pretty)+'\n'

story += '\n## Required complete SHAPE and Torque maps\n\nMeans in percent; gap is Detection minus Identification in pp. Cell counts are shared across methods.\n'
for method in ['SHAPE','Torque']:
    for fault in ['LoE','Friction']:
        for title,metric in [('Identification','Identification_Mean'),('Detection','Detection_Mean'),
                             ('Detection minus identification','Identification_Detection_Gap')]:
            vals = matrix(method,fault,metric)
            tab = pd.DataFrame(vals,index=BINS[fault],columns=QS).map(lambda v:f'{v:.2f}').reset_index(names='Severity bin')
            story += f'\n### {method}: {fault} - {title}\n\n'+md(tab)+'\n'

story += '\n## Exact GMO ceiling departures\n\nOnly non-ceiling cells are listed. All omitted GMO cells have 100% identification.\n\n'
gmo = master[(master.method=='GMO')&~master.Empirical_Ceiling][['fault_class','severity_bin','excitation_quartile','N_unique_runs',
    'Identification_Mean','Detection_Mean','Missed_Detection_Mean','Wrong_Fault_Type_Mean']].copy()
for col in gmo.columns[4:]: gmo[col] = (100*gmo[col]).map(lambda v:f'{v:.2f}')
story += md(gmo)+'\n'

story += '\n## Per-method/fault maxima and adjacency\n\n'
ap = pd.DataFrame(adjacency)[['method','fault_class','Max_Identification_Mean','Max_Cell_Count',
    'Largest_Connected_Exact_Maximum_Component','Adjacent_Nonmaximum_Min','Adjacent_Nonmaximum_Max','Max_Cells_Min_N','Max_Cells_Max_N']].copy()
for col in ['Max_Identification_Mean','Adjacent_Nonmaximum_Min','Adjacent_Nonmaximum_Max']:
    ap[col] = ap[col].map(lambda v:'All cells maximal' if pd.isna(v) else f'{100*v:.2f}%')
story += md(ap)+'\n'

story += '\n## Unique-run count support\n\n'
for fault in FAULTS:
    cm = counts[counts.fault_class==fault].pivot(index='severity_bin',columns='excitation_quartile',values='Canonical_N').reindex(index=BINS[fault],columns=QS)
    cm['Total'] = cm.sum(axis=1); cm.loc['Total'] = cm.sum(axis=0)
    story += '\n### '+fault+'\n\n'+md(cm.reset_index(names='Severity bin'))+'\n'

story += '\n## Complete Q1-Q4 trajectories\n\n'+trajectory_md.replace('# Complete regional Q1-Q4 trajectories','')
story += '\n## Figure design and candidate captions\n\n'
story += '''Four method dashboards have LoE/Friction columns and identification/detection rows. Three cross-method maps show identification only with SHAPE/Torque/GMO/EO panels. All panels use identical 0-100% scales, one-decimal mean annotations and one shared colorbar. Final dimensions are 7.16 x 6.25 inches; typography is Times New Roman, annotations 8.5 pt, titles 9.5 pt, axis labels 9 pt, severity ticks 8 pt. PDFs contain vector panels/text/colorbars; PNG previews are also provided.\n\nDashboard caption template: Five-seed mean correct fault identification and binary detection for [method] across observational severity-excitation strata. Columns show LoE and Friction; rows show identification and detection. Q1-Q4 reuse the archived post-fault Joint-2 velocity-RMS strata. Colors and annotations indicate percentages on a common 0-100% scale. Friction severity is dimensionless s_F. Unique simulated-run counts are provided in the companion table; sample SDs are available in the regional tables.\n\nComparison caption template: Five-seed mean [fault] identification for SHAPE, Torque, GMO and EO under the common CWT representation across observational severity-excitation strata. Colors and annotations indicate percentages on a common 0-100% scale. Q1-Q4 reuse the archived post-fault Joint-2 velocity-RMS strata. Counts and sample SDs are provided in the companion tables.\n'''
write('19_regional_summary.md',story)

# Preserve every previous output and frozen source; new files are separately indexed.
changed_frozen = [p for p,h in before_frozen.items() if not Path(p).is_file() or sha(Path(p)) != h]
added_frozen = [str(p) for p in FROZEN.rglob('*') if p.is_file() and str(p) not in before_frozen]
changed_previous = [p for p,h in before_previous.items() if not Path(p).is_file() or sha(Path(p)) != h]
assert not changed_frozen and not added_frozen and not changed_previous
assert sha(TEX) == tex_before
provenance = {'timestamp_utc':datetime.now(timezone.utc).isoformat(),
    'source_canonical_sha256':sha(SOURCE),'script':str(Path(__file__).resolve()),'script_sha256':sha(Path(__file__)),
    'python_version':platform.python_version(),'pandas_version':pd.__version__,'numpy_version':np.__version__,
    'matplotlib_version':matplotlib.__version__,'frozen_files_checked':len(before_frozen),
    'prior_files_checked':len(before_previous),'frozen_changed_files':changed_frozen,'frozen_added_files':added_frozen,
    'prior_changed_files':changed_previous,'Final_Report_unchanged':True,'identity_checks':errors,
    'master_rows':len(master),'trajectory_rows':len(tr),'pdf_count':7,
    'exact_identification_ceiling_cells':int(master.Empirical_Ceiling.sum()),
    'exact_detection_ceiling_cells':int(np.isclose(master.Detection_Mean,1,atol=TOL,rtol=0).sum()),
    'core_ambiguity_cells':int(master.Wrong_Type_Dominates_Outcomes.sum()),
    'nominal_plurality_cells':int(master.Missed_Detection_Dominates_Outcomes.sum()),
    'nominal_majority_cells':int((master.Missed_Detection_Mean>.5+TOL).sum()),
    'source_inputs':[{ 'path':str(OUT/f),'sha256':sha(OUT/f)} for f in ['03_joint_multiclass_recall.csv','04_joint_binary_detection.csv',
                         '05_joint_confusion_destinations.csv','03_joint_metrics_by_seed.csv']],
    'generated_files':[{ 'path':str(p.relative_to(OUT)),'sha256':sha(p)} for p in OUT.rglob('*')
                       if p.is_file() and str(p) not in before_previous]}
write('27_regional_provenance.json',json.dumps(provenance,indent=2))
print(json.dumps({'status':'PASS','master_rows':len(master),'trajectory_rows':len(tr),'identity_errors':errors,
    'core_ambiguity_cells':provenance['core_ambiguity_cells'],'nominal_plurality_cells':provenance['nominal_plurality_cells'],
    'frozen_files_unchanged':len(before_frozen),'previous_files_unchanged':len(before_previous),'generated_pdf_count':7},indent=2))
