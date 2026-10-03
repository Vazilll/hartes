"""
vazus_core.cli_pixel_visualizer — Re-export bridge for CLIPixelVisualizer.
Provides backward-compatible root-level import alias for CLIPixelVisualizer.
"""

from vazus_core.integrations.cli_pixel_visualizer import (
    CLIPixelVisualizer,
    cli_visualizer,
)

__all__ = ["CLIPixelVisualizer", "cli_visualizer"]
