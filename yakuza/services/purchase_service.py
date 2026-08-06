from django.db import transaction

from yakuza.models import Purchase
from yakuza.utils.generators import generate_purchase_number


class PurchaseService:

    @staticmethod
    @transaction.atomic
    def create_purchase(form):

        purchase = form.save(commit=False)

        purchase.purchase_number = generate_purchase_number()

        purchase.save()

        return purchase