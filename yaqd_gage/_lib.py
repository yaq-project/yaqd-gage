import numpy as np
import asyncio
import time

from yaqd_core import HasMeasureTrigger, IsSensor, IsDaemon

from ._constants import transfer_modes, acq_status_codes
from ._pygage import to_voltage


class GaGeSynchronous(HasMeasureTrigger, IsSensor, IsDaemon):
    """parent class for synchronous (non-streaming) acquisitions.  mostly daemons"""

    async def _capture_and_fetch(
        self,
        channel_indices: list[int],
        segment_count,
        record_count=1,
    ):
        before = time.time()
        self._pg.start_capture()
        # wait for capture to complete
        while True:
            code = self._pg.get_status()
            if acq_status_codes[code] == "ACQ_STATUS_READY":
                break
            await asyncio.sleep(0)

        finished_measurement = time.time()
        # read out
        shots = {}
        # trick the daq into thinking depth is the total size of the data
        total_size = segment_count * (self._config["depth"] + self._tail_size)
        temp_segment_size = segment_count * (self._config["segment_size"] + self._tail_size)
        self.logger.debug(f"{self.total_size=}, {self._tail_size=}")
        self._pg.set_acquisition_config(
            {
                "Depth": self.total_size,
                "SegmentCount": 1,
                "SegmentSize": temp_segment_size,
            }
        )
        self._pg.commit()
        for i in channel_indices:
            shots = self._process_single_channel(
                self, i, segment_count, record_count, total_size
            )
            shots.update({f"ai{i}": shots})
            await asyncio.sleep(0)
        self._pg.set_acquisition_config(
            {
                "Depth": self._config["depth"],
                "SegmentCount": segment_count,
                "SegmentSize": self._config["segment_size"],
            },
        )
        self._pg.commit()
        fetched_measurement = time.time()
        self.logger.info(f"measurement: {finished_measurement-before} sec")
        self.logger.info(f"data xt: {fetched_measurement-finished_measurement} sec")
        return shots

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

    def get_measured_samples(self):
        return self._samples

    def close(self):
        self._pg.free_system()

    def get_segment_count(self) -> int:
        return self._state["segment_count"]

    def get_segment_count_limits(self) -> list[int]:
        return [1, self._max_segment_count]
