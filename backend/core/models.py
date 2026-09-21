from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Greenhouse(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True, default="")
    area_m2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Zone(models.Model):
    STATUS_IDLE = "idle"
    STATUS_GROWING = "growing"
    STATUS_FALLOW = "fallow"
    STATUS_CHOICES = [
        (STATUS_IDLE, "空闲"),
        (STATUS_GROWING, "在种"),
        (STATUS_FALLOW, "休耕"),
    ]

    greenhouse = models.ForeignKey(
        Greenhouse, on_delete=models.CASCADE, related_name="zones"
    )
    zone_code = models.CharField(max_length=40)
    crop_name = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_IDLE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["greenhouse_id", "zone_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["greenhouse", "zone_code"],
                name="uniq_zone_code_per_greenhouse",
            )
        ]

    def __str__(self):
        return f"{self.greenhouse.name}/{self.zone_code}"


class ClimateLog(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="climate_logs")
    recorded_at = models.DateTimeField()
    temp_c = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(20), MaxValueValidator(100)],
    )
    par_umol = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    co2_ppm = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"Climate@{self.zone_id} {self.recorded_at}"


class IrrigationCycle(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "已排程"),
        (STATUS_RUNNING, "进行中"),
        (STATUS_DONE, "已完成"),
        (STATUS_SKIPPED, "已跳过"),
    ]

    zone = models.ForeignKey(
        Zone, on_delete=models.CASCADE, related_name="irrigation_cycles"
    )
    start_at = models.DateTimeField()
    duration_min = models.PositiveIntegerField(default=30)
    water_liters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]

    def __str__(self):
        return f"Irrig@{self.zone_id} {self.start_at} ({self.status})"


class FogQuota(models.Model):
    """雾化值班配额：同区同日唯一，消费与气候湿度写路径联锁。"""

    zone = models.ForeignKey(
        Zone, on_delete=models.CASCADE, related_name="fog_quotas"
    )
    work_date = models.DateField()
    max_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    used_minutes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-work_date", "zone_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["zone", "work_date"],
                name="uniq_fog_quota_zone_date",
            )
        ]

    def __str__(self):
        return f"FogQuota@{self.zone_id} {self.work_date}"

    @property
    def max_minutes(self):
        return self.max_hours * 60
