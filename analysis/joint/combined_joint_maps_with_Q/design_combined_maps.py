"""Design review only: combine existing cell means; no scientific aggregation."""
from pathlib import Path
import csv, json, re, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
PAPER=Path(r'C:\Users\Johnny\Desktop\Git\Image Processing Project\Latex Report')
W=252/72.27
H=5.76
PH=.92
QS=['Q1','Q2','Q3','Q4']
CODES=['B1','B2','B3','B4']
BINS={'LoE':['[0.02, 0.05)','[0.05, 0.10)','[0.10, 0.20)','[0.20, 0.30]'],
      'Friction':['[0.02, 0.10)','[0.10, 0.30)','[0.30, 0.75)','[0.75, 1.50]']}
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
    'pdf.fonttype':42,'ps.fonttype':42,'font.size':7.8})

def output(name):
    p=OUT/name
    assert not p.exists(),p
    return p

def text_color(rgb):
    x=np.array(rgb[:3]);x=np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
    l=float(x@np.array([.2126,.7152,.0722]))
    return 'black' if (l+.05)/.05 >=1.05/(l+.05) else 'white'

def draw(name,source,key,methods,titles):
    with source.open(newline='',encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    idx={(r['fault_class'],r['severity_bin'],r['excitation_quartile'],r[key]):r for r in rows}
    assert len(idx)==len(rows)
    fig=plt.figure(figsize=(W,H),dpi=200)
    left,right,gap=.28,W-.02,.025
    pw=(right-left-2*gap)/3
    # Rows top-to-bottom: identification LoE/Friction, detection LoE/Friction. Q ticks beneath each metric half.
    ys=[4.36,3.34,1.86,.84]
    metrics=['Identification_Mean']*2+['Detection_Mean']*2
    faults=['LoE','Friction']*2
    cmap=plt.get_cmap('cividis');norm=matplotlib.colors.Normalize(0,100)
    axes={};annot=[];artists=[];rowlabels=[]
    fig.text((left+right)/2/W,(H-.095)/H,'(a) Identification',ha='center',va='center',fontsize=8.2)
    for c,(method,title) in enumerate(zip(methods,titles)):
        x=left+c*(pw+gap)
        fig.text((x+pw/2)/W,(H-.29)/H,title,ha='center',va='center',fontsize=8.6)
        for row,(fault,field,y) in enumerate(zip(faults,metrics,ys)):
            ax=fig.add_axes([x/W,y/H,pw/W,PH/H],sharex=axes[(c,0)] if row else None)
            axes[(c,row)]=ax
            arr=np.array([[100*float(idx[(fault,b,q,method)][field]) for q in QS] for b in BINS[fault]])
            assert (arr>=0).all() and (arr<=100).all()
            im=ax.pcolormesh(np.arange(5),np.arange(5),arr,cmap=cmap,norm=norm,
                shading='flat',linewidth=.25,edgecolors='white',rasterized=False)
            ax.set(xlim=(0,4),ylim=(4,0))
            ax.set_xticks(np.arange(4)+.5,QS)
            ax.tick_params(axis='x',length=0,pad=3,labelsize=7,labelbottom=row in (1,3))
            ax.set_yticks(np.arange(4)+.5,CODES) if c==0 else ax.set_yticks([])
            ax.tick_params(axis='y',length=0,pad=1,labelsize=7)
            for s in ax.spines.values():s.set_visible(False)
            for i,b in enumerate(BINS[fault]):
                for j,q in enumerate(QS):
                    v=float(arr[i,j]);label=f'{v:.1f}'
                    artists.append(ax.text(j+.5,i+.5,label,ha='center',va='center',fontsize=7.8,color=text_color(cmap(norm(v)))))
                    annot.append({'fault_class':fault,'severity_bin':b,'excitation_quartile':q,
                        key:method,'field':field,'value_percent':v,'annotation':label})
    for y,fault in zip(ys,faults):
        rowlabels.append(fig.text(.055/W,(y+PH/2)/H,fault+' severity',rotation=90,ha='center',va='center',fontsize=7.8))
    # Separating rule and a clear label distinguish metrics without a second bar.
    fig.add_artist(matplotlib.lines.Line2D([left/W,right/W],[3.10/H,3.10/H],
        transform=fig.transFigure,color='.65',linewidth=.35))
    fig.text((left+right)/2/W,2.96/H,'(b) Binary detection',ha='center',va='center',fontsize=8.2)
    fig.text((left+right)/2/W,.55/H,'Excitation stratum',ha='center',va='center',fontsize=7.8)
    cbax=fig.add_axes([(left+.08)/W,.34/H,(right-left-.16)/W,.075/H])
    cb=fig.colorbar(im,cax=cbax,orientation='horizontal',ticks=range(0,101,20))
    cb.ax.tick_params(labelsize=7.5,length=1.5,pad=1.5);cb.outline.set_linewidth(.3)
    cb.set_label('Rate (%)',fontsize=7.8,labelpad=3)
    cb.solids.set_rasterized(False);cb.solids.set_edgecolor('face')
    fig.canvas.draw();renderer=fig.canvas.get_renderer()
    outside=[]
    for a in fig.findobj(matplotlib.text.Text):
        if a.get_visible() and a.get_text():
            box=a.get_window_extent(renderer)
            if box.x0<-.5 or box.y0<-.5 or box.x1>fig.bbox.width+.5 or box.y1>fig.bbox.height+.5:outside.append(a.get_text())
    assert not outside,outside
    boxes=[a.get_window_extent(renderer) for a in artists]
    assert all(b.width < pw/4*fig.dpi and b.height < PH/4*fig.dpi for b in boxes)
    assert not any(b.overlaps(c) for i,b in enumerate(boxes) for c in boxes[i+1:])
    severity_gaps=[]
    for row,a in enumerate(rowlabels):
        clearance=(min(t.get_window_extent(renderer).x0 for t in axes[(0,row)].get_yticklabels())-a.get_window_extent(renderer).x1)*72/fig.dpi
        assert clearance>=2
        severity_gaps.append(clearance)
    fig.savefig(output(name+'.pdf'),metadata={'Title':name,'Subject':'Combined identification/detection maps; existing five-seed means; review only'})
    plt.close(fig)
    return {'name':name,'source':str(source),'methods':methods,'dimensions_inches':[W,H],
        'annotations':annot,'annotation_font_pt':7.8,'B_Q_font_pt':7,'header_font_pt':8.6,
        'metric_heading_font_pt':8.2,'severity_label_to_B_gap_pt':severity_gaps,
        'scale_percent':[0,100],'colormap':'cividis','source_metric_recalculation':False}

specs=[draw('combined_CWT_formulations_identification_detection',ROOT/'10_regional_master_table.csv',
    'method',['SHAPE','Torque','EO'],['SHAPE','Torque','EO']),
    draw('combined_SHAPE_pipelines_identification_detection',ROOT/'figure_review_representation/joint_SHAPE_pipeline_summary.csv',
    'representation',['shape_cwt','shape_temporal','shape_fft'],['CWT','Temporal','FFT'])]
output('design_checks.json').write_text(json.dumps({'status':'PASS','figures':specs,'annotations_verified':384},indent=2),encoding='utf-8')
print(json.dumps({'status':'PASS','figures':2,'annotations':384,'width_inches':W,'height_inches':H}))
