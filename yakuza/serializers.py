from rest_framework import serializers
from django.contrib.auth.models import User
from yakuza.models import (
    Branch, UserProfile, Supplier, VehicleCompany,
    VehicleColor, VehicleModel, Purchase, PurchaseItem, Stock,
    Sales, Customer, ExpenseMaster, Expense, Notification, Settings, AuditLog,
    InvoiceSetting, InvoiceSequence
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


class VehicleColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleColor
        fields = '__all__'


class VehicleModelSerializer(serializers.ModelSerializer):
    company_name = serializers.ReadOnlyField(source='company.company_name')

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
            'color', 'purchase_price'
        )


class SalesSerializer(serializers.ModelSerializer):
    chassis_number = serializers.CharField(write_only=True)
    battery_number = serializers.CharField(write_only=True)
    motor_number = serializers.CharField(write_only=True)
    controller_number = serializers.CharField(write_only=True)

    class Meta:
        model = Sales
        fields = '__all__'
        read_only_fields = ('invoice_no', 'subtotal', 'cgst', 'sgst', 'grand_total', 'created_by')

    def validate_stock(self, value):
        if value.stock_status != Stock.StockStatus.AVAILABLE:
            raise serializers.ValidationError("Selected stock is not available for sale.")
        request = self.context.get('request')
        if request:
            from yakuza.views import get_user_branch_context
            branch = get_user_branch_context(request)
            if not branch:
                raise serializers.ValidationError("Select a specific branch before creating a sale.")
            if value.branch_id != branch.id:
                raise serializers.ValidationError("Selected stock is not available in the current branch.")
        return value

    def _resolve_invoice_prefix(self):
        """
        Mirrors the prefix resolution used by the Sales page view:
        the branch InvoiceSetting wins, then system Settings, then a
        hardcoded default. Keeping this identical to the page view means
        both bill-creation paths produce consistently formatted numbers
        from the SAME InvoiceSequence counter.
        """
        branch = None
        request = self.context.get('request')
        if request:
            from yakuza.views import get_user_branch_context
            branch = get_user_branch_context(request)

        invoice_setting = (
            InvoiceSetting.objects.filter(branch=branch).first()
            if branch
            else InvoiceSetting.objects.first()
        )

        prefix = ""
        if invoice_setting:
            prefix = (invoice_setting.invoice_prefix or "").strip()

        if not prefix:
            sys_settings = Settings.load()
            if sys_settings:
                prefix = (sys_settings.invoice_prefix or "").strip()

        return prefix or "INV-"

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

        # FIX: invoice_no is read-only, so it never arrives in
        # validated_data, and Sales.save() does not generate one. Without
        # this the API created bills with an EMPTY invoice number, and
        # because Sales.invoice_no is unique=True the second API-created
        # bill failed with an IntegrityError.
        #
        # The API now uses exactly the same InvoiceSequence counter as
        # the Sales page, so numbers from either path share one gap-free,
        # never-reused sequence.
        if not validated_data.get('invoice_no'):
            validated_data['invoice_no'] = InvoiceSequence.next_invoice_no(
                self._resolve_invoice_prefix()
            )

        sale = Sales.objects.create(**validated_data)

        # Keep Stock in step with the sale, as the Sales page view does.
        stock.stock_status = Stock.StockStatus.SOLD
        stock.sale = sale
        stock.save(update_fields=['stock_status', 'sale'])

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
    branch_name = serializers.CharField(source='branch.branch_name', read_only=True, default='All Branches')
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
        fields = ['id', 'user', 'user_name', 'old_value', 'new_value', 'timestamp']


class ProfitReportSerializer(serializers.Serializer):
    total_sales = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_purchase_cost = serializers.DecimalField(max_digits=15, decimal_places=2)
    gross_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
    units_sold = serializers.IntegerField()
