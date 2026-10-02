# Hydrogen Cross-over Sensor Field Study (100 kW ALK)

Analysis code for: *Hydrogen Cross-over Monitoring in Water Electrolysis: 
A Review of Sensing Technologies and A Long-term Field-Stability Study* (Int. J. Hydrogen Energy).
Two co-located sensors (in-house electrochemical vs. commercial TCD/paramagnetic
reference) on a shared manifold; 103 recorded days, 8,041,007 one-hertz samples.

`make_all_figures.py` is the complete, single-file pipeline: it builds the merged
dataset from the raw 1 Hz logs and renders manuscript Figs. 10-13 into `output/figures/`. 
Edit the PATHS block, then run `python3 make_all_figures.py`.

## Data availability
The raw 1 Hz field records are not public under data policy; derived
aggregates are available from the corresponding author on reasonable request.
The released pipeline makes every figure and statistic in the paper auditable.

## Requirements
Python >= 3.10: `pandas`, `numpy`, `pyarrow`, `matplotlib`, `scipy`, `openpyxl`.

## License
MIT.
