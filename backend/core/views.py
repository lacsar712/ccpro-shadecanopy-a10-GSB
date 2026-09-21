from datetime import timedelta

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClimateLog, FogDutyQuota, Greenhouse, IrrigationCycle, Zone
from .serializers import (
    ClimateLogSerializer,
    FogDutyQuotaSerializer,
    FogQuotaConsumeSerializer,
    GreenhouseSerializer,
    IrrigationCycleSerializer,
    ZoneSerializer,
)


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


class FogDutyQuotaViewSet(viewsets.ModelViewSet):
    serializer_class = FogDutyQuotaSerializer

    def get_queryset(self):
        qs = FogDutyQuota.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        work_date = self.request.query_params.get("workDate")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        if work_date:
            qs = qs.filter(work_date=work_date)
        return qs

    @action(detail=True, methods=["post"], url_path="consume")
    def consume(self, request, pk=None):
        """消费配额：同一事务内累加已用分钟并追加一条气候记录。

        - 仅在种 (growing) 分区允许消费，空闲/休耕返回 409；
        - 累计超过 上限小时数×60 返回 409 并回显已用分钟；
        - 成功时气候记录湿度须 ∈ [70, 95]，与配额更新同库同事务提交。
        """
        serializer = FogQuotaConsumeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        minutes = serializer.validated_data["minutes"]
        humidity = serializer.validated_data["humidityPct"]
        temp_c = serializer.validated_data["tempC"]

        with transaction.atomic():
            quota = get_object_or_404(
                FogDutyQuota.objects.select_for_update().select_related("zone"), pk=pk
            )
            if quota.zone.status != Zone.STATUS_GROWING:
                return Response(
                    {
                        "detail": "仅在种分区允许雾化消费，空闲/休耕分区拒绝",
                        "zoneStatus": quota.zone.status,
                        "usedMinutes": quota.used_minutes,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            max_minutes = quota.max_minutes
            if quota.used_minutes + minutes > max_minutes:
                return Response(
                    {
                        "detail": "累计已用分钟将超过上限小时数×60，拒绝消费",
                        "usedMinutes": quota.used_minutes,
                        "maxMinutes": max_minutes,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            quota.used_minutes += minutes
            quota.save(update_fields=["used_minutes", "updated_at"])
            climate_log = ClimateLog.objects.create(
                zone=quota.zone,
                recorded_at=timezone.now(),
                temp_c=temp_c,
                humidity_pct=humidity,
            )

        return Response(
            {
                "quota": FogDutyQuotaSerializer(quota).data,
                "climateLogId": climate_log.id,
                "usedMinutes": quota.used_minutes,
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
        "fogQuotaTodayCount": FogDutyQuota.objects.filter(
            work_date=timezone.localdate()
        ).count(),
    }
    return Response(data)
