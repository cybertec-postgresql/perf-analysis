#!/usr/bin/env Rscript

# Include helpers
source("plots/plot-helpers.R")
plot <- ggplot(get_data()) +
  geom_bin2d(aes(x=detail/1024, y=duration*1000), bins=200) +
  scale_x_continuous(expand=c(0,0), limit=c(0,NA)) +
  scale_y_continuous(expand=c(0,0), limits=c(0,NA)) +
  theme_bw() +
  labs(title="fdatasync() latency vs amount of outstanding writes", x="Amount written [KB]", y="Duration [ms]") +
  scale_fill_distiller(palette="Spectral", transform="log10")

output_plot(plot)

