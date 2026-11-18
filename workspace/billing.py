"""Client-scoped invoicing, issued snapshots, manually recorded payments and PDF export."""
import base64
import calendar
import io
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods, require_POST
from PIL import Image, UnidentifiedImageError
from .billing_models import (BillingProfile, BillingSchedule, Invoice, InvoiceLine, InvoicePayment, InvoiceSequence, money)
from .models import ClientAccount, Member, Notification, ActivityLog
from .views import _context

MAX_INVOICES = 400
PROFILE_FIELDS = ('company_name','legal_name','address','email','phone','website','gstin','pan',
                  'bank_name','account_name','account_number','ifsc','upi_id','footer_text','terms','stamp_text')
PROFILE_LIMITS = {'company_name':180,'legal_name':180,'address':1200,'email':254,'phone':55,'website':160,
                  'gstin':25,'pan':20,'bank_name':140,'account_name':180,'account_number':70,'ifsc':20,
                  'upi_id':90,'footer_text':220,'terms':3000,'stamp_text':65}


def _member(request):
    try:
        m = _context(request)
    except PermissionError:
        raise PermissionError('Sign in to continue')
    if m.role not in ('admin', 'manager', 'client'):
        raise PermissionError('Billing access is restricted to finance managers and client account holders')
    return m


def _manager(m):
    if m.role not in ('admin','manager'):
        raise PermissionError('Only managers can manage invoices')


def _snapshot(profile):
    info = {key:getattr(profile,key) for key in PROFILE_FIELDS}
    if profile.stamp_image:
        try:
            profile.stamp_image.open('rb')
            raw = profile.stamp_image.read(350001)
            profile.stamp_image.close()
            if len(raw) <= 350000:
                info['stamp_b64'] = base64.b64encode(raw).decode('ascii')
        except (OSError, ValueError):
            pass
    return info


def _visible_invoice_qs(m):
    qs = Invoice.objects.select_related('client').prefetch_related('lines','payments')
    if m.role == 'client':
        if not m.client_account_id:
            return qs.none()
        return qs.filter(client_id=m.client_account_id).exclude(status='draft')
    return qs


def _get_invoice(m, invoice_id):
    try:
        key=uuid.UUID(str(invoice_id))
    except (ValueError,TypeError,AttributeError):
        raise ValueError('Invalid invoice identifier')
    obj=_visible_invoice_qs(m).filter(pk=key).first()
    if obj is None:
        raise PermissionError('Invoice not found or not accessible')
    return obj


def _dec(value, label, lower=Decimal('0'), upper=Decimal('9999999999')):
    try:
        n=Decimal(str(value))
        if not n.is_finite() or n < lower or n > upper:
            raise ValueError()
        if n.as_tuple().exponent < -2:
            raise ValueError()
        return money(n)
    except (TypeError, ValueError, InvalidOperation):
        raise ValueError(f'Enter a valid {label} with at most two decimal places')


def _text(data,key,limit,required=False):
    v=str(data.get(key) or '').strip()
    if len(v) > limit or (required and not v):
        raise ValueError(f'{key} is required and must be at most {limit} characters')
    return v


def _date(data,key,required=True):
    val=data.get(key)
    if not val:
        if required:
            raise ValueError(f'{key} is required')
        return None
    out=parse_date(str(val))
    if out is None:
        raise ValueError(f'{key} must be YYYY-MM-DD')
    return out


def _lines(data):
    rows=data.get('items')
    if not isinstance(rows,list) or not rows:
        rows=[{'description':data.get('packageName') or '', 'quantity':data.get('quantity') or 1,
               'unitPrice':data.get('amount') or ''}]
    if not 1 <= len(rows) <= 40:
        raise ValueError('Add between one and forty invoice lines')
    parsed=[]
    for index, row in enumerate(rows):
        if not isinstance(row,dict):
            raise ValueError('Each invoice line must be an object')
        description=_text(row,'description',320,True)
        quantity=_dec(row.get('quantity',1),'quantity',Decimal('.01'),Decimal('99999'))
        unit_price=_dec(row.get('unitPrice',row.get('unit_price')),'unit price',Decimal('.01'),Decimal('999999999'))
        line_total=money(quantity*unit_price)
        if line_total >= Decimal('100000000000'):
            raise ValueError('Line amount is too large')
        parsed.append((description,quantity,unit_price,line_total,index))
    return parsed


