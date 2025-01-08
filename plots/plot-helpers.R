library(ggplot2)

get_data <- function() {

  args <- commandArgs(trailingOnly = TRUE)

  # Determine input source
  if (length(args) > 0) {
    # Read CSV from the file specified in the first argument
    input_file <- args[1]
    if (!file.exists(input_file)) {
      stop(paste("File does not exist:", input_file))
    }
    input_data <- read.csv(input_file, header = TRUE)
  } else {
    input_data <- read.csv(file="stdin", header = TRUE)
  }

  # Check if the input data has been read correctly
  if (nrow(input_data) == 0) {
    stop("No data read from stdin. Ensure a valid CSV is being piped to the script.")
  }

  return(input_data)
}

output_plot <- function(plt) {
  args <- commandArgs(trailingOnly = TRUE)
  output_file <- ifelse(length(args) > 1, args[2], "output.png")

  # Save the plot to the specified output file
  ggsave(output_file, plot = plt, width = 8, height = 8, dpi=140)
  cat("Plot saved to", output_file, "\n")  
}
