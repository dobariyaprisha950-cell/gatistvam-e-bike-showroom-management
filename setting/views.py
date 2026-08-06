import json
import re
from decimal import Decimal
from datetime import datetime
from .models import Settings
# Django Shortcuts & Decorators
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages

# Django DB Functions
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q, Count

# REST Framework Imports
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

# App Models (All models imported cleanly)
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany, BatteryCapacity,
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, Customer, ExpenseMaster, Expense, Notification, Settings, AuditLog,
    NotificationPreference, InvoiceSetting, PrinterSetting, SystemPreference, BackupHistory
)

# App Forms
from yakuza.forms import (
    SupplierForm, VehicleCompanyForm, 
    VehicleModelForm, VehicleColorForm,
    ExpenseForm, ExpenseMasterForm, PurchaseForm
)

# App Permissions & Serializers
from yakuza.permissions import IsSuperAdmin, IsBranchAdmin, IsBranchScoped
from yakuza.serializers import (
    BranchSerializer, UserProfileSerializer, SupplierSerializer,
    VehicleCompanySerializer, BatteryCapacitySerializer, VehicleColorSerializer,
    VehicleModelSerializer, PurchaseSerializer, StockSerializer,
    SalesSerializer, CustomerSerializer, ExpenseMasterSerializer,
    ExpenseSerializer, NotificationSerializer, SettingsSerializer,
    AuditLogSerializer, ProfitReportSerializer
)


# ==========================================
# REST FRAMEWORK VIEWSETS
# ==========================================

class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class VehicleCompanyViewSet(viewsets.ModelViewSet):
    queryset = VehicleCompany.objects.all()
    serializer_class = VehicleCompanySerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class BatteryCapacityViewSet(viewsets.ModelViewSet):
    queryset = BatteryCapacity.objects.all()
    serializer_class = BatteryCapacitySerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class VehicleColorViewSet(viewsets.ModelViewSet):
    queryset = VehicleColor.objects.all()
    serializer_class = VehicleColorSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class VehicleModelViewSet(viewsets.ModelViewSet):
    queryset = VehicleModel.objects.all()
    serializer_class = VehicleModelSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class PurchaseViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin, IsBranchScoped]

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'userprofile', None)
        if profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN:
            return Purchase.objects.all()
        if profile and profile.branch:
            return Purchase.objects.filter(branch=profile.branch)
        return Purchase.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        profile = getattr(user, 'userprofile', None)
        branch = profile.branch if (profile and profile.role != UserProfile.RoleChoices.SUPER_ADMIN) else serializer.validated_data.get('branch')
        serializer.save(created_by=user, branch=branch)


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchScoped]

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'userprofile', None)
        queryset = Stock.objects.all()

        if profile and profile.role != UserProfile.RoleChoices.SUPER_ADMIN:
            queryset = queryset.filter(branch=profile.branch)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(stock_status=status_param)

        return queryset


class SalesViewSet(viewsets.ModelViewSet):
    serializer_class = SalesSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchScoped]

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'userprofile', None)
        if profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN:
            return Sales.objects.all()
        if profile and profile.branch:
            return Sales.objects.filter(stock__branch=profile.branch)
        return Sales.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class ExpenseMasterViewSet(viewsets.ModelViewSet):
    queryset = ExpenseMaster.objects.all()
    serializer_class = ExpenseMasterSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin, IsBranchScoped]

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'userprofile', None)
        if profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN:
            return Expense.objects.all()
        if profile and profile.branch:
            return Expense.objects.filter(branch=profile.branch)
        return Expense.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        profile = getattr(user, 'userprofile', None)
        branch = profile.branch if (profile and profile.role != UserProfile.RoleChoices.SUPER_ADMIN) else serializer.validated_data.get('branch')
        serializer.save(created_by=user, branch=branch)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchScoped]

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'userprofile', None)
        if profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN:
            return Notification.objects.all()
        if profile and profile.branch:
            return Notification.objects.filter(Q(branch=profile.branch) | Q(branch__isnull=True))
        return Notification.objects.none()

    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'notification marked as read'})


class SettingsViewSet(viewsets.ModelViewSet):
    queryset = Settings.objects.all()
    serializer_class = SettingsSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get_object(self):
        return Settings.load()


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]


class ProfitReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]

    def get(self, request):
        user = request.user
        profile = getattr(user, 'userprofile', None)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        branch_id = request.query_params.get('branch_id')

        sales_qs = Sales.objects.all()

        if profile and profile.role != UserProfile.RoleChoices.SUPER_ADMIN:
            sales_qs = sales_qs.filter(stock__branch=profile.branch)
        elif branch_id:
            sales_qs = sales_qs.filter(stock__branch_id=branch_id)

        if start_date:
            sales_qs = sales_qs.filter(invoice_date__gte=start_date)
        if end_date:
            sales_qs = sales_qs.filter(invoice_date__lte=end_date)

        total_sales = sales_qs.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        total_purchase_cost = sales_qs.aggregate(cost=Sum('stock__purchase_price'))['cost'] or Decimal('0.00')
        gross_profit = total_sales - total_purchase_cost

        expenses_qs = Expense.objects.all()
        if profile and profile.role != UserProfile.RoleChoices.SUPER_ADMIN:
            expenses_qs = expenses_qs.filter(branch=profile.branch)
        elif branch_id:
            expenses_qs = expenses_qs.filter(branch_id=branch_id)

        if start_date:
            expenses_qs = expenses_qs.filter(expense_date__gte=start_date)
        if end_date:
            expenses_qs = expenses_qs.filter(expense_date__lte=end_date)

        total_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        net_profit = gross_profit - total_expenses

        report_data = {
            'total_sales': total_sales,
            'total_purchase_cost': total_purchase_cost,
            'gross_profit': gross_profit,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'units_sold': sales_qs.count()
        }

        serializer = ProfitReportSerializer(report_data)
        return Response(serializer.data)


# ==========================================
# AUTH & DASHBOARD VIEWS
# ==========================================

def login(request):
    if request.user.is_authenticated:
        return redirect('yakuza:dashboard')

    if request.method == 'POST':
        u_name = request.POST.get('username')
        p_word = request.POST.get('password')

        user = authenticate(request, username=u_name, password=p_word)

        if user is not None:
            auth_login(request, user)
            next_url = request.GET.get('next') or 'yakuza:dashboard'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password!")
            return render(request, 'yakuza/login.html', {'error': 'Invalid Username or Password'})

    return render(request, 'yakuza/login.html')


def logout_view(request):
    logout(request)
    return redirect('yakuza:login')


def dashboard(request):
    total_vehicles = Stock.objects.count()

    sales_aggregate = Sales.objects.aggregate(total=Sum('grand_total')) if hasattr(Sales, 'grand_total') else Sales.objects.aggregate(total=Sum('total_price'))
    total_sales = sales_aggregate.get('total') or Decimal('0.00')

    total_purchases = Decimal('0.00')
    try:
        if hasattr(PurchaseItem, 'total_price'):
            purchases_aggregate = PurchaseItem.objects.aggregate(total=Sum('total_price'))
            total_purchases = purchases_aggregate.get('total') or Decimal('0.00')
        elif hasattr(PurchaseItem, 'unit_price') and hasattr(PurchaseItem, 'quantity'):
            purchases_aggregate = PurchaseItem.objects.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F('unit_price') * F('quantity'),
                        output_field=DecimalField()
                    )
                )
            )
            total_purchases = purchases_aggregate.get('total') or Decimal('0.00')
    except Exception:
        total_purchases = Decimal('0.00')

    total_profit = total_sales - total_purchases
    profit_margin = round((total_profit / total_sales * 100), 1) if total_sales > 0 else 0

    available_stock = Stock.objects.filter(status='AVAILABLE').count() if hasattr(Stock, 'status') else total_vehicles
    sold_stock = Stock.objects.filter(status='SOLD').count() if hasattr(Stock, 'status') else 0
    reserved_stock = Stock.objects.filter(status='RESERVED').count() if hasattr(Stock, 'status') else 0
    other_stock = max(0, total_vehicles - (available_stock + sold_stock + reserved_stock))

    low_stock_items = Stock.objects.filter(quantity__lte=8)[:4] if hasattr(Stock, 'quantity') else []

    recent_sales = Sales.objects.order_by('-id')[:5]
    recent_purchases = Purchase.objects.order_by('-id')[:5]

    context = {
        'total_vehicles': total_vehicles,
        'total_sales': total_sales,
        'total_purchases': total_purchases,
        'total_profit': total_profit,
        'profit_margin': profit_margin,
        'available_stock': available_stock,
        'sold_stock': sold_stock,
        'reserved_stock': reserved_stock,
        'other_stock': other_stock,
        'low_stock_items': low_stock_items,
        'recent_sales': recent_sales,
        'recent_purchases': recent_purchases,
    }
    return render(request, 'yakuza/dashboard.html', context)


def live_stock(request):
    stock_items = Stock.objects.select_related(
        'model', 'color', 'branch', 'company'
    ).filter(stock_status__in=['AVAILABLE', 'RESERVED'])

    branches = Branch.objects.filter(is_active=True)

    context = {
        'stock_items': stock_items,
        'branches': branches,
    }
    return render(request, 'yakuza/live_stock.html')


# ==========================================
# PURCHASE & DYNAMIC AJAX ENTRY VIEWS
# ==========================================

