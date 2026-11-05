"""Python port of the lab's fiber photometry processing and analysis of the Hadjas 2025 preprint.

- processing: demodulation, resampling to 100 Hz and dF/F of the raw signal of one TDT block, and how they differ
  from the lab's MATLAB code.
- processed_series: the processed series of an NWB file recomputed from its raw series (used by the conversion when
  data_streams.processed is "recomputed").
- lab_comparison: comparison of the recomputed signals with the lab's .mat files (hadjas-2025 compare-processing).
- trial_analysis: trial-aligned dF/F and summary statistics, as in the lab's MATLAB scripts.
- dandi_streaming: streaming of a session's NWB file from DANDI.
- matlab_pipeline.md: the steps of the lab's MATLAB scripts.
- validate_processing.ipynb: recomputes the processed signals of a session and compares them with the lab's.

Import the modules directly, e.g. from hnasko_lab_to_nwb.hadjas_2025.analysis.processing import process_raw_signal.
"""
