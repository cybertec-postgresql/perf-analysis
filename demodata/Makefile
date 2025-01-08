all: block-latency-size.png duration-ccdf.png fdatasync-delta.png fdatasync-latency.png fdatasyncs-and-epolls.png

ioevents.csv: ioevents-2025.01.07-19.54.11.script.zst
	../perf-analysis.py ioevents-2025.01.07-19.54.11.script.zst \
		--include='block_rq(W*S*),fdatasync,pwrite64' --format=csv > ioevents.csv

block-latency-size.png: ioevents.csv
	cd ..; plots/block-latency-size.R demodata/ioevents.csv demodata/block-latency-size.png

duration-ccdf.png: ioevents.csv
	cd ..; plots/duration-ccdf.R demodata/ioevents.csv demodata/duration-ccdf.png

fdatasync-delta.csv: syscalls-630406-2025.01.07-14.22.07.script.zst
	../perf-analysis.py syscalls-630406-2025.01.07-14.22.07.script.zst --delta-datasync --format=csv > fdatasync-delta.csv

fdatasync-delta.png: fdatasync-delta.csv
	cd ..; plots/fdatasync-delta.R demodata/fdatasync-delta.csv demodata/fdatasync-delta.png

datasync-amount.csv: syscalls-630406-2025.01.07-14.22.07.script.zst
	../perf-analysis.py syscalls-630406-2025.01.07-14.22.07.script.zst --amount-datasync --format=csv > datasync-amount.csv

fdatasync-latency.png: datasync-amount.csv
	cd ..; plots/fdatasync-latency.R demodata/datasync-amount.csv demodata/fdatasync-latency.png

fdatasyncs-and-epolls.csv: syscalls-630406-2025.01.07-14.22.07.script.zst
	../perf-analysis.py syscalls-630406-2025.01.07-14.22.07.script.zst --include=fdatasync,epoll_wait --format=csv > fdatasyncs-and-epolls.csv

fdatasyncs-and-epolls.png: fdatasyncs-and-epolls.csv
	cd ..; plots/syscall-histogram.R demodata/fdatasyncs-and-epolls.csv demodata/fdatasyncs-and-epolls.png
