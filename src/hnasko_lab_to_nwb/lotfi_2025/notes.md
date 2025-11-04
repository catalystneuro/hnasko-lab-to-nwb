# Notes concerning the lotfi_2025 conversion

Mice were freely moving on a plastic tub.
Simultaneous passive optogenetic stimulations and fiber photometry recordings were conducted during the first two days.
Briefly, excitatory inputs from either the STN or PPN to SN were stimulated and the activity of SN GABAergic neurons were recorded.
Then mice underwent uncued electrical shocks and were recorded using fiber photometry.

Reference paper:  ["Parkinson's Disease-vulnerable and -resilient dopamine neurons display opposite responses to excitatory input"](https://www.biorxiv.org/content/10.1101/2025.06.03.657460v1)


## Sessions description

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

This conversion pipeline convert only the "Varying duration" and "Varying frequencies" sessions. Refer to embargo_2025 for converting the "Shock" sessions.

## Optogenetic stimulation protocols
Optogenetic stimulations were delivered by a red laser (Shanghai laser, 635nm) at 5 mW power.  The mice received 40 Hz stimulations at various durations (i.e. 250 ms, 1 s and 4 s), 5 trials for each duration, with an inter-stimulation interval (ISI) of 10 s, and trials within session and subject were averaged. In subsequent recording sessions, mice received optogenetic stimulation at varying frequencies (5 Hz, 10 Hz , 20 Hz and 40 Hz), 5 trials for each, with an ISI of 20 s. For a given session block, the stimulation durations were again either 250 ms, 1 s, or 4 s, with the order of stimulation duration blocks (ascending or descending) counterbalanced across animals.

The recordings were done using a fiber photometry rig with optical components from Tucker David Technologies (TDT) and
Doric lenses controlled by a real-time processor from TDT (RZ10x).
TDT software Synapse was used for data acquisition.
Gcamp6f was excited by amplitude modulated signals from two light-emitting diodes (465- and 405-nm isosbestic control, TDT).

### 1. SNr GABA GCaMP6f recordings, STN & PPN stim

#### Fiber photometry

* Setup FP1
* Optical fiber model: 400-um core, 0.39 NA, 6-mm length, 1.25-mm diameter black ceramic ferrule, RWD
* Optical fiber location:  **SNr** (AP -3.3, ML +/-1.4, DV -4.4).
* Targeted neurons: **SNr GABA Neurons** in VGLUT2-Cre x VGAT-Flp mice
* Indicator: 300 nl of AAV1-Ef1a-fDIO-**GCaMP6f** (4e12 vg/mL, Addgene 1283125)
* Indicator injection site: **SNr** (AP -3.3, ML +/-1.3, DV -4.6)

#### Optogenetic Stimulation

* Effector: 150-200 nl of AAV5-Syn-FLEX-**ChrimsonR-tdTomato** (4 – 8.5e12 vg/ml, Addgene 62723)

* Effector injection sites:
    * **STN** (AP -2.00, ML +/-1.6, DV -4.5)
    * **PPN** (AP -4.48, ML +/- 1.1, DV -3.75)

### 2. SNc pan-DA GCaMP6f recordings, STN & PPN stim

#### Fiber photometry

* Setup FP1 
* Optical fiber model: 400-um core, 0.39 NA, 6-mm length, 1.25-mm diameter black ceramic ferrule, RWD
* Optical fiber location: **SNc** (AP -3.2, ML +/-1.4, DV -4.1).
* Targeted neurons: **SNc pan-DA Neurons** in VGLUT2-Cre x DAT-Flp mice
* Indicator: 300 nl of AAV1-Ef1a-fDIO-GCaMP6f (4e12 vg/mL, Addgene 1283125)
* Indicator injection site: **SNc** (AP -3.2, ML +/-1.3, DV -4.3)

####  Optogenetic Stimulation

* Effector: 150-200 nl of AAV5-Syn-FLEX-**ChrimsonR-tdTomato** (4 – 8.5e12 vg/ml, Addgene 62723)
* Effector injection sites:
    * **STN** (AP -2.00, ML +/-1.6, DV -4.5)
    * **PPN** (AP -4.48, ML +/- 1.1, DV -3.75)

### 3. Striatal GRAB_DA recordings (DLS & TS), STN & PPN stim

#### Fiber photometry

* Setup FP3
* Optical fiber model: 200-um core, 0.39 NA, L = 6 mm, 1.25-mm diameter white ceramic ferrule, RWD
* Optical fiber locations: 
    * **DLS** (AP +0.5, ML +/- 2.25, DV -2.75)
    * **TS** (AP -1.25, ML +/-2.9, DV -3.25)
* Targeted neurons: **DA release in striatal subregions (DLS and TS)** in VGLUT2-Cre mice
* Indicator: 300 nl of AAV9-EF1a-GRABDA2m (2e12 vg/mL, Addgene: 140553)
* Indicator injection sites: 
    * **DLS** (AP +0.5, ML +/-2.25, DV -2.95)
    * **TS** (AP -1.25, ML +/-2.9, DV -3.45)

####  Optogenetic Stimulation

* Effector: 150-200 nl of AAV5-Syn-FLEX-**ChrimsonR-tdTomato** (4 – 8.5e12 vg/ml, Addgene 62723)
* Effector injection sites:
    * **STN** (AP -2.00, ML +/-1.6, DV -4.5)
    * **PPN** (AP -4.48, ML +/- 1.1, DV -3.75)

### 4. SNc DA subtype recordings (Anxa1 & Vglut2), STN & PPN stim

#### Fiber photometry Anxa1

* Setup FP3 
* Optical fiber model: 400-um core, 0.39 NA, 6-mm length, 1.25-mm diameter black ceramic ferrule, RWD
* Optical fiber locations: 
    * **SNc** (AP -3.2, ML +/-1.4, DV -4.1).
    * **DLS** (AP +0.5, ML +/- 2.25, DV -2.75)
* Targeted neurons: **DA neurons and terminals projecting to DLS** in VGLUT2-PhiC x Anxa1Cre mice
* Indicator: 300 nl of AAV5-Syn-FLEX-GCaMP8f (1e13 vg/ml, Addgene: 162379)
* Indicator injection site: **SNc** (AP -3.2, ML +/-1.3, DV -4.3)

####  Optogenetic Stimulation Anxa1

* Effector: 150-200 nl of AAVDJ-Ef1a-pSIO-ChrimsonR-tdTomato (1e13 vg/ml, Vectorbuilder)
* Effector injection sites:
    * **STN** (AP -2.00, ML +/-1.6, DV -4.5)
    * **PPN** (AP -4.48, ML +/- 1.1, DV -3.75)

#### Fiber photometry Vglut2

* Setup FP1 
* Optical fiber model: 400-um core, 0.39 NA, 6-mm length, 1.25-mm diameter black ceramic ferrule, RWD
* Optical fiber location: **SNc** (AP -3.2, ML +/-1.6, DV -4.0).
* Targeted neurons: **SNc Vglut2+ DA Neurons** in VGLUT2-Cre x DAT-Flp mice
* Indicator: 300 nl of AAV8-Ef1a-ConFon-GCaMP6f (2.3e12 vg/ml, Addgene: 137122)
* Indicator injection site: **SNc** (AP -3.2, ML +/-1.5, DV -4.2)

####  Optogenetic Stimulation Vglut2

* Effector: 150-200 nl of AAV5-Syn-FLEX-**ChrimsonR-tdTomato** (4 – 8.5e12 vg/ml, Addgene 62723)
* Effector injection sites:
    * **STN** (AP -2.00, ML +/-1.6, DV -4.5)
    * **PPN** (AP -4.48, ML +/- 1.1, DV -3.75)

### 5. DA axon terminal GCaMP recordings, STN stim only

#### Fiber photometry

* Setup FP3
* Optical fiber model: 200-um core, 0.39 NA, L = 6 mm, 1.25-mm diameter white ceramic ferrule, RWD
* Optical fiber locations: 
    * **DLS** (AP +0.5, ML +/- 2.25, DV -2.75)
    * **TS** (AP -1.25, ML +/-2.9, DV -3.25)
* Targeted neurons: **DA axon terminal (DLS and TS)** in VGlut2-cre x DAT-flp
* Indicator: 300 nl of AAV1-Ef1a-fDIO-**GCaMP6f** (4e12 vg/mL, Addgene 1283125)
* Indicator injection sites: 
    * **DLS** (AP +0.5, ML +/-2.25, DV -2.95)
    * **TS** (AP -1.25, ML +/-2.9, DV -3.45)

####  Optogenetic Stimulation

* Effector: 150-200 nl of AAV5-Syn-FLEX-**ChrimsonR-tdTomato** (4 – 8.5e12 vg/ml, Addgene 62723)
* Effector injection site: **STN** (AP -2.00, ML +/-1.6, DV -4.5)

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

## AnyMaze videos
Video needs to be converted in  .mp4 format using ANyMaze software dedicated tool.
The video start timestamp must be stored in an excel file ("video_metadata") two columns: "file_name" and "start_time".
Not all sessions have AnyMaze videos

## Processed data (.mat files)
Example: `PPN_Vglut2_SNr_GABA_GCaMP_varDurs_40Hz_5mW_Demod.mat` file will contain:

### Demodulated Signals:
- `Gc_raw.SNr.[subject].LP5mW`: Raw 465nm demodulated signal
- `af_raw.SNr.[subject].LP5mW`: Raw 405nm demodulated signal
- `Gc.SNr.[subject].LP5mW`: Downsampled 465nm signal (100 Hz)
- `af.SNr.[subject].LP5mW`: Downsampled 405nm signal (100 Hz)

### Processed dF/F Data:
- `dF.SNr.[subject].LP5mW`: Baseline-corrected dF/F traces
- `norm_dF.SNr.[subject].LP5mW.[duration]`: Trial-aligned, baseline-normalized dF/F
- `out_dFs.SNr.LP5mW.[duration]`: Subject-averaged traces for each duration
