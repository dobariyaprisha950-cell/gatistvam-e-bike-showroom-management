from django.db.models.signals import post_save
from django.dispatch import receiver

from yakuza.models import (
    Purchase,
    PurchaseItem,
    Stock,
    Sales,
    Expense,
    Notification,
)
from yakuza.utils import generate_purchase_number

@receiver(post_save, sender=PurchaseItem)
def create_stock_items_on_purchase(sender, instance, created, **kwargs):
    """
    DISABLED: Stock creation for a new PurchaseItem is now handled
    explicitly inside yakuza.views.purchase_page_view(), in the same
    database transaction as the PurchaseItem itself. That is now the single
    authoritative Purchase -> Stock creation path.

    This receiver is intentionally left as a no-op (rather than removed) so
    that if anything else in the project still references or connects this
    signal, it does not silently create a second, duplicate set of Stock
    rows (2x quantity) alongside the explicit creation in the view.
    """
    return


@receiver(post_save, sender=Purchase)
def handle_purchase_post_save(sender, instance, created, **kwargs):
    """
    Post save triggers for Purchase logging and auto number assignment
    """
    if created:
        if not instance.purchase_number:
            instance.purchase_number = generate_purchase_number()
            instance.save(update_fields=['purchase_number'])


@receiver(post_save, sender=Sales)
def handle_sales_post_save(sender, instance, created, **kwargs):
    """
    Sales post-save handler.

    IMPORTANT:
    - Invoice number generation is handled by the sales view.
    - Stock SOLD/update is handled by the sales view.
    - Customer creation/update is handled by the sales view.
    
    Therefore this signal MUST NOT duplicate any of those writes.

    This signal only handles the independent Low Stock notification.
    """

    if not created:
        return

    stock = instance.stock

    # ---------------------------------------------------------
    # LOW STOCK ALERT
    # ---------------------------------------------------------
    if stock and stock.branch and stock.model:

        available_count = Stock.objects.filter(
            branch=stock.branch,
            model=stock.model,
            stock_status=Stock.StockStatus.AVAILABLE
        ).count()

        if available_count <= 2:
            Notification.objects.create(
                branch=stock.branch,
                title="Low Stock Alert",
                message=f"{stock.model} : {available_count}",
                notification_type=Notification.NotificationType.LOW_STOCK,
                created_by=instance.created_by
            )

@receiver(post_save, sender=Expense)
def handle_expense_post_save(sender, instance, created, **kwargs):
    """
    Automatic Feature: Expense Save
    """
    pass