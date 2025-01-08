#!/usr/bin/python3
import argparse
from collections import defaultdict, deque
import csv
import heapq
import json
import io
import math
import re
import sys
from typing import NamedTuple, Iterable, Optional, Dict, Deque
from xml.etree.ElementInclude import include

from attr import dataclass


class Event(NamedTuple):
    filename: str
    line: int
    pid: int
    time: float
    duration: float
    syscall: str
    detail: str
    returncode: int = 0
    fd: Optional[str] = None

class Syscall(NamedTuple):
    name: str
    pid: int
    time: float
    fd: Optional[str] = None

    def to_event(self, filename, line, time, detail, returncode):
        return Event(filename, line, self.pid, time, time - self.time, self.name, detail, returncode, self.fd)

class BIO(NamedTuple):
    issuetime: float
    op: str
    nbytes: str
    sector: str

def to_signed64(v):
    return int(v - (1 << 64)) if v & (1 << 63) else v

def parse_fd(lines, filename=None):
    """Parse perf script output from an iterable returning lines, pairing interesting events"""
    script_line_re = re.compile(r" *([a-zA-Z/0-9#.:_-]+(?: [^ 0-9][#a-zA-Z/0-9:-]*)*)\s+(\d+)\s\[(\d+)\]\s+([0-9.]+):\s+([^: ]+):([^ ]+):\s*(.*)")

    inflight_io = defaultdict(dict)
    running_syscalls: Dict[int, Syscall] = {}

    for i, line in enumerate(lines):
        if line[0] == '\n' or line[0] == '\t':
            continue
        match = script_line_re.match(line)
        if match is None:
            print(f"Invalid line: {repr(line)}")
            continue
        try:
            cmd, pid, cpu, event_time, event_type, event, event_args = match.groups()
            event_time = float(event_time)
            pid = int(pid)
        except:
            print(f"Invalid: {repr(line)}")
            raise
        if event_type == 'syscalls':
            if event.startswith('sys_enter_'):
                event_args_arr = event_args.split(', ')
                fd = int(event_args_arr[0][4:], 16) if event_args_arr[0].startswith('fd: ') else None
                running_syscalls[pid] = Syscall(event[10:], int(pid), event_time, fd)
                continue
            elif event.startswith('sys_exit_'):
                exit_syscall = event[9:]
                cur_syscall : Syscall = running_syscalls.pop(pid, None)
                if cur_syscall is not None and cur_syscall.name == exit_syscall:
                    retcode = to_signed64(int(event_args, 16))
                    yield cur_syscall.to_event(filename, i, event_time, detail=None, returncode=retcode)
        elif event_type == 'block':
            if event == 'block_rq_issue':
                # 253,2 WSM 2048 () 1074153538 + 4 [postmaster]
                device, op, nbytes, _, sector, _, nsector, proc = event_args.split(" ", 7)
                inflight_io[device][sector] = BIO(event_time, op, nbytes, sector)
            elif event == 'block_rq_complete':
                device, op, _, sector, _, nsector, proc = event_args.split(" ", 6)

                bio = inflight_io[device].pop(sector, None)
                if bio is not None:
                    duration = event_time - bio.issuetime
                    yield Event(filename, i, int(pid), event_time, duration, f'block_rq({bio.op})', device, bio.nbytes)

def latency_histogram(events, base=2, min_duration=0.000001):
    """Given iterable of events return a log2 histogram"""
    histogram = defaultdict(dict)
    histogram["__base__"] = base
    min_bucket = math.floor(math.log(min_duration, base)) - 1
    for event in events:
        bucket = math.floor(math.log(event.duration, base)) if event.duration >= min_duration else min_bucket
        syscallinfo = histogram[event.syscall]
        syscallinfo[bucket] = syscallinfo.get(bucket, 0) + 1
    return histogram

def print_histogram(histogram):
    base = histogram.pop("__base__", 2)
    min_bucket = min(k for syscallinfo in histogram.values() for k in syscallinfo.keys())
    max_bucket = max(k for syscallinfo in histogram.values() for k in syscallinfo.keys())

    syscalls = list(histogram.keys())
    syscall_widths = [max(len(syscall), max(len(str(c)) for c in counts.values()))
                      for syscall, counts in histogram.items()]
    column_formats = ["{{:>{}}}".format(w) for w in syscall_widths]

    print("{:12} {}".format("latency [ms]", " ".join(fmt.format(syscall)
                                         for fmt, syscall
                                         in zip(column_formats, syscalls))))

    for bucket in range(min_bucket, max_bucket+1):
        min_latency = 1000*(base**bucket)
        syscall_counts = [fmt.format(str(histogram[syscall].get(bucket, "")))
                          for fmt, syscall
                          in zip(column_formats, syscalls)]
        print("{:12.3f} {}".format(min_latency, " ".join(syscall_counts)))

