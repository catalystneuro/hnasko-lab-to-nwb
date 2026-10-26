# Processing

`hadjas_2025.processing` is a Python port of the steps of the lab's MATLAB analysis scripts. The conversion uses it
when the processed signals are recomputed from the raw signal (`processed: recomputed`, see
[Data streams](data_streams.md)).

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

The module docstring of `src/hnasko_lab_to_nwb/hadjas_2025/processing.py` ("Differences from the lab's MATLAB code")
describes these differences in detail.

## Comparing with the lab's .mat files

```bash
hadjas-2025 compare-processing "<data folder>" "<output folder>" --plot-dir-path "<plot folder>"
```

recomputes the processed signals of every session that has a lab `.mat` file and writes
`processing_comparison.csv` to the output folder, with one row per block and signal (correlation and differences with
the lab's signal). With `--plot-dir-path`, it also writes one figure per session with the lab's and the recomputed
isosbestic fits and dF/F of each block. `--subject-ids` limits the comparison to some subjects.
