from rest_framework import serializers
from .models import Airtime, Data, CableTV


class AirtimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airtime
        exclude = []


class DataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Data
        exclude = []


class CableTVSerializer(serializers.ModelSerializer):
    class Meta:
        model = CableTV
        exclude = []