def parse_files(paths: Iterable[str]):
    for path in paths:
        if path.endswith('.zst') or path.endswith('.zstd'):
            try:
                import zstandard as zstd
            except ImportError:
                sys.stderr.write(f"Can't process {path}: zstandard not installed\n")
                sys.exit(1)

            decompressor = lambda fd: io.TextIOWrapper(zstd.ZstdDecompressor().stream_reader(fd), encoding="utf-8")
        elif path.endswith('.gz'):
            import gzip
            decompressor = lambda fd: io.TextIOWrapper(gzip.GzipFile(fileobj=fd), encoding="utf-8")
        elif path.endswith('.lz4'):
            import lz4.frame
            decompressor = lambda fd: io.TextIOWrapper(lz4.frame.open(fd), encoding="utf-8")
        else:
            decompressor = None

        if decompressor is None:
            with open(path) as fd:
                yield from parse_fd(fd, path)
        else:
            with open(path, 'rb') as fd, decompressor(fd) as src:
                yield from parse_fd(src, path)

def latency_threshold(events: Iterable[Event], threshold, before=None):
    threshold_s = threshold / 1000
    if before:
        before_deque = deque(maxlen=before)
    for event in events:
        if event.duration > threshold_s:
            if before:
                yield from before_deque
            yield event
        if before:
            before_deque.append(event)

def print_events(events: Iterable[Event], show_filename=False):
    try:
        for event in events:
            prefix = f"{event.filename}:{event.line:<8d} " if show_filename else ""
            print(f"{prefix}{event.pid} {event.time:16.6f} {event.duration*1000:7.3f} {event.syscall}{'(fd='+str(event.fd)+')' if event.fd is not None else ''} = {event.returncode} {event.detail or ''}")
    except BrokenPipeError:
        pass

def json_events(events: Iterable[Event], show_filename=False):
    try:
        for event in events:
            json.dump(event._asdict(), sys.stdout)
    except BrokenPipeError:
        pass

def csv_events(events: Iterable[Event], show_filename=False):
    try:
        out = csv.writer(sys.stdout)
        out.writerow(Event._fields)
        for event in events:
            out.writerow(event)
    except BrokenPipeError:
        pass

output_formats = {
    "plain": print_events,
    "json": json_events,
    "csv": csv_events,
}

def has_regex(include_list: Iterable[str]):
    return any('*' in clause for clause in include_list)

def make_regex(include_list: Iterable[str]):
    regex_clauses = []
    for clause in include_list:
        if clause.endswith('*'):
            clause = clause[:-1]
            suffix = ""
        else:
            suffix = "$"
        parts = clause.split('*')
        regex_clauses.append(".*".join(re.escape(part) for part in parts) + suffix)

    return re.compile('|'.join(regex_clauses))

def ignore_events(events, ignore_list):
    if has_regex(ignore_list):
        regex = make_regex(ignore_list)
        return filter(lambda e: not regex.match(e.syscall), events)
    return filter(lambda e: e.syscall in ignore_list, events)

def include_events(events, include_list):
    if has_regex(include_list):
        regex = make_regex(include_list)
        return filter(lambda e: regex.match(e.syscall), events)
    return filter(lambda e: e.syscall in include_list, events)

def top_events(events, n):
    return heapq.nlargest(n, events, lambda e: e.duration)

