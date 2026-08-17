from django.db import transaction
from django.db.models import F, Count
from django.db.models.signals import post_save
from django.dispatch import receiver
from yakuza.models import (
    Purchase, PurchaseItem, Stock, Sales, Customer,
    Expense, Notification, VehicleModel
)
from yakuza.utils import generate_purchase_number, generate_sales_invoice_number, log_audit


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
    Automatic Feature:
    Sale Save -> Stock SOLD -> Update selling price -> Create/Update Customer safely
    """
    if created:
        if not instance.invoice_no:
            instance.invoice_no = generate_sales_invoice_number()
            instance.save(update_fields=['invoice_no'])

        # 1. Update Stock Status and Selling Price
        stock = instance.stock
        if stock:
            stock.stock_status = Stock.StockStatus.SOLD
            stock.selling_price = instance.selling_price
            stock.sale = instance
            stock.save(update_fields=['stock_status', 'selling_price', 'sale'])

        # 2. Safe Customer Creation / Update (MultipleObjectsReturned Prevented)
        customer = Customer.objects.filter(mobile_number=instance.mobile_number).first()
        grand_total_val = getattr(instance, 'grand_total', instance.selling_price)
        branch_name_val = stock.branch.branch_name if (stock and stock.branch) else "HQ"
        model_name_val = stock.model.model_name if (stock and stock.model) else ""

        if customer:
            customer.customer_name = instance.customer_name
            customer.invoice_no = instance.invoice_no
            customer.aadhar_number = instance.aadhar_number
            customer.model_name = model_name_val
            customer.price = grand_total_val
            customer.branch_name = branch_name_val
            customer.payment_mode = instance.payment_method
            customer.save()
        else:
            Customer.objects.create(
                mobile_number=instance.mobile_number,
                customer_name=instance.customer_name,
                aadhar_number=instance.aadhar_number,
                invoice_no=instance.invoice_no,
                model_name=model_name_val,
                price=grand_total_val,
                branch_name=branch_name_val,
                payment_mode=instance.payment_method
            )

        # 3. Check Low Stock Trigger (When Available Quantity <= 2)
        if stock and stock.branch:
            available_count = Stock.objects.filter(
                branch=stock.branch,
                model=stock.model,
                stock_status=Stock.StockStatus.AVAILABLE
            ).count()

            if available_count <= 2:
                Notification.objects.create(
                    branch=stock.branch,  # <--- અહીં Branch પાસ થાય છે
                    title="Low Stock Alert",
                    message=f"{stock.model} : {available_count}",  # <--- બીજી લાઈન માટે ફક્ત Model : Quantity
                    notification_type=Notification.NotificationType.LOW_STOCK,
                    created_by=instance.created_by
                )

@receiver(post_save, sender=Expense)
def handle_expense_post_save(sender, instance, created, **kwargs):
    """
    Automatic Feature: Expense Save
    """
    pass