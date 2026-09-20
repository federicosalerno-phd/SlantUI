Tests. The contrast audit and the prose check both run here and both fail the build. test_window.py opens the real window and runs only with SLANTUI_SHOW_WINDOW=1.

test_wpf_widgets.py opens WPF windows too, and runs with the rest: they sit twenty thousand pixels off the left of the screen and never take the focus. It is the only place the splash, the dropdown and the SVG reader are measured, because none of the three can be checked by reading the source.
