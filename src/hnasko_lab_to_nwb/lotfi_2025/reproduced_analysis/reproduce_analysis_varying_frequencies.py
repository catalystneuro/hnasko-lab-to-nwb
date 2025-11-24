"""
Demonstration script for reproducing Lotfi 2025 fiber photometry analysis - VARYING FREQUENCIES sessions.

This script handles the special case of varying frequency sessions where:
- Multiple duration blocks (250ms, 1s, 4s) are recorded in a single session
- Each block contains trials at different frequencies (5, 10, 20, 40 Hz)
- Raw signal must be cropped by epoch boundaries to process each block separately

Based on the MATLAB analysis scripts by Nick Hollon (Hnasko Lab).

Author: Catalyst Neuro
Date: 2025
"""

# %% Import required libraries
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal as scipy_signal

# Analysis functions
from analysis_functions import (
    baseline_normalize_trials,
    calculate_dff_with_biexponential_fit,
    calculate_summary_statistics,
    extract_trials_around_events,
    get_standard_time_windows,
)

# NWB and DANDI access
from stream_from_dandi import load_nwb_from_dandi

# Configure matplotlib
plt.rcParams["figure.figsize"] = (14, 8)
plt.rcParams["font.size"] = 10

# %% Section 1: Load NWB File from DANDI - VARYING FREQUENCIES SESSION

DANDISET_ID = "001528"
SUBJECT_ID = "C4561"  # Example subject
SESSION_ID = "varying-frequencies"  # IMPORTANT: This is a varying frequencies session

print("=" * 100)
print("LOTFI 2025 ANALYSIS - VARYING FREQUENCIES SESSION")
print("=" * 100)
print(f"\nLoading NWB file from DANDI Archive")
print(f"  Dandiset: {DANDISET_ID}")
print(f"  Subject: {SUBJECT_ID}")
print(f"  Session: {SESSION_ID}\n")

nwbfile, io = load_nwb_from_dandi(DANDISET_ID, SUBJECT_ID, SESSION_ID)

print(f"Session Information:")
print(f"  Start time: {nwbfile.session_start_time}")
print(f"  Subject: {nwbfile.subject.subject_id}")
print(f"  Genotype: {nwbfile.subject.genotype}")
print(f"  Description: {nwbfile.session_description}")

# %% Section 2: Extract Trial Information to Identify Blocks

print("\n" + "=" * 100)
print("STEP 1: IDENTIFY DURATION BLOCKS FROM TRIAL TABLE")
print("=" * 100)
print("\nVarying frequency sessions contain multiple duration blocks.")
print("Each block has a different stimulus duration (250ms, 1s, or 4s).\n")

# Get trial table
trials_table = nwbfile.trials
trials_df = trials_table.to_dataframe()

print(f"Trial table information:")
print(f"  Total trials: {len(trials_df)}")
print(f"  Columns: {list(trials_df.columns)}")
print(f"\nFirst 10 trials:")
print(trials_df.head(10))

# Identify blocks based on 'tags' column
if "tags" not in trials_df.columns:
    raise ValueError("'tags' column not found in trials table. Cannot identify duration blocks.")

# Get unique tags
tags = trials_df["tags"]
print(f"\nUnique tags found: {tags}")

# Organize trials by block
blocks_info = {}
for tag in tags:
    tag = tag[0]
    tag_mask = trials_df["tags"] == tag
    block_trials = trials_df[tag_mask]

    blocks_info[tag] = {
        "trials_df": block_trials,
        "n_trials": len(block_trials),
        "start_time": block_trials["start_time"].min(),
        "stop_time": block_trials["stop_time"].max(),
        "duration_label": tag,
    }

    print(f"\nBlock '{tag}':")
    print(f"  N trials: {blocks_info[tag]['n_trials']}")
    print(f"  Time range: [{blocks_info[tag]['start_time']:.2f}, {blocks_info[tag]['stop_time']:.2f}] s")
    print(f"  Total duration: {blocks_info[tag]['stop_time'] - blocks_info[tag]['start_time']:.2f} s")

