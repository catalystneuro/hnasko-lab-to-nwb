# MATLAB Analysis Report: Hadjas 2025 Fiber Photometry Analysis

## Overview
The analysis processes TDT-acquired fiber photometry signals to examine responses of different dopaminergic and GABAergic neuron subtypes to optogenetic stimulation.

## File Organization

**Categories by Stimulation Source:**
- **STN stimulation**: 10 files
- **PPN stimulation**: 12 files
- **Anxa1 subtype analysis**: 4 files (both STN and PPN)

**Categories by Recording Target:**
1. SNr GABA neurons (2 files each for STN/PPN)
2. SNc pan-DA neurons (2 files each for STN/PPN)
3. Striatal GRAB-DA recordings (2 files each for STN/PPN)
4. SNc DA subtype (Vglut2+ and Anxa1+) neurons (8 files total)
5. Striatal DA terminal GCaMP (2 files for STN only)

**Categories by Protocol:**
- **Varying Durations**: 250ms, 1s, 4s stimulation at 40 Hz
- **Varying Frequencies**: 5 Hz, 10 Hz, 20 Hz, 40 Hz at fixed durations (250ms, 1s, or 4s)

## Common Analysis Pipeline

All MATLAB scripts follow a consistent processing pipeline with minor variations based on experimental conditions:

### 1. Data Loading
**Input:** TDT tank directories containing raw fiber photometry data
**Method:** `TDTbin2mat()` function from TDT SDK
**Key Streams:**
- `Fi1r`: Raw modulated photodetector signal (6103.5156 Hz)
- `_465A`: Pre-demodulated calcium signal (ignored in favor of offline demodulation)
- `_405A`: Pre-demodulated isosbestic signal (ignored in favor of offline demodulation)

**Event Markers:**
- Varying Duration sessions: `sms_`, `s1s_`, `s4s_` (250ms, 1s, 4s stimuli)
- Varying Frequency sessions: `H05_`, `H10_`, `H20_`, `H40_` (5, 10, 20, 40 Hz)

### 2. Signal Demodulation

**Purpose:** Extract calcium (465nm) and isosbestic (405nm) signals from raw modulated photodetector trace

**Driver Frequencies:**
- Calcium channel (465nm): 330 Hz
- Isosbestic channel (405nm): 210 Hz

**Demodulation Steps:**

For each driver frequency:
1. Multiply the raw signal by a sine and a cosine at the driver frequency
2. Lowpass filter both products (2nd-order Butterworth, 6 Hz cutoff)
3. Square the filtered components
4. Sum the squared components
5. Take the square root to get the demodulated signal

**Filter Design:**
- Type: 2nd-order Butterworth lowpass
- Cutoff: 6 Hz
- Implementation: `filtfilt()` for zero-phase filtering

**Output Signals:**
- `Gc_raw`: Raw demodulated 465nm signal (6103.5156 Hz)
- `af_raw`: Raw demodulated 405nm signal (6103.5156 Hz)

### 3. Downsampling

**Original Sampling Rate:** 6103.5156 Hz
**Target Sampling Rate:** 100 Hz
**Method:** Gridded interpolation (`griddedInterpolant`)

**Rationale:**
- Reduces computational load
- 100 Hz is sufficient for capturing calcium dynamics
- Performed before baseline fitting to improve robustness

**Output Signals:**
- `Gc`: Downsampled 465nm signal (100 Hz)
- `af`: Downsampled 405nm signal (100 Hz)

### 4. Baseline Correction and dF/F Calculation

**Two-Step Fitting Process:**

**Step 1: Exponential Fit to Isosbestic (405nm) Signal**

The downsampled 405nm signal is fit with a bi-exponential model, excluding the first 101 samples (about 1 s).
- Model: `f(x) = a*exp(b*x) + c*exp(d*x)`
- Excludes first 1s to avoid artifacts
- Captures slow photobleaching dynamics

**Step 2: Linear Regression to Match 465nm Signal**

A robust linear regression of the 465nm signal on the fitted 405nm curve gives a slope and an intercept. The baseline is the fitted 405nm curve scaled by that slope plus the intercept.

**dF/F Calculation:**

dF/F is the 465nm signal minus the baseline, divided by the baseline, times 100.
- Units: Percentage (%)
- Baseline: Fitted 405nm signal scaled to match 465nm
- Corrects for motion artifacts and photobleaching

**Quality Checks:**
- Warn if 405→465 regression coefficient is negative
- Check for length mismatches between 405 and 465 signals
- Handle special cases (e.g., animals unplugged before session end)

### 5. Trial Extraction and Alignment

