from django.contrib import admin
from django.utils.html import format_html
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany, BatteryCapacity,
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, Customer, ExpenseMaster, Expense, Notification, Settings, AuditLog,
    NotificationPreference, InvoiceSetting, PrinterSetting, SystemPreference, BackupHistory
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('branch_name', 'branch_code', 'city', 'phone', 'is_active', 'created_at')
    search_fields = ('branch_name', 'branch_code', 'city', 'phone')
    list_filter = ('is_active', 'state')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'branch', 'mobile_number', 'is_active')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'mobile_number')
    list_filter = ('role', 'is_active', 'branch')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('supplier_name', 'contact_person', 'phone', 'city', 'is_active')
    search_fields = ('supplier_name', 'contact_person', 'phone')
    list_filter = ('is_active',)


@admin.register(VehicleCompany)
class VehicleCompanyAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'is_active', 'created_at')
    search_fields = ('company_name',)


@admin.register(BatteryCapacity)
class BatteryCapacityAdmin(admin.ModelAdmin):
    list_display = ('capacity_name', 'is_active')
    search_fields = ('capacity_name',)


@admin.register(VehicleColor)
class VehicleColorAdmin(admin.ModelAdmin):
    list_display = ('color_name', 'is_active', 'created_at')
    search_fields = ('color_name',)


@admin.register(VehicleModel)
class VehicleModelAdmin(admin.ModelAdmin):
    list_display = ('model_name', 'company', 'battery_capacity', 'base_purchase_price', 'is_active')
    search_fields = ('model_name', 'company__company_name')
    list_filter = ('company', 'is_active', 'battery_capacity')


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
    readonly_fields = ('purchase_item', 'branch', 'company', 'model', 'color', 'battery_capacity', 'purchase_price')


@admin.register(Sales)
class SalesAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer_name', 'mobile_number', 'selling_price', 'grand_total', 'payment_method', 'created_at')
    search_fields = ('invoice_number', 'customer_name', 'mobile_number', 'aadhar_number')
    list_filter = ('payment_method', 'created_at')
    readonly_fields = ('invoice_number', 'subtotal', 'cgst', 'sgst', 'grand_total', 'created_by')

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


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'username', 'role', 'branch_name', 'module', 'action', 'ip_address')
    list_filter = ('module', 'action', 'branch_name')
    search_fields = ('username', 'module', 'action', 'details')
    readonly_fields = ('user', 'username', 'role', 'branch', 'branch_name', 'module', 'action', 'details', 'old_value', 'new_value', 'ip_address', 'created_at')


@admin.register(BackupHistory)
class BackupHistoryAdmin(admin.ModelAdmin):
    list_display = ('filename', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'created_at')