# %% Section 3: Extract and Process Each Block Separately

print("\n" + "=" * 100)
print("STEP 2: PROCESS EACH DURATION BLOCK SEPARATELY")
print("=" * 100)
print("\nEach block will be processed independently from raw signal to dF/F.\n")

# Get raw modulated signal
raw_signal_name = None
for name in nwbfile.acquisition.keys():
    if "raw" in name.lower() and "signal" in name.lower():
        raw_signal_name = name
        break

if raw_signal_name is None:
    raise ValueError("Could not find raw modulated signal in NWB file")

raw_signal_full = nwbfile.acquisition[raw_signal_name].data[:]
raw_fs = float(nwbfile.acquisition[raw_signal_name].rate)

print(f"Full raw signal:")
print(f"  Name: {raw_signal_name}")
print(f"  Sampling rate: {raw_fs} Hz")
print(f"  Total length: {len(raw_signal_full)} samples")
print(f"  Total duration: {len(raw_signal_full) / raw_fs:.2f} seconds")

# Demodulation parameters
DRIVER_FREQ_CALCIUM = 330  # Hz
DRIVER_FREQ_ISOSBESTIC = 210  # Hz
LOWPASS_CUTOFF = 6  # Hz
TARGET_FS = 100.0  # Hz for downsampling

# Create lowpass filter
b, a = scipy_signal.butter(2, LOWPASS_CUTOFF / (raw_fs / 2), "low")

# Process each block
processed_blocks = {}

for tag, block_info in blocks_info.items():
    print(f"\n{'=' * 80}")
    print(f"Processing Block: {tag}")
    print(f"{'=' * 80}")

    # Extract raw signal for this block (with padding)
    block_start_time = block_info["start_time"]
    block_stop_time = block_info["stop_time"]

    # Add padding (5s before, 10s after) to ensure trial extraction works
    padding_before = 5.0  # seconds
    padding_after = 10.0  # seconds

    padded_start = max(0, block_start_time - padding_before)
    padded_stop = min(len(raw_signal_full) / raw_fs, block_stop_time + padding_after)

    start_idx = int(padded_start * raw_fs)
    stop_idx = int(padded_stop * raw_fs)

    raw_signal_block = raw_signal_full[start_idx:stop_idx]

    print(f"\n1. Extracted raw signal block:")
    print(f"   Time range: [{padded_start:.2f}, {padded_stop:.2f}] s")
    print(f"   Length: {len(raw_signal_block)} samples ({len(raw_signal_block) / raw_fs:.2f} s)")

    # Demodulate
    print(f"\n2. Demodulating block...")
    t_block = np.arange(len(raw_signal_block)) / raw_fs

    # Calcium (465nm)
    sin_465 = raw_signal_block * np.sin(2 * np.pi * DRIVER_FREQ_CALCIUM * t_block)
    cos_465 = raw_signal_block * np.cos(2 * np.pi * DRIVER_FREQ_CALCIUM * t_block)
    sin_465_filt = scipy_signal.filtfilt(b, a, sin_465)
    cos_465_filt = scipy_signal.filtfilt(b, a, cos_465)
    calcium_demod = np.sqrt(sin_465_filt**2 + cos_465_filt**2)

    # Isosbestic (405nm)
    sin_405 = raw_signal_block * np.sin(2 * np.pi * DRIVER_FREQ_ISOSBESTIC * t_block)
    cos_405 = raw_signal_block * np.cos(2 * np.pi * DRIVER_FREQ_ISOSBESTIC * t_block)
    sin_405_filt = scipy_signal.filtfilt(b, a, sin_405)
    cos_405_filt = scipy_signal.filtfilt(b, a, cos_405)
    isosbestic_demod = np.sqrt(sin_405_filt**2 + cos_405_filt**2)

    print(f"   Demodulated signals: {len(calcium_demod)} samples")

    # Downsample
    print(f"\n3. Downsampling to {TARGET_FS} Hz...")
    t_raw = np.arange(len(calcium_demod)) / raw_fs
    t_downsampled = np.arange(0, t_raw[-1], 1 / TARGET_FS)

    calcium_ds = np.interp(t_downsampled, t_raw, calcium_demod)
    isosbestic_ds = np.interp(t_downsampled, t_raw, isosbestic_demod)

    print(f"   Downsampled signals: {len(calcium_ds)} samples")

    # Calculate dF/F
    print(f"\n4. Calculating dF/F...")
    dff_block, fit_results = calculate_dff_with_biexponential_fit(
        calcium_ds,
        isosbestic_ds,
        sampling_rate=TARGET_FS,
        exclude_first_seconds=1.0,
    )

    slope, intercept = fit_results["linear_coefficients"]
    print(f"   dF/F calculated: {len(dff_block)} samples")
    print(f"   Mean: {np.nanmean(dff_block):.2f}%")
    print(f"   Baseline fit slope: {slope:.4f}")

    # Store processed block
    processed_blocks[tag] = {
        "raw_signal": raw_signal_block,
        "calcium_demod": calcium_demod,
        "isosbestic_demod": isosbestic_demod,
        "calcium_ds": calcium_ds,
        "isosbestic_ds": isosbestic_ds,
        "dff": dff_block,
        "time_offset": padded_start,  # Time offset from start of full recording
        "fit_results": fit_results,
        "trials_df": block_info["trials_df"],
    }

