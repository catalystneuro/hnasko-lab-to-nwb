# DANDI:001528 description

Description of DANDI:001528, kept here so that it is reviewed with the conversion and copied to the dandiset
metadata when files are uploaded.

Name: Fiber photometry of substantia nigra responses to optogenetic stimulation of STN, PPN and SNr inputs

Description:

This dataset contains the fiber photometry recordings of Hadjas et al. (2025), "Parkinson's Disease-vulnerable and
-resilient dopamine neurons display opposite responses to excitatory input" (bioRxiv, doi:10.1101/2025.06.03.657460).
In freely moving mice, glutamatergic neurons of the subthalamic nucleus (STN) or the pedunculopontine nucleus (PPN)
expressed ChrimsonR, and their terminals in the substantia nigra (SN) were stimulated with trains of 635 nm laser
pulses at 5 mW while fluorescence was recorded through an optical fiber. In control mice, the STN neurons
expressed mCherry without an opsin. In a further group, GABAergic neurons of the substantia nigra pars reticulata
(SNr) expressed an opsin and were stimulated through a fiber over SNc.

The recordings come from seven groups of mice:

- SNr GABA neurons (GCaMP6f, VGLUT2-Cre x VGAT-Flp mice)
- SNc dopamine neurons (GCaMP6f, VGLUT2-Cre x DAT-Flp mice)
- Vglut2+ dopamine neurons in SNc (GCaMP6f, VGLUT2-Cre x DAT-Flp mice)
- Anxa1+ dopamine neurons in SNc and their axon terminals in the dorsolateral striatum (GCaMP8f, VGLUT2-PhiC31 x
  Anxa1-Cre mice)
- dopamine release in the dorsolateral striatum or the tail of the striatum (GRAB-DA2m, VGLUT2-Cre mice), with
  mCherry controls for STN stimulation
- dopamine release in the dorsolateral striatum or the tail of the striatum during stimulation of SNr GABA neurons
  (GRAB-DA2m, VGAT-Cre mice)
- dopamine axon terminals in the dorsolateral striatum or the tail of the striatum (GCaMP6f, VGLUT2-Cre x DAT-Flp
  mice, STN stimulation only)

Sessions follow one of two protocols. In the varying-durations protocol, 40 Hz trains of 250 ms, 1 s and 4 s
alternate, 5 times each, 10 s apart; the 2022 recordings add 16 s trains, which were not analyzed in the paper. In
the varying-frequencies protocol, one block is recorded per train duration, and in each block trains at 5, 10, 20 and
40 Hz alternate, 5 times each, 20 s apart.

Each NWB file holds one session: the raw photodetector signal recorded by the TDT system, the demodulated,
downsampled and dF/F signals computed by the lab (for the SNr-input group, computed from the raw signal by the
conversion code), the optogenetic stimulation trains with their duration, frequency and power, and the devices, viral vectors and stereotaxic coordinates of the fibers and injections.

The conversion code is at <https://github.com/catalystneuro/hnasko-lab-to-nwb>.
