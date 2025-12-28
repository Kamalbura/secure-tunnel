import random
import time


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

