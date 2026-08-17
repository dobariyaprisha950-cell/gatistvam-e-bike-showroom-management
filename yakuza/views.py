import json
import uuid
import csv
import re
import os
import ast

from datetime import date
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from decimal import Decimal,InvalidOperation
from datetime import time, datetime, timedelta
from urllib.parse import quote
from django.http import HttpResponseForbidden
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings as django_settings
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q, Count
from django.db.models.functions import TruncMonth, TruncDay

# REST Framework Imports
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

# App Specific Imports
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany,
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, Customer, ExpenseMaster, Expense, Notification, Settings, AuditLog,
    InvoiceSetting, BackupHistory
)

from yakuza.permissions import IsSuperAdmin, IsBranchAdmin, IsBranchScoped

from yakuza.serializers import (
    BranchSerializer, UserProfileSerializer, SupplierSerializer,
    VehicleCompanySerializer, VehicleColorSerializer,
    VehicleModelSerializer, PurchaseSerializer, StockSerializer,
    SalesSerializer, CustomerSerializer, ExpenseMasterSerializer,
    ExpenseSerializer, NotificationSerializer, SettingsSerializer,
    AuditLogSerializer, ProfitReportSerializer
)


def format_indian_currency(amount):
    """Formats a numeric amount into Indian Currency display format without decimals."""
    if amount is None:
        return "0"
    val = int(round(Decimal(str(amount))))
    s = str(abs(val))
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        other = s[:-3]
        res = ""
        while len(other) > 2:
            res = "," + other[-2:] + res
            other = other[:-2]
        formatted = other + res + "," + last3
    return f"-{formatted}" if val < 0 else formatted


def format_display_number(num):
    """Formats plain numbers with Indian standard separators."""
    if num is None:
        return "0"
    return format_indian_currency(num)


def get_user_branch_context(request):
    """
    Returns the specific Branch object the user should be restricted to.
    Returns None if the user is a Super Admin viewing 'All Branches'.
    """
    if not request.user.is_authenticated:
        return None
        
    profile = getattr(request.user, 'userprofile', None)
    is_super = (profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN) or request.user.is_superuser
    
    if is_super:
        selected_id = request.session.get('selected_branch_id', 'all')
        if selected_id == 'all' or not selected_id:
            return None
        try:
            return Branch.objects.get(id=int(selected_id), is_active=True)
        except (ValueError, Branch.DoesNotExist):
            return None
            
    return profile.branch if profile else None


@login_required
@require_POST
def switch_branch(request):
    """View to switch current active branch for Super Admin users"""
    profile = getattr(request.user, 'userprofile', None)
    is_super = (profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN) or request.user.is_superuser
    
    if is_super:
        branch_id = request.POST.get('branch_id', 'all')
        request.session['selected_branch_id'] = branch_id
    
    return redirect(request.META.get('HTTP_REFERER', 'yakuza:dashboard'))


# ==========================================
# AUDIT LOG HELPER FUNCTION
# ==========================================
def log_audit(user, module, action, details="", old_val="", new_val="", request=None):
    """
    Creates an AuditLog entry. Branch is resolved via the existing secure
    get_user_branch_context() when a request is available (this reflects the
    branch the action actually happened in, e.g. a Branch Admin's own branch,
    or a Super Admin's currently selected branch). Falls back to the user's
    assigned branch if no request context is available (e.g. background jobs).
    """
    ip_addr = None
    branch_obj = None

    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_addr = x_forwarded_for.split(',')[0]
        else:
            ip_addr = request.META.get('REMOTE_ADDR')
        branch_obj = get_user_branch_context(request)

    if branch_obj is None:
        profile = getattr(user, 'userprofile', None) if user and user.is_authenticated else None
        branch_obj = profile.branch if profile else None

    old_payload = old_val if old_val not in (None, "") else {}
    new_payload = new_val if new_val not in (None, "") else {}
    if details:
        if not isinstance(new_payload, dict):
            new_payload = {'value': new_payload}
        new_payload = {**new_payload, '__audit_description': details}

    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        branch=branch_obj,
        module=module,
        action=action,
        old_value=old_payload,
        new_value=new_payload,
        ip_address=ip_addr
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
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        return Supplier.objects.filter(branch=branch) if branch else Supplier.objects.none()

    def perform_create(self, serializer):
        branch = get_user_branch_context(self.request)
        if not branch:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Select a specific branch before creating supplier data.')
        serializer.save(branch=branch)


class VehicleCompanyViewSet(viewsets.ModelViewSet):
    queryset = VehicleCompany.objects.all()
    serializer_class = VehicleCompanySerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class VehicleColorViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleColorSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        return VehicleColor.objects.filter(branch=branch) if branch else VehicleColor.objects.none()

    def perform_create(self, serializer):
        branch = get_user_branch_context(self.request)
        if not branch:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Select a specific branch before creating color data.')
        serializer.save(branch=branch)


class VehicleModelViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleModelSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        return VehicleModel.objects.filter(branch=branch) if branch else VehicleModel.objects.none()

    def perform_create(self, serializer):
        branch = get_user_branch_context(self.request)
        if not branch:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Select a specific branch before creating model data.')
        serializer.save(branch=branch)


class PurchaseViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin, IsBranchScoped]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        if branch is None:
            return Purchase.objects.all()
        return Purchase.objects.filter(branch=branch)

    def perform_create(self, serializer):
        user = self.request.user
        branch = get_user_branch_context(self.request)
        if not branch:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Select a specific branch before creating a purchase.')

        supplier = serializer.validated_data.get('supplier')
        items = serializer.validated_data.get('items', [])
        if not supplier or supplier.branch_id != branch.id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Selected supplier is not available in the current branch.')
        for item in items:
            if item['model'].branch_id != branch.id or item['color'].branch_id != branch.id:
                from rest_framework.exceptions import ValidationError
                raise ValidationError('Selected model or color is not available in the current branch.')
            
        invoice_date = self.request.data.get('invoice_date')
        save_kwargs = {'created_by': user, 'branch': branch}
        
        if invoice_date and not serializer.validated_data.get('purchase_date'):
            save_kwargs['purchase_date'] = invoice_date

        serializer.save(**save_kwargs)


class StockViewSet(viewsets.ModelViewSet):
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchScoped]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        queryset = Stock.objects.select_related('company', 'model', 'color', 'branch').all()

        if branch is not None:
            queryset = queryset.filter(branch=branch)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(stock_status=status_param)

        return queryset

    def perform_update(self, serializer):
        branch = get_user_branch_context(self.request)
        instance = serializer.instance
        if branch is not None and instance.branch != branch:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to modify stock from another branch.")
        serializer.save()


class SalesViewSet(viewsets.ModelViewSet):
    serializer_class = SalesSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchScoped]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        if branch is None:
            return Sales.objects.all()
        return Sales.objects.filter(stock__branch=branch)

    def perform_create(self, serializer):
        branch = get_user_branch_context(self.request)
        if not branch:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Select a specific branch before creating a sale.')
        with transaction.atomic():
            stock_id = serializer.validated_data['stock'].id
            stock = Stock.objects.select_for_update().get(id=stock_id)
            if stock.branch_id != branch.id or stock.stock_status != Stock.StockStatus.AVAILABLE:
                from rest_framework.exceptions import ValidationError
                raise ValidationError('Vehicle is not available in current branch stock.')
            serializer.validated_data['stock'] = stock
            serializer.save(created_by=self.request.user)


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchScoped]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        if branch is None:
            return Customer.objects.all()
        return Customer.objects.filter(branch_name=branch.branch_name)
    

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        qs = AuditLog.objects.all()
        if branch is not None:
            qs = qs.filter(branch=branch)
        return qs


class ExpenseMasterViewSet(viewsets.ModelViewSet):
    queryset = ExpenseMaster.objects.all()
    serializer_class = ExpenseMasterSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin, IsBranchScoped]

    def get_queryset(self):
        branch = get_user_branch_context(self.request)
        if branch is None:
            return Expense.objects.all()
        return Expense.objects.filter(branch=branch)

    def perform_create(self, serializer):
        user = self.request.user
        branch = get_user_branch_context(self.request) or serializer.validated_data.get('branch')
        if not branch:
            branch = Branch.objects.first()
        serializer.save(created_by=user, branch=branch)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Notification.objects.all()
            
        if hasattr(user, 'userprofile') and user.userprofile.branch:
            return Notification.objects.filter(
                Q(branch=user.userprofile.branch) | Q(branch__isnull=True)
            )
            
        return Notification.objects.all()
    
    @action(detail=True, methods=['post', 'get'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'notification marked as read'}, status=status.HTTP_200_OK)


class SettingsViewSet(viewsets.ModelViewSet):
    queryset = Settings.objects.all()
    serializer_class = SettingsSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get_object(self):
        return Settings.load()


class ProfitReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBranchAdmin]

    def get(self, request):
        branch = get_user_branch_context(request)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        branch_id = request.query_params.get('branch_id')

        sales_qs = Sales.objects.all()

        if branch is not None:
            sales_qs = sales_qs.filter(stock__branch=branch)
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
        if branch is not None:
            expenses_qs = expenses_qs.filter(branch=branch)
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


