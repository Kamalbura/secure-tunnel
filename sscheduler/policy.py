import random
import time


def _get_float(mapping, *keys, default=0.0) -> float:
    for key in keys:
        try:
            value = mapping
            for part in key.split("."):
                if not isinstance(value, dict):
                    value = None
                    break
                value = value.get(part)
            if isinstance(value, (int, float)):
                return float(value)
        except Exception:
            continue
    return float(default)


class SchedulingPolicy:
    """Base class for all scheduling logic."""
    def __init__(self, suites):
        self.suites = list(suites)
        self.current_index = -1

    def next_suite(self):
        """Returns the next suite name to run."""
        raise NotImplementedError("Must implement next_suite")

    def get_duration(self):
        """Returns duration in seconds for the current run."""
        return 10.0  # Default


class LinearLoopPolicy(SchedulingPolicy):
    """Cycles through suites 0 to N, then restarts."""
    def next_suite(self):
        self.current_index = (self.current_index + 1) % len(self.suites)
        return self.suites[self.current_index]


class RandomPolicy(SchedulingPolicy):
    """Picks a random suite every time."""
    def next_suite(self):
        return random.choice(self.suites)


class ManualOverridePolicy(SchedulingPolicy):
    """Runs a specific index repeatedly."""
    def __init__(self, suites, fixed_index=0):
        super().__init__(suites)
        self.fixed_index = fixed_index

    def next_suite(self):
        safe_index = self.fixed_index % len(self.suites)
        return self.suites[safe_index]


class AdaptiveResourcePolicy(LinearLoopPolicy):
    """Adaptive suite selector.

    If thermal/network conditions degrade, schedule a downgrade rekey to a lighter suite.

    Triggers downgrade when any is true:
    - drone_cpu_temp_c > 75
    - gcs_packet_loss_pct > 10
    - gcs_avg_latency_ms > 250
    """

    def __init__(self, suites, *, cooldown_s: float = 15.0):
        super().__init__(suites)
        self._last_metrics = {}
        self._downgrade_next = None
        self._cooldown_s = float(cooldown_s)
        self._last_trigger_ts = 0.0

    def update_metrics(self, metrics: dict) -> None:
        self._last_metrics = metrics or {}
        now = time.time()
        if (now - self._last_trigger_ts) < self._cooldown_s:
            return

        cpu_temp = _get_float(self._last_metrics, "drone.temp_c", "drone_temp_c", default=0.0)
        gcs_loss = _get_float(self._last_metrics, "gcs.packet_loss_pct", "gcs_packet_loss_pct", default=0.0)
        gcs_latency = _get_float(self._last_metrics, "gcs.avg_latency_ms", "gcs_avg_latency_ms", default=0.0)

        if cpu_temp > 75.0 or gcs_loss > 10.0 or gcs_latency > 250.0:
            candidate = self._find_lighter_suite()
            if candidate:
                self._downgrade_next = candidate
                self._last_trigger_ts = now

    def _find_lighter_suite(self):
        # Prefer ML-KEM-512 + Ascon-128a (explicitly requested).
        preferred = None
        for name in self.suites:
            n = str(name).lower()
            if "mlkem512" in n and ("ascon128a" in n or "ascon" in n):
                preferred = name
                break
        if preferred is not None:
            return preferred

        # Otherwise pick the smallest ML-KEM suite available.
        for token in ("mlkem512", "mlkem768", "mlkem1024"):
            for name in self.suites:
                if token in str(name).lower():
                    return name

        # Fallback to the first suite.
        return self.suites[0] if self.suites else None

    def next_suite(self):
        if self._downgrade_next is not None:
            suite = self._downgrade_next
            self._downgrade_next = None
            # Keep current_index aligned with the returned suite if possible.
            try:
                self.current_index = self.suites.index(suite)
            except Exception:
                pass
            return suite
        return super().next_suite()

