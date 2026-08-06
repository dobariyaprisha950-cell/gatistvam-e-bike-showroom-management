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
    Automatic Feature: Purchase Save -> Create Stock Automatically
    """
    if created:
        stock_list = []
        for _ in range(instance.quantity):
            stock_list.append(
                Stock(
                    purchase_item=instance,
                    branch=instance.purchase.branch,
                    company=instance.company,
                    model=instance.model,
                    color=instance.color,
                    battery_capacity=instance.battery_capacity,
                    purchase_price=instance.purchase_price,
                    stock_status=Stock.StockStatus.AVAILABLE,
                    chassis_number=None,
                    battery_number=None,
                    motor_number=None,
                    controller_number=None,
                )
            )
        Stock.objects.bulk_create(stock_list)


@receiver(post_save, sender=Purchase)
def handle_purchase_post_save(sender, instance, created, **kwargs):
    """
    Post save triggers for Purchase logging and auto number assignment
    """
    if created:
        if not instance.purchase_number:
            instance.purchase_number = generate_purchase_number()
            instance.save(update_fields=['purchase_number'])

        Notification.objects.create(
            branch=instance.branch,
            title="New Purchase Registered",
            message=f"Purchase {instance.purchase_number} recorded by {instance.created_by.username}.",
            notification_type=Notification.NotificationType.PURCHASE,
            created_by=instance.created_by
        )


@receiver(post_save, sender=Sales)
def handle_sales_post_save(sender, instance, created, **kwargs):
    """
    Automatic Feature:
    Sale Save -> Stock SOLD -> Update selling price -> Create Customer if mobile does not exist -> Create Notification
    """
    if created:
        if not instance.invoice_number:
            instance.invoice_number = generate_sales_invoice_number()
            instance.save(update_fields=['invoice_number'])

        # 1. Update Stock Status and Selling Price
        stock = instance.stock
        stock.stock_status = Stock.StockStatus.SOLD
        stock.selling_price = instance.selling_price
        stock.sale = instance
        stock.save(update_fields=['stock_status', 'selling_price', 'sale'])

        # 2. Create Customer if mobile does not exist
        Customer.objects.get_or_create(
            mobile_number=instance.mobile_number,
            defaults={
                'customer_name': instance.customer_name,
                'aadhar_number': instance.aadhar_number,
                'invoice_no': instance.invoice_number,
                'model_name': stock.model.model_name,
                'price': instance.grand_total,
                'branch_name': stock.branch.branch_name,
                'payment_mode': instance.payment_method
            }
        )

        # 3. Create Notification
        Notification.objects.create(
            branch=stock.branch,
            title="Vehicle Sale Completed",
            message=f"Invoice {instance.invoice_number} generated for {instance.customer_name}.",
            notification_type=Notification.NotificationType.SALE,
            created_by=instance.created_by
        )

        # 4. Check Low Stock Trigger (When Available Quantity <= 2)
        available_count = Stock.objects.filter(
            branch=stock.branch,
            model=stock.model,
            stock_status=Stock.StockStatus.AVAILABLE
        ).count()

        if available_count <= 2:
            Notification.objects.create(
                branch=stock.branch,
                title="Low Stock Alert",
                message=f"Low Stock warning for {stock.model}: Only {available_count} unit(s) remaining at {stock.branch.branch_name}.",
                notification_type=Notification.NotificationType.LOW_STOCK,
                created_by=instance.created_by
            )


@receiver(post_save, sender=Expense)
def handle_expense_post_save(sender, instance, created, **kwargs):
    """
    Automatic Feature: Expense Save -> Notification
    """
    if created:
        Notification.objects.create(
            branch=instance.branch,
            title="New Expense Logged",
            message=f"Expense of ₹{instance.amount} ({instance.expense_master.expense_name}) logged.",
            notification_type=Notification.NotificationType.EXPENSE,
            created_by=instance.created_by
        )