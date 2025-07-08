# hnasko-lab-to-nwb

NWB conversion scripts for Hnasko lab data to the [Neurodata Without Borders](https://nwb-overview.readthedocs.io/) data format.

This repository contains conversion tools for fiber photometry and optogenetic stimulation experiments conducted in the Hnasko lab. The conversion pipeline handles simultaneous fiber photometry recordings, behavioral videos, and various stimulation protocols (optogenetic and electrical shock) into standardized NWB format.

## Experimental Overview

The Hnasko lab studies the activity of substantia nigra (SN) GABAergic neurons using fiber photometry while manipulating excitatory inputs from either the subthalamic nucleus (STN) or pedunculopontine nucleus (PPN). The experimental paradigm consists of three days:

- **Day 1**: Varying duration optogenetic stimulation (250ms, 1s, 4s at 40Hz)
- **Day 2**: Varying frequency optogenetic stimulation (5Hz, 10Hz, 20Hz, 40Hz at fixed durations)
- **Day 3**: Uncued electrical shock conditioning with auditory cues

### Data Modalities

- **Fiber Photometry**: GCaMP6f calcium imaging from SN GABAergic neurons using TDT acquisition system
- **Optogenetic Stimulation**: ChrimsonR-mediated activation of STN or PPN inputs to SN
- **Behavioral Video**: Ceiling-mounted camera recordings during experiments
- **Electrical Stimulation**: Shock delivery with temporal precision

## Installation

To use this conversion package, you'll need to install it directly from GitHub. This approach allows you to access the latest features and modify the source code if needed to adapt to your specific experimental requirements.

### Prerequisites

Before installation, ensure you have the following tools installed:
- `git` ([installation instructions](https://github.com/git-guides/install-git))
- `conda` ([installation instructions](https://docs.conda.io/en/latest/miniconda.html)) - recommended for managing dependencies

### Installation Steps

From a terminal (note that conda should install one in your system) you can do the following:

```bash
git clone https://github.com/catalystneuro/hnasko-lab-to-nwb
cd hnasko-lab-to-nwb
conda env create --file make_env.yml
conda activate hnasko-lab-to-nwb-env
```

This creates a [conda environment](https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/environments.html) which isolates the conversion code from your system libraries. We recommend that you run all your conversion related tasks and analysis from the created environment in order to minimize issues related to package dependencies.

If you fork this repository and are running code from that fork, instead use:

```bash
git clone https://github.com/your_github_username/hnasko-lab-to-nwb
```

Alternatively, if you want to avoid conda altogether (for example if you use another virtual environment tool) you can install the repository with the following commands using only pip:

```bash
git clone https://github.com/catalystneuro/hnasko-lab-to-nwb
cd hnasko-lab-to-nwb
pip install --editable .
```

Note: both of the methods above install the repository in [editable mode](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs). The dependencies for this environment are stored in the dependencies section of the `pyproject.toml` file.

## Data Organization

### Expected Directory Structure

Your data should be organized as follows:

```
data_directory/
├── STN/                                    # Optogenetic stimulation location
│   ├── Fiber photometry_TDT/
│   │   ├── Varying durations/
│   │   │   └── {subject_id}-{timestamp}/   # TDT session folder
│   │   ├── Varying frequencies/
│   │   │   └── {subject_id}-{timestamp}/
│   │   └── Shocks/
│   │       └── {subject_id}-{timestamp}/
│   └── AnyMaze videos_slk/converted_video/
│       ├── Varying durations/
│       │   ├── {subject_id}*.mp4
│       │   └── video_metadata.xlsx
│       ├── Varying frequencies/
│       └── Shocks/
└── PPN/                                    # Alternative stimulation location
    ├── Fiber photometry_TDT/
    └── AnyMaze videos_slk/converted_video/
```

### TDT Data Structure

The TDT acquisition system generates the following data streams:

- **Fi1r**: Raw modulated fiber photometry signal
- **_405A**: Isosbestic control signal (405nm, filtered at 6Hz)
- **_465A**: Calcium-sensitive signal (465nm, filtered at 6Hz)

#### TDT Events by Protocol

**Varying Duration Sessions:**
- `sms_` or `ssm_`: 250ms optogenetic stimulation intervals
- `s1s_`: 1s optogenetic stimulation intervals
- `s4s_`: 4s optogenetic stimulation intervals

**Varying Frequency Sessions:**
- `H05_`: 5Hz optogenetic stimulation
- `H10_`: 10Hz optogenetic stimulation
- `H20_`: 20Hz optogenetic stimulation
- `H40_`: 40Hz optogenetic stimulation

**Shock Sessions:**
- `CSm_`: Conditioned stimulus minus (auditory cue not paired with shock)
- `CSp_`: Conditioned stimulus plus (auditory cue paired with shock)
- `sms_`, `s1s_`, `s4s_`: Uncued shock stimulation at different durations

## Usage

### Running a Single Session Conversion

Once you have installed the package, you can run any of the conversion scripts in a notebook or a python file:

```python
from pathlib import Path
from datetime import datetime
from hnasko_lab_to_nwb.lotfi_2025.convert_session import session_to_nwb

# Define your data paths
output_dir_path = Path("./nwb_output")
tdt_folder_path = Path("./data/STN/Fiber photometry_TDT/Varying durations/subject01-240101-120000")
video_file_paths = [Path("./data/STN/AnyMaze videos_slk/converted_video/Varying durations/subject01_250ms.mp4")]
video_metadata_file_path = Path("./data/STN/AnyMaze videos_slk/converted_video/Varying durations/video_metadata.xlsx")

# Run conversion
session_to_nwb(
    output_dir_path=output_dir_path,
    session_starting_time=datetime(2024, 1, 1, 12, 0, 0),
    subject_id="subject01",
    protocol_type="Varying durations",
    ogen_stimulus_location="STN",
    tdt_folder_path=tdt_folder_path,
    video_file_paths=video_file_paths,
    video_metadata_file_path=video_metadata_file_path,
    overwrite=True,
    verbose=True
)
```

### Batch Processing

For converting multiple sessions, you can use the batch processing script:

```bash
python src/hnasko_lab_to_nwb/lotfi_2025/convert_session.py
```

This script uses the `LocalPathExpander` to automatically discover and convert all sessions in your data directory. Modify the `data_dir_path` and `output_dir_path` variables in the script to match your setup.

### Conversion Parameters

#### Required Parameters

- `output_dir_path`: Directory where NWB files will be saved
- `session_starting_time`: Session start time as datetime object
- `subject_id`: Unique identifier for the subject
- `protocol_type`: One of "Varying durations", "Varying frequencies", or "Shocks"
- `ogen_stimulus_location`: Either "STN" or "PPN"
- `tdt_folder_path`: Path to TDT session folder
- `video_file_paths`: List of video file paths

#### Optional Parameters

- `video_metadata_file_path`: Path to video metadata Excel file
- `stub_test`: Create stub NWB files for testing (default: False)
- `overwrite`: Overwrite existing NWB files (default: False)
- `verbose`: Print detailed conversion progress (default: False)

## Repository Structure

Each conversion is organized in a directory of its own in the `src` directory:

```
hnasko-lab-to-nwb/
├── LICENSE
├── make_env.yml
├── pyproject.toml
├── README.md
└── src/
    └── hnasko_lab_to_nwb/
        └── lotfi_2025/
            ├── __init__.py
            ├── convert_session.py          # Main conversion script
            ├── convert_all_sessions.py     # Batch processing script
            ├── nwbconverter.py            # NWBConverter class definition
            ├── notes.md                   # Conversion-specific notes
            ├── interfaces/
            │   ├── __init__.py
            │   └── demodulated_tdt_interface.py  # Custom demodulated signal interface
            ├── metadata/
            │   ├── general_metadata.yaml         # General experimental metadata
            │   ├── varying_durations_ogen_metadata.yaml
            │   ├── varying_frequencies_ogen_metadata.yaml
            │   └── shock_stimulus_metadata.yaml
            └── utils/
                ├── __init__.py
                ├── add_optogenetic_stimulation.py
                ├── add_shock_stimuli.py
                ├── demodulate_fp_signal.py
                └── get_video_aligned_starting_time.py
```

### Key Files

- **`convert_session.py`**: Main script that defines the function to convert one full session
- **`nwbconverter.py`**: Contains the `Lofti2025NWBConverter` class that combines all data interfaces
- **`metadata/`**: YAML files containing experimental metadata for different protocols
- **`interfaces/`**: Custom data interfaces, including demodulated fiber photometry
- **`utils/`**: Utility functions for signal processing and stimulus addition

## Helpful Definitions

This conversion project is comprised primarily by DataInterfaces, NWBConverters, and conversion scripts.

### DataInterface

In neuroconv, a [DataInterface](https://neuroconv.readthedocs.io/en/main/user_guide/datainterfaces.html) is a class that specifies the procedure to convert a single data modality to NWB. This is usually accomplished with a single read operation from a distinct set of files. For example, in this conversion:

- **`TDTFiberPhotometryInterface`**: Converts raw TDT fiber photometry data
- **`TDTDemodulatedFiberPhotometryInterface`**: Converts demodulated calcium and isosbestic signals
- **`ExternalVideoInterface`**: Converts behavioral video recordings

### NWBConverter

In neuroconv, a [NWBConverter](https://neuroconv.readthedocs.io/en/main/user_guide/nwbconverter.html) is a class that combines many data interfaces and specifies the relationships between them, such as temporal alignment. The `Lofti2025NWBConverter` combines:

- Fiber photometry data (raw and demodulated)
- Behavioral videos with temporal alignment
- Optogenetic and shock stimulation metadata

### Conversion Scripts

The conversion scripts determine which sessions to convert, instantiate the appropriate NWBConverter object, and convert all of the specified sessions, saving them to an output directory of .nwb files.

## Data Conversion Pipeline

This project implements a comprehensive pipeline for converting fiber photometry and stimulation data to NWB format:

**Raw Data → Data Interfaces → Temporal Alignment → Stimulus Addition → NWB Files**

### Processing Steps

1. **Data Loading**: TDT files and videos are loaded through their respective interfaces
2. **Signal Demodulation**: Raw modulated signals are demodulated to extract calcium and isosbestic components
3. **Temporal Alignment**: Video timestamps are aligned with fiber photometry data using metadata
4. **Stimulus Integration**: Optogenetic and shock stimuli are added based on TDT events
5. **Metadata Integration**: Experimental metadata is merged from YAML files
6. **NWB Generation**: All data streams are combined into a standardized NWB file

### Signal Processing

The conversion includes custom signal processing:

- **Demodulation**: Raw modulated signals are demodulated using specified driver frequencies (330Hz for calcium, 210Hz for isosbestic)
- **Video Alignment**: Video timestamps are synchronized with fiber photometry using session metadata
- **Stimulus Reconstruction**: Optogenetic and shock stimuli are reconstructed from TDT event timestamps

## Customizing for New Datasets

To create a new conversion or adapt this one for different experimental paradigms:

### 1. Create a New Dataset Directory

Follow the naming convention and create a new directory under `src/hnasko_lab_to_nwb/`:

```bash
mkdir src/hnasko_lab_to_nwb/new_experiment_2025
```

### 2. Implement Dataset-Specific Interfaces

Create custom interfaces inheriting from existing ones:

```python
from neuroconv.datainterfaces import TDTFiberPhotometryInterface

class CustomTDTInterface(TDTFiberPhotometryInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_to_nwbfile(self, nwbfile, metadata, **kwargs):
        # Custom processing logic
        super().add_to_nwbfile(nwbfile, metadata, **kwargs)
```

### 3. Create an NWBConverter Class

Combine all interfaces for your dataset:

```python
from neuroconv import NWBConverter

class NewExperimentNWBConverter(NWBConverter):
    data_interface_classes = dict(
        FiberPhotometry=CustomTDTInterface,
        Video=ExternalVideoInterface,
        # Add other interfaces as needed
    )
```

### 4. Write Conversion Scripts

Create scripts for single sessions and batch processing following the established patterns.

### 5. Create Metadata Files

Develop YAML metadata files with dataset-specific experimental parameters:

```yaml
NWBFile:
  experiment_description: "Description of your new experiment"
  institution: "Your Institution"
  lab: "Your Lab"

Subject:
  species: "Mus musculus"
  # Add subject-specific metadata

# Add other experimental metadata
```

Each conversion should be self-contained within its directory and follow the established patterns for consistency and maintainability.

## Troubleshooting

### Common Issues

**Installation Problems:**
- Ensure you have Python 3.9+ installed
- Use a fresh conda environment to avoid dependency conflicts
- Check that all required packages are installed: `pip list | grep neuroconv`

**Data Loading Errors:**
- Verify TDT folder structure contains required files (.tbk, .tdx, .tev, .tin, .tsq)
- Check that video files are accessible and in supported formats
- Ensure video metadata Excel file exists if specified

**Conversion Failures:**
- Check that all required metadata fields are present in YAML files
- Verify subject_id and session parameters match your data organization
- Ensure sufficient disk space for output NWB files

**Temporal Alignment Issues:**
- Verify video metadata contains correct timing information
- Check that session_starting_time matches your experimental records
- Ensure TDT and video data cover overlapping time periods

### Performance Optimization

- Use `stub_test=True` for initial testing with small data subsets
- Process sessions in parallel for large datasets
- Consider using SSD storage for faster I/O operations
- Monitor memory usage for large video files

### Getting Help

For issues specific to this conversion:
1. Check the `notes.md` file in the conversion directory
2. Review the metadata YAML files for parameter examples
3. Examine the conversion scripts for usage patterns

For general neuroconv issues:
- Visit the [neuroconv documentation](https://neuroconv.readthedocs.io/)
- Check the [neuroconv GitHub repository](https://github.com/catalystneuro/neuroconv)

## Citation

If you use this conversion in your research, please cite:

- The original experimental work (add appropriate citation)
- [NeuroConv](https://github.com/catalystneuro/neuroconv)
- [NWB](https://www.nwb.org/)

## License

This project is licensed under the terms specified in the LICENSE file.
