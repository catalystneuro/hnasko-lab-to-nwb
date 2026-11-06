# Processing

`hadjas_2025/analysis/` holds a Python port of the lab's MATLAB analysis scripts. `analysis/matlab_pipeline.md`
lists the steps of those scripts. `hadjas_2025.analysis.processing` computes the processed signals; the conversion
uses it when they are recomputed from the raw signal (`processed: recomputed`, see [Data streams](data_streams.md)).

Each TDT block is processed separately:

1. The raw signal is demodulated at the modulation frequency of each LED (multiplied by a sine and a cosine at that
   frequency, lowpass filtered at 6 Hz forward and backward, and combined), which gives the 465 nm signal and the
   isosbestic control at the raw rate.
2. Both are resampled to 100 Hz by linear interpolation.
3. A bi-exponential curve is fitted to the isosbestic control, leaving out the first second of the block, and scaled to
   the 465 nm signal by robust linear regression. dF/F = 100 (465 nm signal - scaled fit) / scaled fit.

## Differences from the lab's results

Steps 1 and 2, the robust regression and the dF/F formula give the lab's values to floating point precision. The
bi-exponential fit can differ, because MATLAB refines one start point of its own and can stop at another fit. Where
the fits differ, the baseline differs by a slowly varying amount. The lab also adjusted the fit by hand for seven
blocks, which the port does not reproduce.

The module docstring of `src/hnasko_lab_to_nwb/hadjas_2025/analysis/processing.py` ("Differences from the lab's
MATLAB code") describes these differences in detail.

## Comparing with the lab's .mat files

```bash
hadjas-2025 compare-processing "<data folder>" "<output folder>" --plot-dir-path "<plot folder>"
```

recomputes the processed signals of every session that has a lab `.mat` file and writes
`processing_comparison.csv` to the output folder, with one row per block and signal (correlation and differences with
the lab's signal). With `--plot-dir-path`, it also writes one figure per session with the lab's and the recomputed
isosbestic fits and dF/F of each block. `--subject-ids` limits the comparison to some subjects.

The notebook `src/hnasko_lab_to_nwb/hadjas_2025/analysis/validate_processing.ipynb` shows each processing step of one
session next to the lab's signals.

## Trial analysis

`hadjas_2025.analysis.trial_analysis` ports the trial analysis of the lab's scripts. It aligns the dF/F on the onset of
each train of the optogenetic epochs table, from 5 s before to 10 s after, subtracts the mean of the second before the
onset, and computes the statistics of the lab's time windows for each train duration and pulse frequency.
`add_trial_analysis` writes them to the `trial_analysis` processing module of an NWB file as two tables,
`trial_aligned_dff_<site>` (one row per train) and `trial_window_statistics_<site>` (one row per condition and
window). The conversion does not write them; the notebook `analysis/reproduce_paper_analysis.ipynb` adds them to a
raw-only file.