@csrf_protect
@transaction.atomic
def register(request):
    if request.user.is_authenticated:
        return redirect('yakuza:dashboard')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            branch_id = data.get('branch_id', '').strip()
            branch_name = data.get('branch_name', '').strip()
            owner_name = data.get('owner_name', '').strip()
            mobile_number = data.get('mobile_number', '').strip()
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            confirm_password = data.get('confirm_password', '').strip()
            branch_address = data.get('branch_address', '').strip()

            if not username or not password:
                return JsonResponse({'success': False, 'message': 'Username & Password are required.'}, status=400)

            if password != confirm_password:
                return JsonResponse({'success': False, 'message': 'Passwords do not match.'}, status=400)

            if User.objects.filter(username=username).exists():
                return JsonResponse({'success': False, 'message': 'Username is already taken.'}, status=400)

            selected_branch = None
            if branch_id:
                selected_branch = Branch.objects.filter(id=branch_id).first()
                if not selected_branch:
                    return JsonResponse({'success': False, 'message': 'Selected branch not found.'}, status=400)
            elif branch_name:
                if Branch.objects.filter(branch_name__iexact=branch_name).exists():
                    selected_branch = Branch.objects.filter(branch_name__iexact=branch_name).first()
                else:
                    branch_code = f"BR-{branch_name[:3].upper()}-{Branch.objects.count() + 1:03d}"
                    selected_branch = Branch.objects.create(
                        branch_name=branch_name,
                        owner_name=owner_name,
                        branch_code=branch_code,
                        address=branch_address,
                        phone=mobile_number
                    )
            else:
                return JsonResponse({'success': False, 'message': 'Please select or add a branch.'}, status=400)

            first_name = owner_name.split()[0] if owner_name else username
            last_name = " ".join(owner_name.split()[1:]) if len(owner_name.split()) > 1 else ""

            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            UserProfile.objects.create(
                user=user,
                branch=selected_branch,
                role=UserProfile.RoleChoices.BRANCH_ADMIN,
                mobile_number=mobile_number,
                is_active=True
            )

            return JsonResponse({
                'success': True,
                'message': 'Account created successfully!',
                'redirect_url': reverse('yakuza:login')
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    branches = Branch.objects.filter(is_active=True)
    return render(request, 'yakuza/register.html', {'branches': branches})


@login_required
def dashboard(request):
    branch = get_user_branch_context(request)

    stock_qs = Stock.objects.all()
    if branch is not None:
        stock_qs = stock_qs.filter(branch=branch)

    available_stock_qs = stock_qs.filter(stock_status=Stock.StockStatus.AVAILABLE)
    total_vehicles_count = available_stock_qs.count()

    sales_qs = Sales.objects.all()
    if branch is not None:
        sales_qs = sales_qs.filter(stock__branch=branch)

    total_sales_val = sales_qs.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')

    purchase_item_qs = PurchaseItem.objects.all()
    if branch is not None:
        purchase_item_qs = purchase_item_qs.filter(purchase__branch=branch)

    total_purchases_val = purchase_item_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    sold_stock_qs = stock_qs.filter(stock_status=Stock.StockStatus.SOLD)
    sold_cost = sold_stock_qs.aggregate(total=Sum('purchase_price'))['total'] or Decimal('0.00')
    total_profit_val = total_sales_val - sold_cost

    if total_sales_val > Decimal('0.00'):
        profit_margin_val = round((total_profit_val / total_sales_val) * Decimal('100.00'), 1)
        profit_margin_formatted = f"{int(profit_margin_val)}%" if profit_margin_val == int(profit_margin_val) else f"{profit_margin_val:.1f}%"
    else:
        profit_margin_formatted = "0%"

    total_vehicles_formatted = format_display_number(total_vehicles_count)
    total_sales_formatted = format_indian_currency(total_sales_val)
    total_purchases_formatted = format_indian_currency(total_purchases_val)
    total_profit_formatted = format_indian_currency(total_profit_val)

    now = timezone.now()
    sales_this_month = (
        sales_qs.filter(invoice_date__year=now.year, invoice_date__month=now.month)
        .annotate(day=TruncDay('invoice_date'))
        .values('day')
        .annotate(total=Sum('grand_total'))
        .order_by('day')
    )

    chart_labels, chart_data = [], []
    if sales_this_month.exists():
        for entry in sales_this_month:
            if entry['day']:
                chart_labels.append(entry['day'].strftime('%d %b'))
                chart_data.append(float(entry['total'] or 0))
    else:
        sales_recent_chart = sales_qs.order_by('invoice_date')[:12]
        for s in sales_recent_chart:
            chart_labels.append(s.invoice_date.strftime('%d %b'))
            chart_data.append(float(s.grand_total))
    
    stock_group_qs = (
        available_stock_qs.values('model__model_name', 'color__color_name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    stock_model_labels, stock_model_counts = [], []
    for item in stock_group_qs:
        m_name = item['model__model_name'] or 'Unknown Model'
        c_name = item['color__color_name'] or 'N/A'
        stock_model_labels.append(f"{m_name} ({c_name})")
        stock_model_counts.append(item['count'])

    sys_settings = Settings.load()
    threshold = getattr(sys_settings, 'low_stock_threshold', 2)

    low_stock_qs = (
        available_stock_qs.values('model__model_name', 'color__color_name')
        .annotate(quantity=Count('id'))
        .filter(quantity__lte=threshold)
        .order_by('quantity')
    )

    low_stock_items = [
        {
            'model_name': item['model__model_name'] or 'Vehicle',
            'color_name': item['color__color_name'] or 'N/A',
            'quantity': item['quantity']
        }
        for item in low_stock_qs
    ]

    recent_sales = sales_qs.select_related('stock', 'stock__model').order_by('-id')[:5]
    purchases_qs = Purchase.objects.all()
    if branch is not None:
        purchases_qs = purchases_qs.filter(branch=branch)
        
    recent_purchases = purchases_qs.select_related('supplier').order_by('-id')[:5]
    for pur in recent_purchases:
        pur.computed_total = pur.items.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    # --- SOTRE & EDIT SALE DROPDOWN LOGIC ---
    edit_id = request.GET.get('edit_id')
    edit_sale = Sales.objects.filter(id=edit_id).first() if edit_id else None

    available_model_ids = set(available_stock_qs.values_list('model_id', flat=True).distinct())
    available_color_ids = set(available_stock_qs.values_list('color_id', flat=True).distinct())

    if edit_sale and edit_sale.stock:
        if edit_sale.stock.model_id:
            available_model_ids.add(edit_sale.stock.model_id)
        if edit_sale.stock.color_id:
            available_color_ids.add(edit_sale.stock.color_id)

    # See sales() view for why we do not re-filter by VehicleModel.branch /
    # VehicleColor.branch here: available_model_ids / available_color_ids are
    # already derived from Stock rows scoped to the current branch (the
    # reliable source of branch truth), and re-filtering by the master
    # record's own (possibly legacy-NULL) branch field would incorrectly
    # drop valid entries.
    models_qs = VehicleModel.objects.filter(id__in=available_model_ids, is_active=True)
    colors_qs = VehicleColor.objects.filter(id__in=available_color_ids, is_active=True)

    context = {
        'total_vehicles': total_vehicles_formatted,
        'total_sales': total_sales_formatted,
        'total_purchases': total_purchases_formatted,
        'total_profit': total_profit_formatted,
        'profit_margin': profit_margin_formatted,
        'sales_chart_labels': json.dumps(chart_labels),
        'sales_chart_data': json.dumps(chart_data),
        'stock_model_labels': json.dumps(stock_model_labels),
        'stock_model_counts': json.dumps(stock_model_counts),
        'total_available_raw': total_vehicles_count,
        'low_stock_items': low_stock_items,
        'recent_sales': recent_sales,
        'recent_purchases': recent_purchases,
        # Added missing context keys:
        'edit_sale': edit_sale,
        'models': models_qs,
        'colors': colors_qs,
    }
    
    return render(request, 'yakuza/dashboard.html', context)

@login_required
def get_sales_chart_data(request):
    filter_type = request.GET.get('filter', 'this_month')
    branch = get_user_branch_context(request)
    
    sales_qs = Sales.objects.all()
    if branch is not None:
        sales_qs = sales_qs.filter(stock__branch=branch)
        
    labels, data = [], []
    now = timezone.now()

    if filter_type == 'this_month':
        sales_grouped = (
            sales_qs.filter(invoice_date__year=now.year, invoice_date__month=now.month)
            .annotate(day=TruncDay('invoice_date'))
            .values('day')
            .annotate(total=Sum('grand_total'))
            .order_by('day')
        )
        for entry in sales_grouped:
            if entry['day']:
                labels.append(entry['day'].strftime('%d %b'))
                data.append(float(entry['total'] or 0))

    elif filter_type == 'this_year':
        sales_grouped = (
            sales_qs.filter(invoice_date__year=now.year)
            .annotate(month=TruncMonth('invoice_date'))
            .values('month')
            .annotate(total=Sum('grand_total'))
            .order_by('month')
        )
        for entry in sales_grouped:
            if entry['month']:
                labels.append(entry['month'].strftime('%b'))
                data.append(float(entry['total'] or 0))

    else:
        sales_grouped = (
            sales_qs.annotate(month=TruncMonth('invoice_date'))
            .values('month')
            .annotate(total=Sum('grand_total'))
            .order_by('month')
        )
        for entry in sales_grouped:
            if entry['month']:
                labels.append(entry['month'].strftime('%b %Y'))
                data.append(float(entry['total'] or 0))

    return JsonResponse({'labels': labels, 'data': data})


@login_required
def live_stock(request):
    branch = get_user_branch_context(request)

    stock_qs = Stock.objects.filter(
        stock_status=Stock.StockStatus.AVAILABLE
    ).select_related('model', 'color', 'company', 'model__company')

    if branch is not None:
        stock_qs = stock_qs.filter(branch=branch)

    grouped_dict = {}
    available_color_ids = set()

    for item in stock_qs:
        model_obj = item.model
        color_obj = item.color
        if not model_obj or not color_obj:
            continue

        available_color_ids.add(color_obj.id)
        key = (model_obj.id, color_obj.id)

        if key not in grouped_dict:
            price = item.selling_price if (item.selling_price and item.selling_price > Decimal('0.00')) else item.purchase_price
            if not price or price == Decimal('0.00'):
                price = model_obj.base_purchase_price or Decimal('0.00')

            comp_name = item.company.company_name if item.company else (model_obj.company.company_name if model_obj.company else '')

            grouped_dict[key] = {
                'model_id': model_obj.id,
                'model_name': model_obj.model_name,
                'company_name': comp_name,
                'color_id': color_obj.id,
                'color_name': color_obj.color_name,
                'quantity': 0,
                'price': price,
            }
        grouped_dict[key]['quantity'] += 1

    grouped_items = list(grouped_dict.values())
    colors = VehicleColor.objects.filter(id__in=available_color_ids).order_by('color_name')

    return render(request, 'yakuza/live_stock.html', {
        'grouped_items': grouped_items,
        'colors': colors,
    })


# ==========================================
# PURCHASE PAGE VIEWS & AJAX
# ==========================================
@login_required
def purchase_page_view(request):
    branch = get_user_branch_context(request)

    if request.method == 'POST':
        try:
            if not branch:
                return JsonResponse({'success': False, 'error': 'Select a specific branch before creating a purchase.'}, status=400)

            with transaction.atomic():
                supplier_id = request.POST.get('supplier') or request.POST.get('supplier_id')
                invoice_number = request.POST.get('invoice_number', '').strip()
                invoice_date = request.POST.get('invoice_date', '').strip()
                purchase_date = request.POST.get('purchase_date', '').strip() or invoice_date
                remarks = request.POST.get('remarks', '').strip()
                invoice_photo = request.FILES.get('invoice_photo')

                if not supplier_id or not invoice_number or not invoice_date:
                    return JsonResponse({'success': False, 'error': 'Supplier, Invoice number, and Invoice date are required.'}, status=400)

                try:
                    supplier = Supplier.objects.get(id=supplier_id, branch=branch, is_active=True)
                except Supplier.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Selected supplier is not available in the current branch.'}, status=400)

                purchase_number = f"PUR-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
                while Purchase.objects.filter(purchase_number=purchase_number).exists():
                    purchase_number = f"PUR-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

                purchase = Purchase.objects.create(
                    purchase_number=purchase_number,
                    purchase_date=purchase_date,
                    supplier=supplier,
                    branch=branch,
                    invoice_number=invoice_number,
                    invoice_date=invoice_date,
                    invoice_photo=invoice_photo,
                    remarks=remarks,
                    created_by=request.user
                )

                raw_items = request.POST.get('vehicle_items_json') or request.POST.get('vehicle_items') or request.POST.get('items') or '[]'
                vehicle_items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items

                if not vehicle_items or not isinstance(vehicle_items, list):
                    raise ValueError("At least one vehicle entry is required.")

                for item in vehicle_items:
                    model_id = item.get('model_id') or item.get('vehicle_model') or item.get('model')
                    if not model_id:
                        raise ValueError("Vehicle model is required for all entries.")

                    vehicle_model = VehicleModel.objects.select_related('company').get(id=model_id, branch=branch, is_active=True)
                    unit_price = Decimal(str(item.get('purchase_price') or item.get('unit_price') or item.get('price') or '0'))
                    if unit_price <= 0:
                        raise ValueError(f"Purchase price for model '{vehicle_model.model_name}' must be greater than zero.")

                    color_allocations = item.get('color_allocations') or item.get('colors') or []
                    if not color_allocations:
                        color_id = item.get('color_id') or item.get('color')
                        qty = int(item.get('quantity', 1))
                        if color_id:
                            color_allocations = [{'color_id': color_id, 'quantity': qty}]

                    if not color_allocations or not isinstance(color_allocations, list):
                        raise ValueError(f"Color allocation is missing for vehicle model '{vehicle_model.model_name}'.")

                    alloc_total_qty = 0
                    for alloc in color_allocations:
                        color_id = alloc.get('color_id') or alloc.get('color')
                        alloc_qty = int(alloc.get('quantity', 0))

                        if not color_id or alloc_qty <= 0:
                            continue

                        color_obj = VehicleColor.objects.get(id=color_id, branch=branch, is_active=True)
                        purchase_item = PurchaseItem.objects.create(
                            purchase=purchase,
                            company=vehicle_model.company,
                            model=vehicle_model,
                            color=color_obj,
                            quantity=alloc_qty,
                            purchase_price=unit_price
                        )

                        # Create the AVAILABLE Stock rows for this PurchaseItem
                        # directly, in the same transaction, so Stock creation
                        # is guaranteed to happen and is not dependent on a
                        # signal being connected. Stock is the single
                        # authoritative inventory source that both Live Stock
                        # and Sales read from.
                        Stock.objects.bulk_create([
                            Stock(
                                purchase_item=purchase_item,
                                branch=branch,
                                company=vehicle_model.company,
                                model=vehicle_model,
                                color=color_obj,
                                purchase_price=unit_price,
                                stock_status=Stock.StockStatus.AVAILABLE,
                                chassis_number=None,
                                battery_number=None,
                                motor_number=None,
                                controller_number=None,
                            )
                            for _ in range(alloc_qty)
                        ])

                        alloc_total_qty += alloc_qty

                    if alloc_total_qty <= 0:
                        raise ValueError(f"No valid color quantity allocated for model '{vehicle_model.model_name}'.")

                redirect_url = reverse('yakuza:purchase_history')
                return JsonResponse({'success': True, 'purchase_id': purchase.id, 'purchase_number': purchase.purchase_number, 'redirect_url': redirect_url})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    suppliers = Supplier.objects.filter(is_active=True, branch=branch) if branch else Supplier.objects.none()
    models = VehicleModel.objects.filter(is_active=True, branch=branch) if branch else VehicleModel.objects.none()
    colors = VehicleColor.objects.filter(is_active=True, branch=branch) if branch else VehicleColor.objects.none()

    return render(request, 'yakuza/purchase.html', {'suppliers': suppliers, 'models': models, 'colors': colors})

@login_required
@require_POST
def add_company_ajax(request):
    company_name = None
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            company_name = data.get('company_name') or data.get('name')
        except Exception:
            pass
    if not company_name:
        company_name = request.POST.get('company_name') or request.POST.get('name')
        
    if not company_name:
        return JsonResponse({'success': False, 'error': 'Company name is required.'}, status=400)
        
    company_name_clean = company_name.strip()
    if VehicleCompany.objects.filter(company_name__iexact=company_name_clean).exists():
        return JsonResponse({'success': False, 'error': 'Company already exists.'}, status=400)
        
    try:
        company = VehicleCompany.objects.create(company_name=company_name_clean, is_active=True)
        return JsonResponse({'success': True, 'id': company.id, 'name': company.company_name})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def add_supplier_ajax(request):
    branch = get_user_branch_context(request)
    if not branch:
        return JsonResponse({'success': False, 'error': 'Select a specific branch before adding a supplier.'}, status=400)
    supplier_name = None
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            supplier_name = data.get('supplier_name') or data.get('name')
        except Exception:
            pass
    
    if not supplier_name:
        supplier_name = request.POST.get('supplier_name') or request.POST.get('name')
    
    if not supplier_name:
        return JsonResponse({'success': False, 'error': 'Supplier name is required.'}, status=400)
    
    supplier_name_clean = supplier_name.strip()
    if Supplier.objects.filter(branch=branch, supplier_name__iexact=supplier_name_clean).exists():
        return JsonResponse({'success': False, 'error': 'Supplier already exists.'}, status=400)
    
    try:
        supplier = Supplier.objects.create(branch=branch, supplier_name=supplier_name_clean, is_active=True)
        return JsonResponse({'success': True, 'id': supplier.id, 'name': supplier.supplier_name})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def add_model_ajax(request):
    branch = get_user_branch_context(request)
    if not branch:
        return JsonResponse({'success': False, 'error': 'Select a specific branch before adding a model.'}, status=400)
    model_name, company_id = None, None
    
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            model_name = data.get('model_name') or data.get('name')
            company_id = data.get('company_id')
        except Exception:
            pass
            
    if not model_name:
        model_name = request.POST.get('model_name') or request.POST.get('name')
    if not company_id:
        company_id = request.POST.get('company_id')
        
    if not model_name:
        return JsonResponse({'success': False, 'error': 'Model name is required.'}, status=400)
        
    company = VehicleCompany.objects.filter(id=company_id, is_active=True).first() if company_id else None
    if not company:
        company = VehicleCompany.objects.filter(is_active=True).first() or VehicleCompany.objects.create(company_name='Default Company', is_active=True)
            
    model_name_clean = model_name.strip()
    existing_model = VehicleModel.objects.filter(branch=branch, company=company, model_name__iexact=model_name_clean).first()
    if existing_model:
        return JsonResponse({'success': True, 'id': existing_model.id, 'name': existing_model.model_name})
        
    try:
        model = VehicleModel.objects.create(branch=branch, company=company, model_name=model_name_clean, is_active=True)
        return JsonResponse({'success': True, 'id': model.id, 'name': model.model_name})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def add_color_ajax(request):
    branch = get_user_branch_context(request)
    if not branch:
        return JsonResponse({'success': False, 'error': 'Select a specific branch before adding a color.'}, status=400)
    color_name = None
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            color_name = data.get('color_name') or data.get('name') or data.get('colorName')
        except Exception:
            pass
            
    if not color_name:
        color_name = request.POST.get('color_name') or request.POST.get('name') or request.POST.get('colorName')
        
    if not color_name:
        return JsonResponse({'success': False, 'error': 'Color name is required.'}, status=400)
    
    color_name_clean = color_name.strip()
    if VehicleColor.objects.filter(branch=branch, color_name__iexact=color_name_clean).exists():
        return JsonResponse({'success': False, 'error': 'Color already exists.'}, status=400)
    
    try:
        color = VehicleColor.objects.create(branch=branch, color_name=color_name_clean, is_active=True)
        return JsonResponse({'success': True, 'id': color.id, 'name': color.color_name})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

            
@login_required
def purchase_history(request):
    branch_context = get_user_branch_context(request)
    purchases = Purchase.objects.all().select_related('supplier', 'branch').prefetch_related('items').order_by('-id')
    
    if branch_context is not None:
        purchases = purchases.filter(branch=branch_context)
    elif not request.user.is_superuser:
        user_branch = getattr(getattr(request.user, 'userprofile', None), 'branch', None)
        purchases = purchases.filter(branch=user_branch) if user_branch else purchases.none()

    for purchase in purchases:
        purchase.computed_qty = sum(item.quantity for item in purchase.items.all())
        purchase.computed_total = sum(item.total_amount for item in purchase.items.all())

    return render(request, 'yakuza/purchase_history.html', {'purchases': purchases})


# ==========================================
# SALES & CUSTOMER DATABASE VIEWS
# ==========================================
@login_required
@transaction.atomic
def sales(request):
    branch = get_user_branch_context(request)
    sys_settings = Settings.load()
    invoice_setting = InvoiceSetting.objects.filter(branch=branch).first() if branch else InvoiceSetting.objects.first()

    # ૧ વર્ષથી જૂના Audit Logs ઓટોમેટિક ડિલીટ કરવા માટે
    one_year_ago = timezone.now() - timedelta(days=365)
    AuditLog.objects.filter(timestamp__lt=one_year_ago).delete()

    if request.method == 'POST':
        try:
            sale_id = request.POST.get('current_sale_id')
            customer_name = request.POST.get('customer_name', '').strip()
            contact_number = request.POST.get('contact_number', '').strip()
            aadhar_number = request.POST.get('aadhar_number', '').strip()
            model_name = request.POST.get('model_name', '').strip()
            vehicle_color = request.POST.get('vehicle_color', '').strip()
            price_val = Decimal(request.POST.get('price', '0') or '0')
            chassis_number = request.POST.get('chassis_number', '').strip()
            battery_number = request.POST.get('battery_number', '').strip()
            motor_number = request.POST.get('motor_number', '').strip()
            controller_number = request.POST.get('controller_number', '').strip()
            payment_type = request.POST.get('payment_type', 'CASH')
            discount_val = Decimal(request.POST.get('discount', '0') or '0')

            if not customer_name or not contact_number or not model_name or price_val <= 0 or not chassis_number:
                return JsonResponse({'status': 'error', 'message': 'Please fill all required fields correctly.'}, status=400)

            existing_sale = None
            if sale_id and str(sale_id).isdigit():
                existing_sale = get_object_or_404(Sales, id=int(sale_id))
                if branch is not None and existing_sale.stock and existing_sale.stock.branch != branch:
                    return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

            payment_type_map = {'Cash': Sales.PaymentMethod.CASH, 'UPI': Sales.PaymentMethod.UPI, 'EMI': Sales.PaymentMethod.EMI}
            payment_method = payment_type_map.get(payment_type, Sales.PaymentMethod.CASH)

            # Resolve or allocate the Stock unit for this sale.
            #
            # A Stock row is created EMPTY (chassis_number / battery_number /
            # motor_number / controller_number all NULL) at purchase time --
            # those identifiers are only assigned the first time a specific
            # unit is actually sold, which is right here. So a NEW sale must
            # look up an AVAILABLE, not-yet-assigned unit by branch + model
            # + color (never by chassis_number, since it doesn't exist on
            # the row yet), then write the submitted identifiers onto it.
            # Editing the same vehicle continues to work with the Stock
            # unit already attached to that sale.
            stock_obj = None

            if existing_sale and existing_sale.stock and \
               existing_sale.stock.model.model_name == model_name and \
               existing_sale.stock.color.color_name == vehicle_color:
                stock_qs = Stock.objects.select_for_update().filter(id=existing_sale.stock_id).select_related("model", "color", "branch")
                if branch is not None:
                    stock_qs = stock_qs.filter(branch=branch)
                stock_obj = stock_qs.first()
                if not stock_obj:
                    return JsonResponse({'status': 'error', 'message': 'Vehicle is not available in current branch stock.'}, status=400)
            else:
                stock_qs = Stock.objects.select_for_update().filter(
                    model__model_name=model_name,
                    color__color_name=vehicle_color,
                    stock_status=Stock.StockStatus.AVAILABLE,
                    chassis_number__isnull=True,
                ).select_related("model", "color", "branch")
                if branch is not None:
                    stock_qs = stock_qs.filter(branch=branch)
                stock_obj = stock_qs.first()

                if not stock_obj:
                    return JsonResponse({'status': 'error', 'message': 'Vehicle is not available in current branch stock.'}, status=400)

            # chassis_number is unique across all Stock -- make sure the
            # submitted number isn't already assigned to a different unit.
            if Stock.objects.filter(chassis_number=chassis_number).exclude(id=stock_obj.id).exists():
                return JsonResponse({'status': 'error', 'message': 'This chassis number is already assigned to another vehicle.'}, status=400)

            if stock_obj.stock_status == Stock.StockStatus.SOLD and not (existing_sale and stock_obj.sale_id == existing_sale.id):
                return JsonResponse({'status': 'error', 'message': 'Selected vehicle stock is already sold.'}, status=400)

            # Assign / correct the physical vehicle identifiers on this unit.
            stock_obj.chassis_number = chassis_number
            stock_obj.battery_number = battery_number
            stock_obj.motor_number = motor_number
            stock_obj.controller_number = controller_number

            if existing_sale:
                # --- BILL PRICE CHANGE AUDIT LOG CHECK ---
                old_price = existing_sale.selling_price
                if old_price != price_val:
                    old_price_str = f"₹{old_price:,.0f}" if old_price == int(old_price) else f"₹{old_price:,.2f}"
                    new_price_str = f"₹{price_val:,.0f}" if price_val == int(price_val) else f"₹{price_val:,.2f}"

                    AuditLog.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        branch=branch,
                        module="Sales",
                        action="BILL_PRICE_CHANGE",
                        old_value={"price": old_price_str},
                        new_value={"price": new_price_str}
                    )
                sale = existing_sale
                old_stock = sale.stock
                if old_stock and old_stock != stock_obj:
                    old_stock.stock_status = Stock.StockStatus.AVAILABLE
                    old_stock.sale = None
                    old_stock.save()

                sale.customer_name = customer_name
                sale.mobile_number = contact_number
                sale.aadhar_number = aadhar_number
                sale.payment_method = payment_method
                sale.selling_price = price_val
                sale.discount = discount_val
                sale.stock = stock_obj
                sale.save()
            else:
                prefix = (invoice_setting.invoice_prefix if invoice_setting and invoice_setting.invoice_prefix else (sys_settings.invoice_prefix if sys_settings else "INV-")) or "INV-"
                auto_inv = f"{prefix}{timezone.now().year}-{(Sales.objects.count() + 1):04d}"

                sale = Sales.objects.create(
                    stock=stock_obj,
                    customer_name=customer_name,
                    mobile_number=contact_number,
                    aadhar_number=aadhar_number,
                    invoice_no=auto_inv,
                    payment_method=payment_method,
                    selling_price=price_val,
                    discount=discount_val,
                    created_by=request.user
                )

            stock_obj.stock_status = Stock.StockStatus.SOLD
            stock_obj.sale = sale
            stock_obj.save()

            b_name = branch.branch_name if branch else "Main Branch"
            existing_customer = Customer.objects.filter(mobile_number=contact_number).first()
            if existing_customer:
                existing_customer.customer_name = customer_name
                existing_customer.aadhar_number = aadhar_number
                existing_customer.branch_name = b_name
                existing_customer.model_name = stock_obj.model.model_name
                existing_customer.price = price_val
                existing_customer.payment_mode = sale.get_payment_method_display()
                existing_customer.save()
            else:
                Customer.objects.create(
                    mobile_number=contact_number,
                    customer_name=customer_name,
                    aadhar_number=aadhar_number,
                    branch_name=b_name,
                    model_name=stock_obj.model.model_name,
                    price=price_val,
                    payment_mode=sale.get_payment_method_display()
                )

            return JsonResponse({
                'status': 'success',
                'sale_id': sale.id,
                'invoice_no': sale.invoice_no,
                'customer_name': sale.customer_name,
                'mobile_number': sale.mobile_number,
                'model_name': stock_obj.model.model_name,
                'color': stock_obj.color.color_name if stock_obj.color else '',
                'price': f"{price_val:.2f}",
                'sgst': f"{getattr(sale, 'sgst', 0):.2f}",
                'cgst': f"{getattr(sale, 'cgst', 0):.2f}",
                'discount': f"{discount_val:.2f}",
                'grand_total': f"{getattr(sale, 'grand_total', price_val - discount_val):.2f}",
                'chassis_number': stock_obj.chassis_number,
                'battery_number': stock_obj.battery_number or '',
                'motor_number': stock_obj.motor_number or '',
                'controller_number': stock_obj.controller_number or '',
                'payment_method': sale.get_payment_method_display(),
                'created_at': sale.created_at.strftime('%Y-%m-%d')
            })

        except Exception as e:
            transaction.set_rollback(True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # --- GET REQUEST (VIEW / EDIT FORM) ---
    edit_sale = None
    edit_id = request.GET.get('edit') or request.GET.get('sale_id')
    if edit_id and str(edit_id).isdigit():
        edit_sale = Sales.objects.filter(id=int(edit_id)).select_related('stock', 'stock__model', 'stock__color').first()
        if edit_sale and branch is not None and edit_sale.stock and edit_sale.stock.branch != branch:
            edit_sale = None

    prefix = (invoice_setting.invoice_prefix if invoice_setting and invoice_setting.invoice_prefix else (sys_settings.invoice_prefix if sys_settings else "INV-")) or "INV-"
    auto_invoice_no = edit_sale.invoice_no if edit_sale else f"{prefix}{timezone.now().year}-{(Sales.objects.count() + 1):04d}"

    branch_name = branch.branch_name if branch else "All Branches"
    billing_phone = (invoice_setting.phone if invoice_setting and invoice_setting.phone else (branch.phone if branch else "")) if branch else ""
    billing_gstin = (invoice_setting.gstin if invoice_setting and invoice_setting.gstin else (branch.gst_number if branch else "")) if branch else ""

    # --- MODEL & COLOR DROPDOWNS MATHE AVAILABLE IDs FETCH ---
    available_stock_qs = Stock.objects.filter(stock_status=Stock.StockStatus.AVAILABLE)
    if branch is not None:
        available_stock_qs = available_stock_qs.filter(branch=branch)

    available_model_ids = set(available_stock_qs.values_list('model_id', flat=True).distinct())
    available_color_ids = set(available_stock_qs.values_list('color_id', flat=True).distinct())

    if edit_sale and edit_sale.stock:
        if edit_sale.stock.model_id:
            available_model_ids.add(edit_sale.stock.model_id)
        if edit_sale.stock.color_id:
            available_color_ids.add(edit_sale.stock.color_id)

    # NOTE: We deliberately do NOT re-filter these by VehicleModel.branch /
    # VehicleColor.branch here. available_model_ids / available_color_ids
    # above were already derived from Stock rows scoped to the current
    # branch (Stock.branch is a required, non-null field and is always set
    # correctly at purchase time), which is the authoritative source of
    # "what's available in this branch". VehicleModel.branch / VehicleColor.branch
    # can still be NULL on legacy master-data rows created before branch-wise
    # master data was introduced, even though their Stock is correctly
    # branch-scoped. Re-filtering by the master record's own branch field
    # excluded those legacy-but-valid rows entirely, which is why the Model
    # and Color dropdowns on the Sales page were rendering empty.
    models_qs = VehicleModel.objects.filter(id__in=available_model_ids, is_active=True)
    colors_qs = VehicleColor.objects.filter(id__in=available_color_ids, is_active=True)

    context = {
        'invoice_setting': invoice_setting,
        'sys_settings': sys_settings,
        'branch': branch,
        'branch_name': branch_name,  
        'billing_phone': billing_phone,
        'billing_gstin': billing_gstin,
        'edit_sale': edit_sale,
        'auto_invoice_no': auto_invoice_no,
        'models': models_qs,
        'colors': colors_qs,
    }
    return render(request, 'yakuza/sales.html', context)


@login_required
@require_GET
def get_sales_stock_options_ajax(request):
    """
    Cascading dropdown support for the Sales page.
    Given a Model name (and optionally a Color name), returns only the
    Colors and chassis numbers that actually have AVAILABLE Stock in the
    CURRENT branch for that model. Source of truth is always Stock (never
    VehicleModel.branch / VehicleColor.branch, which can be legacy-NULL) --
    this never creates Model/Color/Stock, it only reads what already exists.
    """
    branch = get_user_branch_context(request)
    model_name = request.GET.get('model_name', '').strip()
    color_name = request.GET.get('color_name', '').strip()
    edit_sale_id = request.GET.get('edit_sale_id', '').strip()

    if not model_name:
        return JsonResponse({'status': 'error', 'message': 'Model name is required.'}, status=400)

    stock_qs = Stock.objects.filter(model__model_name=model_name)
    if branch is not None:
        stock_qs = stock_qs.filter(branch=branch)

    # When editing an existing sale, its currently-assigned stock row is
    # SOLD (to itself) rather than AVAILABLE -- include it explicitly so the
    # user can keep their current selection while editing.
    editable_stock_id = None
    if edit_sale_id and str(edit_sale_id).isdigit():
        edit_sale = Sales.objects.filter(id=int(edit_sale_id)).select_related('stock').first()
        if edit_sale and edit_sale.stock and (branch is None or edit_sale.stock.branch_id == branch.id):
            editable_stock_id = edit_sale.stock_id

    stock_qs = stock_qs.filter(Q(stock_status=Stock.StockStatus.AVAILABLE) | Q(id=editable_stock_id))

    color_ids = stock_qs.values_list('color_id', flat=True).distinct()
    colors = list(
        VehicleColor.objects.filter(id__in=color_ids, is_active=True)
        .values('id', 'color_name').order_by('color_name')
    )

    chassis_list = []
    if color_name:
        chassis_list = [
            c for c in stock_qs.filter(color__color_name=color_name).values_list('chassis_number', flat=True) if c
        ]

    return JsonResponse({'status': 'success', 'colors': colors, 'chassis': chassis_list})


@login_required
@require_POST
def upload_invoice_pdf(request, sale_id):
    sale = get_object_or_404(Sales, id=sale_id)
    pdf_file = request.FILES.get('pdf_file')
    
    if pdf_file:
        cust_name = (sale.customer_name or "Customer").strip().replace(" ", "_")
        inv_no = str(sale.invoice_no).replace("/", "_")
        file_name = f"{cust_name}-{inv_no}.pdf"
        
        sale.invoice_pdf.save(file_name, pdf_file, save=True)
        return JsonResponse({'status': 'success', 'pdf_url': sale.invoice_pdf.url, 'message': 'Invoice PDF uploaded successfully.'})
    return JsonResponse({'status': 'error', 'message': 'No PDF file attached.'}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def save_and_share_whatsapp(request, sale_id=None):
    if not sale_id:
        return JsonResponse({'status': 'error', 'message': 'Sale ID is required.'}, status=400)

    sale = get_object_or_404(Sales.objects.select_related('stock__model', 'stock__color', 'created_by'), id=sale_id)

    if not sale.invoice_pdf or not hasattr(sale.invoice_pdf, 'url'):
        return JsonResponse({'status': 'error', 'message': 'Invoice PDF is not available.'}, status=400)

    mobile = str(sale.mobile_number or "").strip().replace(" ", "").replace("-", "").replace("+", "")
    if len(mobile) == 10:
        mobile = "91" + mobile

    customer_name = sale.customer_name or "Customer"
    inv_no = str(sale.invoice_no or sale.id)
    model_name = sale.stock.model.model_name if sale.stock and sale.stock.model else "Vehicle"

    message = f"Hello {customer_name},\nThank you for purchasing {model_name}!\nInvoice No: {inv_no}\nTotal Amount: ₹{sale.grand_total:.2f}\nThank you for choosing us!"
    whatsapp_url = f"https://api.whatsapp.com/send?phone={mobile}&text={quote(message)}"

    return JsonResponse({
        "status": "success",
        "invoice_url": sale.invoice_pdf.url,
        "invoice_filename": f"Invoice_{inv_no}.pdf",
        "whatsapp_url": whatsapp_url,
        "invoice_no": inv_no,
        "customer_name": customer_name,
        "customer_phone": mobile
    })


@login_required
def generate_invoice_pdf(request, sale_id):
    sale = get_object_or_404(Sales, id=sale_id)
    cust_name_clean = (sale.customer_name or "Customer").strip().replace(" ", "_")
    inv_no_clean = str(sale.invoice_no).replace("/", "_")
    custom_filename = f"{cust_name_clean}-{inv_no_clean}.pdf"
    
    if sale.invoice_pdf:
        return FileResponse(sale.invoice_pdf.open('rb'), content_type='application/pdf', filename=custom_filename)

    context = {
        'sale': sale,
        'customer_name': sale.customer_name,
        'mobile_number': sale.mobile_number,
        'invoice_no': sale.invoice_no,
        'invoice_date': getattr(sale, 'invoice_date', getattr(sale, 'created_at', None)),
        'grand_total': sale.grand_total,
    }
    
    html = render_to_string('sales/invoice_pdf_template.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{custom_filename}"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('An error occurred while generating PDF.', status=500)
    return response


@login_required
def customer(request):
    branch = get_user_branch_context(request)
    sales_qs = Sales.objects.select_related('stock', 'stock__model', 'stock__color', 'stock__branch').order_by('-id')

    if branch is not None:
        sales_qs = sales_qs.filter(stock__branch=branch)

    return render(request, 'yakuza/customer.html', {'customers': sales_qs, 'vehicle_models': VehicleModel.objects.filter(is_active=True)})


@login_required
def get_customer_invoice_ajax(request, sale_id):
    branch = get_user_branch_context(request)
    try:
        sale = Sales.objects.select_related('stock', 'stock__model', 'stock__color', 'stock__branch').get(id=sale_id)
        if branch is not None and sale.stock and sale.stock.branch != branch:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

        stock = sale.stock
        branch_obj = stock.branch if stock else None

        return JsonResponse({
            "status": "success",
            "sale_id": sale.id,
            "invoice_no": sale.invoice_no,
            "invoice_date": sale.invoice_date.strftime('%Y-%m-%d') if sale.invoice_date else "",
            "customer_name": sale.customer_name,
            "mobile_number": sale.mobile_number,
            "aadhar_number": sale.aadhar_number or "",
            "payment_method": sale.get_payment_method_display(),
            "model_name": stock.model.model_name if stock and stock.model else "-",
            "color_name": stock.color.color_name if stock and stock.color else "N/A",
            "chassis_number": stock.chassis_number if stock else "N/A",
            "battery_number": stock.battery_number if stock else "N/A",
            "motor_number": stock.motor_number if stock else "N/A",
            "controller_number": stock.controller_number if stock else "N/A",
            "price": f"{sale.selling_price:.2f}",
            "subtotal": f"{sale.subtotal:.2f}",
            "cgst": f"{sale.cgst:.2f}",
            "sgst": f"{sale.sgst:.2f}",
            "discount": f"{sale.discount:.2f}",
            "grand_total": f"{sale.grand_total:.2f}",
            "branch_name": branch_obj.branch_name if branch_obj else "Main Branch",
            "branch_address": branch_obj.address if branch_obj else "",
            "branch_phone": branch_obj.phone if branch_obj else "",
            "branch_gst": branch_obj.gst_number if branch_obj else "",
            "invoice_pdf_url": sale.invoice_pdf.url if sale.invoice_pdf else ""
        })
    except Sales.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Unable to identify sale.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

@login_required
def expenses(request):
    branch = get_user_branch_context(request)

    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

            expense_name = data.get('expense_name', '').strip()
            amount = data.get('amount')
            expense_type = data.get('expense_type', 'Daily Expense')
            expense_date = data.get('expense_date')
            expense_month = data.get('expense_month')
            description = data.get('description', '').strip()

            if not expense_name or not amount:
                return JsonResponse({'success': False, 'error': 'Expense name and amount are required.'}, status=400)

            profile = getattr(request.user, 'userprofile', None)
            active_branch = branch or (profile.branch if profile else None) or Branch.objects.filter(is_active=True).first()

            if not active_branch:
                return JsonResponse({'success': False, 'error': 'No active branch available for expense.'}, status=400)

            if expense_type == 'Monthly Expense' and expense_month:
                date_obj = datetime.strptime(f"{expense_month}-01", "%Y-%m-%d").date()
            elif expense_date:
                date_obj = datetime.strptime(expense_date, "%Y-%m-%d").date()
            else:
                date_obj = timezone.now().date()

            master, _ = ExpenseMaster.objects.get_or_create(expense_name=expense_name)
            expense = Expense.objects.create(
                expense_master=master,
                branch=active_branch,
                expense_date=date_obj,
                amount=Decimal(str(amount)),
                description=description,
                created_by=request.user
            )

            return JsonResponse({'success': True, 'message': 'Expense saved successfully!'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json'
    if is_ajax:
        expenses_qs = Expense.objects.select_related('expense_master', 'branch').order_by('-expense_date', '-id')
        if branch is not None:
            expenses_qs = expenses_qs.filter(branch=branch)

        expenses_data = [
            {
                'id': exp.id,
                'expense_name': exp.expense_master.expense_name,
                'amount': f"{exp.amount:.2f}",
                'expense_date': exp.expense_date.strftime('%Y-%m-%d'),
                'display_date': exp.expense_date.strftime('%d-%m-%Y'),
                'description': exp.description or '',
                'month_key': exp.expense_date.strftime('%Y-%m'),
                'month_display': exp.expense_date.strftime('%B %Y')
            }
            for exp in expenses_qs
        ]
        return JsonResponse({'success': True, 'expenses': expenses_data})

    return render(request, 'yakuza/expenses.html', {'expense_masters': ExpenseMaster.objects.filter(is_active=True)})


@login_required
@require_POST
def edit_expense(request, pk):
    try:
        expense = get_object_or_404(Expense, pk=pk)
        branch = get_user_branch_context(request)
        if branch and expense.branch != branch:
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        expense_name = data.get('expense_name', '').strip()
        amount = data.get('amount')
        expense_date = data.get('expense_date')
        description = data.get('description', '').strip()

        if not expense_name or not amount:
            return JsonResponse({'success': False, 'error': 'Expense name and amount are required.'}, status=400)

        master, _ = ExpenseMaster.objects.get_or_create(expense_name=expense_name)
        expense.expense_master = master
        expense.amount = Decimal(str(amount))
        if expense_date:
            expense.expense_date = datetime.strptime(expense_date, "%Y-%m-%d").date()
        expense.description = description
        expense.save()

        return JsonResponse({'success': True, 'message': 'Expense updated successfully!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def delete_expense(request, pk):
    try:
        expense = get_object_or_404(Expense, pk=pk)
        branch = get_user_branch_context(request)
        if branch and expense.branch != branch:
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

        expense_id = expense.id
        expense.delete()

        return JsonResponse({'success': True, 'message': 'Expense deleted successfully!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def generate_daily_reminder_check(branch=None):
    """Compatibility wrapper; scheduled creation is centralized in utils."""
    from yakuza.utils import create_daily_sales_reminder
    if branch:
        return create_daily_sales_reminder(branch)
    return [create_daily_sales_reminder(item) for item in Branch.objects.filter(is_active=True)]

def check_and_create_low_stock_notifications(branch=None):
    """Calculates stock from AVAILABLE status only and creates alerts per branch context."""
    from yakuza.models import Stock, Settings, Notification, Branch

    branches = [branch] if branch else Branch.objects.filter(is_active=True)
    sys_settings = Settings.load()
    threshold = getattr(sys_settings, 'low_stock_threshold', 2)

    for b in branches:
        # Stock status MUST be AVAILABLE (SOLD stock excluded)
        available_stock_count = Stock.objects.filter(
            branch=b,
            stock_status=Stock.StockStatus.AVAILABLE
        ).count()

        if available_stock_count <= threshold:
            today = timezone.localtime(timezone.now()).date()
            already_alerted = Notification.objects.filter(
                branch=b,
                notification_type=Notification.NotificationType.LOW_STOCK,
                created_at__date=today
            ).exists()

            if not already_alerted:
                Notification.objects.create(
                    branch=b,
                    title="⚠️ Low Stock Warning",
                    message=f"Available stock for branch '{b.branch_name}' has fallen to {available_stock_count} units (Threshold: {threshold}).",
                    notification_type=Notification.NotificationType.LOW_STOCK,
                    is_read=False
                )

@login_required
def notifications(request):
    branch = get_user_branch_context(request)
    
    # Run dynamic Low Stock check on real DB stock
    check_and_create_low_stock_notifications(branch=branch)

    # Filter ONLY LOW_STOCK & REMINDER notifications
    notifications_qs = Notification.objects.filter(
        notification_type__in=[
            Notification.NotificationType.LOW_STOCK,
            Notification.NotificationType.REMINDER
        ]
    )
    if branch is not None:
        notifications_qs = notifications_qs.filter(Q(branch=branch) | Q(branch__isnull=True))

    return render(request, 'yakuza/notifications.html', {
        'notifications': notifications_qs.order_by('-created_at')
    })

@login_required
def reports(request):
    user_branch = get_user_branch_context(request)
    now = timezone.localtime(timezone.now())
    today_date = now.date()
    first_day_of_month = today_date.replace(day=1)

    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    company_filter = request.GET.get('company', '').strip()
    model_filter = request.GET.get('model', '').strip()
    payment_filter = request.GET.get('payment_method', '').strip()

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else first_day_of_month
    except ValueError:
        date_from = first_day_of_month

    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else today_date
    except ValueError:
        date_to = today_date

    sales_base = Sales.objects.all()
    purchase_item_base = PurchaseItem.objects.all()
    expense_base = Expense.objects.all()
    stock_base = Stock.objects.all()

    if user_branch:
        sales_base = sales_base.filter(stock__branch=user_branch)
        purchase_item_base = purchase_item_base.filter(purchase__branch=user_branch)
        expense_base = expense_base.filter(branch=user_branch)
        stock_base = stock_base.filter(branch=user_branch)

    todays_sales = sales_base.filter(invoice_date=today_date).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')

    curr_month_sales_qs = sales_base.filter(invoice_date__gte=first_day_of_month, invoice_date__lte=today_date)
    monthly_sales = curr_month_sales_qs.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')

    curr_month_purchase_qs = purchase_item_base.filter(purchase__purchase_date__gte=first_day_of_month, purchase__purchase_date__lte=today_date)
    monthly_purchase = curr_month_purchase_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    curr_month_expense_qs = expense_base.filter(expense_date__gte=first_day_of_month, expense_date__lte=today_date)
    monthly_expense = curr_month_expense_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    sales_purchase_cost = curr_month_sales_qs.aggregate(cost=Sum('stock__purchase_price'))['cost'] or Decimal('0.00')
    monthly_profit = monthly_sales - sales_purchase_cost - monthly_expense

    avail_stock_qs = stock_base.filter(stock_status=Stock.StockStatus.AVAILABLE)
    stock_units = avail_stock_qs.count()
    stock_value = avail_stock_qs.aggregate(val=Sum(ExpressionWrapper(F('purchase_price'), output_field=DecimalField())))['val'] or Decimal('0.00')

    filtered_sales = sales_base.filter(invoice_date__gte=date_from, invoice_date__lte=date_to)
    filtered_purchases = purchase_item_base.filter(purchase__purchase_date__gte=date_from, purchase__purchase_date__lte=date_to)
    filtered_expenses = expense_base.filter(expense_date__gte=date_from, expense_date__lte=date_to)

    if company_filter:
        filtered_sales = filtered_sales.filter(stock__company__company_name__iexact=company_filter)
        filtered_purchases = filtered_purchases.filter(company__company_name__iexact=company_filter)

    if model_filter:
        filtered_sales = filtered_sales.filter(stock__model_id=model_filter)
        filtered_purchases = filtered_purchases.filter(model_id=model_filter)

    if payment_filter:
        filtered_sales = filtered_sales.filter(payment_method__iexact=payment_filter)

    sp_labels, sp_sales_data, sp_purchase_data = [], [], []
    curr_dt = date_from
    while curr_dt <= date_to:
        sp_labels.append(curr_dt.strftime('%b %d'))
        d_sales = filtered_sales.filter(invoice_date=curr_dt).aggregate(t=Sum('grand_total'))['t'] or Decimal('0.00')
        d_purchases = filtered_purchases.filter(purchase__purchase_date=curr_dt).aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        sp_sales_data.append(float(d_sales))
        sp_purchase_data.append(float(d_purchases))
        curr_dt += timedelta(days=1)

    exp_grouped = filtered_expenses.values('expense_master__expense_name').annotate(total_amt=Sum('amount')).order_by('-total_amt')
    exp_labels = [item['expense_master__expense_name'] for item in exp_grouped]
    exp_values = [float(item['total_amt']) for item in exp_grouped]

    profit_labels = sp_labels
    profit_values = []
    curr_dt = date_from
    while curr_dt <= date_to:
        s_day = sales_base.filter(invoice_date=curr_dt)
        if company_filter:
            s_day = s_day.filter(stock__company__company_name__iexact=company_filter)
        if model_filter:
            s_day = s_day.filter(stock__model_id=model_filter)
        if payment_filter:
            s_day = s_day.filter(payment_method__iexact=payment_filter)

        day_sales = s_day.aggregate(t=Sum('grand_total'))['t'] or Decimal('0.00')
        day_sales_cost = s_day.aggregate(t=Sum('stock__purchase_price'))['t'] or Decimal('0.00')
        day_exp = expense_base.filter(expense_date=curr_dt).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

        profit_values.append(float(day_sales - day_sales_cost - day_exp))
        curr_dt += timedelta(days=1)

    top_models_qs = filtered_sales.values('stock__model__model_name').annotate(
        sold_qty=Count('id'),
        revenue=Sum('grand_total'),
        purchase_cost=Sum('stock__purchase_price')
    ).order_by('-sold_qty')[:5]

    top_selling_models = [
        {
            'name': item['stock__model__model_name'],
            'sold_qty': item['sold_qty'],
            'revenue': f"{(item['revenue'] or Decimal('0.00')):,.2f}",
            'profit': f"{((item['revenue'] or Decimal('0.00')) - (item['purchase_cost'] or Decimal('0.00'))):,.2f}"
        }
        for item in top_models_qs
    ]

    chart_data_json = json.dumps({
        'salesPurchaseLabels': sp_labels,
        'salesData': sp_sales_data,
        'purchaseData': sp_purchase_data,
        'expenseLabels': exp_labels,
        'expenseValues': exp_values,
        'profitLabels': profit_labels,
        'profitValues': profit_values,
    })

    context = {
        'todays_sales': f"{todays_sales:,.2f}",
        'monthly_sales': f"{monthly_sales:,.2f}",
        'monthly_purchase': f"{monthly_purchase:,.2f}",
        'monthly_expense': f"{monthly_expense:,.2f}",
        'monthly_profit': f"{monthly_profit:,.2f}",
        'stock_value': f"{stock_value:,.2f}",
        'total_stock_units': stock_units,
        'date_from': date_from.strftime('%Y-%m-%d'),
        'date_to': date_to.strftime('%Y-%m-%d'),
        'companies': VehicleCompany.objects.filter(is_active=True).values_list('company_name', flat=True),
        'models': VehicleModel.objects.filter(is_active=True),
        'top_selling_models': top_selling_models,
        'chart_data_json': chart_data_json,
    }
    return render(request, 'yakuza/reports.html', context)


@login_required
def generate_reports_pdf(request):
    user_branch = get_user_branch_context(request)
    now = timezone.localtime(timezone.now())
    today_date = now.date()
    first_day_of_month = today_date.replace(day=1)

    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else first_day_of_month
    except ValueError:
        date_from = first_day_of_month

    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else today_date
    except ValueError:
        date_to = today_date

    sales_qs = Sales.objects.filter(invoice_date__gte=date_from, invoice_date__lte=date_to)
    exp_qs = Expense.objects.filter(expense_date__gte=date_from, expense_date__lte=date_to)
    
    if user_branch:
        sales_qs = sales_qs.filter(stock__branch=user_branch)
        exp_qs = exp_qs.filter(branch=user_branch)

    tot_sales = sales_qs.aggregate(t=Sum('grand_total'))['t'] or Decimal('0.00')
    tot_cost = sales_qs.aggregate(t=Sum('stock__purchase_price'))['t'] or Decimal('0.00')
    tot_exp = exp_qs.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    tot_profit = tot_sales - tot_cost - tot_exp

    branch_name = user_branch.branch_name if user_branch else "All Branches"
    generated_at = now.strftime("%d %b %Y, %I:%M %p")

    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 12px; color: #172b4d; padding: 10px; }}
            .header {{ text-align: center; margin-bottom: 20px; border-bottom: 2px solid #0052cc; padding-bottom: 10px; }}
            .header h1 {{ color: #0052cc; margin: 0; font-size: 20px; text-transform: uppercase; }}
            .header p {{ margin: 5px 0 0 0; font-size: 12px; color: #5e6c84; }}
            .meta {{ margin-bottom: 20px; font-size: 11px; color: #6b778c; background: #f4f5f7; padding: 8px; border-radius: 4px; }}
            .card-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            .card-table td {{ padding: 12px; border: 1px solid #dfe1e6; background-color: #fafbfc; text-align: center; width: 33.33%; }}
            .card-title {{ font-size: 10px; color: #6b778c; text-transform: uppercase; margin-bottom: 4px; font-weight: bold; }}
            .card-amount {{ font-size: 15px; font-weight: bold; color: #0052cc; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Business Performance Report</h1>
            <p>Branch: {branch_name}</p>
        </div>
        
        <div class="meta">
            <strong>Date Range:</strong> {date_from} to {date_to} &nbsp;|&nbsp; 
            <strong>Generated On:</strong> {generated_at}
        </div>

        <table class="card-table">
            <tr>
                <td>
                    <div class="card-title">Total Sales</div>
                    <div class="card-amount">₹{tot_sales:,.2f}</div>
                </td>
                <td>
                    <div class="card-title">Total Expense</div>
                    <div class="card-amount">₹{tot_exp:,.2f}</div>
                </td>
                <td>
                    <div class="card-title">Net Profit</div>
                    <div class="card-amount">₹{tot_profit:,.2f}</div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Business_Report_{date_from}_to_{date_to}.pdf"'
    
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    if pisa_status.err:
        return HttpResponse('Error creating PDF report', status=500)
    return response


# ==========================================
# SETTINGS & CONFIGURATIONS
# ==========================================
@login_required
def settings(request):
    user = request.user
    user_profile, _ = UserProfile.objects.get_or_create(user=user)
    
    # Get active branch context
    branch_context = get_user_branch_context(request)
    
    # -------------------------------------------------------------
    # STRICT USER MANAGEMENT LIST RULE:
    # 1. UserProfile.branch == current branch
    # 2. UserProfile.role == BRANCH_ADMIN
    # 3. Super User (is_superuser=True) & other roles/branches excluded at DB level
    # -------------------------------------------------------------
    if branch_context:
        users_qs = User.objects.filter(
            is_superuser=False,
            userprofile__branch=branch_context,
            userprofile__role=UserProfile.RoleChoices.BRANCH_ADMIN
        ).select_related('userprofile', 'userprofile__branch')
    else:
        users_qs = User.objects.none()

    settings_obj = Settings.load()
    is_super = (user_profile.role == UserProfile.RoleChoices.SUPER_ADMIN) or user.is_superuser
    current_branch = branch_context if is_super else user_profile.branch
    
    if current_branch:
        invoice_settings, _ = InvoiceSetting.objects.get_or_create(branch=current_branch)
    else:
        invoice_settings = InvoiceSetting.objects.first()

    # Audit logs are matched by the branch recorded on the log entry itself
    # (branch at the time of the action), not the user's current branch.
    if branch_context:
        audit_logs = AuditLog.objects.filter(
            branch=branch_context
        ).select_related('user', 'branch').order_by('-timestamp')[:100]
    else:
        audit_logs = AuditLog.objects.none()

    context = {
        'user_profile': user_profile,
        'current_branch': current_branch,
        'settings_obj': settings_obj,
        'invoice_settings': invoice_settings,
        'users_list': users_qs.order_by('-id'),
        'all_branches': Branch.objects.filter(is_active=True),
        'audit_logs': audit_logs,
        'last_backup': BackupHistory.objects.order_by('-created_at').first(),
    }

    return render(request, 'yakuza/settings.html', context)

from django.views.decorators.csrf import csrf_protect

@login_required
@csrf_protect
def toggle_user_status(request, user_id):
    branch_context = get_user_branch_context(request)
    
    target_user = get_object_or_404(
        User, 
        id=user_id, 
        is_superuser=False, 
        userprofile__branch=branch_context,
        userprofile__role=UserProfile.RoleChoices.BRANCH_ADMIN
    )
    
    if request.method == "POST":
        target_user.is_active = not target_user.is_active
        target_user.save()
        
    return redirect(reverse('yakuza:settings') + '#section-users')

@login_required
@require_POST
def add_user(request):
    branch_context = get_user_branch_context(request)
    if not branch_context:
        return HttpResponseForbidden("Valid Branch Context Required.")
    
    username = request.POST.get('username')
    password = request.POST.get('password')
    role = request.POST.get('role')
    
    # Super User ક્રિએટ ન થવો જોઈએ
    if role == UserProfile.RoleChoices.SUPER_ADMIN:
        return HttpResponseForbidden("Cannot create Super User from Branch Context.")
    
    # 1. New User Default Active (is_active=True)
    new_user = User.objects.create_user(
        username=username,
        password=password,
        is_active=True
    )
    
    # 2. Strict allocation to CURRENT BRANCH only
    UserProfile.objects.create(
        user=new_user,
        branch=branch_context,
        role=role
    )
    
    # yakuza:settings પર સાચું redirect
    return redirect('yakuza:settings')

@login_required
@require_POST
@transaction.atomic
def update_profile_ajax(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    full_name = request.POST.get('full_name', '').strip()
    username = request.POST.get('username', '').strip()
    mobile = request.POST.get('mobile', '').strip()

    curr_pass = request.POST.get('curr_password', '').strip()
    new_pass = request.POST.get('new_password', '').strip()
    confirm_pass = request.POST.get('confirm_password', '').strip()

    if curr_pass or new_pass or confirm_pass:
        if not curr_pass or not user.check_password(curr_pass):
            return JsonResponse({'status': 'error', 'message': 'Current password is incorrect!'}, status=400)

        if new_pass != confirm_pass or len(new_pass) < 6:
            return JsonResponse({'status': 'error', 'message': 'Password validation failed.'}, status=400)

        user.set_password(new_pass)
        user.save()
        update_session_auth_hash(request, user)

    if username and username != user.username:
        if User.objects.filter(username=username).exclude(id=user.id).exists():
            return JsonResponse({'status': 'error', 'message': 'This username is already taken.'}, status=400)
        user.username = username

    if full_name:
        name_parts = full_name.split(' ', 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ''

    user.save()
    profile.mobile_number = mobile
    if 'profile_photo' in request.FILES:
        profile.profile_photo = request.FILES['profile_photo']
    profile.save()

    return JsonResponse({'status': 'success', 'message': 'Profile updated successfully!', 'photo_url': profile.profile_photo.url if profile.profile_photo else ''})


@login_required
@require_POST
@transaction.atomic
def update_branch_ajax(request):
    user = request.user
    branch = get_user_branch_context(request) or (Branch.objects.first() if user.is_superuser else None)

    if branch:
        branch.branch_name = request.POST.get('branch_name', branch.branch_name)
        branch.owner_name = request.POST.get('owner_name', branch.owner_name)
        branch.address = request.POST.get('address') or request.POST.get('branch_address') or branch.address
        branch.gst_number = request.POST.get('gst_number', branch.gst_number)
        branch.phone = request.POST.get('phone') or request.POST.get('branch_phone') or branch.phone

        if 'logo' in request.FILES:
            branch.logo = request.FILES['logo']
        elif 'branch_logo' in request.FILES:
            branch.logo = request.FILES['branch_logo']

        branch.save()
        return JsonResponse({'status': 'success', 'message': 'Branch details updated successfully!'})

    return JsonResponse({'status': 'error', 'message': 'Branch not found.'}, status=400)


@login_required
@require_POST
@transaction.atomic
def update_invoice_ajax(request):
    user = request.user
    branch = get_user_branch_context(request) or (Branch.objects.first() if user.is_superuser else None)

    inv_setting, _ = InvoiceSetting.objects.get_or_create(branch=branch)
    inv_setting.company_name = request.POST.get('company_name', inv_setting.company_name)
    inv_setting.invoice_prefix = request.POST.get('invoice_prefix', inv_setting.invoice_prefix)
    inv_setting.company_address = request.POST.get('company_address', inv_setting.company_address)
    inv_setting.gstin = request.POST.get('gstin', inv_setting.gstin)
    inv_setting.phone = request.POST.get('phone', inv_setting.phone)
    inv_setting.terms = request.POST.get('terms', inv_setting.terms)

    if 'logo' in request.FILES:
        inv_setting.logo = request.FILES['logo']
    elif 'company_logo' in request.FILES:
        inv_setting.logo = request.FILES['company_logo']

    inv_setting.save()

    sys_setting = Settings.load()
    sys_setting.company_name = inv_setting.company_name or sys_setting.company_name
    sys_setting.invoice_prefix = inv_setting.invoice_prefix or sys_setting.invoice_prefix
    sys_setting.company_address = inv_setting.company_address or sys_setting.company_address
    sys_setting.gstin = inv_setting.gstin or sys_setting.gstin
    sys_setting.company_phone = inv_setting.phone or sys_setting.company_phone
    sys_setting.save()

    return JsonResponse({'status': 'success', 'message': 'Invoice settings updated successfully!'})


@login_required
@require_POST
@transaction.atomic
def save_user_ajax(request):
    profile = getattr(request.user, 'userprofile', None)
    is_super = (profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN) or request.user.is_superuser
    
    if not is_super:
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    role = request.POST.get('role', '').strip()
    if role != UserProfile.RoleChoices.SUPER_ADMIN:
        return JsonResponse({'status': 'error', 'message': 'Invalid role.'}, status=400)

    username = request.POST.get('username', '').strip()
    fullname = request.POST.get('fullname', '').strip()
    password = request.POST.get('password', '').strip()
    confirm_password = request.POST.get('confirm_password', '').strip()
    status_val = request.POST.get('status', 'Active').strip()

    if not username or not fullname or not password:
        return JsonResponse({'status': 'error', 'message': 'Required fields missing.'}, status=400)

    if password != confirm_password:
        return JsonResponse({'status': 'error', 'message': 'Password and Confirm Password must match.'}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({'status': 'error', 'message': 'Username already exists.'}, status=400)

    first_name = fullname.split()[0] if fullname else username
    last_name = " ".join(fullname.split()[1:]) if len(fullname.split()) > 1 else ""

    is_active = (status_val == 'Active')

    new_user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        is_active=is_active
    )
    new_user.is_superuser = True
    new_user.is_staff = True
    new_user.save()

    UserProfile.objects.create(
        user=new_user,
        branch=None,
        role=UserProfile.RoleChoices.SUPER_ADMIN,
        is_active=is_active
    )

    return JsonResponse({'status': 'success', 'message': 'Super User added successfully!'})

@login_required
@require_POST
def update_notifications_ajax(request):
    sys_setting = Settings.load()
    status_val = request.POST.get('notification_status')
    sys_setting.notification_status = status_val in ['on', 'true', '1']
    sys_setting.auto_delete_days = request.POST.get('auto_delete_days', '30')
    sys_setting.save()

    return JsonResponse({'status': 'success', 'message': 'Notification settings updated!'})

@login_required
def get_audit_log_details(request, log_id):
    try:
        if not IsBranchAdmin().has_permission(request, None):
            return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

        branch = get_user_branch_context(request)
        if branch is None:
            return JsonResponse({'success': False, 'error': 'Select a specific branch before viewing audit details.'}, status=400)

        qs = AuditLog.objects.filter(branch=branch)
        log_entry = get_object_or_404(qs, id=log_id)

        missing = object()

        def parse_value(value):
            if not value:
                return {}
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (TypeError, ValueError):
                    pass
                try:
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
                return value
            return value

        old_value = parse_value(log_entry.old_value)
        new_value = parse_value(log_entry.new_value)

        if isinstance(new_value, dict):
            new_value.pop('__audit_description', None)
        if isinstance(old_value, dict):
            old_value.pop('__audit_description', None)

        old_dict = old_value if isinstance(old_value, dict) else ({'Value': old_value} if old_value not in ({}, None, '') else {})
        new_dict = new_value if isinstance(new_value, dict) else ({'Value': new_value} if new_value not in ({}, None, '') else {})

        def display(value):
            if value is missing or value == {} or value is None:
                return '—'
            if value == '':
                return '""'
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False, sort_keys=True)
            return str(value)

        diff = []
        for key in sorted(set(old_dict).union(new_dict)):
            before = old_dict.get(key, missing)
            after = new_dict.get(key, missing)
            if before != after:
                diff.append({
                    'field': str(key).replace('_', ' ').title(),
                    'before': display(before),
                    'after': display(after),
                })

        # Fallback: If no dictionary key diff exists, show raw values or Action description
        if not diff:
            before_str = display(old_value)
            after_str = display(new_value)
            action_desc = getattr(log_entry, 'action', '') or getattr(log_entry, 'description', '')
            
            if before_str != '—' or after_str != '—':
                diff.append({
                    'field': 'Data Change',
                    'before': before_str,
                    'after': after_str,
                })
            elif action_desc:
                diff.append({
                    'field': 'Action Performed',
                    'before': '—',
                    'after': str(action_desc),
                })

        user_str = log_entry.user.get_full_name() or log_entry.user.username if log_entry.user else 'System'
        time_str = log_entry.timestamp.strftime('%d %b %Y, %I:%M %p') if log_entry.timestamp else '—'

        return JsonResponse({
            'success': True,
            'details': {
                'user': user_str,
                'time': time_str,
            },
            'diff': diff,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def clear_audit_log(request):
    """Clear audit logs for the currently active branch only. Never clears
    another branch's logs, and never clears all branches at once (even for
    Super Admin) -- a specific branch must be active."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    if not IsBranchAdmin().has_permission(request, None):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    branch_context = get_user_branch_context(request)
    if branch_context is None:
        return JsonResponse({
            'success': False,
            'error': 'Select a specific branch before clearing audit logs.'
        }, status=400)

    deleted_count, _ = AuditLog.objects.filter(branch=branch_context).delete()

    return JsonResponse({
        'success': True,
        'message': f'Audit logs cleared successfully for {branch_context.branch_name}.',
        'deleted_count': deleted_count
    })

@login_required
def export_audit_logs(request, fmt):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="audit_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    branch = get_user_branch_context(request)
    logs_qs = AuditLog.objects.all()
    if branch is not None:
        logs_qs = logs_qs.filter(branch=branch)

    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'User', 'Branch', 'Module', 'Action', 'IP Address'])

    for log in logs_qs.order_by('-timestamp')[:1000]:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d') if log.timestamp else '',
            log.timestamp.strftime('%H:%M:%S') if log.timestamp else '',
            log.user.username if log.user else 'System',
            log.branch.branch_name if log.branch else 'Global',
            log.module,
            log.action,
            log.ip_address or '127.0.0.1'
        ])

    return response

@login_required
def export_audit_csv(request):
    branch_context = get_user_branch_context(request)
    if branch_context:
        audit_logs = AuditLog.objects.filter(branch=branch_context).select_related('user', 'branch').order_by('-timestamp')
    else:
        audit_logs = AuditLog.objects.none()

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="Audit_Logs.csv"'
    # Excel does not assume UTF-8 for a plain "text/csv" file without a
    # byte-order mark, and falls back to the system codepage -- which
    # renders the Rupee symbol (₹) as "■". Writing the UTF-8 BOM first
    # makes Excel read the file as UTF-8 and display ₹ correctly.
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['User', 'Old Value', 'Updated Value', 'Date/Time'])

    for log in audit_logs:
        if log.user:
            user_name = log.user.get_full_name() or log.user.username
        else:
            user_name = "System"
        old_val = log.old_value.get('price', '') if isinstance(log.old_value, dict) else (log.old_value or '')
        new_val = log.new_value.get('price', '') if isinstance(log.new_value, dict) else (log.new_value or '')
        formatted_time = log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""

        writer.writerow([user_name, old_val or '—', new_val or '—', formatted_time])

    return response


# ---------------------------------------------------------
# EXPORT AUDIT LOG TO PDF
# ---------------------------------------------------------
@login_required
def export_audit_pdf(request):
    branch_context = get_user_branch_context(request)
    if branch_context:
        audit_logs = AuditLog.objects.filter(branch=branch_context).select_related('user', 'branch').order_by('-timestamp')
    else:
        audit_logs = AuditLog.objects.none()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Audit_Logs.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("<b>Audit Logs Report</b>", styles['Title']))
    elements.append(Spacer(1, 15))

    table_data = [['User', 'Old Value', 'Updated Value', 'Date/Time']]
    for log in audit_logs:
        if log.user:
            user_name = log.user.get_full_name() or log.user.username
        else:
            user_name = "System"
        old_val = log.old_value.get('price', '') if isinstance(log.old_value, dict) else (log.old_value or '')
        new_val = log.new_value.get('price', '') if isinstance(log.new_value, dict) else (log.new_value or '')
        # ReportLab's default Helvetica font has no glyph for ₹ (U+20B9),
        # so it silently renders it as "n". Use "Rs." instead in the PDF.
        old_val = old_val.replace('₹', 'Rs. ') if old_val else '—'
        new_val = new_val.replace('₹', 'Rs. ') if new_val else '—'
        formatted_time = log.timestamp.strftime("%d %b %Y, %I:%M %p") if log.timestamp else ""

        table_data.append([user_name, old_val, new_val, formatted_time])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]))

    elements.append(table)
    doc.build(elements)
    return response

@login_required
def create_backup_ajax(request):
    """Create a strict branch-isolated backup for Super User and Branch Admin.
    Only ever backs up the currently active branch (Super Admin's selected
    branch, or a Branch Admin's own branch) -- never a full-database dump."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

    if not IsBranchAdmin().has_permission(request, None):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    # Backend-resolved branch only -- any frontend-supplied branch_id is ignored.
    branch = get_user_branch_context(request)
    if branch is None:
        return JsonResponse({'success': False, 'error': 'Select a specific branch before creating a backup.'}, status=400)

    user_profile = request.user.userprofile
    if user_profile.role == 'BRANCH_ADMIN' and user_profile.branch_id != branch.id:
        return JsonResponse({'success': False, 'error': 'Unauthorized branch backup attempt.'}, status=403)

    data_to_backup = {
        'branch': branch.branch_name,
        'branch_id': branch.id,
        'purchases': list(Purchase.objects.filter(branch_id=branch.id).values()),
        'purchase_items': list(PurchaseItem.objects.filter(purchase__branch_id=branch.id).values()),
        'stock': list(Stock.objects.filter(branch_id=branch.id).values()),
        'sales': list(Sales.objects.filter(stock__branch_id=branch.id).values()),
        'customers': list(Customer.objects.filter(branch_name=branch.branch_name).values()),
        'expenses': list(Expense.objects.filter(branch_id=branch.id).values()),
        'notifications': list(Notification.objects.filter(branch_id=branch.id).values()),
        # Included for record-keeping only -- audit history is not overwritten on restore (see restore_backup).
        'audit_logs': list(AuditLog.objects.filter(branch_id=branch.id).values()),
    }

    backup_json = json.dumps(data_to_backup, indent=4, default=str)
    filename = f"Gatistvam_{branch.branch_name.replace(' ', '_')}_Backup_{date.today().isoformat()}.json"

    size_mb = len(backup_json.encode('utf-8')) / (1024 * 1024)
    BackupHistory.objects.create(
        branch=branch,
        created_by=request.user,
        filename=filename,
        file_size=f"{size_mb:.2f} MB",
    )

    response = HttpResponse(backup_json, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def safe_decimal(val):
    if val is None:
        return Decimal('0.00')
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')

@login_required
def restore_backup(request):
    """Restore backup with strict branch isolation and transaction safety."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

    if not IsBranchAdmin().has_permission(request, None):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    # Backend-resolved branch only -- any frontend-supplied branch_id is ignored.
    branch = get_user_branch_context(request)
    if branch is None:
        return JsonResponse({'success': False, 'error': 'Select a specific branch before restoring a backup.'}, status=400)

    user_profile = request.user.userprofile
    if user_profile.role == 'BRANCH_ADMIN' and user_profile.branch_id != branch.id:
        return JsonResponse({'success': False, 'error': 'Unauthorized branch restore attempt.'}, status=403)

    upload_file = request.FILES.get('backup_file')
    if not upload_file:
        return JsonResponse({'success': False, 'error': 'No backup file provided.'}, status=400)

    try:
        file_content = upload_file.read().decode('utf-8')
        backup_data = json.loads(file_content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Invalid backup file format or malformed JSON.'}, status=400)

    if not isinstance(backup_data, dict) or 'branch_id' not in backup_data:
        return JsonResponse({'success': False, 'error': 'Invalid backup file structure.'}, status=400)

    backup_branch_id = backup_data.get('branch_id')
    backup_branch_name = backup_data.get('branch', 'Unknown')
    if not backup_branch_id or int(backup_branch_id) != int(branch.id):
        return JsonResponse({
            'success': False,
            'error': f"This backup belongs to {backup_branch_name} and cannot be restored while {branch.branch_name} is active."
        }, status=400)

    try:
        with transaction.atomic():
            # --- Step 1: remove existing branch data (dependency-safe order) ---
            Sales.objects.filter(stock__branch_id=branch.id).delete()
            Stock.objects.filter(branch_id=branch.id).delete()
            PurchaseItem.objects.filter(purchase__branch_id=branch.id).delete()
            Purchase.objects.filter(branch_id=branch.id).delete()
            Customer.objects.filter(branch_name=branch.branch_name).delete()
            Expense.objects.filter(branch_id=branch.id).delete()
            Notification.objects.filter(branch_id=branch.id).delete()

            # --- Step 2: recreate in FK dependency order, with old-id -> new-object mapping ---
            purchase_id_map = {}
            purchase_item_id_map = {}
            stock_id_map = {}

            for item in backup_data.get('purchases', []):
                old_id = item.pop('id', None)
                if item.get('supplier_id') and not Supplier.objects.filter(id=item['supplier_id']).exists():
                    raise ValueError(f'Supplier referenced by Purchase #{old_id} no longer exists.')
                if item.get('created_by_id') and not User.objects.filter(id=item['created_by_id']).exists():
                    item['created_by_id'] = request.user.id
                item['branch_id'] = branch.id
                
                # Clean/safe decimal fields if present
                for dec_key in ['total_amount', 'paid_amount', 'balance_amount', 'discount']:
                    if dec_key in item:
                        item[dec_key] = safe_decimal(item[dec_key])

                new_purchase = Purchase.objects.create(**item)
                if old_id is not None:
                    purchase_id_map[old_id] = new_purchase

            for item in backup_data.get('purchase_items', []):
                old_id = item.pop('id', None)
                old_purchase_id = item.pop('purchase_id', None)
                new_purchase = purchase_id_map.get(old_purchase_id)
                if new_purchase is None:
                    raise ValueError(f'Purchase referenced by PurchaseItem #{old_id} could not be restored.')
                for fk_field, fk_model in (('company_id', VehicleCompany), ('model_id', VehicleModel), ('color_id', VehicleColor)):
                    if item.get(fk_field) and not fk_model.objects.filter(id=item[fk_field]).exists():
                        raise ValueError(f'{fk_model.__name__} referenced by PurchaseItem #{old_id} no longer exists.')
                item['purchase_id'] = new_purchase.id

                for dec_key in ['price', 'quantity', 'total_price', 'mrp']:
                    if dec_key in item:
                        if dec_key == 'quantity':
                            item[dec_key] = int(safe_decimal(item[dec_key]))
                        else:
                            item[dec_key] = safe_decimal(item[dec_key])

                new_item = PurchaseItem.objects.create(**item)
                if old_id is not None:
                    purchase_item_id_map[old_id] = new_item

            for item in backup_data.get('stock', []):
                old_id = item.pop('id', None)
                old_purchase_item_id = item.pop('purchase_item_id', None)
                item.pop('sale_id', None) 
                if old_purchase_item_id is not None:
                    new_purchase_item = purchase_item_id_map.get(old_purchase_item_id)
                    if new_purchase_item is None:
                        raise ValueError(f'PurchaseItem referenced by Stock #{old_id} could not be restored.')
                    item['purchase_item_id'] = new_purchase_item.id
                for fk_field, fk_model in (('company_id', VehicleCompany), ('model_id', VehicleModel), ('color_id', VehicleColor)):
                    if item.get(fk_field) and not fk_model.objects.filter(id=item[fk_field]).exists():
                        raise ValueError(f'{fk_model.__name__} referenced by Stock #{old_id} no longer exists.')
                item['branch_id'] = branch.id

                for dec_key in ['purchase_price', 'selling_price', 'mrp']:
                    if dec_key in item:
                        item[dec_key] = safe_decimal(item[dec_key])

                new_stock = Stock.objects.create(**item)
                if old_id is not None:
                    stock_id_map[old_id] = new_stock

            for item in backup_data.get('sales', []):
                old_id = item.pop('id', None)
                old_stock_id = item.pop('stock_id', None)
                new_stock = stock_id_map.get(old_stock_id)
                if new_stock is None:
                    raise ValueError(f'Stock referenced by Sale #{old_id} could not be restored.')
                if item.get('created_by_id') and not User.objects.filter(id=item['created_by_id']).exists():
                    item['created_by_id'] = request.user.id
                item['stock_id'] = new_stock.id

                for dec_key in ['selling_price', 'discount', 'total_amount', 'paid_amount', 'balance_amount']:
                    if dec_key in item:
                        item[dec_key] = safe_decimal(item[dec_key])

                new_sale = Sales.objects.create(**item)
                new_stock.sale = new_sale
                new_stock.save(update_fields=['sale'])

            for item in backup_data.get('customers', []):
                item.pop('id', None)
                item['branch_name'] = branch.branch_name
                Customer.objects.create(**item)

            for item in backup_data.get('expenses', []):
                old_id = item.pop('id', None)
                if item.get('expense_master_id') and not ExpenseMaster.objects.filter(id=item['expense_master_id']).exists():
                    raise ValueError(f'Expense category referenced by Expense #{old_id} no longer exists.')
                if item.get('created_by_id') and not User.objects.filter(id=item['created_by_id']).exists():
                    item['created_by_id'] = request.user.id
                item['branch_id'] = branch.id

                for dec_key in ['amount']:
                    if dec_key in item:
                        item[dec_key] = safe_decimal(item[dec_key])

                Expense.objects.create(**item)

            for item in backup_data.get('notifications', []):
                item.pop('id', None)
                if item.get('created_by_id') and not User.objects.filter(id=item['created_by_id']).exists():
                    item['created_by_id'] = None
                item['branch_id'] = branch.id
                Notification.objects.create(**item)

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Restore failed and rolled back: {str(e)}'}, status=500)

    return JsonResponse({'success': True, 'message': f'Backup restored successfully for {branch.branch_name}.'})
