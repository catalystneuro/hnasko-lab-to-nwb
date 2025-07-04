# Notes concerning the embargo_2025 conversion

Mice were freely moving on a plastic tub.
Simultaneous passive optogenetic stimulations and fiber photometry recordings were conducted during the first two days.
Briefly, excitatory inputs from either the STN or PPN to SN were stimulated and the activity of SN GABAergic neurons were recorded.
Then mice underwent uncued electrical shocks and were recorded using fiber photometry.

## Session description

Each subject --> 3 experimental days:

### Day 1: Varying duration
During day 1, mice were placed in a plastic tub and were recorded for 3.5 minutes.
The mice received a 40 Hz stimulation at various durations (i.e. 250ms, 1s and 4s) 5 times for each duration
with an inter-stimulus interval (ISI) of 10s.

### Day 2: Varying frequencies
The next day, the animals were placed in the same set-up and underwent 3 recording sessions corresponding
to a fixed duration of stimulation (i.e., 250ms, 1s, and 4s). Each session lasted 8 minutes.
The animals received optogenetic stimulation at varying frequencies (5 Hz, 10 Hz , 20 Hz and 40 Hz)
5 times for each duration with an ISI of 10s.

### Day 3: Shock
During day 3, animals were placed in a shock chamber and recorded for 6 minutes.
Uncued shocks (0.3 mA) at various durations (250ms, 1s and 4s, 5 times for each duration) were delivered
in a randomized order and ISI.

## Fiber photometry data
The recordings were done using a fiber photometry rig with optical components from Tucker David Technologies (TDT) and
Doric lenses controlled by a real-time processor from TDT (RZ10x).
TDT software Synapse was used for data acquisition.
Gcamp6f was excited by amplitude modulated signals from two light-emitting diodes (465- and 405-nm isosbestic control, TDT).

## Optogenetic stimulation and shock stimulus
Stimulation and shock timestamps were digitized in Synapse software by respectively AnyMaze and MedPC.
Optogenetic stimulation metadata:
```yaml
Stimulus:
 OptogeneticStimulusSite:
   - name: optogenetic_stimulus_site
     description: The site where the optogenetic stimulation was applied.
     excitation_lambda: 635.0 # Excitation wavelength in nanometers.
 OptogeneticSeries:
   name: optogenetic_series
   site: optogenetic_stimulus_site
   description: The reconstructed timeseries for the optogenetic stimulation.
 OptogeneticStimulusInterval:
   name: optogenetic_stimulus_interval
   description: Optogenetic stimulus events from TDT epochs.
TDTEvents:
 stream_names: ["sms_","s1s_","s4s_"] #
 stimuli_frequencies: [40.0, 40.0, 40.0]
```
## TDT data structure

### TDT stream
For all subjects and all session types:
- From stream '_405A' --> isosbestic signal # ignore --> 6Hz filtered
- From stream '_465A' --> calcium signal # ignore --> 6Hz filtered
- Stream 'Fi1r' --> raw signal

### TDT events
For "Varying duration" sessions
- 'ssm_' or 'sms_'--> time intervals for optogenetic stimulation delivered for 250ms each stimulus,
- 's1s_'--> time intervals for optogenetic stimulation delivered for 1s each stimulus,
- 's4s_'--> time intervals for optogenetic stimulation delivered for 4s each stimulus

For "Varying frequencies" sessions
- 'H10_'--> time intervals for optogenetic stimulation delivered at 10Hz,
- 'H20_'--> time intervals for optogenetic stimulation delivered at 20Hz,
- 'H40_'--> time intervals for optogenetic stimulation delivered at 40Hz,
- 'H05_'--> time intervals for optogenetic stimulation delivered at 5Hz

For "Shock" sessions
- 'CSm_' --> conditioned stimulus minus (auditory cue not paired with shock)
- 'CSp_' --> conditioned stimulus plus (auditory cue paired with shock)

For new "Shock" sessions
- 'sms_'--> time intervals for uncued shock stimulation delivered for 250ms each stimulus,
- 's1s_'--> time intervals for uncued shock stimulation delivered for 1s each stimulus,
- 's4s_'--> time intervals for uncued shock stimulation delivered for 4s each stimulus

## AnyMaze videos
Video needs to be converted in  .mp4 format using ANyMaze software dedicated tool.
The video start timestamp must be stored in an excel file ("video_metadata") two columns: "file_name" and "start_time".
