# NWB file structure

Each file holds one session. This page lists where each part of the session is stored; `<site>` is the recording
site of the subject, for example `SNr`, `SNc`, `DLS` or `TS`. Times are in seconds from the start of the session's
first TDT block (`session_start_time`, in the lab's time zone).

| Path in the file | Content |
|---|---|
| `acquisition/raw_signal_<site>` | raw photodetector signal (TDT `Fi1r`), at the rate of the rig |
| `processing/ophys/demodulated_calcium_signal_<site>` | 465 nm signal, demodulated and lowpass filtered at 6 Hz, at the raw rate |
| `processing/ophys/demodulated_isosbestic_control_<site>` | isosbestic control, demodulated and lowpass filtered at 6 Hz, at the raw rate |
| `processing/ophys/downsampled_calcium_signal_<site>` | 465 nm signal at 100 Hz |
| `processing/ophys/downsampled_isosbestic_control_<site>` | isosbestic control at 100 Hz |
| `processing/ophys/deltaF_over_F_<site>` | dF/F in percent, at 100 Hz |
| `intervals/optogenetic_epochs_table` | one row per stimulation train |
| `intervals/trials` | one row per block of a varying-frequencies session |
| `general/fiber_photometry` | fiber photometry table, indicators, viruses and injections |
| `general/optogenetic_experiment_metadata` | stimulation sites, effectors, viruses and injections |
| `general/devices` | fibers, LEDs, photodetector, filters, dichroic mirror, laser |
| `general/subject` | subject ID, sex, age, strain, genotype, description |

The processed series are present when the conversion wrote them (see [Data streams](data_streams.md)). Their
descriptions say whether they come from the lab's `.mat` file or were recomputed by this package.

## Fiber photometry series

All series are `FiberPhotometryResponseSeries` (ndx-fiber-photometry). Each points to its row of the fiber
photometry table: the 465 nm row for the raw signal, the 465 nm and dF/F series, the isosbestic row for the
isosbestic series. The table row gives the location, wavelengths, indicator, optical fiber, LED, photodetector and
filters. The descriptions of the LEDs and of the demodulated series give the modulation frequencies.

A session of several blocks (varying frequencies) is stored as one series per signal, concatenated over the blocks.
Each series has timestamps, with a gap between blocks, so the series stay on the same clock as the stimulation
epochs.

## Optogenetic stimulation

`intervals/optogenetic_epochs_table` (ndx-optogenetics) has one row per train, from its onset and offset recorded by
TDT Synapse. Besides the standard columns (start and stop time, power, wavelength, pulse period, number of pulses,
stimulation site) it has:

- `stimulus_frequency`: the pulse frequency in Hz.
- `train_duration`: the train duration of the protocol (`250ms`, `1s`, `4s` or `16s`). The recorded duration is
  `stop_time - start_time`.
- `tdt_block`: the TDT block folder of the train.

The pulse width was not recorded, so `pulse_length_in_ms` is NaN.

## Trials

In a varying-frequencies session, `trials` has one row per block, from its first to its last raw sample, tagged with
the block's train duration. In SN pan GABA PPN, where the three durations are in one block, each trial spans the trains
of one duration. Varying-durations sessions have no trials table.

## Reading a file

```python
from pynwb import NWBHDF5IO

with NWBHDF5IO("sub-C8972_ses-varying_frequencies.nwb", "r") as io:
    nwbfile = io.read()
    dff = nwbfile.processing["ophys"]["deltaF_over_F_TS"]
    dff_values, dff_times = dff.data[:], dff.timestamps[:]
    trains = nwbfile.intervals["optogenetic_epochs_table"].to_dataframe()
    trials = nwbfile.trials.to_dataframe()
```

Files on DANDI can also be opened in the browser with [Neurosift](https://neurosift.app).
