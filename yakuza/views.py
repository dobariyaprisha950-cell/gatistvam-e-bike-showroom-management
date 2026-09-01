import json
import uuid
import csv
import re
import os
import ast
import io
import django.conf
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import calendar
from pathlib import Path
from datetime import date
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
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
from django.db import transaction, IntegrityError
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q, Count
from django.db.models.functions import TruncMonth, TruncDay

# REST Framework Imports
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
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
    if amount is None:
        return "0"

    val = int(round(Decimal(str(amount))))
    s = str(abs(val))

    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        other = s[:-3]
        parts = []

        while len(other) > 2:
            parts.insert(0, other[-2:])
            other = other[:-2]

        parts.insert(0, other)
        formatted = ",".join(parts) + "," + last3

    return f"-{formatted}" if val < 0 else formatted

def format_display_number(num):
    return format_indian_currency(num)

def get_user_branch_context(request):
    """
    Returns the currently selected branch.

    Super Admin:
        - Branch selected -> that Branch object
        - No branch selected -> None

    Normal user:
        - Always returns their assigned branch.
    """
    if not request.user.is_authenticated:
        return None

    profile = getattr(request.user, 'userprofile', None)

    is_super = (
        (profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN)
        or request.user.is_superuser
    )

    if is_super:
        selected_id = request.session.get('selected_branch_id')

        if not selected_id:
            return None

        try:
            return Branch.objects.get(
                id=int(selected_id),
                is_active=True
            )
        except (ValueError, TypeError, Branch.DoesNotExist):
            return None

    return profile.branch if profile else None


@login_required
@require_POST
def switch_branch(request):
    """Switch the active branch for Super Admin users."""

    profile = getattr(request.user, 'userprofile', None)

    is_super = (
        (profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN)
        or request.user.is_superuser
    )

    if is_super:
        branch_id = request.POST.get('branch_id', '').strip()

        if branch_id:
            try:
                branch = Branch.objects.get(
                    id=int(branch_id),
                    is_active=True
                )

                request.session['selected_branch_id'] = str(branch.id)
                request.session.modified = True

            except (ValueError, TypeError, Branch.DoesNotExist):
                request.session.pop('selected_branch_id', None)
                request.session.modified = True
        else:
            request.session.pop('selected_branch_id', None)
            request.session.modified = True

    return redirect(
        request.META.get('HTTP_REFERER', 'yakuza:dashboard')
    )
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
# LOW STOCK NOTIFICATION SYNCHRONIZER
# ==========================================
def sync_low_stock_notifications(branch=None):
    """
    Synchronizes real database stock data with the Notification system.
    Creates, updates, or cleans up Low Stock Notification records for the given branch.
    Only triggers when current_stock == 1 for a specific MODEL + COLOR combination.
    """
    if branch is not None:
        branches = [branch]
    else:
        branches = list(Branch.objects.filter(is_active=True))

    for b in branches:
        # Group available stock by model and color for this branch
        available_stock_qs = (
            Stock.objects.filter(
                branch=b,
                stock_status=Stock.StockStatus.AVAILABLE
            )
            .values('model__id', 'model__model_name', 'color__id', 'color__color_name')
            .annotate(current_stock=Count('id'))
            .filter(current_stock=1)  # EXACTLY 1 MODEL IN STOCK
        )

        active_low_stock_titles = set()

        for item in available_stock_qs:
            model_name = item['model__model_name'] or 'Vehicle'
            color_name = item['color__color_name'] or 'N/A'
            
            # Format title and message using dynamic database values
            title = f"Low Stock Alert: {model_name} ({color_name})"
            message = f"Low Stock Alert: {model_name} ({color_name}) have only 1 model."
            
            active_low_stock_titles.add(title)

            # Prevent duplicate notifications for the same branch + model + color
            notif, created = Notification.objects.get_or_create(
                branch=b,
                notification_type=Notification.NotificationType.LOW_STOCK,
                title=title,
                defaults={
                    'message': message,
                    'is_read': False
                }
            )
            
            # Update existing notification message if needed
            if not created and notif.message != message:
                notif.message = message
                notif.save(update_fields=['message'])

        # Remove notifications where current_stock is no longer equal to 1 (e.g. stock becomes 2 or more, or 0)
        Notification.objects.filter(
            branch=b,
            notification_type=Notification.NotificationType.LOW_STOCK
        ).exclude(title__in=active_low_stock_titles).delete()


def check_and_create_low_stock_notifications(branch=None):
    """
    Wrapper function calling the synchronizer logic.
    """
    sync_low_stock_notifications(branch=branch)

# ==========================================
# REST FRAMEWORK VIEWSETS
# ==========================================

class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()  # Router ne basename shodhma help karva maate
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        user_profile = getattr(user, 'userprofile', None)

        if user.is_superuser or (user_profile and user_profile.role == UserProfile.RoleChoices.SUPER_ADMIN):
            return UserProfile.objects.all()

        user_branch = get_user_branch_context(self.request)
        if user_branch:
            return UserProfile.objects.filter(branch=user_branch)

        return UserProfile.objects.none()
    
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
        # NOTE: must return EVERY active color valid for this branch --
        # both branch-specific colors and legacy/global colors (branch is
        # NULL). Previously this filtered on `branch=branch` only, which
        # silently hid any color created before per-branch color scoping
        # existed, making it look like "only the latest color" was
        # available. See utils.get_visible_vehicle_colors for the single
        # source of truth used by the Purchase page too.
        branch = get_user_branch_context(self.request)
        from .utils import get_visible_vehicle_colors
        return get_visible_vehicle_colors(branch)

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
            # Color may legitimately be a legacy/global master record
            # (branch_id is None) -- only reject a color that belongs to
            # a *different* branch. Model allocation is unaffected by
            # this fix and keeps its existing strict-branch check.
            color_branch_id = item['color'].branch_id
            if item['model'].branch_id != branch.id or color_branch_id not in (branch.id, None):
                from rest_framework.exceptions import ValidationError
                raise ValidationError('Selected model or color is not available in the current branch.')
            
        invoice_date = self.request.data.get('invoice_date')
        save_kwargs = {'created_by': user, 'branch': branch}
        
        if invoice_date and not serializer.validated_data.get('purchase_date'):
            save_kwargs['purchase_date'] = invoice_date

        serializer.save(**save_kwargs)