def _set_invoice_fields(obj,data,client):
    obj.client=client
    obj.bill_to_name=_text(data,'billToName',180) or client.company or client.name
    obj.bill_to_email=_text(data,'billToEmail',254) or client.email
    obj.bill_to_address=_text(data,'billToAddress',1200)
    obj.bill_to_gstin=_text(data,'billToGstin',25).upper()
    obj.package_name=_text(data,'packageName',240,True)
    obj.description=_text(data,'description',1500)
    obj.issue_date=_date(data,'issueDate')
    obj.due_date=_date(data,'dueDate')
    if obj.due_date < obj.issue_date:
        raise ValueError('Due date must be on or after issue date')
    obj.period_start=_date(data,'periodStart',False)
    obj.period_end=_date(data,'periodEnd',False)
    if bool(obj.period_start) != bool(obj.period_end) or (obj.period_start and obj.period_start>obj.period_end):
        raise ValueError('Enter a valid service period (start and end)')
    obj.tax_label=_text(data,'taxLabel',45) or 'Tax'
    obj.tax_rate=_dec(data.get('taxRate',0),'tax rate',Decimal('0'),Decimal('100'))
    obj.discount=_dec(data.get('discount',0),'discount')
    obj.notes=_text(data,'notes',3000)
    obj.terms=_text(data,'terms',3000)
    obj.currency='INR'


@transaction.atomic
def save_draft(data, actor, obj=None):
    _manager(actor)
    try:
        client=ClientAccount.objects.get(pk=uuid.UUID(str(data.get('clientId',''))))
    except (ClientAccount.DoesNotExist,ValueError,TypeError):
        raise ValueError('Select a valid client')
    if obj is not None:
        obj=Invoice.objects.select_for_update().get(pk=obj.pk)
        if obj.status!='draft' or obj.recurring_schedule_id:
            raise ValueError('Only manual draft invoices can be edited')
    else:
        obj=Invoice(created_by=actor)
    _set_invoice_fields(obj,data,client)
    lines=_lines(data)
    subtotal=money(sum((r[3] for r in lines),Decimal('0')))
    if obj.discount>subtotal:
        raise ValueError('Discount may not exceed subtotal')
    if subtotal>Decimal('9999999999'):
        raise ValueError('Invoice subtotal exceeds the supported limit')
    obj.subtotal=subtotal
    obj.tax_amount=money((subtotal-obj.discount)*obj.tax_rate/Decimal('100'))
    obj.total=money(subtotal-obj.discount+obj.tax_amount)
    if obj.total>Decimal('9999999999'):
        raise ValueError('Invoice total exceeds the supported limit')
    obj.save()
    obj.lines.all().delete()
    InvoiceLine.objects.bulk_create([InvoiceLine(invoice=obj,description=d,quantity=q,unit_price=p,amount=a,position=i)
        for d,q,p,a,i in lines])
    ActivityLog.objects.create(actor=actor,client=client,action='invoice_draft_saved',entity_type='Invoice',
        entity_id=str(obj.pk),detail=f'Draft package: {obj.package_name}')
    return obj


@transaction.atomic
def issue_invoice(invoice, actor=None):
    """Atomic issue with sequential number and seller snapshot. Call from job or admin API."""
    obj=Invoice.objects.select_for_update().get(pk=invoice.pk)
    if obj.status!='draft':
        raise ValueError('Only draft invoices can be issued')
    if not obj.lines.exists() or obj.total<=0:
        raise ValueError('Invoice needs at least one positive line')
    if obj.due_date < obj.issue_date:
        raise ValueError('Due date cannot precede issue date')
    year=obj.issue_date.year
    InvoiceSequence.objects.get_or_create(year=year,defaults={'next_number':1})
    seq=InvoiceSequence.objects.select_for_update().get(year=year)
    number=f'TF-{year}-{seq.next_number:05d}'
    seq.next_number+=1
    seq.save(update_fields=['next_number'])
    obj.invoice_number=number
    obj.seller_snapshot=_snapshot(BillingProfile.objects.get_or_create(pk=1)[0])
    obj.issued_at=timezone.now()
    obj.status='issued'
    obj.save(update_fields=['invoice_number','seller_snapshot','issued_at','status','updated_at'])
    ActivityLog.objects.create(actor=actor,client=obj.client,action='invoice_issued',entity_type='Invoice',
        entity_id=str(obj.pk),detail=number)
    recipients=Member.objects.filter(role='client',client_account=obj.client,is_active=True)
    Notification.objects.bulk_create([Notification(recipient=m,client=obj.client,title=f'Invoice {number} issued',
        body=f'{obj.package_name}: INR {obj.total}. Due {obj.due_date.isoformat()}.') for m in recipients])
    return obj


