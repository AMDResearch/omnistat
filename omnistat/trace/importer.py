import argparse
import sys

import numpy
import pandas

from omnistat.trace.pytorch import PytorchProfilerTrace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=int, help="Job ID", required=True)
    parser.add_argument("--trace", type=int, help="Trace ID", required=True)
    parser.add_argument("--file", type=str, help="Pytorch profiler JSON trace file", required=True)
    args = parser.parse_args()

    trace = PytorchProfilerTrace(args.file)
    trace.minimize()
    trace.flatten()

    df = trace.generate_dataframe()

    min_ms = df.head(1)[0].item()
    max_ms = df.tail(1)[1].item()
    resolution_ms = 10

    # Generate timestamps for Prometheus samples. Includes start and end
    # times for all spans in the trace, as well as periodic steps at the
    # desired resolution to ensure values remain active in Prometheus.
    starts = df[0].to_numpy()
    ends = df[1].to_numpy()
    steps = numpy.arange(min_ms, max_ms, resolution_ms)

    times = numpy.concatenate((steps, starts, ends))
    times.sort(kind="stable")
    times = numpy.unique(times, axis=0)

    names = df[2].to_numpy()
    names = numpy.unique(names)

    # Generate initial empty dataframe with timestamps as rows and event names
    # as columns.
    zeros = numpy.zeros((len(times), len(names)), dtype=bool)
    empty = numpy.column_stack((times, zeros))
    columns = ["time"] + list(names)
    metrics = pandas.DataFrame(empty, columns=columns)

    # Load values for each one of the events in the trace, setting value to 1
    # (True) to mark active events.
    for i, row in df.iterrows():
        start_ms = row[0]
        end_ms = row[1]
        name = row[2]
        metrics.loc[(metrics["time"] >= start_ms) & (metrics['time'] <= end_ms), name] = 1

    # Store trace as OpenMetrics dump.
    for i, row in metrics.iterrows():
        time_ms = row["time"]
        for name in names:
            value = row[name].item()
            print(f'rmsjob_trace{{jobid="{args.job}",traceid="{args.trace}",marker="{name}"}} {value} {time_ms/1000}')
    print("# EOF")


if __name__ == "__main__":
    main()
