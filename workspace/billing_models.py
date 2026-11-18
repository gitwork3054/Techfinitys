"""Relational client billing. Amounts, issued snapshots and numbering are server-owned."""
import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.utils import timezone

CENT = Decimal('0.01')


def money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


class BillingProfile(models.Model):
    """The organisation's invoice stationery (single record, PK=1)."""
    company_name = models.CharField(max_length=180, default='Techfinitys')
    legal_name = models.CharField(max_length=180, blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=55, blank=True)
    website = models.CharField(max_length=160, blank=True)
    gstin = models.CharField(max_length=25, blank=True)
    pan = models.CharField(max_length=20, blank=True)
    bank_name = models.CharField(max_length=140, blank=True)
    account_name = models.CharField(max_length=180, blank=True)
    account_number = models.CharField(max_length=70, blank=True)
    ifsc = models.CharField(max_length=20, blank=True)
    upi_id = models.CharField(max_length=90, blank=True)
    footer_text = models.CharField(max_length=220, blank=True, default='Thank you for your business.')
    terms = models.TextField(blank=True, default='Payment due by the date shown on this invoice.')
    stamp_text = models.CharField(max_length=65, default='AUTHORISED', blank=True)
    stamp_image = models.ImageField(upload_to='billing/stamps/', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class InvoiceSequence(models.Model):
    year = models.PositiveSmallIntegerField(unique=True)
    next_number = models.PositiveIntegerField(default=1)


class BillingSchedule(models.Model):
    FREQUENCY = [(1, 'Monthly'), (3, 'Quarterly'), (12, 'Yearly')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey('workspace.ClientAccount', on_delete=models.CASCADE, related_name='billing_schedules')
    package_name = models.CharField(max_length=240)
    description = models.CharField(max_length=500, blank=True)
    quantity = models.DecimalField(max_digits=9, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=13, decimal_places=2)
    discount = models.DecimalField(max_digits=13, decimal_places=2, default=0)
    tax_label = models.CharField(max_length=45, default='Tax')
    tax_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    months = models.PositiveSmallIntegerField(choices=FREQUENCY, default=1)
    anchor_day = models.PositiveSmallIntegerField(default=1)
    next_run_on = models.DateField(db_index=True)
    due_days = models.PositiveSmallIntegerField(default=7)
    auto_issue = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey('workspace.Member', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_run_on', 'created_at']


class Invoice(models.Model):
    STATUS = [('draft', 'Draft'), ('issued', 'Issued'), ('partially_paid', 'Partially paid'), ('paid', 'Paid'), ('void', 'Voided')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=36, unique=True, null=True, blank=True)
    client = models.ForeignKey('workspace.ClientAccount', on_delete=models.PROTECT, related_name='structured_invoices')
    bill_to_name = models.CharField(max_length=180)
    bill_to_email = models.EmailField(blank=True)
    bill_to_address = models.TextField(blank=True)
    bill_to_gstin = models.CharField(max_length=25, blank=True)
    package_name = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='draft', db_index=True)
    currency = models.CharField(max_length=3, default='INR')
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    tax_label = models.CharField(max_length=45, default='Tax')
    tax_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=13, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=13, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=13, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=13, decimal_places=2, default=0)
    paid_total = models.DecimalField(max_digits=13, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    seller_snapshot = models.JSONField(default=dict, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey('workspace.Member', null=True, on_delete=models.SET_NULL, related_name='invoices_created')
    recurring_schedule = models.ForeignKey(BillingSchedule, null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    cycle_start = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['client', 'status', 'issue_date'], name='tf_invoice_scope_idx')]
        constraints = [models.UniqueConstraint(fields=['recurring_schedule', 'cycle_start'], condition=models.Q(recurring_schedule__isnull=False), name='tf_invoice_schedule_cycle')]

    @property
    def balance_due(self):
        return money(max(Decimal('0'), self.total - self.paid_total))

    def recalculate(self):
        self.subtotal = money(sum((money(line.quantity * line.unit_price) for line in self.lines.all()), Decimal('0')))
        self.discount = min(self.discount, self.subtotal)
        net = self.subtotal - self.discount
        self.tax_amount = money(net * self.tax_rate / Decimal('100'))
        self.total = money(net + self.tax_amount)


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(max_length=320)
    quantity = models.DecimalField(max_digits=9, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=13, decimal_places=2)
    amount = models.DecimalField(max_digits=13, decimal_places=2)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']


class InvoicePayment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=13, decimal_places=2)
    paid_on = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=30, default='bank_transfer')
    reference = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=300, blank=True)
    recorded_by = models.ForeignKey('workspace.Member', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_on', '-created_at']
        constraints = [models.UniqueConstraint(fields=['invoice', 'reference'], condition=~models.Q(reference=''), name='tf_invoice_payment_ref_unique')]