@transaction.atomic
def record_payment(invoice, data, actor):
    _manager(actor)
    obj=Invoice.objects.select_for_update().get(pk=invoice.pk)
    if obj.status not in ('issued','partially_paid'):
        raise ValueError('Payments may only be recorded against issued, unpaid invoices')
    amount_paid=_dec(data.get('amount'),'payment amount',Decimal('.01'))
    if amount_paid>obj.balance_due:
        raise ValueError('Payment exceeds outstanding balance')
    method=_text(data,'method',30) or 'bank_transfer'
    if method not in ('bank_transfer','upi','cash','cheque','card','other'):
        raise ValueError('Invalid payment method')
    reference=_text(data,'reference',120)
    if reference and InvoicePayment.objects.filter(invoice=obj,reference=reference).exists():
        raise ValueError('This payment reference was already recorded')
    paid_on=_date(data,'paidOn')
    InvoicePayment.objects.create(invoice=obj,amount=amount_paid,method=method,reference=reference,
        note=_text(data,'note',300),paid_on=paid_on,recorded_by=actor)
    obj.paid_total=money(obj.paid_total+amount_paid)
    obj.status='paid' if obj.paid_total>=obj.total else 'partially_paid'
    obj.save(update_fields=['paid_total','status','updated_at'])
    ActivityLog.objects.create(actor=actor,client=obj.client,action='invoice_payment',entity_type='Invoice',
        entity_id=str(obj.pk),detail=f'{obj.invoice_number}: INR {amount_paid} ({method})')
    return obj


@transaction.atomic
def void_invoice(invoice,actor,reason):
    _manager(actor)
    obj=Invoice.objects.select_for_update().get(pk=invoice.pk)
    if obj.status!='issued' or obj.payments.exists():
        raise ValueError('Only issued invoices without recorded payments can be voided')
    obj.status='void';obj.save(update_fields=['status','updated_at'])
    ActivityLog.objects.create(actor=actor,client=obj.client,action='invoice_voided',entity_type='Invoice',
        entity_id=str(obj.pk),detail=(obj.invoice_number or '')+' - '+reason)
    return obj


def _invoice_json(obj,details=False):
    due=obj.status in ('issued','partially_paid') and obj.due_date<timezone.localdate()
    result={'id':str(obj.pk),'number':obj.invoice_number or 'DRAFT',
       'clientId':str(obj.client_id),'clientName':obj.client.name,'packageName':obj.package_name,
       'billToName':obj.bill_to_name,'billToEmail':obj.bill_to_email,'billToAddress':obj.bill_to_address,
       'billToGstin':obj.bill_to_gstin,'description':obj.description,
       'status':obj.status,'overdue':due,'issueDate':obj.issue_date.isoformat(),'dueDate':obj.due_date.isoformat(),
       'periodStart':obj.period_start.isoformat() if obj.period_start else '',
       'periodEnd':obj.period_end.isoformat() if obj.period_end else '',
       'currency':obj.currency,'taxLabel':obj.tax_label,'taxRate':str(obj.tax_rate),
       'discount':str(obj.discount),'subtotal':str(obj.subtotal),'taxAmount':str(obj.tax_amount),
       'total':str(obj.total),'paidTotal':str(obj.paid_total),'balanceDue':str(obj.balance_due),
       'notes':obj.notes,'terms':obj.terms,'createdAt':obj.created_at.isoformat(),
       'recurringScheduleId':str(obj.recurring_schedule_id) if obj.recurring_schedule_id else ''}
    if details:
        result['items']=[{'id':x.id,'description':x.description,'quantity':str(x.quantity),
                          'unitPrice':str(x.unit_price),'amount':str(x.amount)} for x in obj.lines.all()]
        result['payments']=[{'id':x.id,'amount':str(x.amount),'paidOn':x.paid_on.isoformat(),
                             'method':x.method,'reference':x.reference,'note':x.note} for x in obj.payments.all()]
    return result