def recv_to_send_latency(events: Iterable[Event]) -> Iterable[Event]:
    """Analyses walreceiver latency from receiving data to sending feedback message with write LSN.

    Assumes syscall events are only captured from walsender process.

    Returns syscall events of recv-to-send type. Event details contain info with percentage of time spent
    in each syscall.
    """
    # Time of last unwritten packet received
    buffered_recv: Optional[float] = None
    # Time of receive of data from last write
    written_recv: Optional[float] = None
    # All events since written_recv
    relevant_events: Deque[Event] = deque()
    cur_file = None

    for event in events:
        if event.filename != cur_file:
            buffered_recv = written_recv = None
            cur_file = event.filename
            relevant_events.clear()
        if event.syscall == 'recvfrom' and event.returncode > 0 and buffered_recv is None:
            buffered_recv = event.time
        elif event.syscall == 'pwrite64':
            if written_recv is None:
                written_recv = buffered_recv
            buffered_recv = None
        elif event.syscall == 'sendto' and written_recv is not None:
            if event.filename == cur_file:
                event_stats = defaultdict(float)
                for evt in relevant_events:
                    if evt.time >= written_recv:
                        event_stats[evt.syscall] += evt.duration

                total_duration = event.time - written_recv
                event_stats['none'] = total_duration - sum(event_stats.values())

                event_stats_str = ", ".join(f"{syscall}: {syscall_duration/total_duration*100:0.1f}%"
                    for syscall, syscall_duration in
                    sorted(event_stats.items(), key=lambda t: t[1], reverse=True)
                    if syscall_duration > total_duration/1000
                )

                yield Event(event.filename, event.line, event.pid, event.time, total_duration, 'recv-to-send', event_stats_str, 0)
            written_recv = None
            if buffered_recv is None:
                # We have replied to all received data, don't need to keep events around
                relevant_events.clear()
            else:
                # Discard events up to last interesting one
                while relevant_events and relevant_events[0].time < buffered_recv:
                    relevant_events.popleft()
        if buffered_recv is not None or written_recv is not None:
            relevant_events.append(event)

def ignore_first_datasync(events: Iterable[Event]) -> Iterable[Event]:
    cur_file = None
    seen_fdatasync = True
    for event in events:
        if event.filename != cur_file:
            cur_file = event.filename
            seen_fdatasync = True
        if event.syscall == 'openat':
            seen_fdatasync = False
        if event.syscall == 'fdatasync' and not seen_fdatasync:
            seen_fdatasync = True
            yield event

def amount_datasync(events: Iterable[Event]) -> Iterable[Event]:
    amounts = defaultdict(int)
    for event in events:
        if event.syscall == 'pwrite64' and event.returncode > 0:
            amounts[event.pid, event.fd] += event.returncode
        if event.syscall == 'fdatasync':
            amount = amounts.pop((event.pid, event.fd), 0)
            yield event._replace(detail=str(amount))

def delta_datasync(events: Iterable[Event]) -> Iterable[Event]:
    last_datasyncs = {}
    cur_file = None
    for event in events:
        if event.filename != cur_file:
            cur_file = event.filename
            last_datasyncs = {}
        if event.syscall == 'fdatasync':
            fd = (event.pid, event.fd)
            last = last_datasyncs.pop(fd, None)
            if last is not None:
                yield event._replace(detail=event.time - event.duration - last.time)
            last_datasyncs[fd] = event

def main():
    parser = argparse.ArgumentParser(description='Calculate statistics from perf syscall event data')
    parser.add_argument('--base', type=int, help="Base for logarithmic histogram bins. (default: 2)", default=2)
    parser.add_argument('--stats', action="store_true", help="Calculate latency histograms per syscall")
    parser.add_argument('--min-latency', type=float, help="Output all events that take more than [ms]")
    parser.add_argument('--before', '-B', type=int, help="Output N events before the matched event")
    parser.add_argument('--ignore', help="Comma separated list of syscalls to ignore")
    parser.add_argument('--include', help="Comma separated list of syscalls to include")
    parser.add_argument('--top', type=int, help="Output top N syscalls by latency")
    parser.add_argument('--recv-to-send', action="store_true", help="Calculate latency from first receive to next send")
    parser.add_argument('--ignore-first-datasync', action="store_true", help="Filter out first datasyncs after opening a file")
    parser.add_argument('--amount-datasync', action="store_true", help="Calculate amount of data fdatasynced")
    parser.add_argument('--delta-datasync', action="store_true", help="Calculate time since last fdatasync")
    parser.add_argument('--format', default="plain", help="Output format", choices=["plain", "json", "csv"])
    parser.add_argument('files', nargs='*', help='Script files to parse')
    args = parser.parse_args()

    if len(args.files):
        events = parse_files(args.files)
        show_filename = len(args.files) > 1
    else:
        events = parse_fd(sys.stdin)
        show_filename = False

    if args.ignore:
        events = ignore_events(events, set(args.ignore.split(',')))
    if args.include:
        events = include_events(events, set(args.include.split(',')))

    if args.recv_to_send:
        events = recv_to_send_latency(events)
    if args.ignore_first_datasync:
        events = ignore_first_datasync(events)
    if args.amount_datasync:
        events = amount_datasync(events)
    if args.delta_datasync:
        events = delta_datasync(events)

    if args.min_latency:
        events = latency_threshold(events, args.min_latency, args.before)

    if args.top is not None:
        events = top_events(events, args.top)

    if args.stats:
        print_histogram(latency_histogram(events, base=args.base))
    else:
        output_formats[args.format](events, show_filename=show_filename)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass