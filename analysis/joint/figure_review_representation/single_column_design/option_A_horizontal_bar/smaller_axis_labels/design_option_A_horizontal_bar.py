"""Two requested variants of A, each with identification and binary detection.

Read existing verified means only. Preserve all sources and previous products.
Use original shape_ai Python, then bundled Python for the rendering script.
"""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
DESIGN=OUT.parent.parent
REVIEW=DESIGN.parent
FROZEN=Path(r'C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY')
PAPER=Path(r'C:\Users\Johnny\Desktop\Git\Image Processing Project\Latex Report')
SOURCE=REVIEW/'joint_SHAPE_pipeline_summary.csv'
REPS=['shape_cwt','shape_temporal','shape_fft']
TITLES=['CWT','Temporal','FFT']
FAULTS=['LoE','Friction']
QS=['Q1','Q2','Q3','Q4']
CODES=['B1','B2','B3','B4']
BINS={'LoE':['[0.02, 0.05)','[0.05, 0.10)','[0.10, 0.20)','[0.20, 0.30]'],
      'Friction':['[0.02, 0.10)','[0.10, 0.30)','[0.30, 0.75)','[0.75, 1.50]']}

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def snapshot():
    return {str(p):sha(p) for root in [REVIEW.parent,FROZEN,PAPER] for p in root.rglob('*')
            if p.is_file() and not p.is_relative_to(OUT)}

def output(name):
    p=OUT/name
    assert p.is_relative_to(OUT) and not p.exists(),p
    p.parent.mkdir(parents=True,exist_ok=True)
    return p

def contrast(rgb):
    x=np.asarray(rgb)[:3];linear=np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
    lum=float(linear@np.array([.2126,.7152,.0722]));black=(lum+.05)/.05;white=1.05/(lum+.05)
    return ('black',black) if black>=white else ('white',white)

def draw(shared_x,field,metric):
    variant='shared_x' if shared_x else 'repeated_Q'
    left,right,gap=.28,W-.02,.025
    ph,bottom,rowgap,top=.92,.84,.10 if shared_x else .24,.32
    pw=(right-left-2*gap)/3;H=bottom+2*ph+rowgap+top
    fig=plt.figure(figsize=(W,H),dpi=200)
    cmap=plt.get_cmap('cividis');norm=matplotlib.colors.Normalize(0,100)
    annotations=[];cell_boxes=[];artists=[];ratios=[];all_axes={};row_artists=[]
    for col,(rep,title) in enumerate(zip(REPS,TITLES)):
        x=left+col*(pw+gap)
        fig.text((x+pw/2)/W,(H-.15)/H,title,ha='center',va='center',fontsize=8.6)
        for row,fault in enumerate(FAULTS):
            y=bottom+(1-row)*(ph+rowgap)
            kwargs={'sharex':all_axes[(col,0)]} if shared_x and row==1 else {}
            ax=fig.add_axes([x/W,y/H,pw/W,ph/H],**kwargs);all_axes[(col,row)]=ax
            group=DATA[DATA.fault_class.eq(fault)&DATA.representation.eq(rep)].set_index(['severity_bin','excitation_quartile'])
            arr=np.array([[100*float(group.loc[(b,q),field]) for q in QS] for b in BINS[fault]])
            assert (arr>=0).all() and (arr<=100).all()
            im=ax.pcolormesh(np.arange(5),np.arange(5),arr,cmap=cmap,norm=norm,
                shading='flat',linewidth=.25,edgecolors='white',rasterized=False)
            ax.set(xlim=(0,4),ylim=(4,0));ax.set_xticks(np.arange(4)+.5,QS)
            ax.tick_params(axis='x',labelsize=7.0,length=0,pad=3,labelbottom=not(shared_x and row==0))
            if col==0:ax.set_yticks(np.arange(4)+.5,CODES)
            else:ax.set_yticks([])
            ax.tick_params(axis='y',labelsize=7.0,length=0,pad=1)
            for spine in ax.spines.values():spine.set_visible(False)
            for i,b in enumerate(BINS[fault]):
                for j,q in enumerate(QS):
                    value=float(arr[i,j]);text=f'{value:.1f}';color,ratio=contrast(cmap(norm(value)));ratios.append(ratio)
                    artist=ax.text(j+.5,i+.5,text,ha='center',va='center',fontsize=7.8,color=color)
                    artists.append(artist)
                    annotations.append({'fault_class':fault,'representation':rep,'severity_bin_original':b,'display_bin':CODES[i],
                        'excitation_quartile':q,'source_field':field,'source_fraction':float(group.loc[(b,q),field]),'annotation':text})
    for row,fault in enumerate(FAULTS):
        y=bottom+(1-row)*(ph+rowgap)
        row_artists.append(fig.text(.055/W,(y+ph/2)/H,fault+' severity',rotation=90,ha='center',va='center',fontsize=7.8))
    fig.text((left+right)/2/W,.55/H,'Excitation stratum',ha='center',va='center',fontsize=7.8)
    # Inset only the bar ends so its centered 0/100 tick labels stay in-page.
    cbax=fig.add_axes([(left+.08)/W,.34/H,(right-left-.16)/W,.075/H])
    cb=fig.colorbar(im,cax=cbax,orientation='horizontal',ticks=range(0,101,20))
    cb.ax.tick_params(labelsize=7.5,length=1.5,pad=1.5);cb.outline.set_linewidth(.3)
    cb.set_label('Identification (%)' if metric=='identification' else 'Binary detection (%)',fontsize=7.8,labelpad=3)
    cb.solids.set_rasterized(False);cb.solids.set_edgecolor('face')
    fig.canvas.draw();renderer=fig.canvas.get_renderer();outside=[];margins=[]
    for a in fig.findobj(matplotlib.text.Text):
        if a.get_visible() and a.get_text():
            box=a.get_window_extent(renderer)
            if box.x0<-.5 or box.y0<-.5 or box.x1>fig.bbox.width+.5 or box.y1>fig.bbox.height+.5:outside.append(a.get_text())
    assert not outside,outside
    severity_gaps=[]
    for row,a in enumerate(row_artists):
        box=a.get_window_extent(renderer)
        leftmost=min(t.get_window_extent(renderer).x0 for t in all_axes[(0,row)].get_yticklabels())
        clearance=(leftmost-box.x1)*72/fig.dpi
        assert clearance>=2.0,clearance
        severity_gaps.append(clearance)
    for a in artists:
        box=a.get_window_extent(renderer);cw=pw/4*fig.dpi;ch=ph/4*fig.dpi
        assert box.width<cw and box.height<ch,(a.get_text(),box.width,cw)
        margins.append([(cw-box.width)*72/fig.dpi,(ch-box.height)*72/fig.dpi]);cell_boxes.append(box)
    overlaps=[(i,j) for i,a in enumerate(cell_boxes) for j,b in enumerate(cell_boxes[i+1:],i+1) if a.overlaps(b)]
    assert not overlaps,overlaps
    name='option_A_'+variant+'_'+metric
    fig.savefig(output(name+'.pdf'),metadata={'Title':'SHAPE option A: horizontal bar, '+variant+', '+metric,
        'Subject':'Design review only; fixed means and bin/Q order; no scientific aggregation','Creator':Path(__file__).name})
    plt.close(fig)
    return {'name':name,'variant':variant,'metric':metric,'width_inches':W,'height_inches':H,
        'panel_width_inches':pw,'panel_height_inches':ph,'cell_width_points':pw/4*72,
        'annotation_font_pt':7.8,'B_Q_font_pt':7.0,'severity_label_to_B_clearance_points':severity_gaps,'header_font_pt':8.6,'row_label_font_pt':7.8,
        'global_x_font_pt':7.8,'colorbar_tick_font_pt':7.5,'colorbar_label_font_pt':7.8,
        'Q_sets':3 if shared_x else 6,'upper_row_Q_visible':not shared_x,
        'colorbar_orientation':'horizontal','colorbar_below_Excitation_stratum':True,
        'minimum_annotation_clearance_points':np.min(margins,axis=0).tolist(),
        'text_outside_canvas':outside,'annotation_box_overlaps':overlaps,'minimum_contrast_ratio':min(ratios),
        'annotations':annotations}