def _schedule_json(s):
    return {'id':str(s.pk),'clientId':str(s.client_id),'clientName':s.client.name,
       'packageName':s.package_name,'description':s.description,'quantity':str(s.quantity),
       'amount':str(s.unit_price),'discount':str(s.discount),'taxLabel':s.tax_label,'taxRate':str(s.tax_rate),
       'months':s.months,'nextRunOn':s.next_run_on.isoformat(),'dueDays':s.due_days,
       'autoIssue':s.auto_issue,'active':s.active}


def _serialize_profile(p):
    return {field:getattr(p,field) for field in PROFILE_FIELDS} | {'hasStamp':bool(p.stamp_image)}


def _json_response_error(error):
    if isinstance(error,PermissionError):return JsonResponse({'error':str(error)},status=403)
    if isinstance(error, (ValueError,IntegrityError)):
        return JsonResponse({'error':str(error) if isinstance(error, ValueError) else 'Duplicate or conflicting invoice record'},status=400)
    return JsonResponse({'error':'Invalid request'},status=400)


@require_http_methods(['GET','POST'])
def billing_api(request):
    try:
        member=_member(request)
        if request.method=='GET':
            qs=_visible_invoice_qs(member).order_by('-created_at')[:MAX_INVOICES]
            invoices=[_invoice_json(i,details=True) for i in qs]
            profile=BillingProfile.objects.filter(pk=1).first()
            payload={'invoices':invoices,'canManage':member.role in ('admin','manager'),
                    'seller':_serialize_profile(profile) if profile and member.role in ('admin','manager') else {},
                    'schedules':[_schedule_json(s) for s in BillingSchedule.objects.select_related('client').all()[:200]]
                         if member.role in ('admin','manager') else [],
                    'storageWarning':not bool(settings.DATABASES['default']['ENGINE'].endswith('postgresql'))}
            return JsonResponse(payload)
        _manager(member)
        data=json.loads(request.body.decode('utf-8'))
        if not isinstance(data,dict):raise ValueError('JSON object required')
        action=str(data.get('action') or '')
        if action in ('save_draft','create_draft'):
            inv = _get_invoice(member,data.get('id')) if data.get('id') else None
            inv=save_draft(data,member,inv)
            return JsonResponse({'invoice':_invoice_json(inv,True)})
        if action == 'issue':
            inv=issue_invoice(_get_invoice(member,data.get('id')),member)
            return JsonResponse({'invoice':_invoice_json(inv,True)})
        if action == 'payment':
            inv=record_payment(_get_invoice(member,data.get('id')),data,member)
            return JsonResponse({'invoice':_invoice_json(inv,True)})
        if action == 'void':
            reason=_text(data,'reason',500,True)
            inv=void_invoice(_get_invoice(member,data.get('id')),member,reason)
            return JsonResponse({'invoice':_invoice_json(inv,True)})
        if action=='profile':
            if member.role!='admin':raise PermissionError('Only Super Admin may edit invoice letterhead')
            with transaction.atomic():
                p,_=BillingProfile.objects.get_or_create(pk=1)
                for key in PROFILE_FIELDS:
                    if key in data:
                        value=_text(data,key,PROFILE_LIMITS[key],required=key=='company_name')
                        setattr(p,key,value)
                p.save()
                ActivityLog.objects.create(actor=member,action='billing_profile_updated',entity_type='BillingProfile',entity_id='1')
            return JsonResponse({'seller':_serialize_profile(p)})
        if action=='schedule':
            if data.get('id'):
                s=BillingSchedule.objects.get(pk=uuid.UUID(str(data['id'])))
            else:
                s=BillingSchedule(created_by=member)
            # Existing schedules can be paused/resumed without resubmitting package fields.
            # Preserve the agreed billing terms once a schedule is created.
            if not data.get('id'):
                try: s.client=ClientAccount.objects.get(pk=uuid.UUID(str(data.get('clientId',''))))
                except (ClientAccount.DoesNotExist,TypeError,ValueError):raise ValueError('Select a client')
                s.package_name=_text(data,'packageName',240,True)
                s.description=_text(data,'description',500)
                s.quantity=_dec(data.get('quantity',1),'quantity',Decimal('.01'),Decimal('99999'))
                s.unit_price=_dec(data.get('amount'),'package amount',Decimal('.01'),Decimal('999999999'))
                s.discount=_dec(data.get('discount',0),'discount')
                package_subtotal=money(s.quantity*s.unit_price)
                if package_subtotal>Decimal('9999999999'):
                    raise ValueError('Recurring package exceeds the supported invoice limit')
                if s.discount>=package_subtotal:
                    raise ValueError('Discount must be less than the package amount')
                s.tax_rate=_dec(data.get('taxRate',0),'tax rate',Decimal('0'),Decimal('100'))
                planned_total=money(package_subtotal-s.discount+money((package_subtotal-s.discount)*s.tax_rate/Decimal('100')))
                if planned_total>Decimal('9999999999'):
                    raise ValueError('Recurring total exceeds the supported invoice limit')
                s.tax_label=_text(data,'taxLabel',45) or 'Tax'
                s.months=int(data.get('months') or 1)
                if s.months not in (1,3,12):raise ValueError('Choose monthly, quarterly or yearly')
                s.next_run_on=_date(data,'nextRunOn')
                s.anchor_day=s.next_run_on.day
                s.due_days=int(data.get('dueDays',7))
                if s.due_days<0 or s.due_days>180:raise ValueError('Due days must be between 0 and 180')
            if 'active' in data: s.active=data['active'] is True
            if 'autoIssue' in data: s.auto_issue=data['autoIssue'] is True
            s.save()
            return JsonResponse({'schedule':_schedule_json(s)})
        raise ValueError('Unknown billing action')
    except (ValueError,PermissionError,IntegrityError) as error:
        return _json_response_error(error)
    except (ClientAccount.DoesNotExist,Invoice.DoesNotExist,BillingSchedule.DoesNotExist):
        return JsonResponse({'error':'Record not found'},status=404)
    except (json.JSONDecodeError,UnicodeDecodeError):
        return JsonResponse({'error':'Invalid JSON'},status=400)


