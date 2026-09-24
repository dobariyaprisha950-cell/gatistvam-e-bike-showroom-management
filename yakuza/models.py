from django.db import models, transaction
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .validators import validate_mobile_number, validate_aadhar_number, validate_pincode, validate_gstin


class Branch(models.Model):
    branch_name = models.CharField(max_length=100, unique=True)
    branch_code = models.CharField(max_length=20, unique=True)
    owner_name = models.CharField(max_length=150, blank=True, null=True)
    address = models.TextField()
    city = models.CharField(max_length=50)
    phone = models.CharField(max_length=10, validators=[validate_mobile_number])
    gst_number = models.CharField(max_length=15, validators=[validate_gstin], blank=True, null=True)
    logo = models.ImageField(upload_to='branch_logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Branches"
        ordering = ['branch_name']

    def __str__(self):
        return f"{self.branch_name} ({self.branch_code})"


class UserProfile(models.Model):
    class RoleChoices(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        BRANCH_ADMIN= 'BRANCH_ADMIN', 'Branch Admin'

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(
        max_length=20, 
        choices=RoleChoices.choices, 
        default=RoleChoices.BRANCH_ADMIN
    )
    mobile_number = models.CharField(max_length=15, blank=True, null=True)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class Supplier(models.Model):
    # Legacy rows remain unassigned until an administrator explicitly assigns
    # them. New master data is always created for a resolved branch.
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='suppliers')
    supplier_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.supplier_name


class VehicleCompany(models.Model):
    company_name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Vehicle Companies"

    def __str__(self):
        return self.company_name


class VehicleColor(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicle_colors')
    color_name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.color_name

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['branch', 'color_name'], name='unique_color_name_per_branch')
        ]


class VehicleModel(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicle_models')
    company = models.ForeignKey(VehicleCompany, on_delete=models.CASCADE, related_name='models')
    model_name = models.CharField(max_length=100)
    base_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['branch', 'company', 'model_name'], name='unique_model_name_per_branch_company')
        ]

    def __str__(self):
        return f"{self.company.company_name} - {self.model_name}"