print(f"\n{'=' * 80}")
print(f"All {len(processed_blocks)} blocks processed successfully!")
print(f"{'=' * 80}")

# %% Section 3b: Validate Reproduced Signals Against NWB-Stored Signals

print("\n" + "=" * 100)
print("VALIDATION: COMPARE REPRODUCED SIGNALS WITH NWB-STORED SIGNALS")
print("=" * 100)
print("\nValidating each block's reproduced signals against NWB-stored data.\n")

# Get NWB processing module
ophys_module = nwbfile.processing["ophys"]

# Find NWB signal names
calcium_nwb_name = None
isosbestic_nwb_name = None
dff_nwb_name = None

for name in ophys_module.data_interfaces.keys():
    if "downsampled_calcium" in name.lower():
        calcium_nwb_name = name
    elif "downsampled_isosbestic" in name.lower():
        isosbestic_nwb_name = name
    elif "deltaf_over_f" in name.lower() or "dff" in name.lower():
        dff_nwb_name = name

# Extract full NWB signals
calcium_nwb_full = ophys_module[calcium_nwb_name].data[:]
isosbestic_nwb_full = ophys_module[isosbestic_nwb_name].data[:]
dff_nwb_full = ophys_module[dff_nwb_name].data[:] if dff_nwb_name else None

validation_results = {}