@require_http_methods(['GET'])
def invoice_pdf(request,invoice_id):
    try:
        member=_member(request)
        invoice=_get_invoice(member,invoice_id)
    except (PermissionError,ValueError):
        return HttpResponse('Invoice not found',status=404)
    seller=invoice.seller_snapshot or _snapshot(BillingProfile.objects.get_or_create(pk=1)[0])
    # Keep PDF rendering detached from mutable client values: use issue-time snapshots.
    raw_stamp=None
    if seller.get('stamp_b64'):
        try:raw_stamp=base64.b64decode(seller['stamp_b64'],validate=True)
        except (ValueError,TypeError):pass
    payload={'number':invoice.invoice_number or 'DRAFT','status':invoice.status,
       'seller':seller,'bill_to_name':invoice.bill_to_name,'bill_to_email':invoice.bill_to_email,
       'bill_to_address':invoice.bill_to_address,'bill_to_gstin':invoice.bill_to_gstin,
       'issue_date':invoice.issue_date,'due_date':invoice.due_date,'period_start':invoice.period_start,
       'period_end':invoice.period_end,'currency':invoice.currency,'notes':invoice.notes,
       'terms':invoice.terms or seller.get('terms',''),'tax_label':invoice.tax_label,'tax_rate':invoice.tax_rate,
       'subtotal':invoice.subtotal,'discount':invoice.discount,'tax_amount':invoice.tax_amount,
       'total':invoice.total,'paid_total':invoice.paid_total,'balance_due':invoice.balance_due,
       'items':[{'description':l.description,'quantity':l.quantity,'unit_price':l.unit_price,'amount':l.amount}
                for l in invoice.lines.all()]}
    from .billing_pdf import build_pdf
    logo=Path(settings.BASE_DIR)/'workspace/static/images/techfinitys-logo.png'
    try:binary=build_pdf(payload,logo_path=str(logo),stamp_image=raw_stamp)
    except Exception:
        return HttpResponse('Could not render invoice PDF',status=500)
    response=HttpResponse(binary,content_type='application/pdf')
    fname=(invoice.invoice_number or 'Invoice-draft')+'.pdf'
    response['Content-Disposition']=f'attachment; filename="{fname}"'
    response['Cache-Control']='private, no-store'
    return response


