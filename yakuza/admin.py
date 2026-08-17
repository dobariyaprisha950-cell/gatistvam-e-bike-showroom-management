from django.contrib import admin
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany, 
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, Customer, ExpenseMaster, Expense, Notification, Settings, AuditLog,
    NotificationPreference, InvoiceSetting, PrinterSetting, SystemPreference, BackupHistory
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('branch_name', 'branch_code', 'city', 'phone', 'is_active', 'created_at')
    search_fields = ('branch_name', 'branch_code', 'city', 'phone')
    list_filter = ('is_active',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'branch', 'mobile_number', 'is_active')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'mobile_number')
    list_filter = ('role', 'is_active', 'branch')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('supplier_name', 'is_active', 'created_at')
    search_fields = ('supplier_name',)
    list_filter = ('is_active',)


@admin.register(VehicleCompany)
class VehicleCompanyAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'is_active', 'created_at')
    search_fields = ('company_name',)


@admin.register(VehicleColor)
class VehicleColorAdmin(admin.ModelAdmin):
    list_display = ('color_name', 'is_active', 'created_at')
    search_fields = ('color_name',)


@admin.register(VehicleModel)
class VehicleModelAdmin(admin.ModelAdmin):
    list_display = ('model_name', 'company', 'base_purchase_price', 'is_active')
    search_fields = ('model_name', 'company__company_name')
    list_filter = ('company', 'is_active')


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1
    readonly_fields = ('subtotal', 'cgst_amount', 'sgst_amount', 'total_amount')


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('purchase_number', 'supplier', 'branch', 'purchase_date', 'invoice_number', 'created_by')
    search_fields = ('purchase_number', 'invoice_number', 'supplier__supplier_name')
    list_filter = ('branch', 'purchase_date')
    inlines = [PurchaseItemInline]
    readonly_fields = ('purchase_number', 'created_by')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('model', 'branch', 'color', 'chassis_number', 'battery_number', 'stock_status', 'purchase_price', 'selling_price')
    search_fields = ('chassis_number', 'battery_number', 'motor_number', 'controller_number', 'model__model_name')
    list_filter = ('stock_status', 'branch', 'company', 'color')
    readonly_fields = ('purchase_item', 'branch', 'company', 'model', 'color', 'purchase_price')


@admin.register(Sales)
class SalesAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'customer_name', 'mobile_number', 'selling_price', 'grand_total', 'payment_method', 'created_at')
    search_fields = ('invoice_no', 'customer_name', 'mobile_number', 'aadhar_number')
    list_filter = ('payment_method', 'created_at')
    readonly_fields = ('invoice_no', 'subtotal', 'cgst', 'sgst', 'grand_total', 'created_by')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'mobile_number', 'model_name', 'branch_name', 'payment_mode', 'created_at')
    search_fields = ('customer_name', 'mobile_number', 'model_name')
    list_filter = ('branch_name', 'payment_mode', 'created_at')


@admin.register(ExpenseMaster)
class ExpenseMasterAdmin(admin.ModelAdmin):
    list_display = ('expense_name', 'is_active')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_master', 'branch', 'amount', 'expense_date', 'created_by')
    search_fields = ('expense_master__expense_name', 'description')
    list_filter = ('branch', 'expense_date')
    readonly_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'branch', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'branch')
    readonly_fields = ('branch', 'title', 'message', 'notification_type', 'created_at')


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'company_phone', 'invoice_prefix', 'low_stock_threshold', 'auto_backup')


@admin.register(InvoiceSetting)
class InvoiceSettingAdmin(admin.ModelAdmin):
    list_display = ('branch', 'company_name', 'gstin', 'phone', 'invoice_prefix')
    search_fields = ('company_name', 'gstin', 'phone')
    list_filter = ('branch',)


@admin.register(PrinterSetting)
class PrinterSettingAdmin(admin.ModelAdmin):
    list_display = ('branch', 'printer_name', 'paper_size', 'copies')
    list_filter = ('paper_size', 'branch')


@admin.register(SystemPreference)
class SystemPreferenceAdmin(admin.ModelAdmin):
    list_display = ('key', 'value')
    search_fields = ('key', 'value')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'sms_alerts', 'low_stock_alerts', 'daily_summary')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('get_user_name', 'get_branch_name', 'module', 'timestamp')
    list_filter = ('module', 'timestamp')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'module', 'action')
    readonly_fields = ('user', 'module', 'action', 'old_value', 'new_value', 'ip_address', 'timestamp')

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return "System"
    get_user_name.short_description = 'User'

    def get_branch_name(self, obj):
        if obj.user and hasattr(obj.user, 'userprofile') and obj.user.userprofile.branch:
            return obj.user.userprofile.branch.name
        return "—"
    get_branch_name.short_description = 'Branch'

@admin.register(BackupHistory)
class BackupHistoryAdmin(admin.ModelAdmin):
    list_display = ('filename', 'branch', 'file_size', 'created_by', 'created_at')
    list_filter = ('branch', 'created_at')
    search_fields = ('filename',)