for tag, block_data in processed_blocks.items():
    print(f"\nValidating Block: {tag}")
    print(f"{'-' * 60}")

    # Get block time range
    time_offset = block_data["time_offset"]
    dff_block = block_data["dff"]
    block_duration = len(dff_block) / TARGET_FS

    # Convert to sample indices in NWB signals
    start_sample = int(time_offset * TARGET_FS)
    end_sample = start_sample + len(dff_block)

    # Extract corresponding NWB segments
    calcium_nwb_block = calcium_nwb_full[start_sample:end_sample]
    isosbestic_nwb_block = isosbestic_nwb_full[start_sample:end_sample]

    # Handle length mismatches
    min_len = min(len(block_data["calcium_ds"]), len(calcium_nwb_block))

    # Validate calcium signal
    calcium_repro = block_data["calcium_ds"][:min_len]
    calcium_nwb = calcium_nwb_block[:min_len]
    corr_calcium = np.corrcoef(calcium_repro, calcium_nwb)[0, 1]
    rmse_calcium = np.sqrt(np.mean((calcium_repro - calcium_nwb) ** 2))

    # Validate isosbestic signal
    isosbestic_repro = block_data["isosbestic_ds"][:min_len]
    isosbestic_nwb = isosbestic_nwb_block[:min_len]
    corr_isosbestic = np.corrcoef(isosbestic_repro, isosbestic_nwb)[0, 1]
    rmse_isosbestic = np.sqrt(np.mean((isosbestic_repro - isosbestic_nwb) ** 2))

    print(f"  Calcium Signal:")
    print(f"    Correlation: {corr_calcium:.6f}")
    print(f"    RMSE: {rmse_calcium:.4f}")

    print(f"  Isosbestic Signal:")
    print(f"    Correlation: {corr_isosbestic:.6f}")
    print(f"    RMSE: {rmse_isosbestic:.4f}")

    # Validate dF/F if available
    if dff_nwb_full is not None:
        dff_nwb_block = dff_nwb_full[start_sample:end_sample]
        dff_repro = block_data["dff"][:min_len]
        dff_nwb = dff_nwb_block[:min_len]

        corr_dff = np.corrcoef(dff_repro, dff_nwb)[0, 1]
        rmse_dff = np.sqrt(np.mean((dff_repro - dff_nwb) ** 2))

        print(f"  dF/F Signal:")
        print(f"    Correlation: {corr_dff:.6f}")
        print(f"    RMSE: {rmse_dff:.4f}%")

        validation_results[tag] = {
            "corr_calcium": corr_calcium,
            "corr_isosbestic": corr_isosbestic,
            "corr_dff": corr_dff,
            "rmse_calcium": rmse_calcium,
            "rmse_isosbestic": rmse_isosbestic,
            "rmse_dff": rmse_dff,
        }
    else:
        validation_results[tag] = {
            "corr_calcium": corr_calcium,
            "corr_isosbestic": corr_isosbestic,
            "rmse_calcium": rmse_calcium,
            "rmse_isosbestic": rmse_isosbestic,
        }

    if corr_calcium > 0.999 and corr_isosbestic > 0.999:
        print(f"  ✓ VALIDATION PASSED for signals (r > 0.999)")
    else:
        print(f"  ⚠ WARNING: Check demodulation for this block")

# Visualize validation for each block
for tag, block_data in processed_blocks.items():
    print(f"\nCreating validation plots for block: {tag}")

    time_offset = block_data["time_offset"]
    start_sample = int(time_offset * TARGET_FS)
    end_sample = start_sample + len(block_data["dff"])

    # Extract NWB segments
    calcium_nwb_block = calcium_nwb_full[start_sample:end_sample]
    isosbestic_nwb_block = isosbestic_nwb_full[start_sample:end_sample]

    min_len = min(len(block_data["calcium_ds"]), len(calcium_nwb_block))

    # Create time vector
    time_vec = np.arange(min_len) / TARGET_FS / 60  # in minutes

    # Create comparison plots
    fig, axes = plt.subplots(2, 1, figsize=(15, 8))
    fig.suptitle(f"Block {tag} - Signal Validation", fontsize=14, fontweight="bold")

    # Calcium comparison
    axes[0].plot(time_vec, calcium_nwb_block[:min_len], "k-", linewidth=1, alpha=0.7, label="NWB Stored")
    axes[0].plot(time_vec, block_data["calcium_ds"][:min_len], "r--", linewidth=1, alpha=0.7, label="Reproduced")
    axes[0].set_ylabel("Calcium Signal (a.u.)")
    axes[0].set_title(f"Calcium (465nm) - r={validation_results[tag]['corr_calcium']:.6f}")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Isosbestic comparison
    axes[1].plot(time_vec, isosbestic_nwb_block[:min_len], "k-", linewidth=1, alpha=0.7, label="NWB Stored")
    axes[1].plot(time_vec, block_data["isosbestic_ds"][:min_len], "b--", linewidth=1, alpha=0.7, label="Reproduced")
    axes[1].set_xlabel("Time (minutes)")
    axes[1].set_ylabel("Isosbestic Signal (a.u.)")
    axes[1].set_title(f"Isosbestic (405nm) - r={validation_results[tag]['corr_isosbestic']:.6f}")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()

    # dF/F validation plot if available
    if dff_nwb_full is not None and "corr_dff" in validation_results[tag]:
        dff_nwb_block = dff_nwb_full[start_sample:end_sample]

        fig, axes = plt.subplots(3, 1, figsize=(15, 10))
        fig.suptitle(f"Block {tag} - dF/F Validation", fontsize=14, fontweight="bold")

        # Full trace comparison
        axes[0].plot(time_vec, dff_nwb_block[:min_len], "k-", linewidth=1, alpha=0.7, label="NWB Stored")
        axes[0].plot(time_vec, block_data["dff"][:min_len], "r--", linewidth=1, alpha=0.7, label="Reproduced")
        axes[0].set_ylabel("dF/F (%)")
        axes[0].set_title(f"dF/F Comparison - r={validation_results[tag]['corr_dff']:.6f}")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # Zoomed view (first 2 minutes or entire block if shorter)
        zoom_samples = min(int(2 * 60 * TARGET_FS), min_len)
        axes[1].plot(
            time_vec[:zoom_samples], dff_nwb_block[:zoom_samples], "k-", linewidth=1, alpha=0.7, label="NWB Stored"
        )
        axes[1].plot(
            time_vec[:zoom_samples], block_data["dff"][:zoom_samples], "r--", linewidth=1, alpha=0.7, label="Reproduced"
        )
        axes[1].set_ylabel("dF/F (%)")
        axes[1].set_title("dF/F Comparison - Zoomed")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        # Residuals
        residuals = block_data["dff"][:min_len] - dff_nwb_block[:min_len]
        axes[2].plot(time_vec, residuals, "purple", linewidth=0.8)
        axes[2].axhline(0, color="black", linestyle="--", linewidth=1, alpha=0.5)
        axes[2].set_xlabel("Time (minutes)")
        axes[2].set_ylabel("Difference (%)")
        axes[2].set_title(f"Residuals - RMSE={validation_results[tag]['rmse_dff']:.4f}%")
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

print("\n" + "=" * 100)
print("Validation complete for all blocks!")
print("=" * 100)

# %% Section 4: Extract Trials from Each Block

print("\n" + "=" * 100)
print("STEP 3: EXTRACT TRIALS FROM EACH BLOCK")
print("=" * 100)

# Organize trials by block and frequency
organized_data = {}

for tag, block_data in processed_blocks.items():
    print(f"\nProcessing trials for block: {tag}")

    dff_block = block_data["dff"]
    time_offset = block_data["time_offset"]
    trials_df = block_data["trials_df"]

    # Adjust trial times relative to block start
    adjusted_trial_times = trials_df["start_time"].values - time_offset

    # Group trials by frequency (if frequency column exists)
    if "stimulus_frequency" in trials_df.columns:
        unique_frequencies = trials_df["stimulus_frequency"].unique()

        for freq in unique_frequencies:
            freq_mask = trials_df["stimulus_frequency"] == freq
            freq_trials = trials_df[freq_mask]
            freq_trial_times = adjusted_trial_times[freq_mask]

            # Extract trials
            trials, time_vec = extract_trials_around_events(
                dff_block,
                freq_trial_times,
                sampling_rate=TARGET_FS,
                baseline_duration=5.0,
                post_event_duration=10.0,
            )

            # Normalize trials
            normalized = baseline_normalize_trials(trials, time_vec)

            # Create condition label
            condition_label = f"{tag}_{int(freq)}Hz"

            # Parse duration from tag
            if "250ms" in tag or "250" in tag:
                duration = 0.25
            elif "1s" in tag or tag == "1":
                duration = 1.0
            elif "4s" in tag or tag == "4":
                duration = 4.0
            else:
                # Try to extract from tag
                duration = float(tag.replace("s", "").replace("ms", "")) if any(c.isdigit() for c in tag) else 1.0

            organized_data[condition_label] = {
                "trials": trials,
                "time_vector": time_vec,
                "normalized": normalized,
                "duration": duration,
                "frequency": freq,
                "block": tag,
                "n_trials": len(freq_trials),
            }

            print(f"  {condition_label}: {len(freq_trials)} trials, duration={duration}s, freq={freq}Hz")
    else:
        # No frequency column, just organize by block
        # Extract trials
        trials, time_vec = extract_trials_around_events(
            dff_block,
            adjusted_trial_times,
            sampling_rate=TARGET_FS,
            baseline_duration=5.0,
            post_event_duration=10.0,
        )

        # Normalize trials
        normalized = baseline_normalize_trials(trials, time_vec)

        # Parse duration
        if "250ms" in tag:
            duration = 0.25
        elif "1s" in tag:
            duration = 1.0
        elif "4s" in tag:
            duration = 4.0
        else:
            duration = 1.0

        organized_data[tag] = {
            "trials": trials,
            "time_vector": time_vec,
            "normalized": normalized,
            "duration": duration,
            "frequency": None,
            "block": tag,
            "n_trials": len(trials_df),
        }

        print(f"  {tag}: {len(trials_df)} trials, duration={duration}s")

# %% Section 5: Calculate Summary Statistics

print("\n" + "=" * 100)
print("STEP 4: CALCULATE SUMMARY STATISTICS")
print("=" * 100)

statistics_by_condition = {}

for condition_label, data_dict in organized_data.items():
    normalized_trials = data_dict["normalized"]
    time_vec = data_dict["time_vector"]
    stim_duration = data_dict["duration"]

    # Get standard time windows
    time_windows = get_standard_time_windows(stim_duration)

    # Calculate statistics
    stats = calculate_summary_statistics(
        normalized_trials,
        time_vec,
        time_windows,
        sampling_rate=TARGET_FS,
    )

    statistics_by_condition[condition_label] = {
        "windows": time_windows,
        "statistics": stats,
    }

    print(f"\n{condition_label} (n={normalized_trials.shape[0]} trials):")
    during_idx = list(time_windows.keys()).index("during_stim")
    print(f"  Mean dF/F: {stats['mean'][during_idx]:.2f}%")
    print(f"  Peak: {stats['peak'][during_idx]:.2f}%")
    print(f"  AUC: {stats['auc'][during_idx]:.2f}")

# %% Section 6: Visualize Trials by Duration Block

print("\n" + "=" * 100)
print("STEP 5: VISUALIZE TRIALS ORGANIZED BY DURATION")
print("=" * 100)

# Group conditions by duration
duration_groups = {}
for condition_label, data_dict in organized_data.items():
    duration = data_dict["duration"]
    if duration not in duration_groups:
        duration_groups[duration] = []
    duration_groups[duration].append(condition_label)

# Create heatmaps organized by duration
for duration, conditions in sorted(duration_groups.items()):
    n_conditions = len(conditions)
    fig, axes = plt.subplots(1, n_conditions, figsize=(5 * n_conditions, 5))

    if n_conditions == 1:
        axes = [axes]

    fig.suptitle(f"Stimulus Duration: {duration}s - All Frequencies", fontsize=14, fontweight="bold")

    for idx, condition_label in enumerate(conditions):
        data_dict = organized_data[condition_label]
        normalized_trials = data_dict["normalized"]
        time_vec = data_dict["time_vector"]
        frequency = data_dict.get("frequency", "N/A")

        im = axes[idx].imshow(
            normalized_trials,
            aspect="auto",
            cmap="RdBu_r",
            vmin=-5,
            vmax=20,
            extent=[time_vec[0], time_vec[-1], normalized_trials.shape[0], 0],
        )

        axes[idx].axvline(0, color="white", linestyle="--", linewidth=2)
        axes[idx].axvline(duration, color="white", linestyle=":", linewidth=1.5, alpha=0.8)
        axes[idx].set_xlabel("Time (s)")
        axes[idx].set_ylabel("Trial")
        axes[idx].set_title(f"{frequency} Hz\n(n={normalized_trials.shape[0]})")
        plt.colorbar(im, ax=axes[idx], label="Normalized dF/F (%)")

    plt.tight_layout()
    plt.show()

# %% Section 7: Plot Mean Traces by Frequency within Each Duration

print("\n" + "=" * 100)
print("STEP 6: PLOT MEAN TRACES BY FREQUENCY")
print("=" * 100)

# Create separate plots for each duration
freq_colors = {5: "blue", 10: "green", 20: "orange", 40: "red"}

