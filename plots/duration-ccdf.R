#!/usr/bin/env Rscript

# Include helpers
source("plots/plot-helpers.R")

plot <- ggplot(get_data(), aes(x=duration*1000, color=syscall)) +
  geom_line(aes(y = log10(1 - after_stat(y))), stat="ecdf") +
  scale_x_continuous(expand=c(0,0), limit=c(0,NA)) +
  scale_y_continuous(expand=c(0,0), labels=function (v) { sprintf("%0.4f%%", 10^(v+2)) } ) +
  theme_bw() +
  labs(title="CCDF of durations", x="Duration [ms]", y="ECCDF")

output_plot(plot)