**Time Windows:**
- **Baseline**: 5 seconds before stimulus onset
- **Post-stimulus**: 10 seconds after stimulus onset
- **Total window**: 15 seconds per trial

**Extraction Steps:**

For each stimulus event:
1. Get the onset time from the TDT epocs
2. Convert it to a sample index at 100 Hz (rounded down)
3. Extract dF/F from 5 s before to 10 s after onset
4. Store the trials in a matrix of timepoints by trials

**Baseline Normalization:**

Each trial is normalized by subtracting its mean dF/F over the 1 s before stimulus onset (samples 400 to 500 of the trial window).

**Output:**
- `dF_trials`: Raw dF/F traces aligned to stimulus onset
- `norm_dF`: Baseline-normalized dF/F (subtracts 1s pre-stimulus mean)

### 6. Summary Statistics

**Metrics Calculated:**

**A. Mean dF/F in Specific Time Windows**

Time windows vary by stimulus duration:

**For 250ms stimuli:**
- `stm0_250ms`: 0-250ms (during stimulus)
- `stm250_1250ms`: 250-1250ms (0-1s post-stimulus offset)
- `stm250_500ms`: 250-500ms (0-250ms post-stimulus offset)
- `preStm250ms`: -250-0ms (pre-stimulus baseline)

**For 1s stimuli:**
- `stm0_1s`: 0-1s (during stimulus)
- `stm1_2s`: 1-2s (0-1s post-stimulus offset)
- `stm750_1000ms`: 750-1000ms (last 250ms of stimulus)

**For 4s stimuli:**
- `stm0_4s`: 0-4s (during stimulus)
- `stm3_4s`: 3-4s (last 1s of stimulus)
- `stm4_5s`: 4-5s (0-1s post-stimulus offset)
- `stm3750_4000ms`: 3750-4000ms (last 250ms of stimulus)
- `stm4_8s`: 4-8s (0-4s post-stimulus offset)

**Additional windows:**
- `stm_n1_0s`: -1 to 0s (1s pre-stimulus baseline)
- `stm_n4_0s`: -4 to 0s (4s pre-stimulus baseline)

**B. Area Under the Curve (AUC)**

The normalized dF/F of each trial is integrated over the time window and the result is averaged across trials.
- Trapezoidal integration
- Normalized by sampling rate
- Averaged across trials
- Calculated for each time window

**C. Peak Response Metrics**

**Peak from Mean Trace:**

The maximum of the trial-averaged normalized dF/F within the time window.

**Maximum Absolute Deviation:**

The maximum of the absolute normalized dF/F within the time window and its time index, computed per trial and on the trial-averaged trace.
- Captures both positive and negative peaks
- Important for inhibitory responses

**D. Derived Metrics**

**Pre- vs Post-Stimulus Comparisons:**
- Rebound: mean dF/F in the 1 s after stimulus offset minus mean dF/F in the last 250 ms of the stimulus
- Mean dF/F during the stimulus minus mean dF/F in the pre-stimulus baseline
- Mean dF/F in the 1 s after stimulus offset minus mean dF/F in the pre-stimulus baseline

### 7. Special Handling for Varying Frequency Sessions

**Challenge:** Some sessions recorded all three duration blocks (250ms, 1s, 4s) in a single continuous recording

**Solution:**
- Parse events by duration order (Ascending vs Descending)
- Ascending: [250ms trials 1-5, 1s trials 6-10, 4s trials 11-15]
- Descending: [4s trials 1-5, 1s trials 6-10, 250ms trials 11-15]
- Extract trials from continuous dF/F trace using parsed timestamps

**Special Case - Subject C4608:**
- 250ms and 1s stimuli in one recording session
- 4s stimuli in separate second session
- Required custom code to merge data from two sessions

### 8. Output Data Structure

Results are stored in nested structures indexed by recording site, subject and laser power.

**Per-Subject Data:**
- Raw demodulated 465nm and 405nm signals
- Downsampled 465nm and 405nm signals
- Baseline-corrected dF/F
- Trial-aligned dF/F, raw and baseline-normalized, per stimulus condition

**Group-Level Outputs:**
- Mean traces for plotting (timepoints by subjects), per stimulus condition
- Summary statistics (stimulus condition by subjects), per time window: mean dF/F, AUC, peak of the mean trace, and maximum absolute deviation of the mean trace

**Concatenated for Export:**
- Mean traces of all durations or all frequencies concatenated, for export to Prism

## Key Differences Across Scripts

### 1. By Recording Site

**SNr GABA Neurons:**
- Expect excitatory responses to STN/PPN stimulation
- Color scale: [-2 to 8] %dF/F for heatmaps

