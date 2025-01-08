#!/usr/bin/env Rscript

# Include helpers
source("plots/plot-helpers.R")
plot <- ggplot(subset(get_data(), grepl("block_rq\\(W.*", syscall))) +
  geom_bin2d(aes(x=returncode/1024, y=duration*1000), bins=100) +
  scale_x_continuous(expand=c(0,0), limit=c(0,NA)) +
  scale_y_continuous(expand=c(0,0), limits=c(0,NA)) +
  theme_bw() +
  labs(title="Block I/O completion time for write requests vs request size", x="I/O size [KB]", y="Duration [ms]") +
  scale_fill_distiller(palette="Spectral", transform="log10")

output_plot(plot)

