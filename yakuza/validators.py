import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_mobile_number(value):
    pattern = r'^[6-9]\d{9}$'
    if not re.match(pattern, str(value)):
        raise ValidationError(
            _('%(value)s is not a valid 10-digit Indian mobile number.'),
            params={'value': value},
        )


def validate_aadhar_number(value):
    if value:
        pattern = r'^\d{12}$'
        if not re.match(pattern, str(value)):
            raise ValidationError(
                _('%(value)s is not a valid 12-digit Aadhaar number.'),
                params={'value': value},
            )


def validate_pincode(value):
    if value:
        pattern = r'^\d{6}$'
        if not re.match(pattern, str(value)):
            raise ValidationError(
                _('%(value)s is not a valid 6-digit Indian PIN code.'),
                params={'value': value},
            )


def validate_gstin(value):
    if value:
        pattern = r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
        if not re.match(pattern, str(value).upper()):
            raise ValidationError(
                _('%(value)s is not a valid GSTIN number.'),
                params={'value': value},
            )