# yakuza/views.py

class StockViewSet(viewsets.ModelViewSet):
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Stock.objects.select_related('branch', 'model', 'color', 'company').all()
        
        # Frontend માંથી all_branches=true પેરામીટર આવે છે કે નહીં તે ચેક કરો
        show_all = self.request.query_params.get('all_branches', 'false').lower() == 'true'
        
        # યુઝરની પ્રોફાઇલમાંથી બ્રાન્ચ મેળવો
        user_profile = getattr(self.request.user, 'userprofile', None)
        user_branch = user_profile.branch if user_profile else None
        
        # જો superuser કે super_admin ન હોય અને all_branches=true ન મોકલ્યું હોય, તો જ કરન્ટ બ્રાન્ચ ફિલ્ટર કરો
        is_super_admin = self.request.user.is_superuser or (user_profile and user_profile.role == 'SUPER_ADMIN')

        if not show_all and not is_super_admin and user_branch is not None:
            queryset = queryset.filter(branch=user_branch)
            
        # સર્ચ કરવા માટેનું લોજિક
        search_query = self.request.query_params.get('search', None) or self.request.query_params.get('q', None)
        if search_query:
            queryset = queryset.filter(
                Q(model__model_name__icontains=search_query) |
                Q(color__color_name__icontains=search_query) |
                Q(chassis_number__icontains=search_query)
            )

        return queryset

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

        expenses_qs = Expense.objects.all()
        if branch is not None:
            expenses_qs = expenses_qs.filter(branch=branch)
        elif branch_id:
            expenses_qs = expenses_qs.filter(branch_id=branch_id)

        if start_date:
            expenses_qs = expenses_qs.filter(expense_date__gte=start_date)
        if end_date:
            expenses_qs = expenses_qs.filter(expense_date__lte=end_date)

        total_sales = sales_qs.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        # Calculate purchase cost directly from sold stock attached to filtered sales
        total_purchase_cost = sales_qs.aggregate(total=Sum('stock__purchase_price'))['total'] or Decimal('0.00')
        total_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        gross_profit = total_sales - total_purchase_cost
        net_profit = gross_profit - total_expenses

        # Safe Margin Calculation
        profit_margin = (net_profit / total_sales * 100) if total_sales > 0 else Decimal('0.00')

        report_data = {
            'total_sales': total_sales,
            'total_purchase_cost': total_purchase_cost,
            'gross_profit': gross_profit,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
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

    sync_low_stock_notifications(branch)

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

    total_purchase_val = purchase_item_qs.aggregate(
    total=Sum('subtotal')
)['total'] or Decimal('0.00')


    sold_stock_qs = stock_qs.filter(stock_status=Stock.StockStatus.SOLD)
    sold_cost = sold_stock_qs.aggregate(total=Sum('purchase_price'))['total'] or Decimal('0.00')
    total_profit_val = total_sales_val - sold_cost

    # Safe Profit Margin Calculation
    if total_sales_val > 0:
        profit_margin_val = (total_profit_val / total_sales_val) * Decimal('100')
    else:
        profit_margin_val = Decimal('0.00')

    total_vehicles_formatted = format_display_number(total_vehicles_count)
    total_sales_formatted = format_indian_currency(total_sales_val)
    total_purchases_formatted = format_indian_currency(total_purchase_val)
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
        
        pur.computed_total = pur.items.aggregate(total=Sum('subtotal'))['total'] or Decimal('0.00')

    edit_id = request.GET.get('edit_id')
    edit_sale = Sales.objects.filter(id=edit_id).first() if edit_id else None

    available_model_ids = set(available_stock_qs.values_list('model_id', flat=True).distinct())
    available_color_ids = set(available_stock_qs.values_list('color_id', flat=True).distinct())

    if edit_sale and edit_sale.stock:
        if edit_sale.stock.model_id:
            available_model_ids.add(edit_sale.stock.model_id)
        if edit_sale.stock.color_id:
            available_color_ids.add(edit_sale.stock.color_id)

    models_qs = VehicleModel.objects.filter(id__in=available_model_ids, is_active=True)
    colors_qs = VehicleColor.objects.filter(id__in=available_color_ids, is_active=True)

    context = {
        'total_vehicles': total_vehicles_formatted,
        'total_sales': total_sales_formatted,
        'total_purchases': total_purchases_formatted,
        'total_profit': total_profit_formatted,
        'profit_margin': profit_margin_val,
        'sales_chart_labels': json.dumps(chart_labels),
        'sales_chart_data': json.dumps(chart_data),
        'stock_model_labels': json.dumps(stock_model_labels),
        'stock_model_counts': json.dumps(stock_model_counts),
        'total_available_raw': total_vehicles_count,
        'low_stock_items': low_stock_items,
        'recent_sales': recent_sales,
        'recent_purchases': recent_purchases,
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
def _parse_vehicle_line_items(vehicle_items, branch):
    """
    Flattens the same 'vehicle_items_json' payload shape used by the Purchase
    page (one row per model, exploded into one or more color allocations)
    into a flat list of {model_id, color_id, quantity, unit_price} dicts.

    This is the single source of truth for interpreting that payload, used
    by BOTH the create flow and the edit flow, so the two never disagree on
    how a vehicle entry maps to PurchaseItem/Stock rows.
    """
    if not vehicle_items or not isinstance(vehicle_items, list):
        raise ValueError("At least one vehicle entry is required.")

    flattened = []

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

            # Legacy/global colors (branch is NULL) are valid too
            color_obj = VehicleColor.objects.get(
                Q(branch=branch) | Q(branch__isnull=True),
                id=color_id,
                is_active=True,
            )

            flattened.append({
                'model': vehicle_model,
                'color': color_obj,
                'quantity': alloc_qty,
                'unit_price': unit_price,
            })
            alloc_total_qty += alloc_qty

        if alloc_total_qty <= 0:
            raise ValueError(f"No valid color quantity allocated for model '{vehicle_model.model_name}'.")

    if not flattened:
        raise ValueError("At least one valid vehicle color allocation is required.")

    return flattened


def _reconcile_purchase_items_and_stock(purchase, branch, line_items):
    """
    THE single source of truth for Purchase Edit stock reconciliation.

    Brings the PurchaseItem + Stock rows of an existing `purchase` to match
    the desired final state described by `line_items` (as produced by
    `_parse_vehicle_line_items`), reversing whatever the OLD allocation was
    and applying the NEW allocation -- without ever double-counting stock.

    Matching key: (model_id, color_id). For each key:
      - If a PurchaseItem already exists for that (model, color) on this
        purchase, it is UPDATED IN PLACE (never deleted+recreated), and its
        AVAILABLE Stock rows are grown/shrunk to match the new quantity
        (net change only -- e.g. 5 -> 8 adds exactly 3, 8 -> 5 removes
        exactly 3). SOLD stock rows are never touched or deleted.
      - If no PurchaseItem exists yet for that key (e.g. model/color was
        changed to something new), a new PurchaseItem + AVAILABLE Stock rows
        are created for it -- this is the "apply new allocation" half of a
        model/color change.
      - Any PurchaseItem that existed before but is no longer present in the
        desired state (e.g. the old model/color of a changed entry) is
        removed along with its AVAILABLE Stock rows -- this is the "reverse
        old allocation" half of a model/color change.

    A quantity reduction (or removal) that would require deleting more units
    than are currently AVAILABLE (i.e. some units of that exact
    model+color+purchase-item are already SOLD) is rejected with a
    ValueError, which the caller turns into a 400 + full transaction
    rollback -- sold stock is never silently deleted or reassigned.
    """
    desired = {}
    for li in line_items:
        key = (li['model'].id, li['color'].id)
        entry = desired.setdefault(key, {'model': li['model'], 'color': li['color'], 'quantity': 0, 'unit_price': li['unit_price']})
        entry['quantity'] += li['quantity']
        entry['unit_price'] = li['unit_price']

    existing_items = list(
        purchase.items.select_related('model', 'color', 'company').all()
    )
    existing_by_key = {}
    for it in existing_items:
        existing_by_key.setdefault((it.model_id, it.color_id), []).append(it)

    handled_keys = set()

    for key, data in desired.items():
        vehicle_model = data['model']
        color_obj = data['color']
        new_qty = data['quantity']
        new_price = data['unit_price']

        items_for_key = existing_by_key.get(key, [])

        if items_for_key:
            # UPDATE existing PurchaseItem in place -- never create a duplicate.
            item = items_for_key[0]
            handled_keys.add(key)
            old_qty = item.quantity

            sold_count = Stock.objects.filter(purchase_item=item, stock_status=Stock.StockStatus.SOLD).count()
            if new_qty < sold_count:
                raise ValueError(
                    f"Cannot reduce quantity for '{vehicle_model.model_name} ({color_obj.color_name})' below "
                    f"{sold_count} unit(s) that are already sold."
                )

            item.company = vehicle_model.company
            item.model = vehicle_model
            item.color = color_obj
            item.purchase_price = new_price
            item.quantity = new_qty
            item.save()  # recalculates subtotal/total_amount via PurchaseItem.save()

            # Keep AVAILABLE stock in sync with the (possibly changed) model/color/price.
            Stock.objects.filter(purchase_item=item, stock_status=Stock.StockStatus.AVAILABLE).update(
                branch=branch, company=vehicle_model.company, model=vehicle_model,
                color=color_obj, purchase_price=new_price,
            )

            if new_qty > old_qty:
                # Reverse nothing -- simply APPLY the extra new units.
                diff = new_qty - old_qty
                Stock.objects.bulk_create([
                    Stock(
                        purchase_item=item, branch=branch, company=vehicle_model.company,
                        model=vehicle_model, color=color_obj, purchase_price=new_price,
                        stock_status=Stock.StockStatus.AVAILABLE,
                        chassis_number=None, battery_number=None, motor_number=None, controller_number=None,
                    )
                    for _ in range(diff)
                ])
            elif new_qty < old_qty:
                # REVERSE exactly the removed units (only ever AVAILABLE, never SOLD).
                diff = old_qty - new_qty
                removable_ids = list(
                    Stock.objects.filter(purchase_item=item, stock_status=Stock.StockStatus.AVAILABLE)
                    .order_by('-id').values_list('id', flat=True)[:diff]
                )
                if len(removable_ids) < diff:
                    raise ValueError(
                        f"Cannot reduce quantity for '{vehicle_model.model_name} ({color_obj.color_name})' -- "
                        f"not enough available (unsold) stock to remove."
                    )
                Stock.objects.filter(id__in=removable_ids).delete()
            # new_qty == old_qty: quantity unchanged, only price/model/color (if any) applied above.

        else:
            # New (model, color) combination for this purchase -- APPLY new allocation from scratch.
            item = PurchaseItem.objects.create(
                purchase=purchase, company=vehicle_model.company, model=vehicle_model,
                color=color_obj, quantity=new_qty, purchase_price=new_price,
            )
            Stock.objects.bulk_create([
                Stock(
                    purchase_item=item, branch=branch, company=vehicle_model.company,
                    model=vehicle_model, color=color_obj, purchase_price=new_price,
                    stock_status=Stock.StockStatus.AVAILABLE,
                    chassis_number=None, battery_number=None, motor_number=None, controller_number=None,
                )
                for _ in range(new_qty)
            ])

    # Anything that existed before but is no longer in the desired state
    # (e.g. the OLD model/color of an entry that was changed) -- REVERSE it fully.
    for key, items_for_key in existing_by_key.items():
        if key in handled_keys:
            continue
        for item in items_for_key:
            sold_count = Stock.objects.filter(purchase_item=item, stock_status=Stock.StockStatus.SOLD).count()
            if sold_count > 0:
                raise ValueError(
                    f"Cannot remove '{item.model.model_name} ({item.color.color_name})' from this purchase -- "
                    f"{sold_count} unit(s) already sold."
                )
            Stock.objects.filter(purchase_item=item, stock_status=Stock.StockStatus.AVAILABLE).delete()
            item.delete()


@login_required
def purchase_page_view(request, purchase_id=None):
    branch = get_user_branch_context(request)

    # ---- Resolve edit target (if any) with strict branch isolation ----
    purchase = None
    if purchase_id is not None:
        purchase = get_object_or_404(
            Purchase.objects.select_related('supplier', 'branch'),
            id=purchase_id
        )
        # A user must not be able to edit another branch's purchase by
        # manually changing the Purchase ID in the URL.
        if not branch or purchase.branch_id != branch.id:
            return HttpResponseForbidden("You do not have permission to edit this purchase.")

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

                raw_items = request.POST.get('vehicle_items_json') or request.POST.get('vehicle_items') or request.POST.get('items') or '[]'
                vehicle_items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
                line_items = _parse_vehicle_line_items(vehicle_items, branch)

                if purchase is not None:
                    # ==========================================
                    # EDIT / UPDATE MODE -- same Purchase ID, no duplicates.
                    # ==========================================
                    # Re-fetch + lock the row for the duration of this transaction so
                    # a double-submit (or two concurrent edits) can't race each other.
                    purchase = Purchase.objects.select_for_update().get(id=purchase.id, branch=branch)

                    purchase.purchase_date = purchase_date
                    purchase.supplier = supplier
                    purchase.invoice_number = invoice_number
                    purchase.invoice_date = invoice_date
                    if remarks:
                        purchase.remarks = remarks
                    if invoice_photo:
                        purchase.invoice_photo = invoice_photo
                    elif request.POST.get('remove_invoice_photo') == '1':
                        purchase.invoice_photo = None
                    purchase.save()

                    # Reverse OLD stock effect + apply NEW stock effect (net-only, atomic).
                    _reconcile_purchase_items_and_stock(purchase, branch, line_items)

                    redirect_url = reverse('yakuza:purchase_history')
                    return JsonResponse({'success': True, 'purchase_id': purchase.id, 'purchase_number': purchase.purchase_number, 'redirect_url': redirect_url, 'mode': 'update'})

                # ==========================================
                # CREATE MODE -- unchanged from the original implementation.
                # ==========================================
                purchase_number = f"PUR-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
                while Purchase.objects.filter(purchase_number=purchase_number).exists():
                    purchase_number = f"PUR-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

                new_purchase = Purchase.objects.create(
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

                for li in line_items:
                    purchase_item = PurchaseItem.objects.create(
                        purchase=new_purchase,
                        company=li['model'].company,
                        model=li['model'],
                        color=li['color'],
                        quantity=li['quantity'],
                        purchase_price=li['unit_price']
                    )

                    stock_items = [
                        Stock(
                            purchase_item=purchase_item,
                            branch=branch,
                            company=li['model'].company,
                            model=li['model'],
                            color=li['color'],
                            purchase_price=li['unit_price'],
                            stock_status=Stock.StockStatus.AVAILABLE,
                            chassis_number=None,
                            battery_number=None,
                            motor_number=None,
                            controller_number=None,
                        )
                        for _ in range(li['quantity'])
                    ]
                    Stock.objects.bulk_create(stock_items)

                redirect_url = reverse('yakuza:purchase_history')
                return JsonResponse({'success': True, 'purchase_id': new_purchase.id, 'purchase_number': new_purchase.purchase_number, 'redirect_url': redirect_url, 'mode': 'create'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    suppliers = Supplier.objects.filter(is_active=True, branch=branch) if branch else Supplier.objects.none()
    models = VehicleModel.objects.filter(is_active=True, branch=branch) if branch else VehicleModel.objects.none()

    from .utils import get_visible_vehicle_colors
    colors = get_visible_vehicle_colors(branch)

    context = {'suppliers': suppliers, 'models': models, 'colors': colors, 'purchase': purchase}

    if purchase is not None:
        # Build the pre-fill payload for the Vehicle Entries table: one row
        # per model (matching how the page groups entries), each carrying
        # its existing color allocations -- exactly what the JS needs to
        # reconstruct `vehicleEntries` on load.
        existing_items_qs = purchase.items.select_related('model', 'color', 'company').order_by('id')
        grouped = {}
        order = []
        for it in existing_items_qs:
            if it.model_id not in grouped:
                grouped[it.model_id] = {
                    'id': f've_existing_{it.model_id}',
                    'modelId': str(it.model_id),
                    'modelName': it.model.model_name,
                    'quantity': 0,
                    'unitPrice': float(it.purchase_price),
                    'totalAmount': 0,
                    'colorAllocations': [],
                }
                order.append(it.model_id)
            grouped[it.model_id]['quantity'] += it.quantity
            grouped[it.model_id]['colorAllocations'].append({
                'colorId': str(it.color_id),
                'colorName': it.color.color_name,
                'quantity': it.quantity,
            })

        existing_items_list = []
        for model_id in order:
            g = grouped[model_id]
            g['totalAmount'] = round(g['quantity'] * g['unitPrice'], 2)
            existing_items_list.append(g)

        context['existing_items_json'] = json.dumps(existing_items_list)

    return render(request, 'yakuza/purchase.html', context)

@transaction.atomic
def repair_missing_stock():
    created_count = 0
    items = PurchaseItem.objects.select_related('purchase', 'company', 'model', 'color').all()
    
    for item in items:
        # Currently existing stock rows for this purchase item
        existing_stock_count = Stock.objects.filter(purchase_item=item).count()
        missing_qty = item.quantity - existing_stock_count
        
        if missing_qty > 0:
            new_stocks = [
                Stock(
                    purchase_item=item,
                    branch=item.purchase.branch,
                    company=item.company,
                    model=item.model,
                    color=item.color,
                    purchase_price=item.purchase_price,
                    stock_status=Stock.StockStatus.AVAILABLE,
                    chassis_number=None,
                    battery_number=None,
                    motor_number=None,
                    controller_number=None,
                )
                for _ in range(missing_qty)
            ]
            Stock.objects.bulk_create(new_stocks)
            created_count += missing_qty
            print(f"Repaired: Added {missing_qty} missing stock rows for Item ID {item.id} ({item.model.model_name} - {item.color.color_name})")

    print(f"Total Repaired Stock Rows: {created_count}")


#repair_missing_stock()

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
@require_POST
def edit_model_ajax(request, model_id):
    """
    Corrects the spelling of an EXISTING VehicleModel IN PLACE.

    Data-safety guarantees:
      - The VehicleModel row is UPDATED, never deleted+recreated.
      - Its primary key never changes.
      - `branch` and `company` are left untouched, so every Purchase,
        PurchaseItem, and Stock row that references this model via FK keeps
        working unchanged and automatically shows the corrected name the
        next time it's displayed (they store the model_id, not a copy of
        the name).
    """
    branch = get_user_branch_context(request)
    if not branch:
        return JsonResponse({'success': False, 'error': 'Select a specific branch before editing a model.'}, status=400)

    model_obj = get_object_or_404(VehicleModel, id=model_id)

    # Branch isolation: a user must not be able to edit another branch's
    # model, even by guessing/typing its ID directly into the AJAX URL.
    if model_obj.branch_id != branch.id:
        return JsonResponse({'success': False, 'error': 'You do not have permission to edit this model.'}, status=403)

    new_name = None
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            new_name = data.get('model_name') or data.get('name')
        except Exception:
            pass
    if not new_name:
        new_name = request.POST.get('model_name') or request.POST.get('name')

    if not new_name or not new_name.strip():
        return JsonResponse({'success': False, 'error': 'Model name is required.'}, status=400)

    new_name_clean = new_name.strip()

    # Prevent duplicate ACTIVE model names within the same branch (and same
    # company, matching the existing create-time scoping), case-insensitive,
    # excluding this model itself.
    duplicate_exists = VehicleModel.objects.filter(
        branch=branch, company=model_obj.company, model_name__iexact=new_name_clean, is_active=True
    ).exclude(id=model_obj.id).exists()
    if duplicate_exists:
        return JsonResponse({'success': False, 'error': f"A model named '{new_name_clean}' already exists in this branch."}, status=400)

    try:
        with transaction.atomic():
            model_obj.model_name = new_name_clean
            model_obj.save(update_fields=['model_name'])
    except IntegrityError:
        return JsonResponse({'success': False, 'error': f"A model named '{new_name_clean}' already exists in this branch."}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': True, 'id': model_obj.id, 'name': model_obj.model_name})


@login_required
@require_POST
def edit_color_ajax(request, color_id):
    """
    Corrects the spelling of an EXISTING VehicleColor IN PLACE.

    Data-safety guarantees:
      - The VehicleColor row is UPDATED, never deleted+recreated.
      - Its primary key never changes.
      - `branch` is left untouched -- a global color (branch IS NULL) stays
        global, a branch-specific color keeps its existing branch -- so
        every Purchase/PurchaseItem/Stock row referencing this color via FK
        keeps working unchanged.
    """
    branch = get_user_branch_context(request)
    if not branch:
        return JsonResponse({'success': False, 'error': 'Select a specific branch before editing a color.'}, status=400)

    color_obj = get_object_or_404(VehicleColor, id=color_id)

    # Branch isolation: the current branch's own colors, and legacy/global
    # colors (branch IS NULL) which the Purchase page already treats as
    # visible/usable from every branch -- but never another branch's color.
    if color_obj.branch_id is not None and color_obj.branch_id != branch.id:
        return JsonResponse({'success': False, 'error': 'You do not have permission to edit this color.'}, status=403)

    new_name = None
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            new_name = data.get('color_name') or data.get('name') or data.get('colorName')
        except Exception:
            pass
    if not new_name:
        new_name = request.POST.get('color_name') or request.POST.get('name') or request.POST.get('colorName')

    if not new_name or not new_name.strip():
        return JsonResponse({'success': False, 'error': 'Color name is required.'}, status=400)

    new_name_clean = new_name.strip()

    # Duplicate check scoped exactly the way this color is scoped (its own
    # branch, or global if branch IS NULL) -- never scoped to the editor's
    # current branch, since that could wrongly flag/miss global colors.
    duplicate_exists = VehicleColor.objects.filter(
        branch=color_obj.branch, color_name__iexact=new_name_clean, is_active=True
    ).exclude(id=color_obj.id).exists()
    if duplicate_exists:
        return JsonResponse({'success': False, 'error': f"A color named '{new_name_clean}' already exists."}, status=400)

    try:
        with transaction.atomic():
            color_obj.color_name = new_name_clean
            color_obj.save(update_fields=['color_name'])
    except IntegrityError:
        return JsonResponse({'success': False, 'error': f"A color named '{new_name_clean}' already exists."}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': True, 'id': color_obj.id, 'name': color_obj.color_name})


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
       
        purchase.computed_total = sum(item.subtotal for item in purchase.items.all())

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

            if not customer_name or not contact_number or not model_name or price_val <= 0 or not chassis_number:
                return JsonResponse({'status': 'error', 'message': 'Please fill all required fields correctly.'}, status=400)

            existing_sale = None
            if sale_id and str(sale_id).isdigit():
                existing_sale = get_object_or_404(Sales, id=int(sale_id))
                if branch is not None and existing_sale.stock and existing_sale.stock.branch != branch:
                    return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

            payment_type_map = {'Cash': Sales.PaymentMethod.CASH, 'UPI': Sales.PaymentMethod.UPI, 'EMI': Sales.PaymentMethod.EMI}
            payment_method = payment_type_map.get(payment_type, Sales.PaymentMethod.CASH)

            
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
                sale.stock = stock_obj
                sale.save()
               
            else:
                prefix = (invoice_setting.invoice_prefix if invoice_setting and invoice_setting.invoice_prefix else (sys_settings.invoice_prefix if sys_settings else "INV-")) or "INV-"
                year = timezone.now().year

                if prefix.endswith(f"{year}-"):
                    auto_inv = f"{prefix}{(Sales.objects.count() + 1):04d}"
                else:
                    auto_inv = f"{prefix}{year}-{(Sales.objects.count() + 1):04d}"
                sale = Sales.objects.create(
                    stock=stock_obj,
                    customer_name=customer_name,
                    mobile_number=contact_number,
                    aadhar_number=aadhar_number,
                    invoice_no=auto_inv,
                    payment_method=payment_method,
                    selling_price=price_val,
                    created_by=request.user
                )
                         

            stock_obj.stock_status = Stock.StockStatus.SOLD
            stock_obj.sale = sale
            stock_obj.save()
            
           
            b_name = branch.branch_name if branch else "Main Branch"

            # Customer must always be resolved inside the current branch.
            customer_qs = Customer.objects.filter(
                mobile_number=contact_number
            )

            if branch is not None:
                customer_qs = customer_qs.filter(branch=branch)

            existing_customer = customer_qs.first()

            if existing_customer:
                existing_customer.customer_name = customer_name
                existing_customer.aadhar_number = aadhar_number
                existing_customer.branch = branch
                existing_customer.branch_name = b_name
                existing_customer.model_name = stock_obj.model.model_name
                existing_customer.price = price_val
                existing_customer.payment_mode = sale.get_payment_method_display()
                existing_customer.save()

                

            else:
                customer = Customer.objects.create(
                    mobile_number=contact_number,
                    customer_name=customer_name,
                    aadhar_number=aadhar_number,
                    branch=branch,
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
                'grand_total': f"{getattr(sale, 'grand_total'):.2f}",
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
    year = timezone.now().year

    if edit_sale:
        auto_invoice_no = edit_sale.invoice_no
    elif prefix.endswith(f"{year}-"):
        auto_invoice_no = f"{prefix}{(Sales.objects.count() + 1):04d}"
    else:
        auto_invoice_no = f"{prefix}{year}-{(Sales.objects.count() + 1):04d}"

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

    cust_name_clean = (
        sale.customer_name or "Customer"
    ).strip().replace(" ", "_")

    inv_no_clean = str(
        sale.invoice_no or sale.id
    ).replace("/", "_")

    custom_filename = f"{cust_name_clean}-{inv_no_clean}.pdf"

    # ---------------------------------------------------------
    # PDF already created hoy to return saved PDF
    # ---------------------------------------------------------
    if sale.invoice_pdf:
        return FileResponse(
            sale.invoice_pdf.open("rb"),
            content_type="application/pdf",
            as_attachment=False,
            filename=custom_filename
        )

    # ---------------------------------------------------------
    # PDF create nathi thayu
    # Template thi navo PDF generate karvano nathi.
    # Customer.js aa response joi ne popup batavse.
    # ---------------------------------------------------------
    return JsonResponse(
        {
            "status": "error",
            "message": "Please Create Sales PDF first"
        },
        status=404
    )

@login_required
def customer(request):
    branch = get_user_branch_context(request)

    sales_qs = (
        Sales.objects
        .select_related(
            'stock',
            'stock__model',
            'stock__color',
            'stock__branch'
        )
        .order_by('-id')
    )

    if branch is not None:
        sales_qs = sales_qs.filter(stock__branch=branch)

    # Invoice Settings
    invoice_setting = InvoiceSetting.objects.first()

    return render(
        request,
        'yakuza/customer.html',
        {
            'customers': sales_qs,
            'vehicle_models': VehicleModel.objects.filter(is_active=True),
            'invoice_setting': invoice_setting,
            'branch': branch,
        }
    )

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
    monthly_purchase = curr_month_purchase_qs.aggregate(total=Sum('subtotal'))['total'] or Decimal('0.00')

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
        d_purchases = filtered_purchases.filter(purchase__purchase_date=curr_dt).aggregate(t=Sum('subtotal'))['t'] or Decimal('0.00')
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



def setup_unicode_fonts():
    """
    Checks if Unicode font exists in static/fonts/. 
    If found, registers it; otherwise safely defaults to Helvetica.
    """
    font_name = 'Helvetica'
    font_name_bold = 'Helvetica-Bold'

    try:
        base_dir = django_settings.BASE_DIR
    except Exception:
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent.parent

    font_path = os.path.join(base_dir, 'static', 'fonts', 'DejaVuSans.ttf')
    font_bold_path = os.path.join(base_dir, 'static', 'fonts', 'DejaVuSans-Bold.ttf')

    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        font_name = 'DejaVuSans'

    if os.path.exists(font_bold_path):
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_bold_path))
        font_name_bold = 'DejaVuSans-Bold'

    return font_name, font_name_bold

@login_required
def generate_reports_pdf(request):

    font_regular, font_bold = setup_unicode_fonts()

    date_from_str = request.GET.get("date_from", "").strip()
    date_to_str = request.GET.get("date_to", "").strip()

    today = date.today()

    try:
        start_date = (
            datetime.strptime(date_from_str, "%Y-%m-%d").date()
            if date_from_str
            else today.replace(day=1)
        )
    except ValueError:
        start_date = today.replace(day=1)

    try:
        end_date = (
            datetime.strptime(date_to_str, "%Y-%m-%d").date()
            if date_to_str
            else today
        )
    except ValueError:
        end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    branch = get_user_branch_context(request)

    sales_qs = Sales.objects.all()
    purchase_item_qs = PurchaseItem.objects.all()
    expense_qs = Expense.objects.all()

    if branch is not None:
        sales_qs = sales_qs.filter(stock__branch=branch)
        purchase_item_qs = purchase_item_qs.filter(purchase__branch=branch)
        expense_qs = expense_qs.filter(branch=branch)

    sales_qs = sales_qs.filter(
        invoice_date__gte=start_date,
        invoice_date__lte=end_date,
    )

    purchase_item_qs = purchase_item_qs.filter(
        purchase__purchase_date__gte=start_date,
        purchase__purchase_date__lte=end_date,
    )

    expense_qs = expense_qs.filter(
        expense_date__gte=start_date,
        expense_date__lte=end_date,
    )

    sales_by_day = {}

    sales_data = (
        sales_qs
        .values("invoice_date")
        .annotate(total=Sum("grand_total"))
    )

    for item in sales_data:
        sales_by_day[item["invoice_date"]] = (
            item["total"] or Decimal("0.00")
        )

    purchases_by_day = {}

    purchase_data = (purchase_item_qs.values("purchase__purchase_date").annotate(total=Sum("subtotal")))

    for item in purchase_data:
        purchases_by_day[item["purchase__purchase_date"]] = (
            item["total"] or Decimal("0.00")
        )

    expenses_by_day = {}

    expense_data = (
        expense_qs
        .values("expense_date")
        .annotate(total=Sum("amount"))
    )

    for item in expense_data:
        expenses_by_day[item["expense_date"]] = (
            item["total"] or Decimal("0.00")
        )

    response = HttpResponse(
        content_type="application/pdf"
    )

    filename = (
        f"Report_{start_date.strftime('%d-%m-%Y')}_to_"
        f"{end_date.strftime('%d-%m-%Y')}.pdf"
    )

    response['Content-Disposition'] = 'inline; filename="invoice.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    title_style = ParagraphStyle(
        "DocTitle",
        fontName=font_bold,
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1E293B"),
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        fontName=font_regular,
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748B"),
    )

    header_cell_style = ParagraphStyle(
        "HeaderCell",
        fontName=font_bold,
        fontSize=9,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.white,
    )

    month_header_style = ParagraphStyle(
        "MonthHeaderCell",
        fontName=font_bold,
        fontSize=10,
        leading=12,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#0F172A"),
    )

    cell_style_left = ParagraphStyle(
        "CellLeft",
        fontName=font_regular,
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
    )

    cell_style_right = ParagraphStyle(
        "CellRight",
        fontName=font_regular,
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT,
    )

    bold_cell_left = ParagraphStyle(
        "BoldCellLeft",
        fontName=font_bold,
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
    )

    bold_cell_right = ParagraphStyle(
        "BoldCellRight",
        fontName=font_bold,
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT,
    )

    elements = []

    branch_title = (
        branch.branch_name
        if branch
        else "All Branches Summary"
    )

    elements.append(
        Paragraph(
            f"{branch_title} - Financial Report",
            title_style,
        )
    )

    elements.append(
        Paragraph(
            f"Period: {start_date.strftime('%d-%m-%Y')} "
            f"to {end_date.strftime('%d-%m-%Y')}",
            subtitle_style,
        )
    )

    elements.append(Spacer(1, 15))

    # ---------------------------------------------------------
    # COLUMN ORDER:
    # DATE → PURCHASE → SALES → EXPENSE → NET PROFIT
    # ---------------------------------------------------------

    table_data = [
        [
            Paragraph("Date", header_cell_style),
            Paragraph("Purchase", header_cell_style),
            Paragraph("Sales", header_cell_style),
            Paragraph("Expense", header_cell_style),
            Paragraph("Net Profit", header_cell_style),
        ]
    ]

    current_date = start_date
    current_month_key = None

    m_purchase = Decimal("0.00")
    m_sales = Decimal("0.00")
    m_expense = Decimal("0.00")
    m_profit = Decimal("0.00")

    g_purchase = Decimal("0.00")
    g_sales = Decimal("0.00")
    g_expense = Decimal("0.00")
    g_profit = Decimal("0.00")

    style_commands = [
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#1E293B"),
        ),
        (
            "ALIGN",
            (0, 0),
            (-1, -1),
            "CENTER",
        ),
        (
            "VALIGN",
            (0, 0),
            (-1, -1),
            "MIDDLE",
        ),
        (
            "BOTTOMPADDING",
            (0, 0),
            (-1, -1),
            4,
        ),
        (
            "TOPPADDING",
            (0, 0),
            (-1, -1),
            4,
        ),
        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.5,
            colors.HexColor("#CBD5E1"),
        ),
    ]

    row_idx = 1

    while current_date <= end_date:

        month_key = (
            current_date.year,
            current_date.month,
        )

        if current_month_key != month_key:

            if current_month_key is not None:

                month_name = calendar.month_name[
                    current_month_key[1]
                ].upper()

                table_data.append(
                    [
                        Paragraph(
                            f"{month_name} "
                            f"{current_month_key[0]} TOTAL",
                            bold_cell_left,
                        ),
                        Paragraph(
                            f"RS. {format_indian_currency(m_purchase)}",
                            bold_cell_right,
                        ),
                        Paragraph(
                            f"RS. {format_indian_currency(m_sales)}",
                            bold_cell_right,
                        ),
                        Paragraph(
                            f"RS. {format_indian_currency(m_expense)}",
                            bold_cell_right,
                        ),
                        Paragraph(
                            f"RS. {format_indian_currency(m_profit)}",
                            bold_cell_right,
                        ),
                    ]
                )

                style_commands.append(
                    (
                        "BACKGROUND",
                        (0, row_idx),
                        (-1, row_idx),
                        colors.HexColor("#E2E8F0"),
                    )
                )

                row_idx += 1

                table_data.append(
                    ["", "", "", "", ""]
                )

                style_commands.append(
                    (
                        "SPAN",
                        (0, row_idx),
                        (-1, row_idx),
                    )
                )

                row_idx += 1

                m_purchase = Decimal("0.00")
                m_sales = Decimal("0.00")
                m_expense = Decimal("0.00")
                m_profit = Decimal("0.00")

            current_month_key = month_key

            month_name = calendar.month_name[
                current_month_key[1]
            ].upper()

            table_data.append(
                [
                    Paragraph(
                        f"{month_name} "
                        f"{current_month_key[0]}",
                        month_header_style,
                    ),
                    "",
                    "",
                    "",
                    "",
                ]
            )

            style_commands.append(
                (
                    "SPAN",
                    (0, row_idx),
                    (-1, row_idx),
                )
            )

            style_commands.append(
                (
                    "BACKGROUND",
                    (0, row_idx),
                    (-1, row_idx),
                    colors.HexColor("#F1F5F9"),
                )
            )

            row_idx += 1

        d_purchase = purchases_by_day.get(
            current_date,
            Decimal("0.00"),
        )

        d_sale = sales_by_day.get(
            current_date,
            Decimal("0.00"),
        )

        d_expense = expenses_by_day.get(
            current_date,
            Decimal("0.00"),
        )

        d_profit = (
            d_sale
            - d_purchase
            - d_expense
        )

        m_purchase += d_purchase
        m_sales += d_sale
        m_expense += d_expense
        m_profit += d_profit

        g_purchase += d_purchase
        g_sales += d_sale
        g_expense += d_expense
        g_profit += d_profit

        table_data.append(
            [
                Paragraph(
                    current_date.strftime("%d-%m-%Y"),
                    cell_style_left,
                ),
                Paragraph(
                    f"RS. {format_indian_currency(d_purchase)}",
                    cell_style_right,
                ),
                Paragraph(
                    f"RS. {format_indian_currency(d_sale)}",
                    cell_style_right,
                ),
                Paragraph(
                    f"RS. {format_indian_currency(d_expense)}",
                    cell_style_right,
                ),
                Paragraph(
                    f"RS. {format_indian_currency(d_profit)}",
                    cell_style_right,
                ),
            ]
        )

        row_idx += 1
        current_date += timedelta(days=1)

    if current_month_key is not None:

        month_name = calendar.month_name[
            current_month_key[1]
        ].upper()

        table_data.append(
            [
                Paragraph(
                    f"{month_name} "
                    f"{current_month_key[0]} TOTAL",
                    bold_cell_left,
                ),
                Paragraph(
                    f"RS. {format_indian_currency(m_purchase)}",
                    bold_cell_right,
                ),
                Paragraph(
                    f"RS. {format_indian_currency(m_sales)}",
                    bold_cell_right,
                ),
                Paragraph(
                    f"RS. {format_indian_currency(m_expense)}",
                    bold_cell_right,
                ),
                Paragraph(
                    f"RS. {format_indian_currency(m_profit)}",
                    bold_cell_right,
                ),
            ]
        )

        style_commands.append(
            (
                "BACKGROUND",
                (0, row_idx),
                (-1, row_idx),
                colors.HexColor("#E2E8F0"),
            )
        )

        row_idx += 1

        table_data.append(
            ["", "", "", "", ""]
        )

        style_commands.append(
            (
                "SPAN",
                (0, row_idx),
                (-1, row_idx),
            )
        )

        row_idx += 1

    table_data.append(
        [
            Paragraph(
                "GRAND TOTAL",
                bold_cell_left,
            ),
            Paragraph(
                f"RS. {format_indian_currency(g_purchase)}",
                bold_cell_right,
            ),
            Paragraph(
                f"RS. {format_indian_currency(g_sales)}",
                bold_cell_right,
            ),
            Paragraph(
                f"RS. {format_indian_currency(g_expense)}",
                bold_cell_right,
            ),
            Paragraph(
                f"RS. {format_indian_currency(g_profit)}",
                bold_cell_right,
            ),
        ]
    )

    style_commands.append(
        (
            "BACKGROUND",
            (0, row_idx),
            (-1, row_idx),
            colors.HexColor("#CBD5E1"),
        )
    )

    # Date column thodi nani, amount columns equal.
    col_widths = [
        110,
        150,
        150,
        150,
        150,
    ]

    report_table = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=1,
    )

    report_table.setStyle(
        TableStyle(style_commands)
    )

    elements.append(report_table)

    doc.build(elements)

    return response
# ==========================================
# SETTINGS & CONFIGURATIONS
# ==========================================
@login_required
def settings(request):
    current_branch = get_user_branch_context(request)
    user_profile = getattr(request.user, 'userprofile', None)
    branches = Branch.objects.all()
    
    # Group live stock data branch-wise: Only AVAILABLE Stock
    branch_stock_data = []
    for branch in branches:
        items = Stock.objects.filter(
            branch=branch,
            stock_status=Stock.StockStatus.AVAILABLE
        ).values(
            model_name=F('model__model_name'),
            color_name=F('color__color_name')
        ).annotate(quantity=Count('id'))
        
        total_quantity = sum(item['quantity'] for item in items)
        
        branch_stock_data.append({
            'branch': branch,
            'items': items,
            'total_quantity': total_quantity
        })

    if request.user.is_superuser or (user_profile and user_profile.role == UserProfile.RoleChoices.SUPER_ADMIN):
        # Super Admin sees ALL users
        users_list = User.objects.select_related('userprofile', 'userprofile__branch').all()
    elif current_branch:
        # Branch Admin / Regular user sees ONLY users from their branch
        users_list = User.objects.select_related('userprofile', 'userprofile__branch').filter(
            userprofile__branch=current_branch
        )
    else:
        # Fallback if no branch assigned
        users_list = User.objects.none()

    # Other settings context
    invoice_settings = InvoiceSetting.objects.filter(branch=current_branch).first() if current_branch else InvoiceSetting.objects.first()
    settings_obj = Settings.objects.first()
    audit_logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:50]
    last_backup = BackupHistory.objects.order_by('-created_at').first()

    context = {
        'current_branch': current_branch,
        'user_profile': user_profile,
        'users_list': users_list,
        'invoice_settings': invoice_settings,
        'settings_obj': settings_obj,
        'audit_logs': audit_logs,
        'last_backup': last_backup,
        'branch_stock_data': branch_stock_data,
    }
    return render(request, 'yakuza/settings.html', context)

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
                for dec_key in ['total_amount', 'paid_amount', 'balance_amount']:
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

                for dec_key in ['selling_price', 'total_amount', 'paid_amount', 'balance_amount']:
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

def service_worker(request):
    js = """
const CACHE_NAME = 'gatistvam-pwa-v1';

self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
"""

    response = HttpResponse(js, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response