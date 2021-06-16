import re

from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import (
    OuterRef, Exists, Count, Q, F, Sum, Case, When, Value, Subquery,
    IntegerField, FloatField
)
from django.db.models.functions import ACos, Cos, Sin, Radians
from django.db.models.expressions import OuterRef
from django.utils.translation import gettext_lazy as _

from rest_framework import status as response_status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import NotAcceptable, NotFound, ValidationError
from rest_framework.pagination import LimitOffsetPagination

from utils.generals import get_model
from utils.pagination import build_result_pagination
from .serializers import (
    CreateInquirySerializer,
    ListInquirySerializer,
    RetrieveInquirySerializer,
    InquiryListProposeSerializer
)
from ..offer.serializers import ListOfferSerializer

Inquiry = get_model('procure', 'Inquiry')
Offer = get_model('procure', 'Offer')
Propose = get_model('procure', 'Propose')

# Define to avoid used ...().paginate__
_PAGINATOR = LimitOffsetPagination()


class InquiryApiView(viewsets.ViewSet):
    """
    POST Params;
    --------
        {
            "keyword": "string",                    [optional]
            "location": {                           [required]
                "latitude": "float",
                "longiteu": "float"
            },
            "items": [                              [optional]
                {"label": "string"},
                {"label": "string"}
            ]
        }

    GET Attribute;
    --------
        [*] results all inquiries submited
    """

    lookup_field = 'uuid'
    permission_classes = (IsAuthenticated,)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._context = {}
        self._uuid = None
        self._queryset = Inquiry.objects \
            .prefetch_related('user', 'items', 'location') \
            .select_related('user', 'location')

    def dispatch(self, request, *args, **kwargs):
        self._uuid = kwargs.get('uuid')
        self._context.update({'request': request})
        return super().dispatch(request, *args, **kwargs)

    def _instances(self):
        return self._queryset \
            .annotate(propose_count=Count('proposes')) \
            .order_by('-create_at')

    # My own inquiries
    def _instance(self, is_update=False):
        try:
            if is_update:
                return self._instances().select_for_update() \
                    .get(uuid=self._uuid)
            else:
                return self._instances().get(uuid=self._uuid)
        except ObjectDoesNotExist:
            raise NotFound(detail=_("Not found"))
        except DjangoValidationError as e:
            raise ValidationError(detail=str(e))

    # People inquiries
    def _hunt_instances(self, keyword):
        keywords = re.split(r"[^A-Za-z']+", keyword) if keyword else []
        keyword_query = Q()

        for keyword in keywords:
            keyword_query |= Q(keyword__icontains=keyword)

        user = self.request.user
        default_listing = user.default_listing

        if default_listing:
            listing_latitude = default_listing.location.latitude
            listing_longitude = default_listing.location.longitude

            # Calculate distance
            calculate_distance = Value(6371) * ACos(
                Cos(Radians(listing_latitude, output_field=FloatField()))
                * Cos(Radians(F('location__latitude'), output_field=FloatField()))
                * Cos(Radians(F('location__longitude'), output_field=FloatField())
                      - Radians(listing_longitude, output_field=FloatField()))
                + Sin(Radians(listing_latitude, output_field=FloatField()))
                * Sin(Radians(F('location__latitude'), output_field=FloatField())),
                output_field=FloatField()
            )

            newest_offers = Offer.objects \
                .filter(propose__inquiry_id=OuterRef('pk'),
                        propose__listing_id=default_listing.id,
                        propose__listing__members__user_id=user.id)
        else:
            newest_offers = Offer.objects.none()

        return self._queryset \
            .annotate(
                is_offered=Exists(newest_offers),
                distance=calculate_distance
            ) \
            .filter(keyword_query) \
            .exclude(user_id=self.request.user.id) \
            .order_by('distance', '-create_at')

    @transaction.atomic()
    def create(self, request, format='json'):
        serializer = CreateInquirySerializer(data=request.data,
                                             context=self._context)
        if serializer.is_valid(raise_exception=True):
            try:
                serializer.save()
            except ValidationError as e:
                return Response({'detail': _(" ".join(e.messages))}, status=response_status.HTTP_406_NOT_ACCEPTABLE)

            _serializer = RetrieveInquirySerializer(
                serializer.instance, context=self._context)
            return Response(_serializer.data, status=response_status.HTTP_201_CREATED)
        return Response(serializer.errors, status=response_status.HTTP_400_BAD_REQUEST)

    @transaction.atomic()
    def partial_update(self, request, uuid=None, format='json'):
        instance = self._instance(is_update=True)

        # can't edit if has proposes
        if instance.proposes.count() > 0:
            raise ValidationError({'detail': _("Has proposes can't edit")})

        serializer = CreateInquirySerializer(instance, partial=True, many=False,
                                             data=request.data, context=self._context)
        if serializer.is_valid(raise_exception=True):
            try:
                serializer.save()
            except ValidationError as e:
                return Response({'detail': _(" ".join(e.messages))}, status=response_status.HTTP_406_NOT_ACCEPTABLE)

            _serializer = RetrieveInquirySerializer(
                serializer.instance, context=self._context)
            return Response(_serializer.data, status=response_status.HTTP_200_OK)
        return Response(serializer.errors, status=response_status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def destroy(self, request, uuid=None, format='json'):
        instance = self._instances().filter(uuid=uuid)

        try:
            instance.delete()
        except DjangoValidationError as e:
            raise NotAcceptable(detail=' '.join(e))
        return Response({'detail': _("Delete success!")},
                        status=response_status.HTTP_200_OK)

    """
    All inquiries
    """

    def list(self, request, format='json'):
        params = request.query_params
        obtain = params.get('obtain', None)
        keyword = params.get('keyword', None)

        if obtain == 'hunt':
            instances = self._hunt_instances(keyword)
        else:
            instances = self._instances().filter(user_id=request.user.id)

        paginator = _PAGINATOR.paginate_queryset(instances, request)
        serializer = ListInquirySerializer(paginator, context=self._context,
                                           many=True)
        results = build_result_pagination(self, _PAGINATOR, serializer)
        return Response(results, status=response_status.HTTP_200_OK)

    """
    A single
    """

    def retrieve(self, request, uuid=None, format='json'):
        instance = self._instance()
        serializer = RetrieveInquirySerializer(instance, many=False,
                                               context=self._context)
        return Response(serializer.data, status=response_status.HTTP_200_OK)

    """
    Get proposes
    """

    @action(methods=['GET'], detail=True, url_name='proposes', url_path='proposes',
            permission_classes=(IsAuthenticated,))
    def proposes(self, request, uuid=None, format='json'):
        """
        Return if user is:
        - inquiry creator
        - or propose creator
        """
        newest_offers = Offer.objects \
            .annotate(
                total_item_cost=Sum('items__cost'),
                total_cost=Case(
                    When(cost__lte=0, then=F('total_item_cost')),
                    default=F('cost'),
                    output_field=IntegerField()
                )
            ) \
            .filter(
                propose__inquiry__uuid=uuid,
                propose__listing_id=OuterRef('listing__id'),
                propose__uuid=OuterRef('uuid'),
                is_newest=True
            ) \
            .order_by('-create_at')

        proposes = Propose.objects \
            .prefetch_related('listing', 'inquiry', 'user', 'offers') \
            .select_related('listing', 'inquiry', 'user') \
            .annotate(
                offer_count=Count('offers', distinct=True),
                newest_offer_cost=Subquery(
                    newest_offers.values('total_cost')[:1]),
                newest_offer_date=Subquery(
                    newest_offers.values('create_at')[:1]),
            ) \
            .filter(
                Q(inquiry__uuid=uuid),
                Q(offers__user_id=request.user.id)
                | Q(inquiry__user_id=request.user.id)
            ) \
            .order_by('-newest_offer_date')

        paginator = _PAGINATOR.paginate_queryset(proposes, request)
        serializer = InquiryListProposeSerializer(paginator, many=True,
                                                  context=self._context)
        results = build_result_pagination(self, _PAGINATOR, serializer)
        return Response(results, status=response_status.HTTP_200_OK)

    """
    Get offers
    """

    @action(methods=['GET'], detail=True, url_name='offers', url_path='offers',
            permission_classes=(IsAuthenticated,))
    def offers(self, request, uuid=None, format='json'):
        """
        Return if user is:
        - inquiry creator
        - or offer creator
        """
        offers = Offer.objects \
            .prefetch_related('items', 'items__inquiry_item', 'propose', 'user') \
            .select_related('propose', 'user') \
            .annotate(total_offer_cost=Sum('items__cost')) \
            .filter(
                Q(propose__inquiry__uuid=uuid),
                Q(user_id=request.user.id)
                | Q(propose__inquiry__user_id=request.user.id)
            )

        paginator = _PAGINATOR.paginate_queryset(offers, request)
        serializer = ListOfferSerializer(paginator, many=True,
                                         context=self._context)
        results = build_result_pagination(self, _PAGINATOR, serializer)
        return Response(results, status=response_status.HTTP_200_OK)