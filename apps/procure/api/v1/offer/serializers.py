from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from rest_framework import serializers
from utils.generals import get_model

Offer = get_model('procure', 'Offer')
OfferItem = get_model('procure', 'OfferItem')


class BaseOfferSerializer(serializers.ModelSerializer):
    links = serializers.SerializerMethodField()
    total_offer_cost = serializers.IntegerField(read_only=True)
    listing = serializers.CharField(source='propose.listing.label')

    def get_links(self, instance):
        request = self.context.get('request')

        return {
            'retrieve': request.build_absolute_uri(
                reverse('procure_api:offer-detail',
                        kwargs={'uuid': instance.uuid})
            ),
        }


"""
READ
"""


class OfferItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferItem
        fields = ('uuid', 'create_at', 'cost', 'discount',
                  'description',)


class ListOfferSerializer(BaseOfferSerializer):
    items = OfferItemSerializer(many=True)

    class Meta:
        model = Offer
        exclude = ('propose', 'user',)


class RetrieveOfferSerializer(BaseOfferSerializer):
    class Meta:
        model = Offer
        fields = ('uuid', 'listing', 'create_at', 'cost', 'discount', 'description',
                  'can_goto', 'can_goto_radius', 'latitude', 'longitude',
                  'is_newest', 'items', 'total_offer_cost',)
        depth = 1