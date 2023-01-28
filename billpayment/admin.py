from django.contrib import admin
from .models import Data, Airtime, CableTV, Electricity, BillPaymentReversal

admin.site.register(Data)
admin.site.register(Airtime)
admin.site.register(CableTV)
admin.site.register(Electricity)
admin.site.register(BillPaymentReversal)
