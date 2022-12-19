from rest_framework import serializers
from .models import Airtime, Data, CableTV, Electricity


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


class ElectricitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Electricity
        exclude = []