def purchase_page_view(request):
    suppliers = Supplier.objects.all()
    companies = VehicleCompany.objects.all()
    models = VehicleModel.objects.all()
    colors = VehicleColor.objects.all()
    
    # Auto Generated Purchase ID String
    purchase_number = f"PUR-{Purchase.objects.count() + 1:06d}"

    context = {
        'suppliers': suppliers,
        'companies': companies,
        'models': models,
        'colors': colors,
        'purchase_number': purchase_number,
    }
    return render(request, 'yakuza/purchase.html', context)


# 1. AJAX: Add Supplier
@require_POST
def add_supplier_ajax(request):
    name = request.POST.get('supplier_name')
    contact = request.POST.get('contact_person', '')
    phone = request.POST.get('phone', '')
    
    if name:
        supplier = Supplier.objects.create(
            supplier_name=name,
            contact_person=contact,
            phone=phone
        )
        return JsonResponse({
            'success': True,
            'id': supplier.id,
            'name': supplier.supplier_name,
            'contact': supplier.contact_person or '',
            'phone': supplier.phone or ''
        })
    return JsonResponse({'success': False, 'error': 'Supplier Name is required.'}, status=400)


# 2. AJAX: Add Company
@require_POST
def add_company_ajax(request):
    name = request.POST.get('company_name')
    if name:
        company = VehicleCompany.objects.create(company_name=name)
        return JsonResponse({'success': True, 'id': company.id, 'name': company.company_name})
    return JsonResponse({'success': False, 'error': 'Company Name is required.'}, status=400)


# 3. AJAX: Add Model
@require_POST
def add_model_ajax(request):
    company_id = request.POST.get('company_id')
    name = request.POST.get('model_name')
    if company_id and name:
        model = VehicleModel.objects.create(company_id=company_id, model_name=name)
        return JsonResponse({'success': True, 'id': model.id, 'name': model.model_name, 'company_id': model.company_id})
    return JsonResponse({'success': False, 'error': 'Company and Model Name are required.'}, status=400)


# 4. AJAX: Add Color
@require_POST
def add_color_ajax(request):
    name = request.POST.get('color_name')
    hex_code = request.POST.get('color_hex', '#000000')
    if name:
        color = VehicleColor.objects.create(color_name=name, color_hex=hex_code)
        return JsonResponse({'success': True, 'id': color.id, 'name': color.color_name, 'hex': color.color_hex})
    return JsonResponse({'success': False, 'error': 'Color Name is required.'}, status=400)


def purchase_history(request):
    purchases_qs = Purchase.objects.select_related('supplier', 'branch').all().order_by('-purchase_date')

    search_query = request.GET.get('search', '').strip()
    if search_query:
        purchases_qs = purchases_qs.filter(
            Q(purchase_number__icontains=search_query) |
            Q(invoice_number__icontains=search_query) |
            Q(supplier__supplier_name__icontains=search_query)
        )

    supplier_id = request.GET.get('supplier', '').strip()
    if supplier_id:
        purchases_qs = purchases_qs.filter(supplier_id=supplier_id)

    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()
    if from_date:
        purchases_qs = purchases_qs.filter(purchase_date__gte=from_date)
    if to_date:
        purchases_qs = purchases_qs.filter(purchase_date__lte=to_date)

    context = {
        'purchases': purchases_qs,
    }
    return render(request, 'yakuza/purchase_history.html', context)


# ==========================================
# SALES, CUSTOMER, EXPENSES & REPORTS
# ==========================================

def sales(request):
    return render(request, 'yakuza/sales.html')


def customer(request):
    customers = Customer.objects.all().order_by('-created_at')
    return render(request, 'yakuza/customer.html', {'customers': customers})


def expenses(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            if request.user.is_authenticated:
                expense.created_by = request.user
            else:
                from django.contrib.auth.models import User
                expense.created_by = User.objects.first()
            
            expense.save()
            messages.success(request, "Expense added successfully!")
            return redirect('expenses')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ExpenseForm()

    expenses_list = Expense.objects.all().order_by('-expense_date', '-id')
    expense_masters = ExpenseMaster.objects.filter(is_active=True)

    context = {
        'form': form,
        'expenses': expenses_list,
        'expense_masters': expense_masters,
    }
    return render(request, 'yakuza/expenses.html', context)


def edit_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense updated successfully!")
            return redirect('expenses')
    return redirect('expenses')


def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, "Expense deleted successfully!")
    return redirect('expenses')


def notifications(request):
    return render(request, 'yakuza/notifications.html')


def register(request):
    return render(request, 'yakuza/register.html')


def reports(request):
    return render(request, 'yakuza/reports.html')


