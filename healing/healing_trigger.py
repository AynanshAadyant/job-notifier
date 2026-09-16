"""Healing trigger interfaces and concrete trigger detectors."""

from abc import ABC, abstractmethod
from domain.results import HealthReport, AnomalyReport, SelectorStatus


class HealingTrigger(ABC):
    """Abstract interface evaluating whether self-healing is warranted."""

    @abstractmethod
    def should_heal(
        self,
        health_report: HealthReport,
        anomaly_report: AnomalyReport,
        network_error: bool = False,
    ) -> tuple[bool, str]:
        """Determine if healing should trigger.
        
        Returns:
            (should_trigger: bool, reason: str)
        """
        pass


class HardFailureTrigger(HealingTrigger):
    """Triggers healing if any required selector missed entirely."""

    def should_heal(
        self,
        health_report: HealthReport,
        anomaly_report: AnomalyReport,
        network_error: bool = False,
    ) -> tuple[bool, str]:
        # Never heal network/connection errors!
        if network_error:
            return False, "Network/connection error: healing suppressed"

        if health_report.has_hard_failures:
            missed_fields = [
                name for name, fh in health_report.field_healths.items()
                if fh.status == SelectorStatus.MISSED
            ]
            if health_report.total_containers_found == 0:
                return True, f"Hard failure: {health_report.details}"
            return True, f"Hard failure: selectors missed for fields: {', '.join(missed_fields)}"

        return False, ""


class SoftFailureAccumulatorTrigger(HealingTrigger):
    """Triggers healing if soft failures (relocation) persist over consecutive runs."""

    def __init__(self, consecutive_threshold: int = 3):
        self.consecutive_threshold = consecutive_threshold
        self._counter: dict[str, int] = {}

    def should_heal(
        self,
        health_report: HealthReport,
        anomaly_report: AnomalyReport,
        network_error: bool = False,
    ) -> tuple[bool, str]:
        if network_error:
            return False, "Network error suppressed"

        site = health_report.site_name
        if health_report.has_soft_failures:
            count = self._counter.get(site, 0) + 1
            self._counter[site] = count
            if count >= self.consecutive_threshold:
                self._counter[site] = 0
                return True, f"Soft failure threshold ({self.consecutive_threshold} runs) reached for {site}"
        else:
            self._counter[site] = 0

        return False, ""


class AnomalyHealingTrigger(HealingTrigger):
    """Triggers healing if anomalous output detected (e.g. zero valid records)."""

    def should_heal(
        self,
        health_report: HealthReport,
        anomaly_report: AnomalyReport,
        network_error: bool = False,
    ) -> tuple[bool, str]:
        if network_error:
            return False, "Network error suppressed"

        if anomaly_report.is_anomalous:
            return True, f"Anomaly triggered healing: {'; '.join(anomaly_report.reasons)}"

        return False, ""


class CompositeHealingTrigger(HealingTrigger):
    """Aggregates multiple triggers with priority ordering."""

    def __init__(self, triggers: list[HealingTrigger] | None = None):
        self.triggers = triggers or [
            HardFailureTrigger(),
            AnomalyHealingTrigger(),
            SoftFailureAccumulatorTrigger(),
        ]

    def should_heal(
        self,
        health_report: HealthReport,
        anomaly_report: AnomalyReport,
        network_error: bool = False,
    ) -> tuple[bool, str]:
        if network_error:
            return False, "Network/connection error: healing suppressed"

        for trigger in self.triggers:
            triggered, reason = trigger.should_heal(health_report, anomaly_report, network_error)
            if triggered:
                return True, reason

        return False, ""