class Purchase(models.Model):
    purchase_number = models.CharField(max_length=50, unique=True, editable=False)
    purchase_date = models.DateField()
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchases')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='purchases')
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    invoice_photo = models.ImageField(upload_to='invoices/purchase/', blank=True, null=True)
    insurance = models.CharField(max_length=255, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_purchases')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PO #{self.purchase_number} - {self.supplier.supplier_name}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    company = models.ForeignKey(VehicleCompany, on_delete=models.PROTECT)
    model = models.ForeignKey(VehicleModel, on_delete=models.PROTECT)
    color = models.ForeignKey(VehicleColor, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
    
        gross_total = (
            Decimal(str(self.quantity)) *
            Decimal(str(self.purchase_price))
        ).quantize(Decimal('0.01'))

        self.subtotal = gross_total
        self.total_amount = gross_total

        self.cgst_amount = Decimal('0.00')
        self.sgst_amount = Decimal('0.00')

        super().save(*args, **kwargs)
            
    def __str__(self):
        return f"{self.quantity} x {self.model.model_name} ({self.color.color_name})"


class Stock(models.Model):
    class StockStatus(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        SOLD = 'SOLD', 'Sold'
    
    purchase_item = models.ForeignKey(PurchaseItem, on_delete=models.CASCADE, related_name='stock_items', null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='stock')
    company = models.ForeignKey(VehicleCompany, on_delete=models.PROTECT)
    model = models.ForeignKey(VehicleModel, on_delete=models.PROTECT)
    color = models.ForeignKey(VehicleColor, on_delete=models.PROTECT)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_status = models.CharField(max_length=20, choices=StockStatus.choices, default=StockStatus.AVAILABLE)
    chassis_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    battery_number = models.CharField(max_length=100, null=True, blank=True)
    motor_number = models.CharField(max_length=100, null=True, blank=True)
    controller_number = models.CharField(max_length=100, null=True, blank=True)
    sale = models.ForeignKey('Sales', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        chassis = self.chassis_number or 'Unassigned'
        return f"{self.model.model_name} - Chassis: {chassis} ({self.get_stock_status_display()})"


class InvoiceSequence(models.Model):
    """
    Global, monotonically increasing invoice-number counter.

    This is the single source of truth for the numeric part of
    Sales.invoice_no. Once the counter has been initialised it is ONLY
    ever incremented -- never decremented and never recomputed from the
    current set of Sales rows -- which guarantees:

      1. Invoice numbers are unique, even under concurrent requests
         (next_number() takes a row lock via select_for_update()).
      2. A deleted invoice number is NEVER reused, even when the bill
         holding the highest number is the one that gets deleted.

    The original code derived invoice numbers from `Sales.objects.count()`.
    That reissues a previously-used number as soon as ANY bill is deleted,
    because it looks at the CURRENT row count rather than remembering the
    highest number ever issued. This model replaces that.

    INITIALISATION
    --------------
    The counter must start ABOVE any invoice number that already exists,
    otherwise the first bill created on an existing database would be
    handed a number that is already taken (and `Sales.invoice_no` is
    unique=True, so that save would raise IntegrityError).

    Initialisation happens in the migration that creates this table, and
    `_initial_value()` below is used as a runtime fallback so the counter
    is still correct if the table is created some other way (fresh
    install, manual fixture load, restored dump, etc.).
    """
    id = models.PositiveIntegerField(primary_key=True, default=1, editable=False)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Invoice Sequence"
        verbose_name_plural = "Invoice Sequence"

    def __str__(self):
        return f"Invoice sequence (last issued: {self.last_number})"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def extract_number(invoice_no):
        """
        Returns the trailing numeric part of an invoice number, or 0.

        Invoice numbers in this project look like "<PREFIX>-<YEAR>-<NNNN>"
        (e.g. "INV-2026-0004") or "<PREFIX>-<NNNN>". In both cases the
        number we care about is the final dash-separated segment.
        """
        if not invoice_no:
            return 0
        tail = str(invoice_no).rsplit('-', 1)[-1].strip()
        try:
            return int(tail)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _initial_value(cls):
        """
        Highest invoice number currently present in the Sales table.

        Used ONLY to seed the counter the very first time it is created,
        so that an existing database with INV-0001..INV-0005 continues at
        INV-0006 instead of colliding at INV-0001.
        """
        from django.apps import apps
        sales_model = apps.get_model('yakuza', 'Sales')
        highest = 0
        for invoice_no in sales_model.objects.values_list('invoice_no', flat=True):
            highest = max(highest, cls.extract_number(invoice_no))
        return highest

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def next_number(cls):
        """
        Atomically reserves and returns the next invoice number.

        Call this ONLY when a bill is actually being created -- never for
        previews and never when editing an existing bill, so that no
        number is consumed without a bill being issued for it.

        NOTE ON ROLLBACK: if the surrounding request transaction rolls
        back, this increment rolls back with it. That is correct and
        safe: the bill was never created, so no number was ever shown to
        a user or stored, and nothing is "reused". The guarantee that
        matters -- a number belonging to a bill that WAS created is never
        handed out again -- is unaffected, because a committed bill
        implies a committed increment.
        """
        with transaction.atomic():
            seq = cls.objects.select_for_update().filter(pk=1).first()
            if seq is None:
                # First ever use on this database: seed above existing data.
                cls.objects.get_or_create(
                    pk=1,
                    defaults={'last_number': cls._initial_value()},
                )
                seq = cls.objects.select_for_update().get(pk=1)

            seq.last_number += 1
            seq.save(update_fields=['last_number'])
            return seq.last_number

    @classmethod
    def next_invoice_no(cls, prefix, year=None):
        """
        Reserves the next number and formats it into a full invoice
        number for the given prefix.

        THIS IS THE SINGLE ENTRY POINT every bill-creation path must use
        (the Sales page view, the DRF SalesSerializer, and any future
        path), so that no two paths can ever issue the same number or
        fall back to a count()-based scheme.

        The loop is a defensive guard: if the counter is ever behind the
        data (for example after a database restore that re-inserted bills
        with their original numbers), a formatted number could collide
        with an existing row. Rather than raising IntegrityError we skip
        forward, consuming the taken numbers, until we reach a free one.
        Numbers are still only ever moved FORWARD, so nothing is reused.
        """
        from django.apps import apps
        sales_model = apps.get_model('yakuza', 'Sales')

        if year is None:
            year = timezone.now().year

        prefix = (prefix or "INV-").strip() or "INV-"

        for _ in range(1000):
            seq_value = cls.next_number()

            if prefix.endswith(f"{year}-"):
                candidate = f"{prefix}{seq_value:04d}"
            else:
                candidate = f"{prefix}{year}-{seq_value:04d}"

            if not sales_model.objects.filter(invoice_no=candidate).exists():
                return candidate

        raise RuntimeError(
            "Unable to allocate a free invoice number after 1000 attempts; "
            "the InvoiceSequence counter is badly out of sync with the "
            "Sales table."
        )

    @classmethod
    def peek_invoice_no(cls, prefix, year=None):
        """
        Formats the NEXT invoice number for display only, without
        reserving it. Used by the Sales form preview.
        """
        if year is None:
            year = timezone.now().year

        prefix = (prefix or "INV-").strip() or "INV-"
        seq_value = cls.peek_next()

        if prefix.endswith(f"{year}-"):
            return f"{prefix}{seq_value:04d}"
        return f"{prefix}{year}-{seq_value:04d}"

    @classmethod
    def sync_to_existing_data(cls):
        """
        Pushes the counter forward so it sits above every invoice number
        currently in the Sales table. Never moves the counter backwards.

        Called after a backup restore, which re-inserts bills carrying
        their original invoice numbers and would otherwise leave the
        counter behind the data.
        """
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(
                pk=1, defaults={'last_number': 0}
            )
            highest = cls._initial_value()
            if highest > seq.last_number:
                seq.last_number = highest
                seq.save(update_fields=['last_number'])
            return seq.last_number

    @classmethod
    def peek_next(cls):
        """
        Read-only preview of what the next invoice number WOULD be.

        Does NOT reserve or consume anything, so it is safe to call on
        every page load of the Sales form. Because it does not reserve,
        two users opening the form at the same time will see the same
        preview but will still receive different real numbers when they
        actually save.
        """
        seq = cls.objects.filter(pk=1).first()
        last = seq.last_number if seq is not None else cls._initial_value()
        return last + 1


class Sales(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        UPI = 'UPI', 'UPI'
        EMI = 'EMI', 'EMI'

    invoice_no = models.CharField(max_length=50, unique=True, editable=False)
    invoice_date = models.DateField(default=timezone.now)
    customer_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=10, validators=[validate_mobile_number])
    aadhar_number = models.CharField(max_length=12, validators=[validate_aadhar_number], blank=True, null=True)
    extra_accessories = models.TextField(blank=True, default='')
    voltage = models.CharField(max_length=20, blank=True, default='')
    stock = models.OneToOneField(Stock, on_delete=models.PROTECT, related_name='sale_transaction')
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    cgst = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    invoice_photo = models.ImageField(upload_to='invoices/', blank=True, null=True)
    invoice_pdf = models.FileField(upload_to='invoices/pdf/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_sales')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Sales"

    def save(self, *args, **kwargs):
        self.subtotal = round(self.selling_price, 2)
        self.cgst = round(self.subtotal * Decimal('0.025'), 2)
        self.sgst = round(self.subtotal * Decimal('0.025'), 2)
        self.grand_total = round(self.subtotal + self.cgst + self.sgst, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice #{self.invoice_no} - {self.customer_name}"

class Customer(models.Model):
    invoice_no = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        null=True
    )

    customer_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=10, validators=[validate_mobile_number])
    aadhar_number = models.CharField(max_length=12, validators=[validate_aadhar_number], blank=True, null=True)
    invoice_photo = models.ImageField(upload_to='invoices/customer/', blank=True, null=True)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # Legacy free-text branch label. Kept (not removed) so existing data,
    # templates and exports that read branch_name keep working unchanged.
    branch_name = models.CharField(max_length=100, blank=True, null=True)
    # Authoritative branch link used for isolation/filtering going forward.
    # Nullable so existing rows are never deleted; a data migration backfills
    # this from branch_name for rows that already match a Branch by name.
    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='customers'
    )
    payment_mode = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            settings_obj = Settings.load()
            prefix = settings_obj.invoice_prefix or "GTV"

            last_customer = (
                Customer.objects
                .filter(invoice_no__startswith=f"{prefix}-")
                .order_by("-id")
                .first()
            )

            if last_customer and last_customer.invoice_no:
                try:
                    last_number = int(last_customer.invoice_no.rsplit("-", 1)[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1

            self.invoice_no = f"{prefix}-{next_number:05d}"

        super().save(*args, **kwargs)

    @property
    def name(self):
        return self.customer_name

    @property
    def phone(self):
        return self.mobile_number

    def __str__(self):
        return f"{self.customer_name} ({self.mobile_number})"


class ExpenseMaster(models.Model):
    expense_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.expense_name


class Expense(models.Model):
    expense_master = models.ForeignKey(ExpenseMaster, on_delete=models.PROTECT, related_name='expenses')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='expenses')
    expense_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_expenses')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.expense_master.expense_name} - ₹{self.amount} ({self.branch.branch_name})"


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        LOW_STOCK = 'LOW_STOCK', 'Low Stock'
        REMINDER = 'REMINDER', 'Reminder'
        

    TYPE_REMINDER = NotificationType.REMINDER

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=150)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.REMINDER)
    is_read = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_notifications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.title}"


