__all__ = ["CompuScope"]


import asyncio
import time
from typing import Dict

import numpy as np

from ._constants import acq_status_codes, transfer_modes
from ._pygage import PyGage, uses_pygage, async_uses_pygage, to_voltage
from ._lib import GaGeSynchronous

impedences = {"fifty": 50, "onemeg": 1_000_000}


class CompuScope(GaGeSynchronous):
    _kind = "gage-compuscope"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._pg = PyGage()
        self._channel_names = []
        self._max_segment_count = None  # redefined in _config_pygage
        self._config_pygage()
        for i in range(0, len(self._config["channels"])):
            self._channel_names.append(f"channel{i+1}")
            if self._config["channels"][i]["use_baseline"]:
                self._channel_names.append(f"channel{i+1}_signal")
                self._channel_names.append(f"channel{i+1}_baseline")
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
        config["TriggerTimeOut"] = self._config["trigger_time_out"]
        config["TriggerHoldOff"] = self._config["trigger_hold_off"]
        config["ExtClk"] = int(self._config["ext_clk"])
        config["TimeStampMode"] = self._config["time_stamp_mode"]
        config["TimeStampClock"] = self._config["time_stamp_clock"]
        # from state
        config["SegmentCount"] = self._state["segment_count"]
        self._pg.set_acquisition_config(config)
        self._pg.set_multiple_rec_average_count(self._config["record_count"])
        # channel config
        for channel_index, channel in enumerate(self._config["channels"]):
            config = {}
            config["InputRange"] = channel["range"]
            couplings = {"DC": 1, "AC": 2}
            config["Coupling"] = couplings[channel["coupling"]]
            config["Impedance"] = impedences[channel["impedance"]]
            config["DiffInput"] = int(channel["diff_input"])
            config["DirectADC"] = int(channel["direct_adc"])
            config["Filter"] = int(channel["filter"])
            config["DcOffset"] = channel["dc_offset"]
            self._pg.set_channel_config(channel_index + 1, config)
        # trigger config
        for trigger_index, trigger in enumerate(self._config["triggers"]):
            config = {}
            config["Condition"] = trigger["condition"]
            config["Level"] = trigger["level"]
            config["Source"] = trigger["source"]
            config["InputRange"] = trigger["range"]
            config["Impedance"] = impedences[channel["impedance"]]
            config["Relation"] = 0
            self._pg.set_trigger_config(trigger_index + 1, config)
        # finish
        self._pg.commit()
        self._max_segment_count = self._pg.max_segment_count

    @async_uses_pygage
    async def _measure(self):
        # apply state
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
        total_size = segment_count * (self._config["depth"] + self._tail_size)
        temp_segment_size = segment_count * (self._config["segment_size"] + self._tail_size)
        self._pg.set_acquisition_config(
            {
                "Depth": self.total_size,
                "SegmentCount": 1,
                "SegmentSize": temp_segment_size,
            }
        )
        self._pg.commit()

        out = {}
        for i in range(0, len(self._config["channels"])):
            out.update(
                {
                    f"ai{i}": self._process_single_channel(
                        self,
                        i,
                        segment_count,
                        1,
                    )
                }
            )
            await asyncio.sleep(0)

        self._pg.set_acquisition_config(
            {
                "Depth": self._config["depth"],
                "SegmentCount": segment_count,
                "SegmentSize": self._config["segment_size"],
            },
        )
        self._pg.commit()

        self.logger.debug(out)
        return out