**SNc DA Neurons:**
- Complex multiphasic responses
- Color scale: [-5 to 20] %dF/F for heatmaps

**Striatal GRAB-DA:**
- Dopamine release in terminals
- Different color scaling for visualization

**DA Subtypes (Anxa1+ vs Vglut2+):**
- Opposite response profiles (key finding)
- Requires separate analysis for each subtype

### 2. By Protocol Type

**Varying Duration Sessions:**
- Fixed frequency (40 Hz)
- Variable durations (250ms, 1s, 4s)
- Event markers: `sms_`, `s1s_`, `s4s_`
- Focus on duration-dependent dynamics

**Varying Frequency Sessions:**
- Variable frequencies (5, 10, 20, 40 Hz)
- Three duration blocks per session
- Event markers: `H05_`, `H10_`, `H20_`, `H40_`
- Focus on frequency-dependent recruitment

### 3. Visualization

**Individual Animal Heatmaps:**
- Rows: Individual trials (typically 5 per condition)
- Columns: Time (baseline + stimulus + post-stimulus)
- Color: Normalized dF/F values
- White dashed line: Stimulus onset
- White dotted line: Stimulus offset (for varying durations)

**Full Session Plots:**
- Entire recording session dF/F trace
- Vertical lines marking stimulus events (color-coded by condition)
- Raw and fitted signals overlaid

## Dependencies

**MATLAB Toolboxes:**
- TDT SDK: `TDTbin2mat()` for loading TDT data
- Signal Processing Toolbox: `butter()`, `filtfilt()` for filtering
- Curve Fitting Toolbox: `fit()` for exponential fitting
- Statistics Toolbox: `robustfit()` for robust regression

**Custom Functions (Lerner Lab - Not Actually Used):**
- `controlFit3()`: Originally planned but replaced with custom fitting
- `deltaFF()`: Originally planned but replaced with custom dF/F calculation
- `eegfilt()`: From EEGLAB, not used after switch to demodulation

**Note:** The final implementation uses built-in MATLAB functions, making it easier to translate to Python.

## Critical Parameters

### Signal Processing
- **Demodulation frequencies:** 330 Hz (465nm), 210 Hz (405nm)
- **Lowpass filter:** 2nd-order Butterworth, 6 Hz cutoff
- **Downsampling rate:** 100 Hz
- **Baseline fit exclusion:** First 1 second of recording

### Time Windows
- **Pre-stimulus baseline:** 5 seconds
- **Post-stimulus window:** 10 seconds
- **Normalization baseline:** 1 second before stimulus (-1 to 0s)

### Quality Control
- Check for signal length mismatches
- Warn on negative regression coefficients
- Handle session interruptions (animals unplugged)

## Output Files

**MATLAB Workspace (.mat) Files:**
- Contains all processed data structures
- Saved with `-v7.3` flag for large file support
- Typical naming: `[StimLocation]_[Genotype]_[RecordingSite]_[Protocol]_[LaserPower]_Demod.mat`

**Examples:**
- `PPN_Vglut2_SNr_GABA_GCaMP_varDurs_40Hz_5mW_Demod.mat`
- `PPN_Vglut2_SNr_GABA_GCaMP_varFreqs_DurBlocks_ALL_5mW_Demod.mat`
- `PPN_Vglut2-phiC_SNc_Anxa1_GCaMP8f_SNcCells_varDurs_40Hz_5mW_Demod.mat`

## Reproducibility Considerations

**For Python Implementation:**
1. Demodulation can be replicated using scipy signal processing
2. Fitting requires scipy.optimize and scipy.interpolate
3. All calculations use standard mathematical operations
4. No proprietary algorithms beyond TDT data loading

**Data Available in NWB:**
- Raw modulated signal (Fi1r) ✓
- Demodulated signals (465nm, 405nm) ✓
- Downsampled signals (100 Hz) ✓
- Optogenetic stimulation timestamps ✓
- Session metadata ✓

**Not in NWB (needs to be recalculated):**
- dF/F traces
- Trial-aligned data
- Summary statistics
- But all can be derived from available data following this pipeline

## Summary

The MATLAB analysis provides a comprehensive pipeline for processing fiber photometry data with careful attention to:
- Motion artifact correction via isosbestic control
- Photobleaching correction via exponential fitting
- Baseline normalization for trial comparison
- Multiple metrics (mean, AUC, peak) for response quantification
- Handling of complex experimental designs (varying durations and frequencies)

This pipeline can be faithfully reproduced in Python using NumPy, SciPy, and the NWB data format, enabling open-source analysis and extension of these methods.
