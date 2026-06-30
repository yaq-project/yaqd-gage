__all__ = ["CompuScope"]


import asyncio
import time
from typing import Dict

import numpy as np

from ._constants import acq_status_codes
from ._pygage import PyGage, uses_pygage, async_uses_pygage
from ._lib import GaGeSynchronous

impedences = {"fifty": 50, "onemeg": 1_000_000}
couplings = {"DC": 1, "AC": 2}


class CompuScope(GaGeSynchronous):
    _kind = "gage-compuscope"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._pg = PyGage()
        self._channel_names = []
        self._max_segment_count = None  # redefined in _config_pygage
        self._config_pygage()
        for i in range(0, len(self._config["channels"])):
            self._channel_names.append(f"ai{i}")
        self._channel_units = {k: "V" for k in self._channel_names}
        self._samples: Dict[str, np.ndarray] = dict()
        self.set_segment_count(self._state["segment_count"])

    @uses_pygage
    def _config_pygage(self):
        # acqusition config
        config = {}
        config["Mode"] = self._config["mode"]
        config["SampleRate"] = self._config["sample_rate"]
        config["Depth"] = self._config["depth"]
        config["SegmentSize"] = self._config["segment_size"]
        config["TriggerDelay"] = self._config["trigger_delay"]
        config["SegmentCount"] = self._state["segment_count"]
        config["TriggerTimeout"] = self._config["trigger_time_out"]
        config["TriggerHoldoff"] = self._config["trigger_hold_off"]
        config["ExtClk"] = int(self._config["ext_clk"])
        if False:  # TODO: test this
            timestamp_config = 0x00
            if self._config["time_stamp_clock"] == "fixed":
                timestamp_config |= 0x1
            if self._config["time_stamp_mode"] == "free":
                timestamp_config |= 0x10
            config["TimeStampConfig"] = timestamp_config
        else:
            config["TimeStampConfig"] = 0
        # from state
        config["SegmentCount"] = self._state["segment_count"]
        self._pg.set_acquisition_config(config)
        self._pg.set_multiple_rec_average_count(self._config["record_count"])
        # channel config
        for channel_index, channel in enumerate(self._config["channels"]):
            config = {}
            config["InputRange"] = channel["range"]
            config["Coupling"] = couplings[channel["coupling"]]
            config["Impedance"] = impedences[channel["impedance"]]
            config["Filter"] = int(channel["filter"])
            config["DcOffset"] = channel["dc_offset"]
            self._pg.set_channel_config(channel_index + 1, config)
        # trigger config
        for trigger_index, trigger in enumerate(self._config["triggers"]):
            config = {}
            config["Condition"] = trigger["condition"]
            config["Level"] = int(trigger["level"])
            config["Source"] = trigger["source"]
            config["ExtRange"] = trigger["range"]
            config["ExtImpedance"] = impedences[channel["impedance"]]
            config["ExtCoupling"] = couplings[channel["coupling"]]
            config["Relation"] = 0
            self._pg.set_trigger_config(trigger_index + 1, config)
        # finish
        self._pg.commit()
        self._tail_size = self._pg.get_segment_tail_size()
        self._max_segment_count = self._pg.max_segment_count

    @async_uses_pygage
    async def _measure(self):
        # apply state
        try:
            segment_count = self._state["segment_count"]
            self._pg.set_acquisition_config({"SegmentCount": segment_count})
            self._pg.commit()
            # start capture
            self._pg.start_capture()
            # wait for capture to complete
            before = time.time()
            while True:
                code = self._pg.get_status()
                if acq_status_codes[code] == "ACQ_STATUS_READY":
                    break
                await asyncio.sleep(0)
            self.logger.debug("TIME WAITED", time.time() - before)
            # read out
            self.logger.info("here")
            out = await self._capture_and_fetch(
                [_ for _ in range(len(self._config["channels"]))],
                segment_count,
            )

            # self.logger.info(out)
        except Exception as e:
            self.logger.error(e, exc_info=True)
            raise e
        return out