@require_POST
def stamp_upload(request):
    try:
        member=_member(request)
        if member.role!='admin':raise PermissionError('Only Super Admin can upload a company stamp')
        f=request.FILES.get('stamp')
        if not f or f.size>450_000 or f.size<20:
            raise ValueError('Provide a PNG or JPEG stamp image smaller than 450 KB')
        Image.MAX_IMAGE_PIXELS=20_000_000
        raw=f.read()
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ('PNG','JPEG'):
                raise ValueError('Stamp must be PNG or JPEG')
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.thumbnail((800,800))
            image=image.convert('RGBA')
            processed=io.BytesIO();image.save(processed,format='PNG',optimize=True)
        content=processed.getvalue()
        if len(content)>350000:
            raise ValueError('Stamp image too complex; use a smaller PNG')
        from django.core.files.base import ContentFile
        with transaction.atomic():
            profile,_=BillingProfile.objects.get_or_create(pk=1)
            if profile.stamp_image:
                profile.stamp_image.delete(save=False)
            profile.stamp_image.save('authorized-stamp.png',ContentFile(content),save=True)
            ActivityLog.objects.create(actor=member,action='billing_stamp_updated',entity_type='BillingProfile',entity_id='1')
        return JsonResponse({'ok':True})
    except (PermissionError,ValueError,UnidentifiedImageError) as error:
        return _json_response_error(error)


@require_http_methods(['GET'])
def billing_export(request):
    try:m=_member(request)
    except PermissionError:return HttpResponse('Not authorized',status=403)
    if m.role=='client':return HttpResponse('Not authorized',status=403)
    import csv
    response=HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition']='attachment; filename="techfinitys-invoices.csv"'
    writer=csv.writer(response)
    writer.writerow(['Invoice','Client','Package','Status','Issued','Due','Subtotal INR','Discount INR','Tax INR','Total INR','Paid INR','Balance INR'])
    for i in _visible_invoice_qs(m).iterator(chunk_size=200):
        writer.writerow([i.invoice_number or 'DRAFT',i.client.name,i.package_name,i.status,i.issue_date,i.due_date,
                         i.subtotal,i.discount,i.tax_amount,i.total,i.paid_total,i.balance_due])
    return response


def advance_months(value,months,anchor):
    """Preserve the original billing day (Jan 31 -> Feb 28 -> Mar 31)."""
    month=(value.month-1)+months
    year=value.year+month//12
    m=month%12+1
    return date(year,m,min(anchor,calendar.monthrange(year,m)[1]))


@transaction.atomic
def generate_due_schedules(today=None):
    """Idempotent recurrence generation. Intended for an authenticated scheduled command."""
    current=today or timezone.localdate()
    created=[]
    for plan in BillingSchedule.objects.select_for_update().filter(active=True,next_run_on__lte=current).select_related('client'):
        cycles=0
        while plan.next_run_on<=current and cycles<12:
            start=plan.next_run_on
            following=advance_months(start,plan.months,plan.anchor_day)
            existing=Invoice.objects.filter(recurring_schedule=plan,cycle_start=start).first()
            if not existing:
                package=plan.package_name
                sub=money(plan.unit_price*plan.quantity)
                tax=money((sub-plan.discount)*plan.tax_rate/Decimal('100'))
                inv=Invoice.objects.create(client=plan.client,created_by=plan.created_by,
                    recurring_schedule=plan,cycle_start=start,
                    bill_to_name=plan.client.company or plan.client.name,bill_to_email=plan.client.email,
                    package_name=package,description=plan.description,issue_date=start,
                    due_date=start+timedelta(days=plan.due_days),period_start=start,period_end=following-timedelta(days=1),
                    tax_label=plan.tax_label,tax_rate=plan.tax_rate,discount=plan.discount,
                    subtotal=sub,tax_amount=tax,total=money(sub-plan.discount+tax),
                    terms=BillingProfile.objects.get_or_create(pk=1)[0].terms)
                InvoiceLine.objects.create(invoice=inv,description=package,quantity=plan.quantity,
                    unit_price=plan.unit_price,amount=sub)
                if plan.auto_issue:inv=issue_invoice(inv,plan.created_by)
                created.append(inv)
            plan.next_run_on=following
            cycles+=1
        plan.save(update_fields=['next_run_on','updated_at'])
    return created
