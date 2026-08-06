from django.db import models
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .validators import validate_mobile_number, validate_aadhar_number, validate_pincode, validate_gstin


class Branch(models.Model):
    branch_name = models.CharField(max_length=100, unique=True)
    branch_code = models.CharField(max_length=20, unique=True)
    address = models.TextField()
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    pincode = models.CharField(max_length=6, validators=[validate_pincode])
    phone = models.CharField(max_length=10, validators=[validate_mobile_number])
    email = models.EmailField(blank=True, null=True)
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
        BRANCH_MANAGER = 'BRANCH_MANAGER', 'Branch Manager'
        SALES_EXECUTIVE = 'SALES_EXECUTIVE', 'Sales Executive'
        ACCOUNTANT = 'ACCOUNTANT', 'Accountant'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    role = models.CharField(max_length=20, choices=RoleChoices.choices, default=RoleChoices.SALES_EXECUTIVE)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    mobile_number = models.CharField(max_length=10, validators=[validate_mobile_number], blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class Supplier(models.Model):
    supplier_name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=10, validators=[validate_mobile_number])
    email = models.EmailField(blank=True, null=True)
    gstin = models.CharField(max_length=15, validators=[validate_gstin], blank=True, null=True)
    address = models.TextField()
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    pincode = models.CharField(max_length=6, validators=[validate_pincode], blank=True, null=True)
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


class BatteryCapacity(models.Model):
    capacity_name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Battery Capacities"

    def __str__(self):
        return self.capacity_name


class VehicleColor(models.Model):
    color_name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.color_name


class VehicleModel(models.Model):
    company = models.ForeignKey(VehicleCompany, on_delete=models.CASCADE, related_name='models')
    model_name = models.CharField(max_length=100)
    battery_capacity = models.ForeignKey(BatteryCapacity, on_delete=models.PROTECT)
    base_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'model_name')

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
    battery_capacity = models.ForeignKey(BatteryCapacity, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.purchase_price
        self.cgst_amount = self.subtotal * Decimal('0.09')
        self.sgst_amount = self.subtotal * Decimal('0.09')
        self.total_amount = self.subtotal + self.cgst_amount + self.sgst_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.model.model_name} ({self.color.color_name})"


class Stock(models.Model):
    class StockStatus(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        SOLD = 'SOLD', 'Sold'
        TRANSIT = 'TRANSIT', 'In Transit'
        DAMAGED = 'DAMAGED', 'Damaged'

    purchase_item = models.ForeignKey(PurchaseItem, on_delete=models.CASCADE, related_name='stock_items')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='stock')
    company = models.ForeignKey(VehicleCompany, on_delete=models.PROTECT)
    model = models.ForeignKey(VehicleModel, on_delete=models.PROTECT)
    color = models.ForeignKey(VehicleColor, on_delete=models.PROTECT)
    battery_capacity = models.ForeignKey(BatteryCapacity, on_delete=models.PROTECT)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
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


class Sales(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        ONLINE = 'ONLINE', 'Online / UPI'
        FINANCE = 'FINANCE', 'Finance'
        CHEQUE = 'CHEQUE', 'Cheque'

    invoice_number = models.CharField(max_length=50, unique=True, editable=False)
    invoice_date = models.DateField(default=timezone.now)
    customer_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=10, validators=[validate_mobile_number])
    aadhar_number = models.CharField(max_length=12, validators=[validate_aadhar_number], blank=True, null=True)
    stock = models.OneToOneField(Stock, on_delete=models.PROTECT, related_name='sale_transaction')
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    cgst = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_sales')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Sales"

    def save(self, *args, **kwargs):
        discounted = self.selling_price - self.discount
        base_price = discounted / Decimal('1.18')
        self.subtotal = round(base_price, 2)
        tax = discounted - self.subtotal
        self.cgst = round(tax / Decimal('2'), 2)
        self.sgst = round(tax / Decimal('2'), 2)
        self.grand_total = discounted
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.customer_name}"


class Customer(models.Model):
    customer_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=10, validators=[validate_mobile_number])
    aadhar_number = models.CharField(max_length=12, validators=[validate_aadhar_number], blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    invoice_no = models.CharField(max_length=100, blank=True, null=True)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    branch_name = models.CharField(max_length=100, blank=True, null=True)
    payment_mode = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
        PURCHASE = 'PURCHASE', 'Purchase'
        SALE = 'SALE', 'Sale'
        EXPENSE = 'EXPENSE', 'Expense'
        LOW_STOCK = 'LOW_STOCK', 'Low Stock'
        REMINDER = 'REMINDER', 'Reminder'
        SYSTEM = 'SYSTEM', 'System'
        REPORT = 'REPORT', 'Report'

    # Class attributes for backwards compatibility
    TYPE_REMINDER = NotificationType.REMINDER
    TYPE_SYSTEM = NotificationType.SYSTEM
    TYPE_REPORT = NotificationType.REPORT

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=150)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.SYSTEM)
    is_read = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_notifications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_notification_type_display()})"


class Settings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True) 
    company_name = models.CharField(max_length=150, default="Yakuza EV Showroom")
    company_address = models.TextField(blank=True, null=True)
    company_phone = models.CharField(max_length=15, blank=True, null=True)
    company_email = models.EmailField(blank=True, null=True)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    invoice_prefix = models.CharField(max_length=10, default="GTV")
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9.00)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9.00)
    low_stock_threshold = models.IntegerField(default=2)
    dark_mode = models.BooleanField(default=False)
    auto_backup = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)

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
    username = models.CharField(max_length=150, default="System")
    role = models.CharField(max_length=50, default="System")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    branch_name = models.CharField(max_length=100, default="Global")
    module = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    details = models.TextField(blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.username} - {self.module}:{self.action}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preference')
    email_alerts = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    low_stock_alerts = models.BooleanField(default=True)
    daily_summary = models.BooleanField(default=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"


class InvoiceSetting(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name='invoice_setting', null=True, blank=True)
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
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, default="SUCCESS")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Backup Histories"
        ordering = ['-created_at']

    def __str__(self):
        return f"Backup {self.filename} ({self.status})"