class Settings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    company_name = models.CharField(max_length=150, default="Yakuza EV Showroom")
    company_address = models.TextField(blank=True, null=True)
    company_phone = models.CharField(max_length=15, blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    invoice_prefix = models.CharField(max_length=10, default="GTV")
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9.00)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9.00)
    low_stock_threshold = models.IntegerField(default=2)
    auto_backup = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    notification_status = models.BooleanField(default=True)
    auto_delete_days = models.CharField(max_length=10, default="30")
    date_format = models.CharField(max_length=20, default="DD-MM-YYYY")
    time_format = models.CharField(max_length=10, default="12h")

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"System Settings ({self.company_name})"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    # Records the branch the action happened in (independent of the user's
    # current branch assignment, which can change later). Added for strict
    # branch isolation in the Audit Log Settings module.
    branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    module = models.CharField(max_length=100)
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Minimal schema addition for diff tracking
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.module} - {self.timestamp}"

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preference')
    sms_alerts = models.BooleanField(default=False)
    low_stock_alerts = models.BooleanField(default=True)
    daily_summary = models.BooleanField(default=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"


class InvoiceSetting(models.Model):
    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name='invoice_setting', null=True, blank=True)
    company_name = models.CharField(max_length=150, blank=True, null=True)
    invoice_prefix = models.CharField(max_length=20, default="INV-2026-")
    company_address = models.TextField(blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    terms = models.TextField(blank=True, null=True)
    header_text = models.TextField(blank=True, null=True)
    footer_text = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='invoice_logos/', blank=True, null=True)
    show_terms = models.BooleanField(default=True)

    def __str__(self):
        return f"Invoice Setting ({self.branch.branch_name if self.branch else 'Global'})"


class PrinterSetting(models.Model):
    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name='printer_setting', null=True, blank=True)
    printer_name = models.CharField(max_length=100, default="Default Printer")
    paper_size = models.CharField(max_length=20, default="A4")
    copies = models.IntegerField(default=1)

    def __str__(self):
        return f"Printer Setting ({self.branch.branch_name if self.branch else 'Global'})"


class SystemPreference(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()

    def __str__(self):
        return f"{self.key} = {self.value}"


class BackupHistory(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name='backups')
    filename = models.CharField(max_length=255)
    file_size = models.CharField(max_length=50, default="0.00 MB")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.filename} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

