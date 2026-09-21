from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import ClimateLog, FogQuota, Zone


class FogQuotaError(Exception):
    """雾化配额消费失败的基类。"""


class ZoneStatusError(FogQuotaError):
    """分区非「在种」状态，禁止消费。"""

    def __init__(self, status):
        self.status = status
        super().__init__("仅「在种」状态的分区允许消费雾化配额")


class QuotaExceededError(FogQuotaError):
    """累计消费将超过上限（上限小时数 × 60 分钟）。"""

    def __init__(self, quota, requested_minutes):
        self.used_minutes = quota.used_minutes
        self.max_minutes = quota.max_minutes
        self.requested_minutes = requested_minutes
        super().__init__("累计消费分钟数将超过配额上限")


@transaction.atomic
def consume_fog_quota(*, quota_id, minutes, temp_c, humidity_pct, par_umol=0, co2_ppm=0):
    """消费雾化配额并在同一事务追加一条气候记录（湿度强制 70～95）。

    成功返回 (quota, climate_log)；分区状态不允许或超配额时抛错，事务整体回滚，
    不会出现只改配额不写气候的中间状态。
    """
    if not (Decimal("70") <= humidity_pct <= Decimal("95")):
        raise ValueError("雾化气候记录湿度须在 70～95 之间")

    quota = (
        FogQuota.objects.select_for_update()
        .select_related("zone")
        .get(pk=quota_id)
    )
    if quota.zone.status != Zone.STATUS_GROWING:
        raise ZoneStatusError(quota.zone.status)

    new_used = quota.used_minutes + minutes
    if new_used > quota.max_minutes:
        raise QuotaExceededError(quota, minutes)

    quota.used_minutes = new_used
    quota.save(update_fields=["used_minutes", "updated_at"])
    climate_log = ClimateLog.objects.create(
        zone=quota.zone,
        recorded_at=timezone.now(),
        temp_c=temp_c,
        humidity_pct=humidity_pct,
        par_umol=par_umol,
        co2_ppm=co2_ppm,
    )
    return quota, climate_log
