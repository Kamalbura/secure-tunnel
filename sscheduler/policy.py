import random

class SchedulingPolicy:
    def __init__(self, suites):
        self.suites = list(suites)
    def next_suite(self):
        raise NotImplementedError
    def get_duration(self):
        return 10.0

class LinearLoopPolicy(SchedulingPolicy):
    def __init__(self, suites):
        super().__init__(suites)
        self.index = -1
    def next_suite(self):
        self.index = (self.index + 1) % len(self.suites)
        return self.suites[self.index]

class RandomPolicy(SchedulingPolicy):
    def next_suite(self):
        return random.choice(self.suites)
