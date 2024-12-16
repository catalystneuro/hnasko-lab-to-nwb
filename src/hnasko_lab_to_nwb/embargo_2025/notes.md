# Notes concerning the embargo_2025 conversion

## Experiment description
3 experimental days:
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

## TDT data

### TDT stream
For all subjects and all session types:
- From stream '_405A' --> isosbestic signal
- From stream '_465A' --> calcium signal
- Stream 'Fi1r' --> TODO: ask point person

### TDT events
For "Varying duration" sessions
- 'ssm_'--> time intervals for optogenetic stimulation delivered for 250ms each stimulus,
- 's1s_'--> time intervals for optogenetic stimulation delivered for 1s each stimulus,
- 's4s_'--> time intervals for optogenetic stimulation delivered for 4s each stimulus
-
For "Varying frequencies" sessions
- 'H10_'--> time intervals for optogenetic stimulation delivered at 10Hz,
- 'H20_'--> time intervals for optogenetic stimulation delivered at 20Hz,
- 'H40_'--> time intervals for optogenetic stimulation delivered at 40Hz,
- 'H05_'--> time intervals for optogenetic stimulation delivered at 5Hz

For "Shock" sessions
- 'CSm_' --> TODO: ask point person
- 'CSp_' --> TODO: ask point person

## AnyMaze data
TODO: Contact AnyMaze support
