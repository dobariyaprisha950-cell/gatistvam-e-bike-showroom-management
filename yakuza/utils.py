import datetime
import csv
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from django.http import HttpResponse
from .models import Notification, Branch, AuditLog


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit(request, module, action, details="", old_value="", new_value="", target_branch=None):
    user = request.user if request and request.user.is_authenticated else None
    username = user.username if user else "Anonymous"
    
    profile = getattr(user, 'userprofile', None) if user else None
    role = profile.get_role_display() if profile else ("Super Admin" if (user and user.is_superuser) else "System")
    
    branch = target_branch or (profile.branch if profile else None)
    branch_name = branch.branch_name if branch else "Global"
    ip = get_client_ip(request) if request else "0.0.0.0"

    return AuditLog.objects.create(
        user=user,
        username=username,
        role=role,
        branch=branch,
        branch_name=branch_name,
        module=module,
        action=action,
        details=details,
        old_value=str(old_value),
        new_value=str(new_value),
        ip_address=ip
    )


def export_audit_logs_excel(queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date Time', 'User', 'Role', 'Branch', 'Module', 'Action', 'Details', 'Old Value', 'New Value', 'IP Address'])

    for log in queryset:
        writer.writerow([
            log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            log.username,
            log.role,
            log.branch_name,
            log.module,
            log.action,
            log.details,
            log.old_value,
            log.new_value,
            log.ip_address
        ])

    return response


def generate_purchase_number():
    year = datetime.datetime.now().year
    prefix = f"PUR-{year}-"
    from yakuza.models import Purchase
    last_purchase = Purchase.objects.filter(purchase_number__startswith=prefix).order_by('-id').first()
    if not last_purchase:
        return f"{prefix}000001"
    
    last_number_str = last_purchase.purchase_number.split('-')[-1]
    new_number = int(last_number_str) + 1
    return f"{prefix}{new_number:06d}"


def generate_sales_invoice_number():
    year = datetime.datetime.now().year
    from yakuza.models import Settings, Sales
    settings = Settings.load()
    prefix_str = settings.invoice_prefix or "GTV"
    prefix = f"{prefix_str}-{year}-"
    
    last_sale = Sales.objects.filter(invoice_number__startswith=prefix).order_by('-id').first()
    if not last_sale:
        return f"{prefix}000001"
    
    last_number_str = last_sale.invoice_number.split('-')[-1]
    new_number = int(last_number_str) + 1
    return f"{prefix}{new_number:06d}"


def create_notification(title, message, notification_type, branch=None):
    """Helper function to create a new notification."""
    return Notification.objects.create(
        title=title,
        message=message,
        notification_type=notification_type,
        branch=branch
    )


def generate_daily_summary_reminder():
    """Generates daily 7:45 PM summary notification per branch or globally."""
    today = timezone.now().date()
    
    from yakuza.models import Purchase, Sales, Expense

    branches = Branch.objects.all()
    for branch in branches:
        todays_purchases = Purchase.objects.filter(branch=branch, purchase_date=today).aggregate(
            total=Sum('items__total_amount')
        )['total'] or 0.0
        
        todays_sales = Sales.objects.filter(stock__branch=branch, invoice_date=today).aggregate(
            total=Sum('grand_total')
        )['total'] or 0.0
        
        todays_expenses = Expense.objects.filter(branch=branch, expense_date=today).aggregate(
            total=Sum('amount')
        )['total'] or 0.0

        message = (
            f"Daily Summary ({today.strftime('%d %b %Y')}):\n"
            f"• Today's Purchase: ₹{todays_purchases:,.2f}\n"
            f"• Today's Sales: ₹{todays_sales:,.2f}\n"
            f"• Today's Expenses: ₹{todays_expenses:,.2f}"
        )

        create_notification(
            title=f"Daily Financial Summary - {branch.branch_name}",
            message=message,
            notification_type=Notification.TYPE_REMINDER,
            branch=branch
        )


def notify_backup_status(is_success, details=""):
    """Call this function when database backup completes."""
    status_str = "Completed Successfully" if is_success else "Failed"
    title = f"Database Backup {status_str}"
    message = f"System backup was triggered and {status_str.lower()}. {details}"
    create_notification(title=title, message=message, notification_type=Notification.TYPE_SYSTEM)


def notify_monthly_report_ready(report_month_name):
    """Call this function when monthly report becomes available."""
    title = f"Monthly Report Available ({report_month_name})"
    message = f"The financial and stock report for {report_month_name} is ready for download."
    create_notification(title=title, message=message, notification_type=Notification.TYPE_REPORT)