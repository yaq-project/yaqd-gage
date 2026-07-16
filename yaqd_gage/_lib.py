import numpy as np
import asyncio
import time
import json

from yaqd_core import HasMeasureTrigger, IsSensor, IsDaemon

from ._constants import transfer_modes, acq_status_codes
from ._pygage import to_voltage


impedances = {"low": 50, "high": 1_000_000}
couplings = {"DC": 1, "AC": 2}
acq_mode = {"quad": 4, "dual": 2, "single": 1}


class GaGeSynchronous(HasMeasureTrigger, IsSensor, IsDaemon):
    """parent class for synchronous (non-streaming) acquisitions"""

    async def _capture_and_fetch(
        self,
        channel_indices: list[int],
        segment_count: int,
        record_count: int = 1,
    ):
        t_start = time.time()
        self._pg.start_capture()
        # wait for capture to complete
        while True:
            code = self._pg.get_status()
            if acq_status_codes[code] == "ACQ_STATUS_READY":
                break
            await asyncio.sleep(0)

        t_measured = time.time()
        # read out
        out = {}
        # trick the daq into thinking depth is the total size of the data
        temp_depth = segment_count * (self._config["depth"] + self._tail_size)
        temp_segment_size = segment_count * (self._config["segment_size"] + self._tail_size)
        self.logger.debug(f"{temp_depth=}, {self._tail_size=}")
        self._pg.set_acquisition_config(
            {
                "Depth": temp_depth,
                "SegmentCount": 1,
                "SegmentSize": temp_segment_size,
            }
        )
        self._pg.commit()
        for i in channel_indices:
            shots = self._process_single_channel(i, segment_count, temp_depth, record_count)
            out[f"ai{i}"] = shots
            await asyncio.sleep(0)
        self._pg.set_acquisition_config(
            {
                "Depth": self._config["depth"],
                "SegmentCount": segment_count,
                "SegmentSize": self._config["segment_size"],
            },
        )
        self._pg.commit()
        t_fetched = time.time()
        self.logger.info(f"measurement: {t_measured-t_start} sec")
        self.logger.info(f"data xt: {t_fetched-t_measured} sec")
        return out

    def _process_single_channel(
        self,
        channel_index: int,
        segment_count: int,
        total_size: int,
        record_count: int,
    ) -> np.array:
        system_info = self._pg.get_system_info()
        channel_info = self._pg.get_channel_config(channel_index + 1)

        segs = self._pg.transfer_data(
            channel_index=channel_index + 1,
            start_position=0,
            transfer_length=total_size,
            segment_index=1,
            transfer_mode=transfer_modes["default"],
        )[0]
        segs = to_voltage(
            segs.astype(float),
            record_count,
            system_info["SampleOffset"],
            channel_info["DcOffset"],
            channel_info["InputRange"],
            system_info["SampleResolution"],
        ).reshape(segment_count, -1)
        self._samples[f"ai{channel_index}"] = segs[-1]
        self.logger.info(segs.shape)

        # signal
        channel_config = self._config["channels"][channel_index]
        start = channel_config["signal_start_index"]
        stop = channel_config["signal_stop_index"]
        signal = segs[:, start:stop].mean(axis=1)
        # baseline
        if channel_config["use_baseline"]:
            start = channel_config["baseline_start_index"]
            stop = channel_config["baseline_stop_index"]
            baseline = segs[:, start:stop].mean(axis=1)
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

    def get_acq_config(self) -> str:
        d = self._pg.get_acquisition_config()
        return json.dumps(d)
