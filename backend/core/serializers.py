from rest_framework import serializers

from .models import ClimateLog, FogQuota, Greenhouse, IrrigationCycle, Zone


class GreenhouseSerializer(serializers.ModelSerializer):
    areaM2 = serializers.DecimalField(
        source="area_m2", max_digits=10, decimal_places=2
    )
    zoneCount = serializers.SerializerMethodField()

    class Meta:
        model = Greenhouse
        fields = (
            "id",
            "name",
            "location",
            "areaM2",
            "notes",
            "zoneCount",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "zoneCount", "created_at", "updated_at")

    def get_zoneCount(self, obj):
        if hasattr(obj, "zone_count"):
            return obj.zone_count
        return obj.zones.count()


class ZoneSerializer(serializers.ModelSerializer):
    greenhouseId = serializers.PrimaryKeyRelatedField(
        source="greenhouse", queryset=Greenhouse.objects.all()
    )
    zoneCode = serializers.CharField(source="zone_code")
    cropName = serializers.CharField(source="crop_name", allow_blank=True, required=False)
    greenhouseName = serializers.CharField(source="greenhouse.name", read_only=True)

    class Meta:
        model = Zone
        fields = (
            "id",
            "greenhouseId",
            "greenhouseName",
            "zoneCode",
            "cropName",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "greenhouseName", "created_at", "updated_at")

    def validate(self, attrs):
        greenhouse = attrs.get("greenhouse") or getattr(self.instance, "greenhouse", None)
        zone_code = attrs.get("zone_code") or getattr(self.instance, "zone_code", None)
        if greenhouse and zone_code:
            qs = Zone.objects.filter(greenhouse=greenhouse, zone_code=zone_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"zoneCode": "同一温室内分区编码必须唯一"}
                )
        return attrs


class ClimateLogSerializer(serializers.ModelSerializer):
    zoneId = serializers.PrimaryKeyRelatedField(
        source="zone", queryset=Zone.objects.all()
    )
    recordedAt = serializers.DateTimeField(source="recorded_at")
    tempC = serializers.DecimalField(source="temp_c", max_digits=5, decimal_places=2)
    humidityPct = serializers.DecimalField(
        source="humidity_pct", max_digits=5, decimal_places=2
    )
    parUmol = serializers.DecimalField(
        source="par_umol", max_digits=8, decimal_places=2, required=False
    )
    co2Ppm = serializers.DecimalField(
        source="co2_ppm", max_digits=8, decimal_places=2, required=False
    )
    zoneCode = serializers.CharField(source="zone.zone_code", read_only=True)
    greenhouseName = serializers.CharField(
        source="zone.greenhouse.name", read_only=True
    )

    class Meta:
        model = ClimateLog
        fields = (
            "id",
            "zoneId",
            "zoneCode",
            "greenhouseName",
            "recordedAt",
            "tempC",
            "humidityPct",
            "parUmol",
            "co2Ppm",
            "created_at",
        )
        read_only_fields = ("id", "zoneCode", "greenhouseName", "created_at")

    def validate_humidityPct(self, value):
        if value < 20 or value > 100:
            raise serializers.ValidationError("湿度须在 20～100 之间")
        return value


class IrrigationCycleSerializer(serializers.ModelSerializer):
    zoneId = serializers.PrimaryKeyRelatedField(
        source="zone", queryset=Zone.objects.all()
    )
    startAt = serializers.DateTimeField(source="start_at")
    durationMin = serializers.IntegerField(source="duration_min")
    waterLiters = serializers.DecimalField(
        source="water_liters", max_digits=10, decimal_places=2
    )
    zoneCode = serializers.CharField(source="zone.zone_code", read_only=True)
    greenhouseName = serializers.CharField(
        source="zone.greenhouse.name", read_only=True
    )

    class Meta:
        model = IrrigationCycle
        fields = (
            "id",
            "zoneId",
            "zoneCode",
            "greenhouseName",
            "startAt",
            "durationMin",
            "waterLiters",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "zoneCode",
            "greenhouseName",
            "created_at",
            "updated_at",
        )


class FogQuotaSerializer(serializers.ModelSerializer):
    zoneId = serializers.PrimaryKeyRelatedField(
        source="zone", queryset=Zone.objects.all()
    )
    workDate = serializers.DateField(source="work_date")
    maxHours = serializers.DecimalField(
        source="max_hours", max_digits=5, decimal_places=2
    )
    usedMinutes = serializers.IntegerField(source="used_minutes", read_only=True)
    maxMinutes = serializers.SerializerMethodField()
    zoneCode = serializers.CharField(source="zone.zone_code", read_only=True)
    greenhouseName = serializers.CharField(
        source="zone.greenhouse.name", read_only=True
    )
    zoneStatus = serializers.CharField(source="zone.status", read_only=True)

    class Meta:
        model = FogQuota
        fields = (
            "id",
            "zoneId",
            "zoneCode",
            "greenhouseName",
            "zoneStatus",
            "workDate",
            "maxHours",
            "maxMinutes",
            "usedMinutes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "zoneCode",
            "greenhouseName",
            "zoneStatus",
            "maxMinutes",
            "usedMinutes",
            "created_at",
            "updated_at",
        )

    def get_maxMinutes(self, obj):
        return float(obj.max_minutes)

    def validate_maxHours(self, value):
        if value <= 0:
            raise serializers.ValidationError("上限小时数必须为正数")
        return value

    def validate(self, attrs):
        zone = attrs.get("zone") or getattr(self.instance, "zone", None)
        work_date = attrs.get("work_date") or getattr(self.instance, "work_date", None)
        if zone and work_date:
            qs = FogQuota.objects.filter(zone=zone, work_date=work_date)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"workDate": "同一分区同一作业日只能有一条配额"}
                )
        return attrs


class FogQuotaConsumeSerializer(serializers.Serializer):
    minutes = serializers.IntegerField(min_value=1)
    tempC = serializers.DecimalField(max_digits=5, decimal_places=2)
    humidityPct = serializers.DecimalField(max_digits=5, decimal_places=2)
    parUmol = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, default=0
    )
    co2Ppm = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, default=0
    )

    def validate_humidityPct(self, value):
        if value < 70 or value > 95:
            raise serializers.ValidationError("雾化气候记录湿度须在 70～95 之间")
        return value
