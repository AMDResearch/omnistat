import json

import pandas


class PytorchProfilerTrace:
    def __init__(self, trace_file):
        self.file = trace_file
        with open(self.file, "r") as file:
            self.trace = json.load(file)

    def minimize(self, min_duration=1000):
        orig_events = self.trace.get("traceEvents", [])
        min_events = []

        for event in orig_events:
            if not "cat" in event or not "dur" in event:
                continue
            if event["cat"] == "Trace":
                continue
            if event["dur"] < min_duration:
                continue
            event.pop("args", None)
            min_events.append(event)

        self.trace["traceEvents"] = min_events

    def flatten(self):
        orig_events = self.trace.get("traceEvents", [])
        sorted_events = sorted(orig_events, key=lambda i: i["ts"])

        flat_events = []
        last_start = None
        last_end = None

        for event in sorted_events:
            start = event["ts"]
            end = start + event["dur"]

            # Exclude any event that falls entirely under the last event.
            if last_start and last_end and last_start < start and last_end > end:
                continue

            flat_events.append(event)
            last_start = start
            last_end = end

        self.trace["traceEvents"] = flat_events

    def generate_dataframe(self):
        base_time_us = self.trace.get("baseTimeNanoseconds", 0) // 1_000
        events = []
        for event in self.trace.get("traceEvents", []):
            name = event["name"]
            start_ms = (base_time_us + event["ts"]) // 1_000
            end_ms = (base_time_us + event["ts"] + event["dur"]) // 1_000
            events.append([start_ms, end_ms, name])

        return pandas.DataFrame(events, index=None)