# ==========================================
# SETTINGS & PROFILE MANAGEMENT VIEWS
# ==========================================
@login_required
def settings(request):
    user = request.user
    user_profile = getattr(user, 'userprofile', None)
    current_branch = user_profile.branch if user_profile else None
    
    # 1. Notification Preference (User-wise)
    notification_pref, _ = NotificationPreference.objects.get_or_create(user=user)
    
    # 2. Invoice Setting (Branch-wise)
    if current_branch:
        invoice_setting, _ = InvoiceSetting.objects.get_or_create(branch=current_branch)
    else:
        invoice_setting = InvoiceSetting.objects.first()
        if not invoice_setting:
            invoice_setting = InvoiceSetting.objects.create()

    # 3. Printer Setting (Branch-wise)
    if current_branch:
        printer_setting, _ = PrinterSetting.objects.get_or_create(branch=current_branch)
    else:
        printer_setting = PrinterSetting.objects.first()
        if not printer_setting:
            printer_setting = PrinterSetting.objects.create()

    # 4. System Preference & Settings
    system_preference, _ = SystemPreference.objects.get_or_create(id=1)
    
    settings_obj = Settings.objects.first()
    if not settings_obj:
        settings_obj = Settings.objects.create()

    # 5. Branches & Backup History
    all_branches = Branch.objects.all() if (user_profile and user_profile.role == UserProfile.RoleChoices.SUPER_ADMIN) or user.is_superuser else None
    current_branch_backup = BackupHistory.objects.filter(branch=current_branch).last() if current_branch else None
    backup_history = BackupHistory.objects.all().order_by('-created_at')[:10]

    # બધો જ ડેટા એક જ Context માં ભેગો મોકલવો
    context = {
        'settings': settings_obj,
        'notification_pref': notification_pref,
        'invoice_setting': invoice_setting,
        'printer_setting': printer_setting,
        'system_preference': system_preference,
        'all_branches': all_branches,
        'current_branch_backup': current_branch_backup,
        'backup_history': backup_history,
    }
    
    return render(request, 'yakuza/settings.html', context)

@login_required
def update_profile(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()

        profile = getattr(user, 'userprofile', None)
        if profile:
            profile.mobile_number = request.POST.get('mobile_number', profile.mobile_number)
            profile.save()

        messages.success(request, "Your Profile is Updated!")
    return redirect('yakuza:settings')


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your Password Changed Successfully!')
        else:
            messages.error(request, 'Please Enter valid Password.')
    return redirect('yakuza:settings')


@login_required
def update_notification_preferences(request):
    if request.method == 'POST':
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        pref.notify_sales = 'notify_sales' in request.POST
        pref.notify_purchase = 'notify_purchase' in request.POST
        pref.notify_low_stock = 'notify_low_stock' in request.POST
        pref.notify_expenses = 'notify_expenses' in request.POST
        pref.notify_backup = 'notify_backup' in request.POST
        pref.save()
        messages.success(request, "Notifications Settings Saved!")
    return redirect('yakuza:settings')


@login_required
def update_invoice_settings(request):
    if request.method == 'POST':
        inv, _ = InvoiceSetting.objects.get_or_create(user=request.user)
        inv.prefix = request.POST.get('invoice_prefix', inv.prefix)
        inv.starting_number = request.POST.get('starting_number', inv.starting_number)
        inv.gst_number = request.POST.get('gst_number', inv.gst_number)
        inv.footer_text = request.POST.get('footer_text', inv.footer_text)
        inv.terms_and_conditions = request.POST.get('terms_and_conditions', inv.terms_and_conditions)
        inv.save()
        messages.success(request, "Invoice Settings Saved!")
    return redirect('yakuza:settings')


@login_required
def update_printer_settings(request):
    if request.method == 'POST':
        printer, _ = PrinterSetting.objects.get_or_create(user=request.user)
        printer.default_printer = request.POST.get('default_printer', printer.default_printer)
        printer.paper_size = request.POST.get('paper_size', printer.paper_size)
        printer.default_copies = request.POST.get('default_copies', printer.default_copies)
        printer.print_preview = 'print_preview' in request.POST
        printer.save()
        messages.success(request, "Printer Settings Saved!")
    return redirect('yakuza:settings')


@login_required
def update_system_preferences(request):
    if request.method == 'POST' and request.user.is_superuser:
        pref, _ = SystemPreference.objects.get_or_create(id=1)
        pref.currency_symbol = request.POST.get('currency_symbol', pref.currency_symbol)
        pref.timezone = request.POST.get('timezone', pref.timezone)
        pref.low_stock_threshold = request.POST.get('low_stock_threshold', pref.low_stock_threshold)
        pref.save()
        messages.success(request, "System Preferences Saved!")
    return redirect('yakuza:settings')


@login_required
def generate_backup(request):
    if request.method == 'POST':
        user_profile = getattr(request.user, 'userprofile', None)
        branch = user_profile.branch if user_profile else None
        BackupHistory.objects.create(branch=branch, file_path="backups/manual_backup.sql")
        messages.success(request, "Backup Created Successfully !")
    return redirect('yakuza:settings')

