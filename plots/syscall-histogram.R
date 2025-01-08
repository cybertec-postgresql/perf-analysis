#!/usr/bin/env Rscript

# Include helpers
source("plots/plot-helpers.R")
plot <- ggplot(get_data()) +
  geom_freqpoly(aes(x=duration*1000, y=after_stat(density), colour=syscall), bins=100) +
  scale_x_continuous(expand=c(0,0), limit=c(0,NA)) +
  scale_y_log10(expand=c(0,0)) +
  theme_bw() +
  labs(title="Syscall durations", x="Duration [ms]")

output_plot(plot)

