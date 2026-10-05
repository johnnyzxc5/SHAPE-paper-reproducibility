"""Review-only rendering of frozen E4 summaries. No scientific aggregation.

Run with the bundled Python runtime. All data are literal T11/T12 summary
fields; multiplication by 100 is the only numerical display conversion.
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import subprocess

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color
from pypdf import PdfReader
from PIL import Image, ImageOps, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
ROOT = Path(r'C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY')
MANUSCRIPT = Path(r'C:\Users\Johnny\Desktop\Git\Image Processing Project\Latex Report\Final_Report.tex')
POPPLER = Path(r'C:\Users\Johnny\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
SOURCES = [ROOT/'tables/T11_E4_overall_noise.csv', ROOT/'tables/T12_E4_per_class_noise.csv', MANUSCRIPT]
EXPECTED = {
    SOURCES[0]: 'dd544d4dc590a27441b1d1fd6378d45905f26570bf2a048a161f372fd048a9f4',
    SOURCES[1]: 'fce76d2ecf68b3a771f7dd330d6fbda2ceda2cd1370ce3d2411f454347e12a2b',
    SOURCES[2]: '58d1be4719bf48d27e5257f850108361f2315dbd7cfc625a81bbec5cfa543122',
}
METHODS = [('SHAPE','shape_cwt','#0072B2','circle'),
           ('Torque','torque_cwt','#D55E00','square'),
           ('GMO','gmo_cwt','#009E73','triangle'),
           ('EO','energy_cwt','#882255','diamond')]
POS = ['clean','position_0.01deg','position_0.05deg','position_0.2deg']
VEL = ['clean','velocity_40dB','velocity_30dB','velocity_20dB','velocity_10dB']
PANELS = [('position','LoE recall (%)',POS,'T12','Recall_Mean','Recall_SD','LoE'),
          ('velocity','FAR (%)',VEL,'T11','False_Alarm_Rate_Mean','False_Alarm_Rate_SD',None),
          ('position','Friction recall (%)',POS,'T12','Recall_Mean','Recall_SD','Friction'),
          ('velocity','MDR (%)',VEL,'T11','Missed_Detection_Rate_Mean','Missed_Detection_Rate_SD',None)]
WIDTH = 3.50 * 72
HEIGHT = 3.15 * 72

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

def text(c,x,y,s,size=8.5,color='#202020',align='left',bold=False):
    c.setFont('TimesBold' if bold else 'Times',size)
    c.setFillColor(HexColor(color))
    getattr(c,{'left':'drawString','center':'drawCentredString','right':'drawRightString'}[align])(x,y,s)

def marker(c,x,y,kind,color,r=2.0):
    c.setStrokeColor(HexColor(color)); c.setFillColor(HexColor('#FFFFFF'))
    c.setLineWidth(.85)
    if kind=='circle': c.circle(x,y,r,stroke=1,fill=1)
    elif kind=='square': c.rect(x-r,y-r,2*r,2*r,stroke=1,fill=1)
    else:
        p=c.beginPath()
        coords = [(x,y+r*1.15),(x-r,y-r*.8),(x+r,y-r*.8)] if kind=='triangle' else [(x,y+r*1.2),(x-r,y),(x,y-r*1.2),(x+r,y)]
        p.moveTo(*coords[0])
        for xy in coords[1:]: p.lineTo(*xy)
        p.close(); c.drawPath(p,stroke=1,fill=1)

def labels(kind):
    return ['E0','.01','.05','.20'] if kind=='position' else ['E0','40','30','20','10']

def save_pdf(name,fn):
    path=OUT/name
    if path.exists():
        if name=='candidate_B_matrix.pdf': return path
        raise FileExistsError(path)
    c=canvas.Canvas(str(path),pagesize=(WIDTH,HEIGHT),pageCompression=1)
    c.setTitle(name.replace('_',' ').replace('.pdf',''))
    c.setAuthor('E4 review: frozen T11/T12 summaries')
    fn(c); c.showPage(); c.save()
    reader=PdfReader(str(path)); page=reader.pages[0]
    assert len(reader.pages)==1
    assert abs(float(page.mediabox.width)-WIDTH)<1e-6
    assert abs(float(page.mediabox.height)-HEIGHT)<1e-6
    assert not page.images, 'PDF must contain vector graphics only'
    prefix=OUT/path.stem
    subprocess.run([str(POPPLER),'-singlefile','-r','180','-png',str(path),str(prefix)],check=True)
    subprocess.run([str(POPPLER),'-singlefile','-r','150','-png',str(path),str(OUT/(path.stem+'_print_size'))],check=True)
    return path

def curve_figure(c):
    # Two short legend rows; method color, symbol and line style are redundant.
    for i,(method,_,color,symbol) in enumerate(METHODS):
        x=38+(i%2)*114; y=216-(i//2)*12
        c.setStrokeColor(HexColor(color)); c.setLineWidth(1)
        c.setDash([[],[3,2],[4,1.5,1,1.5],[1,1.5]][i])
        c.line(x,y,x+19,y); c.setDash([])
        marker(c,x+9.5,y,symbol,color)
        text(c,x+24,y-3,method,size=8.6)
    text(c,77,185,'Position perturbation',8.8,align='center',bold=True)
    text(c,196,185,'Velocity perturbation',8.8,align='center',bold=True)
    for i,panel in enumerate(PANELS):
        kind,title,conditions,table,field,sdfield,cls=panel
        x=29 if i%2==0 else 150
        y=111 if i<2 else 32
        w=92; h=55
        text(c,x,y+h+6,'('+chr(97+i)+') '+title,8.2)
        for t in [0,50,100]:
            yy=y+h*(t+5)/110
            c.setStrokeColor(HexColor('#DDDDDD')); c.setLineWidth(.35); c.line(x,yy,x+w,yy)
            text(c,x-4,yy-2.6,str(t),8,align='right')
        c.setStrokeColor(HexColor('#777777')); c.setLineWidth(.5)
        c.line(x,y,x,y+h); c.line(x,y,x+w,y)
        xs=[x+5+j*(w-10)/(len(conditions)-1) for j in range(len(conditions))]
        separator=(xs[0]+xs[1])/2
        c.setStrokeColor(HexColor('#AAAAAA')); c.setDash([1.3,1.8]); c.line(separator,y,separator,y+h); c.setDash([])
        for j,xx in enumerate(xs):
            c.setStrokeColor(HexColor('#777777')); c.line(xx,y,xx,y-2)
            if i>=2: text(c,xx,y-12,labels(kind)[j],8,align='center')
        for m,(_,key,color,symbol) in enumerate(METHODS):
            means=[DATA[(table,key,cond,cls,field)]*100 for cond in conditions]
            sds=[RAW_LOOKUP[(table,key,cond,cls)][sdfield]*100 for cond in conditions]
            ys=[y+h*(v+5)/110 for v in means]
            displaced=[xx+[-1.8,-.6,.6,1.8][m] for xx in xs]
            # Small display-only horizontal offsets distinguish coincident bars.
            for xx,mean,sd in zip(displaced,means,sds):
                lo=y+h*(mean-sd+5)/110; hi=y+h*(mean+sd+5)/110
                assert y<=lo<=hi<=y+h, 'SD bar outside displayed margin'
                c.setStrokeColor(HexColor(color)); c.setLineWidth(.45)
                c.line(xx,lo,xx,hi); c.line(xx-1.2,lo,xx+1.2,lo); c.line(xx-1.2,hi,xx+1.2,hi)
            c.setStrokeColor(HexColor(color)); c.setLineWidth(.9)
            c.setDash([[],[3,2],[4,1.5,1,1.5],[1,1.5]][m])
            # E0 remains a separate point: no interpolation to the E4 pass.
            for j in range(1,len(displaced)-1): c.line(displaced[j],ys[j],displaced[j+1],ys[j+1])
            c.setDash([])
            for xx,yy in zip(displaced,ys): marker(c,xx,yy,symbol,color,1.8)
    text(c,75,5,'Position-noise SD (deg)',8.4,align='center')
    text(c,196,5,'Velocity SNR (dB)',8.4,align='center')

STOPS=[(0,'#F7FBFF'),(.25,'#C6DBEF'),(.5,'#6BAED6'),(.75,'#2171B5'),(1,'#08306B')]
def scale_color(value):
    v=max(0,min(1,value))
    for (a,ca),(b,cb) in zip(STOPS,STOPS[1:]):
        if a<=v<=b:
            aa=HexColor(ca); bb=HexColor(cb); f=(v-a)/(b-a)
            return Color(aa.red*(1-f)+bb.red*f,aa.green*(1-f)+bb.green*f,aa.blue*(1-f)+bb.blue*f)
    return HexColor(STOPS[-1][1])

def label_color(bg):
    def lin(v): return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
    l=.2126*lin(bg.red)+.7152*lin(bg.green)+.0722*lin(bg.blue)
    return '#FFFFFF' if 1.05/(l+.05) > (l+.05)/.05 else '#111111'

def matrix_figure(c):
    text(c,82,213,'Position perturbation',8.8,align='center',bold=True)
    text(c,194,213,'Velocity perturbation',8.8,align='center',bold=True)
    for i,panel in enumerate(PANELS):
        kind,title,conditions,table,field,sdfield,cls=panel
        x=39 if i%2==0 else 147
        top=190 if i<2 else 108
        w=88 if i%2==0 else 100; h=54
        cw=w/len(conditions); ch=h/4
        text(c,x,top+5,'('+chr(97+i)+') '+title,8.2)
        for m,(method,key,_,_) in enumerate(METHODS):
            if i%2==0: text(c,x-4,top-(m+.5)*ch-2.7,method,8.5,align='right')
            for j,cond in enumerate(conditions):
                value=DATA[(table,key,cond,cls,field)]
                bx=x+j*cw; by=top-(m+1)*ch
                bg=scale_color(value)
                c.setFillColor(bg); c.setStrokeColor(HexColor('#FFFFFF')); c.setLineWidth(.35)
                c.rect(bx,by,cw,ch,fill=1,stroke=1)
                text(c,bx+cw/2,by+ch/2-2.7,f'{100*value:.1f}',8.1,label_color(bg),align='center')
                assert f'{100*value:.1f}'==f'{100*RAW_LOOKUP[(table,key,cond,cls)][field]:.1f}'
        # Visually separate the independent E0 reference column.
        c.setStrokeColor(HexColor('#333333')); c.setLineWidth(.8); c.line(x+cw,top-h,x+cw,top)
        for j,s in enumerate(labels(kind)):
            text(c,x+(j+.5)*cw,top-h-11,s,8.1,align='center')
    text(c,83,34,'Position-noise SD (deg)',8.3,align='center')
    text(c,197,34,'Velocity SNR (dB)',8.3,align='center')
    bx,by,bw,bh=48,17,156,5
    for j in range(200):
        c.setFillColor(scale_color(j/199)); c.rect(bx+j*bw/200,by,bw/200+.1,bh,fill=1,stroke=0)
    for t in [0,25,50,75,100]: text(c,bx+bw*t/100,by-10,str(t),8,align='center')
    text(c,210,by-.5,'%',8.3)

if __name__=='__main__':
    for path,wanted in EXPECTED.items():
        assert sha(path)==wanted, f'Input changed: {path}'
    for filename,fontname in [('times.ttf','Times'),('timesbd.ttf','TimesBold')]:
        pdfmetrics.registerFont(TTFont(fontname,str(Path(r'C:\Windows\Fonts')/filename)))
    rows={'T11':load(SOURCES[0]),'T12':load(SOURCES[1])}
    DATA={}; RAW_LOOKUP={}; trace=[]
    for kind,title,conditions,table,field,sdfield,cls in PANELS:
        for method,key,color,symbol in METHODS:
            for cond in conditions:
                matches=[(n+2,r) for n,r in enumerate(rows[table]) if r['rep_key']==key and r['Condition']==cond and (cls is None or r['Class']==cls)]
                assert len(matches)==1, (table,key,cond,cls,len(matches))
                line,row=matches[0]
                assert row['Evaluation_Source']==('E0_CANONICAL' if cond=='clean' else 'E4_CANONICAL')
                value=float(row[field]); sd=float(row[sdfield])
                assert math.isfinite(value) and 0<=value<=1
                DATA[(table,key,cond,cls,field)]=value
                RAW_LOOKUP.setdefault((table,key,cond,cls),{}).update({field:value,sdfield:sd})
                trace.append({'Panel':title,'Method':method,'Condition':cond,'Class':cls or '',
                              'Mean':row[field],'Sample_SD':row[sdfield],
                              'Mean_percent':repr(value*100),'Sample_SD_percent':repr(sd*100),
                              'Source_file':str(SOURCES[0] if table=='T11' else SOURCES[1]),
                              'Source_CSV_line':line,'Mean_field':field,'SD_field':sdfield,
                              'Evaluation_Source':row['Evaluation_Source']})
    assert len(trace)==72
    trace_path=OUT/'plotted_fields_traceability.csv'
    if trace_path.exists():
        assert load(trace_path)==[{k:str(v) for k,v in r.items()} for r in trace]
    else:
        with trace_path.open('x',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(trace[0])); writer.writeheader(); writer.writerows(trace)
    paths=[save_pdf('candidate_A_curves_v2.pdf',curve_figure), save_pdf('candidate_B_matrix.pdf',matrix_figure)]
    captions={
        'A_v2': 'Zero-shot diagnostic response under position-only (left) and velocity-only (right) offline perturbations for the four residual formulations under the common CWT representation. Panels show LoE recall, Friction recall, false-alarm rate (FAR), and missed-detection rate (MDR). Points denote five-seed means; error bars show sample standard deviations across seeds, not confidence intervals. E0 denotes the separate unperturbed reference evaluation. Lines connect successive E4 condition means as visual guides; condition spacing is categorical, with small method offsets for visibility. Common axis limits of -5 to 105% retain SD bars without clipping. FAR is conditioned on true Nominal runs, whereas MDR pools the three faulty classes. Velocity SNR is calibrated from training-pooled per-joint velocity RMS. Torque inputs remain fixed under this protocol.',
        'B': 'Zero-shot diagnostic response under position-only (left) and velocity-only (right) offline perturbations for the four residual formulations under the common CWT representation. Cell values are five-seed means (%); rows correspond to SHAPE, Torque, GMO, and EO. Position panels show correct LoE and Friction identification; velocity panels show FAR on true Nominal runs and MDR pooled over the three faulty classes. All panels use a common 0-100% scale. E0 is the separate unperturbed reference evaluation. Velocity SNR is calibrated from training-pooled per-joint velocity RMS. Sample standard deviations are available in the supporting tables. Higher recall indicates more correct identification; higher FAR or MDR indicates more errors. Torque inputs remain fixed under this offline protocol.'
    }
    for variant,caption in captions.items():
        caption_path=OUT/f'candidate_{variant}_caption.txt'
        if caption_path.exists(): assert caption_path.read_text(encoding='utf-8')==caption+'\n'
        else: caption_path.write_text(caption+'\n',encoding='utf-8')
    proofs=[Image.open(OUT/(p.stem+'_print_size.png')).convert('RGB') for p in paths]
    proof=Image.new('RGB',(1240,680),'white'); draw=ImageDraw.Draw(proof)
    font=ImageFont.truetype(r'C:\Windows\Fonts\times.ttf',19)
    for i,im in enumerate(proofs):
        x=45+i*600
        draw.text((x,20),f'Candidate {chr(65+i)} - 3.50-inch width at 150 dpi',font=font,fill='black')
        proof.paste(im,(x,70))
        gray_path=OUT/(paths[i].stem+'_grayscale.png')
        if not gray_path.exists(): ImageOps.grayscale(im).convert('RGB').save(gray_path)
    proof.save(OUT/'comparison_at_print_size_v2.png')
    for path,wanted in EXPECTED.items(): assert sha(path)==wanted
    manifest={'sources':{str(p):sha(p) for p in SOURCES},'output_pdfs':{str(p):sha(p) for p in paths},
              'width_inches':3.5,'height_inches':3.15,'font':'Times New Roman embedded TrueType',
              'fonts_pt':{'panel_titles':8.2,'column_titles':8.8,'curve_ticks':8,'method_labels':8.5,'matrix_values':8.1},
              'source_cells_verified':72,'transformation':'display percent = frozen fraction * 100',
              'sample_sd':'A: plotted unmodified as sample SD, with -5 to 105% margin; B: not plotted, available in traceability file',
              'new_scientific_aggregation':False,'frozen_files_unchanged':True,'pdfs_vector':True}
    (OUT/'render_manifest_v2.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'created':[str(p) for p in paths],'verified_source_cells':72,'dimensions_inches':[3.5,3.15],'frozen_inputs_unchanged':True}))
