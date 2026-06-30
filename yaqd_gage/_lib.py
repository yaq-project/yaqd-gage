import numpy as np

from yaqd_core import HasMeasureTrigger, IsSensor, IsDaemon

from ._constants import transfer_modes
from ._pygage import to_voltage


class GaGeSynchronous(HasMeasureTrigger, IsSensor, IsDaemon):
    """parent class for synchronous (non-streaming) acquisitions.  mostly daemons"""

    def _process_single_channel(
        self,
        channel_index: int,
        segment_count: int,
        record_count: int,
        total_size: int,
    ) -> np.array:
        system_info = self._pg.get_system_info()
        channel_info = self._pg.get_channel_config(channel_index + 1)

        segs = self._pg.transfer_data(
            channel_index=channel_index + 1,
            start_position=0,
            transfer_length=total_size,
            segment_index=1,
            transfer_mode=transfer_modes["data_32"],
        )[0]
        segs = np.array(segs, dtype=float).reshape(segment_count, -1)
        segs = to_voltage(
            segs,
            record_count,
            system_info["SampleOffset"],
            channel_info["DcOffset"],
            channel_info["InputRange"],
            system_info["SampleResolution"],
        )
        self.logger.info(segs.shape)
        # since all segements are now polled simultaneously, 
        # users only view one sample trace for each measurement
        self._samples[f"ai{channel_index}"] = segs[-1]

        # signal
        channel_config = self._config["channels"][channel_index]
        start = channel_config["signal_start_index"]
        stop = channel_config["signal_stop_index"]
        signal = segs[start:stop].mean(axis=0)
        # baseline
        if channel_config["use_baseline"]:
            start = channel_config["baseline_start_index"]
            stop = channel_config["baseline_stop_index"]
            baseline = segs[start:stop].mean(axis=0)
            signal = signal - baseline

        # invert
        if channel_config["invert"]:
            signal *= -1

        return signal

    def set_segment_count(self, count: int) -> None:
        self._state["segment_count"] = count

    def close(self):
        self._pg.free_system()

    def get_segment_count(self) -> int:
        return self._state["segment_count"]

    def get_segment_count_limits(self) -> list[int]:
        return [1, self._max_segment_count]
