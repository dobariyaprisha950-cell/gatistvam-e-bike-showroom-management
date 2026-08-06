from rest_framework import serializers
from django.contrib.auth.models import User
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany, BatteryCapacity,
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, Customer, ExpenseMaster, Expense, Notification, Settings, AuditLog
)


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = '__all__'


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class VehicleCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleCompany
        fields = '__all__'


class BatteryCapacitySerializer(serializers.ModelSerializer):
    class Meta:
        model = BatteryCapacity
        fields = '__all__'


class VehicleColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleColor
        fields = '__all__'


class VehicleModelSerializer(serializers.ModelSerializer):
    company_name = serializers.ReadOnlyField(source='company.company_name')
    battery_capacity_name = serializers.ReadOnlyField(source='battery_capacity.capacity_name')

    class Meta:
        model = VehicleModel
        fields = '__all__'


class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = '__all__'
        read_only_fields = ('subtotal', 'cgst_amount', 'sgst_amount', 'total_amount')


class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True)

    class Meta:
        model = Purchase
        fields = '__all__'
        read_only_fields = ('purchase_number', 'created_by')

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        purchase = Purchase.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseItem.objects.create(purchase=purchase, **item_data)
        return purchase


class StockSerializer(serializers.ModelSerializer):
    company_name = serializers.ReadOnlyField(source='company.company_name')
    model_name = serializers.ReadOnlyField(source='model.model_name')
    color_name = serializers.ReadOnlyField(source='color.color_name')

    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = (
            'purchase_item', 'branch', 'company', 'model',
            'color', 'battery_capacity', 'purchase_price'
        )


class SalesSerializer(serializers.ModelSerializer):
    chassis_number = serializers.CharField(write_only=True)
    battery_number = serializers.CharField(write_only=True)
    motor_number = serializers.CharField(write_only=True)
    controller_number = serializers.CharField(write_only=True)

    class Meta:
        model = Sales
        fields = '__all__'
        read_only_fields = ('invoice_number', 'subtotal', 'cgst', 'sgst', 'grand_total', 'created_by')

    def validate_stock(self, value):
        if value.stock_status != Stock.StockStatus.AVAILABLE:
            raise serializers.ValidationError("Selected stock is not available for sale.")
        return value

    def create(self, validated_data):
        chassis = validated_data.pop('chassis_number')
        battery = validated_data.pop('battery_number')
        motor = validated_data.pop('motor_number')
        controller = validated_data.pop('controller_number')

        stock = validated_data['stock']
        stock.chassis_number = chassis
        stock.battery_number = battery
        stock.motor_number = motor
        stock.controller_number = controller
        stock.save(update_fields=['chassis_number', 'battery_number', 'motor_number', 'controller_number'])

        sale = Sales.objects.create(**validated_data)
        return sale


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'


class ExpenseMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseMaster
        fields = '__all__'


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ('created_by',)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settings
        fields = '__all__'


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = AuditLog
        fields = '__all__'


class ProfitReportSerializer(serializers.Serializer):
    total_sales = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_purchase_cost = serializers.DecimalField(max_digits=15, decimal_places=2)
    gross_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
    units_sold = serializers.IntegerField()