for duration in sorted(duration_groups.keys()):
    fig, ax = plt.subplots(figsize=(12, 6))

    conditions_for_duration = duration_groups[duration]

    for condition_label in conditions_for_duration:
        data_dict = organized_data[condition_label]
        normalized_trials = data_dict["normalized"]
        time_vec = data_dict["time_vector"]
        frequency = data_dict.get("frequency", 0)

        mean_trace = np.nanmean(normalized_trials, axis=0)
        sem_trace = np.nanstd(normalized_trials, axis=0) / np.sqrt(normalized_trials.shape[0])

        color = freq_colors.get(int(frequency), "black")
        ax.plot(time_vec, mean_trace, color=color, linewidth=2, label=f"{int(frequency)} Hz")
        ax.fill_between(time_vec, mean_trace - sem_trace, mean_trace + sem_trace, color=color, alpha=0.2)

    ax.axvline(0, color="gray", linestyle="--", linewidth=1, alpha=0.5, label="Onset")
    ax.axvline(duration, color="gray", linestyle=":", linewidth=1, alpha=0.5, label="Offset")
    ax.axhline(0, color="black", linestyle="-", linewidth=0.5, alpha=0.3)

    ax.set_xlabel("Time relative to stimulus onset (s)")
    ax.set_ylabel("Normalized dF/F (%)")
    ax.set_title(f"Frequency Comparison - {duration}s Stimulation Duration")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()

# %% Section 8: Frequency-Response Curves

print("\n" + "=" * 100)
print("STEP 7: FREQUENCY-RESPONSE ANALYSIS")
print("=" * 100)

# Create frequency-response curves for each duration
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

metric_names = ["Mean dF/F (%)", "Peak dF/F (%)", "AUC"]
metric_keys = ["mean", "peak", "auc"]

for metric_idx, (metric_name, metric_key) in enumerate(zip(metric_names, metric_keys)):
    ax = axes[metric_idx]

    for duration in sorted(duration_groups.keys()):
        frequencies = []
        metric_values = []

        for condition_label in duration_groups[duration]:
            data_dict = organized_data[condition_label]
            frequency = data_dict.get("frequency")

            if frequency is not None:
                stats = statistics_by_condition[condition_label]["statistics"]
                windows = statistics_by_condition[condition_label]["windows"]
                during_idx = list(windows.keys()).index("during_stim")

                frequencies.append(frequency)
                metric_values.append(stats[metric_key][during_idx])

        if frequencies:
            # Sort by frequency
            sorted_pairs = sorted(zip(frequencies, metric_values))
            frequencies, metric_values = zip(*sorted_pairs)

            ax.plot(frequencies, metric_values, "o-", linewidth=2, markersize=8, label=f"{duration}s")

    ax.set_xlabel("Stimulus Frequency (Hz)")
    ax.set_ylabel(metric_name)
    ax.set_title(f"{metric_name} vs Frequency")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xscale("log")
    ax.set_xticks([5, 10, 20, 40])
    ax.set_xticklabels(["5", "10", "20", "40"])

plt.tight_layout()
plt.show()

print("\nFrequency-response curves displayed.")

# %% Section 9: Final Summary

print("\n" + "=" * 100)
print("VARYING FREQUENCIES ANALYSIS COMPLETE")
print("=" * 100)

print(f"\nProcessing Summary:")
print(f"  Subject: {SUBJECT_ID}")
print(f"  Session: {SESSION_ID}")
print(f"  Duration blocks processed: {len(processed_blocks)}")
print(f"  Total conditions analyzed: {len(organized_data)}")
print(f"  Total trials: {sum(d['n_trials'] for d in organized_data.values())}")

print(f"\nConditions by duration:")
for duration in sorted(duration_groups.keys()):
    conditions = duration_groups[duration]
    print(f"  {duration}s: {len(conditions)} frequency conditions")

print(f"\n" + "=" * 100)
print("Analysis successfully reproduced for varying frequencies session!")
print("=" * 100)

# Close NWB file
io.close()
