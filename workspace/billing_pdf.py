"""A4 multi-page client invoices generated entirely on the server with ReportLab.

This renderer accepts an immutable JSON-like document; it has no Django dependency,
so the invoice PDF can be regression-tested independently of the web framework.
"""
import io
import os
from decimal import Decimal
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Flowable, KeepTogether
)

INK = colors.HexColor('#17243F')
MUTED = colors.HexColor('#64748B')
INDIGO = colors.HexColor('#5556E8')
PALE = colors.HexColor('#F2F5FC')
BORDER = colors.HexColor('#DFE5F1')
GREEN = colors.HexColor('#147C6F')

for regular, bold in [
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'),
]:
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont('BillingRegular', regular))
        pdfmetrics.registerFont(TTFont('BillingBold', bold))
        FONT = 'BillingRegular'
        BOLD = 'BillingBold'
        break
else:
    FONT, BOLD = 'Helvetica', 'Helvetica-Bold'


def safe(v):
    return escape(str(v if v is not None else '')).replace('\n', '<br/>')


def amount(value):
    return f'{Decimal(str(value or 0)):,.2f}'


def date(value):
    return str(value or '-').split('T')[0]


def style(name, size=9, leading=None, color=INK, bold=False, align=TA_LEFT, space=0):
    return ParagraphStyle(name=name, fontName=BOLD if bold else FONT, fontSize=size,
                          leading=leading or size * 1.5, textColor=color, alignment=align,
                          spaceAfter=space, wordWrap='CJK')


SMALL = style('small', 8, 12, MUTED)
BODY = style('body', 9, 14)
BODYB = style('bodyb', 9, 14, INK, True)
RIGHT = style('right', 9, 14, INK, False, TA_RIGHT)
RIGHTB = style('rightbold', 9, 14, INK, True, TA_RIGHT)
HEAD = style('head', 8, 12, colors.white, True)
SECTION = style('section', 10, 15, INK, True, space=7)
TITLE = style('title', 16, 24, INK, True)
SMALL_SECTION = style('smallsection', 9, 12, INK, True, space=2)
COMPACT = style('compact', 8, 11)


class Seal(Flowable):
    """A *visual* company mark, not a cryptographic signature or legal e-signature."""
    def __init__(self, organisation, caption, image=None):
        super().__init__()
        self.width, self.height = 188, 102
        self.organisation = str(organisation)[:55]
        self.caption = str(caption or 'AUTHORISED')[:65]
        self.image = image

    def draw(self):
        c = self.canv
        if self.image:
            try:
                c.drawImage(ImageReader(io.BytesIO(self.image)), 75, 20, width=95, height=75,
                            preserveAspectRatio=True, mask='auto', anchor='c')
            except Exception:
                self.image = None
        if not self.image:
            c.saveState()
            c.setStrokeColor(colors.HexColor('#47617C'))
            c.setLineWidth(1.7)
            c.circle(127, 60, 31, stroke=1, fill=0)
            c.setLineWidth(.65)
            c.circle(127, 60, 27, stroke=1, fill=0)
            c.setFont(BOLD, 7.2)
            c.setFillColor(colors.HexColor('#47617C'))
            label = self.caption[:15].upper()
            c.drawCentredString(127, 64, label)
            c.setFont(FONT, 6.4)
            c.drawCentredString(127, 52, 'TECHFINITYS')
            c.restoreState()
        c.setFont(BOLD, 8)
        c.setFillColor(INK)
        c.drawRightString(188, 10, 'For ' + self.organisation[:26])


