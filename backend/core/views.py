from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClimateLog, FogQuota, Greenhouse, IrrigationCycle, Zone
from .serializers import (
    ClimateLogSerializer,
    FogQuotaConsumeSerializer,
    FogQuotaSerializer,
    GreenhouseSerializer,
    IrrigationCycleSerializer,
    ZoneSerializer,
)
from .services import QuotaExceededError, ZoneStatusError, consume_fog_quota


class GreenhouseViewSet(viewsets.ModelViewSet):
    queryset = Greenhouse.objects.annotate(zone_count=Count("zones")).all()
    serializer_class = GreenhouseSerializer


class ZoneViewSet(viewsets.ModelViewSet):
    serializer_class = ZoneSerializer

    def get_queryset(self):
        qs = Zone.objects.select_related("greenhouse").all()
        greenhouse_id = self.request.query_params.get("greenhouseId")
        status = self.request.query_params.get("status")
        if greenhouse_id:
            qs = qs.filter(greenhouse_id=greenhouse_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class ClimateLogViewSet(viewsets.ModelViewSet):
    serializer_class = ClimateLogSerializer

    def get_queryset(self):
        qs = ClimateLog.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        return qs


class IrrigationCycleViewSet(viewsets.ModelViewSet):
    serializer_class = IrrigationCycleSerializer

    def get_queryset(self):
        qs = IrrigationCycle.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        status = self.request.query_params.get("status")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class FogQuotaViewSet(viewsets.ModelViewSet):
    serializer_class = FogQuotaSerializer

    def get_queryset(self):
        qs = FogQuota.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        work_date = self.request.query_params.get("workDate")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        if work_date:
            qs = qs.filter(work_date=work_date)
        return qs

    @action(detail=True, methods=["post"])
    def consume(self, request, pk=None):
        quota = self.get_object()
        serializer = FogQuotaConsumeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            quota, climate_log = consume_fog_quota(
                quota_id=quota.id,
                minutes=data["minutes"],
                temp_c=data["tempC"],
                humidity_pct=data["humidityPct"],
                par_umol=data["parUmol"],
                co2_ppm=data["co2Ppm"],
            )
        except ZoneStatusError as exc:
            return Response(
                {"detail": str(exc), "zoneStatus": exc.status},
                status=status.HTTP_409_CONFLICT,
            )
        except QuotaExceededError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "usedMinutes": exc.used_minutes,
                    "maxMinutes": float(exc.max_minutes),
                    "requestedMinutes": exc.requested_minutes,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {
                "quota": FogQuotaSerializer(quota).data,
                "climateLogId": climate_log.id,
            }
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    data = {
        "greenhouseCount": Greenhouse.objects.count(),
        "growingZoneCount": Zone.objects.filter(status=Zone.STATUS_GROWING).count(),
        "climateLogLast24h": ClimateLog.objects.filter(
            recorded_at__gte=since_24h
        ).count(),
        "irrigationScheduledToday": IrrigationCycle.objects.filter(
            status=IrrigationCycle.STATUS_SCHEDULED,
            start_at__gte=today_start,
            start_at__lt=today_end,
        ).count(),
        "fogQuotaToday": FogQuota.objects.filter(
            work_date=timezone.localdate()
        ).count(),
    }
    return Response(data)
