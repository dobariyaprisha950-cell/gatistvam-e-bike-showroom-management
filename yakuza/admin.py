from django.contrib import admin
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.hashers import make_password
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany, 
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, Customer, ExpenseMaster, Expense, Notification, Settings, AuditLog,
    NotificationPreference, InvoiceSetting, PrinterSetting, SystemPreference, BackupHistory
)


User = get_user_model()

# Keep the choices and answer normalization in step with the public recovery
# flow in yakuza.views (whitespace collapse followed by case folding).
RECOVERY_QUESTION_CHOICES = (
    ('What was the name of your first school?', 'What was the name of your first school?'),
    ('What city were you born in?', 'What city were you born in?'),
    ('What was the name of your first pet?', 'What was the name of your first pet?'),
)


class UserSecurityProfileForm(forms.ModelForm):
    recovery_question = forms.ChoiceField(
        choices=(('', '---------'),) + RECOVERY_QUESTION_CHOICES,
        required=False,
    )
    recovery_answer = forms.CharField(
        label='New security answer',
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}, render_value=False),
        help_text='Leave blank to keep the current answer. Existing answers are never displayed.',
    )

    class Meta:
        model = UserProfile
        fields = ('recovery_question',)

    def clean(self):
        cleaned = super().clean()
        question = cleaned.get('recovery_question') or ''
        answer = ' '.join((cleaned.get('recovery_answer') or '').split()).casefold()
        current_hash = self.instance.recovery_answer_hash
        current_question = self.instance.recovery_question

        if answer:
            if not question:
                self.add_error('recovery_question', 'Choose a security question for the new answer.')
            elif len(answer) < 2:
                self.add_error('recovery_answer', 'Enter an answer of at least 2 characters.')
        elif current_hash:
            if question != current_question:
                self.add_error('recovery_answer', 'Enter a new answer when changing the security question.')
            cleaned['recovery_question'] = current_question
        elif question:
            self.add_error('recovery_answer', 'Enter an answer for the selected security question.')

        cleaned['normalized_recovery_answer'] = answer
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        answer = self.cleaned_data.get('normalized_recovery_answer')
        if answer:
            profile.recovery_answer_hash = make_password(answer)
        if commit:
            profile.save()
            self.save_m2m()
        return profile


class UserSecurityProfileInline(admin.StackedInline):
    model = UserProfile
    form = UserSecurityProfileForm
    fields = ('recovery_question', 'recovery_answer')
    extra = 1
    max_num = 1
    can_delete = False
    verbose_name = 'Security question and answer'
    verbose_name_plural = 'Password recovery security details'

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_authenticated and request.user.is_superuser)

    def has_add_permission(self, request, obj=None):
        return bool(request.user.is_authenticated and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_authenticated and request.user.is_superuser)


class ManagedUserAdmin(DjangoUserAdmin):
    inlines = (UserSecurityProfileInline,)
    list_display = ('username', 'first_name', 'last_name', 'registered_mobile', 'security_details_configured', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'id', 'userprofile__mobile_number')
    list_select_related = ('userprofile',)

    def user_change_password(self, request, id, form_url=''):
        # Django's default UserAdmin grants this view to anyone with change_user.
        # Password resets are intentionally reserved for Django superusers;
        # profile role labels do not grant this capability.
        if not request.user.is_authenticated or not request.user.is_superuser:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().user_change_password(request, id, form_url)

    @admin.display(description='Registered mobile', ordering='userprofile__mobile_number')
    def registered_mobile(self, obj):
        try:
            return obj.userprofile.mobile_number or '—'
        except UserProfile.DoesNotExist:
            return '—'

    @admin.display(boolean=True, description='Security details configured')
    def security_details_configured(self, obj):
        try:
            profile = obj.userprofile
        except UserProfile.DoesNotExist:
            return False
        return bool(profile.recovery_question and profile.recovery_answer_hash)


# Keep normal User administration behavior for existing staff while restricting
# the security-profile inline itself to authenticated Django superusers.
admin.site.unregister(User)
admin.site.register(User, ManagedUserAdmin)


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
    # Security recovery data is editable only through the superuser-only
    # inline on Django's User admin.
    exclude = ('recovery_question', 'recovery_answer_hash', 'recovery_failed_attempts', 'recovery_locked_until')


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
    list_display = ('customer_name', 'mobile_number', 'model_name', 'branch', 'branch_name', 'payment_mode', 'created_at')
    search_fields = ('customer_name', 'mobile_number', 'model_name')
    list_filter = ('branch', 'branch_name', 'payment_mode', 'created_at')


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
