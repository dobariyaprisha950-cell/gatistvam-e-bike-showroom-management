import datetime
import csv

from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Q
from django.http import HttpResponse

from .models import Notification, Branch, AuditLog


def get_visible_vehicle_colors(branch):
    """
    Centralized, branch-safe VehicleColor lookup.

    Returns every ACTIVE color that is valid for the given branch:
      - colors explicitly created for this branch, AND
      - legacy/global colors created before per-branch color scoping
        existed (branch is NULL) -- these are still valid system-wide
        master data and must never be silently dropped.

    IMPORTANT: This must be the single source of truth for "which colors
    can this branch use" so the Purchase page, the VehicleColor API, and
    purchase submission all agree on the same list. Do NOT replace this
    with `.filter(branch=branch)` alone (drops legacy colors) and never
    slice/limit the result (e.g. `.last()`, `[:1]`, `order_by('-id')[:1]`)
    -- every matching color must be returned.
    """
    if not branch:
        from .models import VehicleColor
        return VehicleColor.objects.none()

    from .models import VehicleColor

    return VehicleColor.objects.filter(
        Q(branch=branch) | Q(branch__isnull=True),
        is_active=True,
    ).order_by('color_name')


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR')


def log_audit(
    request,
    module,
    action,
    details="",
    old_value=None,
    new_value=None,
    target_branch=None,
):
    """
    Centralized AuditLog creation helper.

    IMPORTANT:
    This function matches the current AuditLog model exactly.
    """

    user = request.user if request and request.user.is_authenticated else None

    profile = getattr(user, 'userprofile', None) if user else None

    branch = target_branch or (
        profile.branch if profile else None
    )

    ip = get_client_ip(request) if request else None

    # AuditLog currently stores old/new values as JSONField.
    # Keep details inside the new_value payload rather than trying
    # to write to a non-existent `details` column.
    if new_value is None:
        new_value = {}

    if old_value is None:
        old_value = {}

    if details:
        if isinstance(new_value, dict):
            new_value = {
                **new_value,
                "_details": details,
            }
        else:
            new_value = {
                "_details": details,
                "value": str(new_value),
            }

    return AuditLog.objects.create(
        user=user,
        branch=branch,
        module=module,
        action=action,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip,
    )


def export_audit_logs_excel(queryset):
    """
    Export AuditLog records as CSV.
    """

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="audit_logs.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        'Date Time',
        'User',
        'Role',
        'Branch',
        'Module',
        'Action',
        'Old Value',
        'New Value',
        'IP Address',
    ])

    for log in queryset:

        username = (
            log.user.username
            if log.user
            else "System"
        )

        role = "System"

        if log.user:
            profile = getattr(
                log.user,
                'userprofile',
                None
            )

            if profile:
                role = profile.get_role_display()
            elif log.user.is_superuser:
                role = "Super Admin"

        branch_name = (
            log.branch.branch_name
            if log.branch
            else "Global"
        )

        timestamp = (
            log.timestamp.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if log.timestamp
            else ""
        )

        writer.writerow([
            timestamp,
            username,
            role,
            branch_name,
            log.module,
            log.action,
            log.old_value,
            log.new_value,
            log.ip_address or "",
        ])

    return response


def generate_purchase_number():
    """
    Generate the next purchase number for the current year.
    """

    year = datetime.datetime.now().year

    prefix = f"PUR-{year}-"

    from yakuza.models import Purchase

    last_purchase = (
        Purchase.objects
        .filter(
            purchase_number__startswith=prefix
        )
        .order_by('-id')
        .first()
    )

    if not last_purchase:
        return f"{prefix}000001"

    last_number_str = (
        last_purchase.purchase_number
        .split('-')[-1]
    )

    try:
        new_number = int(last_number_str) + 1
    except (ValueError, TypeError):
        new_number = 1

    return f"{prefix}{new_number:06d}"


def generate_sales_invoice_number():
    """
    Generate the next Sales invoice number.

    IMPORTANT:
    Sales model uses `invoice_no`, not `invoice_number`.
    """

    year = datetime.datetime.now().year

    from yakuza.models import Settings, Sales

    settings = Settings.load()

    prefix_str = (
        settings.invoice_prefix
        or "GTV"
    )

    prefix = f"{prefix_str}-{year}-"

    last_sale = (
        Sales.objects
        .filter(
            invoice_no__startswith=prefix
        )
        .order_by('-id')
        .first()
    )

    if not last_sale:
        return f"{prefix}000001"

    last_number_str = (
        last_sale.invoice_no
        .split('-')[-1]
    )

    try:
        new_number = int(last_number_str) + 1
    except (ValueError, TypeError):
        new_number = 1

    return f"{prefix}{new_number:06d}"


def create_notification(
    title,
    message,
    notification_type,
    branch=None,
):
    """
    Helper function to create a notification.
    """

    return Notification.objects.create(
        title=title,
        message=message,
        notification_type=notification_type,
        branch=branch,
    )


def create_daily_sales_reminder(branch):
    """
    Authoritative, branch-safe daily reminder creation path.
    """

    from decimal import Decimal
    from .models import Sales

    with transaction.atomic():

        locked_branch = (
            Branch.objects
            .select_for_update()
            .filter(
                id=branch.id,
                is_active=True,
            )
            .first()
        )

        if not locked_branch:
            return None, False

        today = timezone.localdate()

        existing = (
            Notification.objects
            .filter(
                branch=locked_branch,
                notification_type=(
                    Notification.NotificationType.REMINDER
                ),
                created_at__date=today,
            )
            .first()
        )

        if existing:
            return existing, False

        sales_qs = Sales.objects.filter(
            stock__branch=locked_branch,
            invoice_date=today,
        )

        total_sales = (
            sales_qs
            .aggregate(
                total=Sum('grand_total')
            )['total']
            or Decimal('0.00')
        )

        total_cost = (
            sales_qs
            .aggregate(
                total=Sum(
                    'stock__purchase_price'
                )
            )['total']
            or Decimal('0.00')
        )

        profit = total_sales - total_cost

        profit_pct = (
            profit / total_sales
            * Decimal('100.00')
        ) if total_sales else Decimal('0.00')

        reminder = Notification.objects.create(
            branch=locked_branch,
            title='⏰ Daily Reminder',
            message=(
                f"Today's Sales: "
                f"₹{total_sales:,.2f}\n\n"
                f"Today's Profit: "
                f"₹{profit:,.2f}\n\n"
                f"Profit Percentage: "
                f"{profit_pct:.2f}%"
            ),
            notification_type=(
                Notification.NotificationType.REMINDER
            ),
            is_read=False,
        )

        return reminder, True


def generate_daily_summary_reminder():
    """
    Backward-compatible caller for the authoritative
    branch-safe reminder flow.
    """

    for branch in Branch.objects.filter(
        is_active=True
    ):
        create_daily_sales_reminder(branch)