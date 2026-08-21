# Hydrogen Cross-over Sensor Field Study (100 kW ALK)

Analysis code for: *Hydrogen Cross-over Monitoring in Green-Hydrogen Water
Electrolysis: a Field-Validated Review* (Int. J. Hydrogen Energy).
Two co-located sensors (in-house electrochemical vs. commercial TCD/paramagnetic
reference) on a shared manifold; 103 recorded days, 8,041,007 one-hertz samples.

`make_all_figures.py` is the complete, single-file pipeline: it builds the merged
dataset from the raw 1 Hz logs and renders manuscript Figs. 10-13 and 15 into `output/figures/`
(Fig. 9 is a drawn schematic; `Figure14_t90_startup` is a supplementary
diagnostic, not a manuscript figure). Edit the PATHS block, then run
`python3 make_all_figures.py`.

## Data availability
The raw 1 Hz field records are not public under KEPCO data policy; derived
aggregates are available from the corresponding author on reasonable request.
The released pipeline makes every figure and statistic in the paper auditable.

## Requirements
Python >= 3.10: `pandas`, `numpy`, `pyarrow`, `matplotlib`, `scipy`, `openpyxl`.

## License
MIT.
