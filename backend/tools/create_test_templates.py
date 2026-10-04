"""Synthetic AcroForms for isolated CI. No owner artwork or contract wording is included."""
import argparse
import json
from pathlib import Path
from io import BytesIO
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject, NumberObject, ArrayObject, FloatObject
parser=argparse.ArgumentParser()
parser.add_argument('--output',required=True)
args=parser.parse_args()
output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
manifest=json.loads((Path(__file__).parents[1]/'core/pdf_templates/manifest.json').read_text())
for name, metadata in manifest.items():
    stream=BytesIO();c=canvas.Canvas(stream,pagesize=(612,792))
    for index in range(metadata['pages']):
        c.setFont('Helvetica-Bold',14);c.drawString(30,755,'SYNTHETIC TEST TEMPLATE - NOT A BUSINESS DOCUMENT')
        c.setFont('Helvetica',10);c.drawString(30,730,'Installation test rule: five calendar days.');
        if index==metadata['pages']-1:
            i=0
            for field in metadata['fields']:
                if field in metadata['native_signature_fields']:continue
                x=30 if i%2==0 else 315;y=690-(i//2)*35;i+=1
                c.setFont('Helvetica',7);c.drawString(x,y+18,field)
                if field=='payment_option' and 'Invoice' in name:
                    c.acroForm.radio(name=field,value='A',selected=False,x=x,y=y,size=12)
                    c.acroForm.radio(name=field,value='B',selected=False,x=x+30,y=y,size=12)
                elif field=='payment_option':
                    c.acroForm.choice(name=field,options=['Select payment option','50% deposit / 50% balance','100% on completion'],value='Select payment option',x=x,y=y,width=250,height=16,fontSize=8)
                elif field=='financing_type':
                    c.acroForm.choice(name=field,options=['Non-financed','Financed'],value='Non-financed',x=x,y=y,width=250,height=16,fontSize=8)
                elif field=='gecc_role':
                    roles=['Installation Manager','Comptroller'] if 'Completion' in name else ['Sales Manager','Comptroller']
                    c.acroForm.choice(name=field,options=roles,value=roles[0],x=x,y=y,width=250,height=16,fontSize=8)
                else:
                    c.acroForm.textfield(name=field,value='',x=x,y=y,width=250,height=16,fontSize=8)
        c.showPage()
    c.save()
    writer=PdfWriter();writer.clone_document_from_reader(PdfReader(BytesIO(stream.getvalue())))
    page=writer.pages[-1]
    for i,field in enumerate(metadata['native_signature_fields']):
        widget=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/Widget'),NameObject('/FT'):NameObject('/Sig'),NameObject('/T'):TextStringObject(field),NameObject('/Rect'):ArrayObject([FloatObject(x) for x in [30+i*285,28,280+i*285,48]]),NameObject('/F'):NumberObject(4)})
        ref=writer._add_object(widget)
        page['/Annots'].append(ref);writer.root_object['/AcroForm']['/Fields'].append(ref)
    with (output/name).open('wb') as f:writer.write(f)
print(f'Created {len(manifest)} synthetic templates in {output}')
