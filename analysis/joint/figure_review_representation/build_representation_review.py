"""Read-only frozen-prediction summaries and four review-only vector maps.

Run with the original joint-analysis Python: --phase tables, then --phase figures.
Never trains, infers, simulates, refits bins/Q, or overwrites an existing output.
All scientific fractions are saved at full double precision. Figures show percent.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
FROZEN = Path(r'C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY')
REPORT = Path(r'C:\Users\Johnny\Desktop\Git\Image Processing Project\Latex Report')
TEX = REPORT / 'Final_Report.tex'
PARQUET = FROZEN / 'derived/canonical_e0_primary.parquet'
MASTER = ROOT / '10_regional_master_table.csv'
ORIGINALS = [REPORT / 'figures/E3/E3_joint_severity_excitation_profiles.pdf',
             REPORT / 'figures/E3/E3_joint_severity_excitation_detection.pdf']
REPS = ['shape_cwt', 'shape_temporal', 'shape_fft']
NAMES = dict(zip(REPS, ['CWT', 'Temporal', 'FFT']))
SEEDS = [1729, 2027, 4099, 7919, 104729]
FAULTS = ['LoE', 'Friction', 'Vibration']
QS = ['Q1', 'Q2', 'Q3', 'Q4']
BINS = {
    'LoE': ['[0.02, 0.05)', '[0.05, 0.10)', '[0.10, 0.20)', '[0.20, 0.30]'],
    'Friction': ['[0.02, 0.10)', '[0.10, 0.30)', '[0.30, 0.75)', '[0.75, 1.50]'],
    'Vibration': ['[0.10, 0.50)', '[0.50, 1.00)', '[1.00, 1.75)', '[1.75, 2.50]']}
METRICS = ['Identification', 'Detection', 'Missed_Detection', 'Wrong_Fault_Type']
KEY = ['fault_class', 'severity_bin', 'excitation_quartile', 'representation']
CELL = KEY[:3]
TOL = 1e-12  # numerical reconstruction tolerance, not an effect-size threshold
WIDTH, HEIGHT = 7.16, 3.55

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def snapshot():
    paths = {p for base in [ROOT, FROZEN] for p in base.rglob('*')
             if p.is_file() and not p.is_relative_to(OUT)} | {TEX, *ORIGINALS}
    return {str(p): sha(p) for p in sorted(paths, key=str)}

def output(name):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    if p.exists():
        raise FileExistsError(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def write_json(name, obj):
    output(name).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')

def write_csv(name, df):
    df.to_csv(output(name), index=False, float_format='%.17g')

def sorted_frame(df, keys):
    ranks = {'fault_class': {v:i for i,v in enumerate(FAULTS)},
             'severity_bin': {v:i for bins in BINS.values() for i,v in enumerate(bins)},
             'excitation_quartile': {v:i for i,v in enumerate(QS)},
             'representation': {v:i for i,v in enumerate(REPS)},
             'seed': {v:i for i,v in enumerate(SEEDS)}}
    return df.sort_values(keys, key=lambda s: s.map(ranks[s.name])).reset_index(drop=True)

def validate_population(d):
    assert len(d) == 33750, ('filtered rows', len(d))
    assert set(d.seed) == set(SEEDS)
    assert set(d.cohort) == {'PRIMARY'}
    assert d[KEY + ['run_uid', 'seed', 'parent_trajectory_id', 'dq2_rms_post']].notna().all().all()
    assert not d.duplicated(['run_uid', 'representation', 'seed']).any()
    assert d.groupby('run_uid').size().eq(15).all()
    counts = d.groupby('fault_class').run_uid.nunique()
    assert counts.to_dict() == {f:750 for f in FAULTS}, counts.to_dict()
    for fault in FAULTS:
        reference = set(d.loc[d.fault_class.eq(fault), 'run_uid'])
        for rep in REPS:
            for seed in SEEDS:
                sample = d[d.fault_class.eq(fault) & d.representation.eq(rep) & d.seed.eq(seed)]
                assert len(sample) == 750 and set(sample.run_uid) == reference
    for field in ['fault_class','severity_bin','excitation_quartile','dq2_rms_post',
                  'parent_trajectory_id','split','cohort','s_LoE','s_Friction','A_d']:
        assert d.groupby('run_uid')[field].nunique(dropna=False).eq(1).all(), field
    for fault in FAULTS:
        sub = d[d.fault_class.eq(fault)]
        assert set(sub.severity_bin) == set(BINS[fault])
        assert set(sub.excitation_quartile) == set(QS)
    pred = d.prediction_class
    assert set(pred).issubset({'Nominal', *FAULTS})
    expected = {'true_binary': pd.Series(True,index=d.index),
                'predicted_binary': pred.ne('Nominal'),
                'is_correct_binary': pred.ne('Nominal'),
                'is_correct_multiclass': pred.eq(d.fault_class),
                'is_missed_detection': pred.eq('Nominal'),
                'is_mechanism_confusion': pred.ne('Nominal') & pred.ne(d.fault_class)}
    for field, correct in expected.items():
        assert np.array_equal(d[field].astype(bool), correct), field
    return counts.to_dict()

def reconstruct(seed_table, keys):
    records = []
    for values, group in seed_table.groupby(keys + ['seed'], sort=False):
        row = dict(zip(keys + ['seed'], values))
        row['N_unique_runs'] = int(group.N_unique_runs.sum())
        for metric in METRICS:
            row[metric] = float(np.average(group[metric], weights=group.N_unique_runs))
        records.append(row)
    reconstructed = pd.DataFrame(records)
    result = []
    for values, group in reconstructed.groupby(keys, sort=False):
        row = dict(zip(keys, values))
        assert len(group) == 5 and group.N_unique_runs.nunique() == 1
        row['N_unique_runs'] = int(group.N_unique_runs.iloc[0])
        for metric in METRICS:
            row[metric+'_Mean'] = group[metric].mean()
            row[metric+'_SD'] = group[metric].std(ddof=1)
        result.append(row)
    return pd.DataFrame(result), reconstructed

def make_tables():
    before = snapshot()
    manifest = json.loads((FROZEN / 'audit/analysis_manifest.json').read_text(encoding='utf-8-sig'))
    assert sha(PARQUET) == manifest['derived'][PARQUET.name]['sha256']
    for name in ['T06_E1_severity.csv', 'T09_E3_excitation.csv']:
        assert sha(FROZEN/'tables'/name) == manifest['tables'][name]['sha256']
    d = pd.read_parquet(PARQUET)
    d = d[d.split.eq('test') & d.representation.isin(REPS) & d.fault_class.isin(FAULTS)].copy()
    run_counts = validate_population(d)
    d['Identification'] = d.is_correct_multiclass.astype(float)
    d['Detection'] = d.is_correct_binary.astype(float)
    d['Missed_Detection'] = d.prediction_class.eq('Nominal').astype(float)
    d['Wrong_Fault_Type'] = (d.prediction_class.ne('Nominal') & d.prediction_class.ne(d.fault_class)).astype(float)
    grouped = d.groupby(KEY+['seed'], sort=False)
    seed_table = grouped[METRICS].mean().reset_index()
    seed_table['N_unique_runs'] = grouped.run_uid.nunique().to_numpy()
    seed_table = sorted_frame(seed_table, KEY+['seed'])
    assert len(seed_table) == 720 and seed_table.N_unique_runs.gt(0).all()
    assert np.max(np.abs(seed_table.Identification+seed_table.Wrong_Fault_Type+seed_table.Missed_Detection-1)) < TOL
    assert np.max(np.abs(seed_table.Detection-seed_table.Identification-seed_table.Wrong_Fault_Type)) < TOL
    assert np.max(np.abs(seed_table.Detection+seed_table.Missed_Detection-1)) < TOL
    rows = []
    for values, group in seed_table.groupby(KEY,sort=False):
        row = dict(zip(KEY, values))
        assert len(group) == 5 and group.N_unique_runs.nunique() == 1
        row['Pipeline'] = NAMES[row['representation']]
        row['N_unique_runs'] = int(group.N_unique_runs.iloc[0])
        for metric in METRICS:
            row[metric+'_Mean'] = float(group[metric].mean())
            row[metric+'_SD'] = float(group[metric].std(ddof=1))
        rows.append(row)
    summary = sorted_frame(pd.DataFrame(rows), KEY)
    assert len(summary) == 144
    counts = d.drop_duplicates('run_uid').groupby(CELL,sort=False).run_uid.nunique().reset_index(name='N_unique_runs')
    counts = sorted_frame(counts,CELL)
    assert len(counts) == 48 and counts.N_unique_runs.sum() == 2250
    for _, row in summary.iterrows():
        cell = counts[(counts[CELL] == row[CELL]).all(axis=1)]
        assert len(cell) == 1 and int(cell.N_unique_runs.iloc[0]) == row.N_unique_runs
    sev, sev_seed = reconstruct(seed_table,['fault_class','severity_bin','representation'])
    q, q_seed = reconstruct(seed_table,['fault_class','excitation_quartile','representation'])
    q_all, q_all_seed = reconstruct(seed_table,['excitation_quartile','representation'])
    checks = []
    def check(source, condition, metric, actual, expected):
        diff = abs(float(actual)-float(expected))
        checks.append({'Source':source,'Condition':condition,'Field':metric,
                       'Reconstructed':actual,'Reference':expected,'Abs_Difference':diff,'PASS':diff<TOL})
        assert diff < TOL, checks[-1]
    t06 = pd.read_csv(FROZEN/'tables/T06_E1_severity.csv')
    mapping = {'Identification':'Multiclass_Recall','Detection':'Binary_Detection',
               'Missed_Detection':'Missed_Detection','Wrong_Fault_Type':'Mechanism_Confusion'}
    for _, row in sev.iterrows():
        r = t06[t06.Fault_Class.eq(row.fault_class) & t06.Severity_Bin.eq(row.severity_bin) & t06.rep_key.eq(row.representation)]
        assert len(r) == 1
        r = r.iloc[0]; condition = f'{row.fault_class}|{row.severity_bin}|{row.representation}'
        check('T06',condition,'N_per_Seed',row.N_unique_runs,r.N_per_Seed)
        for metric, ref in mapping.items():
            for stat in ['Mean','SD']:
                check('T06',condition,ref+'_'+stat,row[metric+'_'+stat],r[ref+'_'+stat])
        check('T06',condition,'Destination_Nominal_Mean',row.Missed_Detection_Mean,r.Destination_Nominal_Mean)
        check('T06',condition,'Destination_OtherFault_Mean',row.Wrong_Fault_Type_Mean,r.Destination_OtherFault_Mean)
        # Independent direct marginal from prediction rows guards the weighting.
        direct = d[d.fault_class.eq(row.fault_class) & d.severity_bin.eq(row.severity_bin) & d.representation.eq(row.representation)].groupby('seed')[METRICS].mean()
        weighted = sev_seed[sev_seed.fault_class.eq(row.fault_class) & sev_seed.severity_bin.eq(row.severity_bin) & sev_seed.representation.eq(row.representation)].set_index('seed')
        assert np.max(np.abs(direct.sort_index()[METRICS].to_numpy()-weighted.sort_index()[METRICS].to_numpy())) < TOL
    t09 = pd.read_csv(FROZEN/'tables/T09_E3_excitation.csv')
    for _, row in q.iterrows():
        r = t09[t09.Excitation_Quartile.eq(row.excitation_quartile) & t09.rep_key.eq(row.representation)]
        assert len(r) == 1
        r = r.iloc[0]; condition = f'{row.fault_class}|{row.excitation_quartile}|{row.representation}'
        for stat in ['Mean','SD']:
            field = row.fault_class+'_Recall_'+stat
            check('T09',condition,field,row['Identification_'+stat],r[field])
    for _, row in q_all.iterrows():
        r = t09[t09.Excitation_Quartile.eq(row.excitation_quartile) & t09.rep_key.eq(row.representation)].iloc[0]
        condition = f'ALL_FAULTY|{row.excitation_quartile}|{row.representation}'
        for stat in ['Mean','SD']:
            check('T09',condition,'Fault_Detection_'+stat,row['Detection_'+stat],r['Fault_Detection_'+stat])
    master = pd.read_csv(MASTER)
    for _, row in summary[summary.representation.eq('shape_cwt')].iterrows():
        r = master[master.method.eq('SHAPE') & master.fault_class.eq(row.fault_class) & master.severity_bin.eq(row.severity_bin) & master.excitation_quartile.eq(row.excitation_quartile)]
        assert len(r)==1
        r=r.iloc[0]; condition=f'{row.fault_class}|{row.severity_bin}|{row.excitation_quartile}|SHAPE'
        check('Existing_master',condition,'N_unique_runs',row.N_unique_runs,r.N_unique_runs)
        for metric in METRICS:
            for stat in ['Mean','SD']:
                check('Existing_master',condition,metric+'_'+stat,row[metric+'_'+stat],r[metric+'_'+stat])
    # Full Q trajectories, never endpoints only.
    lines = ['# Full Q trajectories: frozen SHAPE pipeline review','',
             'All values are percentages, mean +/- sample SD across five training seeds. Each Q cell uses its own fixed run population.',
             'Q1-Q4 are observational, based on post-fault measured Joint 2 velocity RMS. Friction severity is dimensionless; Vibration bins use N m.',
             'Identification = correct fault type; detection = any faulty prediction. Wrong type = another faulty class; missed = Nominal.', '']
    for fault in FAULTS:
        for metric in METRICS:
            lines += [f'## {fault}: {metric.replace("_"," ")}', '', '| Pipeline | Severity | Q1 | Q2 | Q3 | Q4 |', '|---|---|---|---|---|---|']
            for rep in REPS:
                for severity in BINS[fault]:
                    group=summary[summary.fault_class.eq(fault) & summary.representation.eq(rep) & summary.severity_bin.eq(severity)].set_index('excitation_quartile')
                    values = [f'{100*group.loc[quartile,metric+"_Mean"]:.2f} +/- {100*group.loc[quartile,metric+"_SD"]:.2f} (N={int(group.loc[quartile,"N_unique_runs"])})' for quartile in QS]
                    lines.append('| '+NAMES[rep]+' | '+severity+' | '+' | '.join(values)+' |')
            lines.append('')
    # Descriptive adjacent-Q differences and seed sign agreement; not tests.
    adjacent = []
    for fault in FAULTS:
        for severity in BINS[fault]:
            for rep in REPS:
                group=seed_table[seed_table.fault_class.eq(fault) & seed_table.severity_bin.eq(severity) & seed_table.representation.eq(rep)]
                for metric in METRICS:
                    pivot=group.pivot(index='seed',columns='excitation_quartile',values=metric).loc[SEEDS,QS]
                    for qa,qb in zip(QS[:-1],QS[1:]):
                        delta=pivot[qb]-pivot[qa]
                        adjacent.append({'fault_class':fault,'severity_bin':severity,'representation':rep,
                            'Metric':metric,'Q_from':qa,'Q_to':qb,'Delta_Mean':delta.mean(),'Delta_SD':delta.std(ddof=1),
                            'Positive_Seeds':int((delta>TOL).sum()),'Negative_Seeds':int((delta<-TOL).sum()),'Equal_Seeds':int((abs(delta)<=TOL).sum())})
    # Full within-cell comparisons, including all inversion/error regions.
    comparative=[]
    for _, c in counts.iterrows():
        group=summary[(summary[CELL]==c[CELL]).all(axis=1)].set_index('representation')
        row={k:c[k] for k in CELL}; row['N_unique_runs']=int(c.N_unique_runs)
        for rep in REPS:
            for metric in METRICS:
                for stat in ['Mean','SD']:
                    row[NAMES[rep]+'_'+metric+'_'+stat]=float(group.loc[rep,metric+'_'+stat])
        for metric in METRICS:
            row['Temporal_minus_CWT_'+metric]=float(group.loc['shape_temporal',metric+'_Mean']-group.loc['shape_cwt',metric+'_Mean'])
        row['CWT_detects_more_and_wrong_types_more']=bool(row['Temporal_minus_CWT_Detection']<-TOL and row['Temporal_minus_CWT_Wrong_Fault_Type']<-TOL)
        row['Temporal_identifies_more_and_misses_more']=bool(row['Temporal_minus_CWT_Identification']>TOL and row['Temporal_minus_CWT_Missed_Detection']>TOL)
        wm=row['FFT_Wrong_Fault_Type_Mean']-row['FFT_Missed_Detection_Mean']
        row['FFT_larger_error_component']='Wrong fault type' if wm>TOL else ('Missed detection' if wm<-TOL else 'Equal')
        outcome={m:row['FFT_'+m+'_Mean'] for m in ['Identification','Missed_Detection','Wrong_Fault_Type']}
        row['FFT_largest_mean_outcome']=max(outcome,key=outcome.get)
        comparative.append(row)
    assert before == snapshot(), 'Protected files changed'
    write_csv('joint_SHAPE_pipeline_seed_metrics.csv',seed_table)
    write_csv('joint_SHAPE_pipeline_summary.csv',summary)
    write_csv('unique_cell_counts.csv',counts)
    write_csv('marginal_reconstruction_checks.csv',pd.DataFrame(checks))
    write_csv('reconstructed_severity_marginals.csv',sev)
    write_csv('reconstructed_Q_class_marginals.csv',q)
    write_csv('adjacent_Q_descriptive_changes.csv',pd.DataFrame(adjacent))
    write_csv('within_cell_pipeline_comparisons.csv',pd.DataFrame(comparative))
    output('full_Q_trajectories_mean_SD.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json('integrity_and_provenance.json',{
        'status':'PASS','created_UTC':datetime.now(timezone.utc).isoformat(),
        'python_executable':sys.executable,'versions':{'python':sys.version,'pandas':pd.__version__,'numpy':np.__version__,'matplotlib':matplotlib.__version__},
        'source_sha256':sha(PARQUET),'run_counts_by_fault':run_counts,'unique_faulty_runs':2250,
        'filtered_evaluations':len(d),'seeds':SEEDS,'pipelines':REPS,'physical_cells':48,'summary_rows':144,'seed_cell_rows':720,
        'duplicate_keys':0,'missing_evaluations':0,'metadata_consistency':'PASS','binary_multiclass_identity':'PASS',
        'marginal_checks':len(checks),'max_reconstruction_error_fraction':max(x['Abs_Difference'] for x in checks),
        'check_tolerance_fraction':TOL,'SD':'ddof=1 across five per-seed metrics, never cell SD averaging',
        'protected_files_unchanged':len(before),'protected_hashes':before,
        'scope':'New descriptive aggregation of frozen faulty test predictions only. No inference, simulations, training, Q fitting, or changes to frozen sources.'})
    print(json.dumps({'status':'PASS','evaluations':len(d),'unique_runs':2250,'cells':48,'marginal_checks':len(checks),
          'max_reconstruction_error':max(x['Abs_Difference'] for x in checks),'protected_files_unchanged':len(before)}))

def contrast(rgb):
    x=np.asarray(rgb)[:3]
    linear=np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
    lum=float(linear@np.array([.2126,.7152,.0722]))
    black=(lum+.05)/.05; white=1.05/(lum+.05)
    return ('black',black) if black>=white else ('white',white)

def save_map(name,source,methods,method_field,field,label,subject):
    fig=plt.figure(figsize=(WIDTH,HEIGHT),dpi=150)
    cmap=plt.get_cmap('cividis'); norm=matplotlib.colors.Normalize(0,100)
    left=1.12;data_right=6.31;gap=.10;ph=1.32
    pw=(data_right-left-(len(methods)-1)*gap)/len(methods)
    ys={'LoE':HEIGHT-.34-ph,'Friction':.36}
    annotations=[];ratios=[];texts=[];cell_padding=[]
    for col,method in enumerate(methods):
        x=left+col*(pw+gap)
        fig.text((x+pw/2)/WIDTH,(HEIGHT-.16)/HEIGHT,method,ha='center',va='center',fontsize=9.5)
        for fault in ['LoE','Friction']:
            y=ys[fault]; ax=fig.add_axes([x/WIDTH,y/HEIGHT,pw/WIDTH,ph/HEIGHT])
            group=source[source.fault_class.eq(fault) & source[method_field].eq(method)].set_index(['severity_bin','excitation_quartile'])
            arr=np.array([[100*group.loc[(b,q),field] for q in QS] for b in BINS[fault]])
            assert np.all(arr>=-TOL) and np.all(arr<=100+TOL)
            im=ax.pcolormesh(np.arange(5),np.arange(5),arr,cmap=cmap,norm=norm,shading='flat',linewidth=.4,edgecolors='white',rasterized=False)
            ax.set(xlim=(0,4),ylim=(4,0)); ax.set_xticks(np.arange(4)+.5,QS)
            if col==0: ax.set_yticks(np.arange(4)+.5,[b.replace(' ','') for b in BINS[fault]])
            else: ax.set_yticks([])
            ax.tick_params(axis='x',labelsize=8,length=0,pad=3)
            ax.tick_params(axis='y',labelsize=7.8,length=0,pad=5)
            for spine in ax.spines.values():spine.set_visible(False)
            for i,b in enumerate(BINS[fault]):
                for j,q in enumerate(QS):
                    value=float(arr[i,j]); text=f'{value:.1f}'; tc,ratio=contrast(cmap(norm(value)))
                    ratios.append(ratio)
                    artist=ax.text(j+.5,i+.5,text,ha='center',va='center',color=tc,fontsize=7.8)
                    texts.append(artist)
                    annotations.append({'fault_class':fault,'severity_bin':b,'excitation_quartile':q,'pipeline_or_method':method,
                        'source_field':field,'source_fraction':value/100,'annotation':text})
    for fault,label_row in [('LoE',r'LoE severity $s_{\mathrm{LoE}}$'),('Friction',r'Friction severity $s_F$')]:
        fig.text(.14/WIDTH,(ys[fault]+ph/2)/HEIGHT,label_row,ha='center',va='center',rotation=90,fontsize=8.7)
    fig.text((left+data_right)/2/WIDTH,.025/HEIGHT,'Excitation stratum',ha='center',va='bottom',fontsize=8.5)
    cbax=fig.add_axes([6.43/WIDTH,.36/HEIGHT,.10/WIDTH,(HEIGHT-.70)/HEIGHT])
    cb=fig.colorbar(im,cax=cbax,orientation='vertical',ticks=list(range(0,101,20)))
    cb.ax.tick_params(labelsize=7.5,length=2,pad=2); cb.outline.set_linewidth(.35)
    cb.set_label(label,fontsize=8,labelpad=5)
    cb.solids.set_rasterized(False); cb.solids.set_edgecolor('face')
    fig.canvas.draw(); renderer=fig.canvas.get_renderer(); bad=[]
    for artist in fig.findobj(matplotlib.text.Text):
        if artist.get_visible() and artist.get_text():
            box=artist.get_window_extent(renderer)
            if box.x0<-1 or box.y0<-1 or box.x1>fig.bbox.width+1 or box.y1>fig.bbox.height+1:bad.append(artist.get_text())
    assert not bad, bad
    for artist in texts:
        box=artist.get_window_extent(renderer)
        cell_width=pw/4*fig.dpi; cell_height=ph/4*fig.dpi
        assert box.width<cell_width and box.height<cell_height
        cell_padding.append([cell_width-box.width,cell_height-box.height])
    fig.savefig(output(name+'.pdf'),metadata={'Title':label+' - review only','Subject':subject,'Creator':Path(__file__).name})
    plt.close(fig)
    return {'name':name,'dimensions_inches':[WIDTH,HEIGHT],'cell_panel_height_inches':ph,'panel_width_inches':pw,
        'source_field':field,'colormap':'cividis','scale_percent':[0,100],'annotation_font_pt':7.8,'severity_font_pt':7.8,
        'Q_font_pt':8,'column_font_pt':9.5,'row_header_font_pt':8.7,'global_x_font_pt':8.5,'colorbar_tick_font_pt':7.5,'colorbar_label_font_pt':8,
        'annotation_count':len(annotations),'min_annotation_contrast_ratio':min(ratios),'text_outside_canvas':bad,
        'minimum_annotation_cell_free_space_pixels':np.min(cell_padding,axis=0).tolist(),'annotations':annotations}

def make_figures():
    before=snapshot()
    assert json.loads((OUT/'integrity_and_provenance.json').read_text(encoding='utf-8'))['status']=='PASS'
    original=pd.read_csv(MASTER)
    fresh=pd.read_csv(OUT/'joint_SHAPE_pipeline_summary.csv')
    assert len(original)==192 and len(fresh)==144
    plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
        'font.size':8,'mathtext.fontset':'stix','pdf.fonttype':42,'ps.fonttype':42,'savefig.dpi':300})
    specs=[]
    for suffix,field,label in [('identification','Identification_Mean','Identification (%)'),('detection','Detection_Mean','Binary detection (%)')]:
        specs.append(save_map('compact_CWT_formulations_joint_'+suffix,original,['SHAPE','Torque','GMO','EO'],'method',field,label,
            'Copy of existing frozen joint map; same cell values/order/colors/fonts, shared right vertical colorbar; observational'))
    for suffix,field,label in [('identification','Identification_Mean','Identification (%)'),('detection','Detection_Mean','Binary detection (%)')]:
        specs.append(save_map('review_SHAPE_pipelines_joint_'+suffix,fresh,['CWT','Temporal','FFT'],'Pipeline',field,label,
            'Exploratory frozen SHAPE-pipeline joint means; observational severity x post-fault excitation; no causal representation isolation'))
    assert before==snapshot(), 'Protected files changed'
    write_json('plot_specifications_and_validation.json',{'status':'PASS','protected_files_unchanged':len(before),
        'original_inches':[7.16,4.25],'new_inches':[WIDTH,HEIGHT],'height_saved_inches':4.25-HEIGHT,
        'height_saved_percent':100*(4.25-HEIGHT)/4.25,'font_sizes_reduced':False,'figures':specs})
    captions=[]
    for s in specs:
        common='Primary test; five-seed means of within-cell run fractions. Q1-Q4 and severity bins are frozen. Friction severity s_F is dimensionless. Observational stratification by post-fault Joint 2 measured velocity RMS; no isolated causal effect of excitation.'
        population='Four residual formulations using their common CWT representation.' if s['name'].startswith('compact') else 'Three evaluated SHAPE pipelines: CWT, Temporal, FFT; architecture and training also differ. Review candidate, not a manuscript figure assignment.'
        captions += [s['name']+': '+s['source_field'].replace('_Mean','').replace('_',' ')+' (%). '+population+' '+common]
    output('review_figure_captions.txt').write_text('\n\n'.join(captions)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','figures':4,'annotations':sum(s['annotation_count'] for s in specs),
        'dimensions_inches':[WIDTH,HEIGHT],'height_reduction_percent':100*(4.25-HEIGHT)/4.25,'font_sizes_reduced':False}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,choices=['tables','figures'])
    args=parser.parse_args()
    if args.phase=='tables':make_tables()
    else:make_figures()
