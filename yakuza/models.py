from django.db import models

class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    city = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name


class VehicleCompany(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class VehicleModel(models.Model):
    company = models.ForeignKey(VehicleCompany, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class VehicleColor(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Supplier(models.Model):
    supplier_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    gst_number = models.CharField(max_length=20, blank=True)
    remarks = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.supplier_name