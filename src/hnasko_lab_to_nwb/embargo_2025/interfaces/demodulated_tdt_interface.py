from ndx_fiber_photometry import FiberPhotometryResponseSeries
from ..utils.demodulate_fp_signal import demodulate_signal
from neuroconv.datainterfaces import TDTFiberPhotometryInterface
from pynwb import ProcessingModule


class DemodulatedTDTInterface(TDTFiberPhotometryInterface):
    keywords = ("fiber photometry",)
    display_name = "DemodulatedTDT"
    info = "Data Interface for converting demodulated fiber photometry data from TDT files."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")
    
    #is it really necessary ? 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_metadata(self):
        return super().get_metadata()

    def get_metadata_schema(self):
        return super().get_metadata_schema()

    def load(self, **kwargs):
        return super().load(**kwargs)

    def get_events(self):
        return super().get_events()

    def get_original_starting_time_and_rate(self):
        return super().get_original_starting_time_and_rate()

    def get_original_timestamps(self):
        return super().get_original_timestamps()

    def get_starting_time_and_rate(self):
        return super().get_starting_time_and_rate()

    def get_timestamps(self):
        return super().get_timestamps()

    def set_aligned_starting_time(self, aligned_starting_time: float):
        super().set_aligned_starting_time(aligned_starting_time)

    def set_aligned_starting_time_and_rate(self, aligned_starting_time: float, rate: float):
        super().set_aligned_starting_time_and_rate(aligned_starting_time, rate)

    def set_aligned_timestamps(self, aligned_timestamps):
        super().set_aligned_timestamps(aligned_timestamps)

    def align_by_interpolation(self, times, values, new_times):
        return super().align_by_interpolation(times, values, new_times)
    
    def add_to_nwbfile(
        self,
        nwbfile,
        metadata: dict,
        *,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
        timing_source="original",
    ):
        
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            t1=t1,
            t2=t2,
            timing_source=timing_source,
        )

        # Load TDT signal stream 
        tdt_photometry = self.load(t1=t1, t2=t2)
        stream_name = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"][0]["stream_name"]
        stream_data = tdt_photometry.streams[stream_name].data
        fs = tdt_photometry.streams[stream_name].fs
        start_time = tdt_photometry.streams[stream_name].start_time

        # Demodulate the signals 
        calcium = demodulate_signal(stream_data[0], fs, driver_freq=330)
        isosbestic = demodulate_signal(stream_data[1], fs, driver_freq=210)

        # FiberPhotometryTable from metadata
        fiber_photometry = nwbfile.lab_meta_data["fiber_photometry"]
        fiber_photometry_table = fiber_photometry.fiber_photometry_table

        # create 'ophys' processing module
        if "ophysme" not in nwbfile.processing:
            ophys_module = ProcessingModule(
                name="ophys",
                description="Processed fiber photometry signals"
            )
            nwbfile.create_processing_module(ophys_module)
        else:
            ophys_module = nwbfile.processing["ophys"]

        # Create and add demodulated FiberPhotometryResponseSeries 
        for name, signal, region_index in zip(
            ["calcium_signal", "isosbestic_signal"],
            [calcium, isosbestic],
            [0, 1],
        ):
            response_metadata = next(
                series_md for series_md in metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"]
                if series_md["name"] == name
            )

            table_region = fiber_photometry_table.create_fiber_photometry_table_region(
                description=response_metadata["fiber_photometry_table_region_description"],
                region=response_metadata["fiber_photometry_table_region"],
            )

            series = FiberPhotometryResponseSeries(
                name=name,
                description=response_metadata["description"],
                data=signal,
                unit=response_metadata["unit"],
                fiber_photometry_table_region=table_region,
                starting_time=start_time,
                rate=fs,
            )

            ophys_module.add(series)