def build_pdf(document, logo_path=None, stamp_image=None):
    """Return PDF bytes. Document must contain verified invoice totals and snapshots."""
    data = document
    seller = data.get('seller') or {}
    buf = io.BytesIO()
    width, height = A4
    left, right = 39, 39
    content_width = width - left - right

    def decorations(c, doc):
        c.saveState()
        c.setFillColor(INK)
        c.rect(0, height - 112, width, 112, stroke=0, fill=1)
        c.setFillColor(INDIGO)
        c.rect(0, height - 116, width, 4, stroke=0, fill=1)
        if logo_path and os.path.isfile(logo_path):
            try:
                c.drawImage(logo_path, left, height-93, width=63, height=63,
                            preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
        c.setFillColor(colors.white)
        c.setFont(BOLD, 18)
        c.drawString(112, height-55, str(seller.get('company_name') or 'Techfinitys')[:39])
        c.setFont(FONT, 8)
        c.setFillColor(colors.HexColor('#CFD8EE'))
        subtitle = str(seller.get('legal_name') or seller.get('website') or 'Client billing & services')[:72]
        c.drawString(113, height-72, subtitle)
        c.setFont(FONT, 7)
        c.setFillColor(colors.HexColor('#E1E6F2'))
        address=str(seller.get('address') or '').replace('\n', ', ')[:72]
        if address: c.drawString(113, height-86, address)
        seller_tax=str(seller.get('gstin') or '')
        if seller_tax: c.drawString(113, height-98, 'GSTIN: ' + seller_tax[:25])
        c.setFont(BOLD, 12)
        c.setFillColor(colors.white)
        c.drawRightString(width-right, height-48, 'INVOICE' if data.get('status') != 'draft' else 'DRAFT INVOICE')
        c.setFont(FONT, 8)
        c.setFillColor(colors.HexColor('#CFD8EE'))
        c.drawRightString(width-right, height-67, str(data.get('number') or 'Unissued draft')[:40])
        c.setStrokeColor(BORDER)
        c.line(left, 62, width-right, 62)
        c.setFont(FONT, 7)
        c.setFillColor(MUTED)
        footer = str(seller.get('footer_text') or 'Thank you for your business.')[:96]
        c.drawString(left, 48, footer)
        c.drawString(left, 34, 'Generated by Techfinitys CRM  |  Computer-generated invoice')
        c.drawRightString(width-right, 34, f'Page {doc.page}')
        if data.get('status') in ('draft', 'void'):
            c.saveState()
            c.translate(width / 2, height / 2)
            c.rotate(35)
            c.setFont(BOLD, 64)
            c.setFillColor(colors.HexColor('#E5E9F4'))
            c.drawCentredString(0, 0, 'DRAFT' if data.get('status') == 'draft' else 'VOID')
            c.restoreState()
        c.restoreState()

    pdf = BaseDocTemplate(buf, pagesize=A4, leftMargin=left, rightMargin=right,
                          topMargin=132, bottomMargin=72, title=f"Invoice {data.get('number') or 'Draft'}",
                          author=str(seller.get('company_name') or 'Techfinitys'), pageCompression=1)
    pdf.addPageTemplates(PageTemplate(id='invoice', frames=[Frame(left, 73, content_width, height-205,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=decorations))
    story = []
    from reportlab.platypus import HRFlowable
    story.append(Paragraph('Invoice details', SECTION))
    meta = [
        [Paragraph('BILL TO', SMALL), Paragraph('INVOICE INFORMATION', SMALL)],
        [Paragraph(safe(data.get('bill_to_name')), BODYB), Paragraph(f"Number: <b>{safe(data.get('number') or 'DRAFT')}</b>", BODY)],
        [Paragraph(safe(data.get('bill_to_address')), BODY), Paragraph('Issued: ' + safe(date(data.get('issue_date'))), BODY)],
        [Paragraph(safe(data.get('bill_to_email')), BODY), Paragraph('Due: ' + safe(date(data.get('due_date'))), BODY)],
        [Paragraph('GSTIN: ' + safe(data['bill_to_gstin']), BODY) if data.get('bill_to_gstin') else '',
         Paragraph('Status: ' + safe(str(data.get('status') or '').replace('_',' ').title()), BODY)],
    ]
    if data.get('period_start'):
        meta.append(['', Paragraph('Service period: ' + safe(date(data.get('period_start'))) + ' to ' + safe(date(data.get('period_end'))), SMALL)])
    info=Table(meta,colWidths=[content_width*.55, content_width*.45],hAlign='LEFT')
    info.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.65,BORDER),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),13),
        ('RIGHTPADDING',(0,0),(-1,-1),13),('TOPPADDING',(0,0),(-1,0),13),
        ('BOTTOMPADDING',(0,0),(-1,0),6),('TOPPADDING',(0,1),(-1,-1),3),
        ('BOTTOMPADDING',(0,-1),(-1,-1),13),
    ]))
    story.extend([info,Spacer(1,7),Paragraph('Package & service charges', SECTION)])
    widths=[38,229,48,97,content_width-412]
    hdr=[Paragraph('#',HEAD),Paragraph('DESCRIPTION',HEAD),Paragraph('QTY',HEAD),
         Paragraph('UNIT PRICE',HEAD),Paragraph('AMOUNT',HEAD)]
    rows=[hdr]
    for i,item in enumerate(data.get('items') or [],1):
        rows.append([Paragraph(str(i),BODY), Paragraph(safe(item.get('description')),BODY),
                     Paragraph(amount(item.get('quantity')),BODY),Paragraph(amount(item.get('unit_price')),RIGHT),
                     Paragraph(amount(item.get('amount')),RIGHT)])
    charges=Table(rows,colWidths=widths,hAlign='LEFT',repeatRows=1,splitByRow=1)
    charges.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),INDIGO),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
        ('LINEBELOW',(0,1),(-1,-1),.55,BORDER),
        ('TOPPADDING',(0,0),(-1,0),8),('BOTTOMPADDING',(0,0),(-1,0),8),
        ('TOPPADDING',(0,1),(-1,-1),7),('BOTTOMPADDING',(0,1),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
    ]))
    story.extend([charges,Spacer(1,6)])

    def total_row(name, value, bold=False):
        return [Paragraph(safe(name), BODYB if bold else BODY),
                Paragraph(f'{safe(data.get("currency") or "INR")} {amount(value)}',RIGHTB if bold else RIGHT)]

    totals = [total_row('Subtotal',data.get('subtotal'))]
    if Decimal(str(data.get('discount') or 0)) > 0:
        totals.append(total_row('Discount', -Decimal(str(data.get('discount'))) ))
    if Decimal(str(data.get('tax_amount') or 0)) > 0:
        totals.append(total_row(f"{data.get('tax_label') or 'Tax'} ({data.get('tax_rate')}%)",data.get('tax_amount')))
    totals.extend([total_row('INVOICE TOTAL',data.get('total'),True)])
    if Decimal(str(data.get('paid_total') or 0)) > 0:
        totals.append(total_row('Payments received',-Decimal(str(data.get('paid_total'))) ))
    totals.append(total_row('BALANCE DUE',data.get('balance_due'),True))
    total_table=Table(totals,colWidths=[192,content_width-192],hAlign='RIGHT')
    total_table.setStyle(TableStyle([
        ('BACKGROUND',(0,-1),(-1,-1),PALE),('LINEABOVE',(0,-1),(-1,-1),1.25,INDIGO),
        ('LINEABOVE',(0,-3),(-1,-3),.4,BORDER),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),11),
    ]))
    story.extend([total_table,Spacer(1,10)])
    # Compact two-column remittance/signature area keeps ordinary invoices on one page.
    left_notes=[]
    if data.get('notes'):
        left_notes += [Paragraph('Notes', SMALL_SECTION), Paragraph(safe(data.get('notes')), COMPACT), Spacer(1, 3)]
    if data.get('terms'):
        left_notes += [Paragraph('Payment terms', SMALL_SECTION), Paragraph(safe(data.get('terms')), COMPACT), Spacer(1, 3)]
    bank = [f'{str(k).replace("_"," ").title()}: {seller.get(k)}' for k in ('bank_name','account_name','account_number','ifsc','upi_id') if seller.get(k)]
    if bank:
        left_notes += [Paragraph('Bank / payment details', SMALL_SECTION), Paragraph(safe('\n'.join(bank)), COMPACT), Spacer(1, 3)]
    right_notes=([Paragraph('DRAFT - NOT ISSUED',SMALL)] if data.get('status')=='draft' else
        [Seal(seller.get('company_name') or 'Techfinitys',
              seller.get('stamp_text') or 'AUTHORISED',stamp_image)])
    remittance=Table([[left_notes or [Paragraph('Thank you for your business.', BODY)], right_notes]],
        colWidths=[content_width*.58,content_width*.42],hAlign='LEFT')
    remittance.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),0),
        ('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))
    story.append(remittance)
    pdf.build(story)
    return buf.getvalue()
