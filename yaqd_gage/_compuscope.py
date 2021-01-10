__all__ = ["CompuScope"]


import asyncio
from typing import Dict, Any, List

import numpy as np  # type: ignore

from yaqd_core import HasMeasureTrigger, IsSensor, IsDaemon

from ._constants import acq_status_codes
from ._pygage import PyGage


class CompuScope(HasMeasureTrigger, IsSensor, IsDaemon):
    _kind = "gage-compuscope"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._pg = PyGage()
        # acqusition config
        config = {}
        config["Mode"] = self._config["mode"]
        config["SampleRate"] = self._config["sample_rate"]
        config["Depth"] = self._config["depth"]
        config["SegmentSize"] = self._config["segment_size"]
        config["TriggerDelay"] = self._config["trigger_delay"]
        config["SegmentCount"] = self._config["segment_count"]
        config["TriggerTimeOut"] = self._config["trigger_time_out"]
        config["TriggerHoldOff"] = self._config["trigger_hold_off"]
        config["ExtClk"] = int(self._config["ext_clk"])
        config["TimeStampMode"] = self._config["time_stamp_mode"]
        config["TimeStampClock"] = self._config["time_stamp_clock"]
        self._pg.set_acquisition_config(config)
        # channel config
        for channel_index, channel in enumerate(self._config["channels"]):
            config = {}
            config["Range"] = channel["range"]
            config["Coupling"] = channel["coupling"]
            config["Impedance"] = int(channel["impedance"])
            config["DiffInput"] = int(channel["diff_input"])
            config["DirectADC"] = int(channel["direct_adc"])
            config["Filter"] = int(channel["filter"])
            config["DcOffset"] = channel["dc_offset"]
            #self._pg.set_channel_config(channel_index + 1, config)
        # trigger config
        for trigger_index, trigger in enumerate(self._config["triggers"]):
            config = {}
            config["Condition"] = trigger["condition"]
            config["Level"] = trigger["level"]
            config["Source"] = 1  # trigger["source"]
            config["Coupling"] = trigger["coupling"]
            config["Range"] = trigger["range"]
            config["Impedance"] = int(channel["impedance"])
            config["Relation"] = 0
            self._pg.set_trigger_config(trigger_index + 1, config)
        # finish
        self._pg.commit()
        self._channel_names = [f"channel{i + 1}" for i in range(0, len(self._config["channels"]))]
        self._channel_units = {k: "V" for k in self._channel_names}

    async def _measure(self):
        # start capture
        self._pg.start_capture()
        # wait for capture to complete
        while True:
            code = self._pg.get_status()
            if acq_status_codes[code] == "ACQ_STATUS_READY":
                break
            await asyncio.sleep(0)
        # read out samples
        samples = {}
        for i in range(0, len(self._channel_names)):
            # TODO: actually calculate these
            start_position = 0
            transfer_length = 2040
            buffer = self._pg.transfer_data(i + 1, start_position, transfer_length)
            chan = self._pg.get_channel_config(i + 1)
            system_info = self._pg.get_system_info()
            data = map(
                lambda x: (
                    ((system_info["SampleOffset"] - x) / system_info["SampleResolution"])
                    * chan["InputRange"]
                    / 2000
                )
                + chan["DcOffset"],
                buffer[0].tolist(),
            )
            samples[self._channel_names[i]] = list(data)
        # process
        out = {k: np.mean(v) for k, v in samples.items()}
        return out
