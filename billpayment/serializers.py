from rest_framework import serializers
from .models import Airtime, Data, CableTV, Electricity


class AirtimeSerializer(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()
    declined_by = serializers.SerializerMethodField()

    def get_approved_by(self, obj):
        if obj.approved_by:
            data = [signatory.user.get_full_name() for signatory in obj.approved_by.all()]
            return data
        return []

    def get_declined_by(self, obj):
        if obj.declined_by:
            data = [signatory.user.get_full_name() for signatory in obj.declined_by.all()]
            return data
        return []

    class Meta:
        model = Airtime
        exclude = []


class DataSerializer(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()
    declined_by = serializers.SerializerMethodField()

    def get_approved_by(self, obj):
        if obj.approved_by:
            data = [signatory.user.get_full_name() for signatory in obj.approved_by.all()]
            return data
        return []

    def get_declined_by(self, obj):
        if obj.declined_by:
            data = [signatory.user.get_full_name() for signatory in obj.declined_by.all()]
            return data
        return []

    class Meta:
        model = Data
        exclude = []


class CableTVSerializer(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()
    declined_by = serializers.SerializerMethodField()

    def get_approved_by(self, obj):
        if obj.approved_by:
            data = [signatory.user.get_full_name() for signatory in obj.approved_by.all()]
            return data
        return []

    def get_declined_by(self, obj):
        if obj.declined_by:
            data = [signatory.user.get_full_name() for signatory in obj.declined_by.all()]
            return data
        return []

    class Meta:
        model = CableTV
        exclude = []


class ElectricitySerializer(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()
    declined_by = serializers.SerializerMethodField()

    def get_approved_by(self, obj):
        if obj.approved_by:
            data = [signatory.user.get_full_name() for signatory in obj.approved_by.all()]
            return data
        return []

    def get_declined_by(self, obj):
        if obj.declined_by:
            data = [signatory.user.get_full_name() for signatory in obj.declined_by.all()]
            return data
        return []

    class Meta:
        model = Electricity
        exclude = []