before=snapshot()
previous=json.loads((DESIGN/'design_validation.json').read_text(encoding='utf-8'))
assert sha(SOURCE)==previous['source_hashes'][str(SOURCE)]
W=previous['geometry_probe']['COLUMN_WIDTH_PT']/72.27
DATA=pd.read_csv(SOURCE)
assert len(DATA)==144 and not DATA.duplicated(['fault_class','severity_bin','excitation_quartile','representation']).any()
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
    'mathtext.fontset':'stix','font.size':7.8,'pdf.fonttype':42,'ps.fonttype':42})
specs=[]
for shared in [False,True]:
    for field,metric in [('Identification_Mean','identification'),('Detection_Mean','detection')]:specs.append(draw(shared,field,metric))
assert before==snapshot()
caption_total=sum(previous['caption_heights_inches'].values())
floatsep=previous['geometry_probe']['FLOAT_SEP_PT']/72.27
pair_heights={variant:sum(s['height_inches'] for s in specs if s['variant']==variant)+caption_total+floatsep for variant in ['repeated_Q','shared_x']}
output('horizontal_bar_design_validation.json').write_text(json.dumps({'status':'PASS','python':sys.executable,
    'source_sha256':sha(SOURCE),'metric_recalculation':'None','protected_files_unchanged':len(before),'figures':specs,
    'scale_percent':[0,100],'colormap':'cividis','caption_estimate_basis':'Previous unchanged prospective IEEE captions',
    'pair_heights_inches_including_previous_captions_and_floatsep':pair_heights},indent=2),encoding='utf-8')
print(json.dumps({'status':'PASS','figures':4,'annotations':384,'width_inches':W,'annotation_font_pt':7.8,
    'height_repeated_Q_inches':specs[0]['height_inches'],'height_shared_x_inches':specs[2]['height_inches'],
    'pair_heights_inches':pair_heights,'protected_files_unchanged':len(before)}))
