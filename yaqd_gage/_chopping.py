__all__ = ["CompuScope"]


import asyncio
import time
from typing import Dict, Any, List

import numpy as np  # type: ignore

from yaqd_core import HasMeasureTrigger, IsSensor, IsDaemon

from ._constants import acq_status_codes, transfer_modes
from ._pygage import PyGage, uses_pygage, async_uses_pygage, to_voltage


impedences = {"fifty": 50, "onemeg": 1_000_000}


class CompuScope(HasMeasureTrigger, IsSensor, IsDaemon):
    _kind = "gage-chopping"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._pg = PyGage()
        self._channel_names = []
        self._max_segment_count = None  # redefined in _config_pygage
        self._config_pygage()
        self._channel_names.append("ai1")
        self._channel_names.append("ai2")
        self._channel_names.append("ai3")
        for pre in "ap":
            self._channel_names += [
                f"{pre}i0",
                f"{pre}i0_a",
                f"{pre}i0_b",
                f"{pre}i0_c",
                f"{pre}i0_d",
                f"{pre}i0_diff_abcd",
                f"{pre}i0_diff_ab",
                f"{pre}i0_diff_ad",
            ]
        self._channel_units = {k: "V" if k.startswith("a") else None for k in self._channel_names}
        self._samples: Dict[str, np.ndarray] = dict()
        self._segments: Dict[str, np.ndarray] = dict()

    @uses_pygage
    def _config_pygage(self):
        acq = self._pg.get_acquisition_config()
        self.logger.info(acq)
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
        config["TimeStampConfig"] = 0  # self._config["time_stamp_mode"]
        # config["TimeStampClock"] = self._config["time_stamp_clock"]
        # from state
        for k in config:
            self.logger.info(f"{k}: {acq.get(k)} | {config.get(k)}")
        config["SegmentCount"] = self._state["segment_count"]
        self._pg.set_acquisition_config(config)
        self._pg.set_multiple_rec_average_count(self._state["record_count"])
        # channel config
        for channel_index, channel in enumerate(self._config["channels"]):
            self.logger.info(f"{channel_index=}")
            # cfg = self._pg.get_channel_config(channel_index)
            # self.logger.info(cfg)
            config = {}
            config["InputRange"] = channel["range"]
            couplings = {"DC": 1, "AC": 2}
            config["Coupling"] = couplings[channel["coupling"]]
            config["Impedance"] = impedences[channel["impedance"]]
            # config["DiffInput"] = int(channel["diff_input"])
            # config["DirectADC"] = int(channel["direct_adc"])
            config["Filter"] = int(channel["filter"])
            config["DcOffset"] = channel["dc_offset"]
            self._pg.set_channel_config(channel_index + 1, config)
        # trigger config
        for trigger_index, trigger in enumerate(self._config["triggers"]):
            tcfg = self._pg.get_trigger_config(trigger_index + 1)
            self.logger.info(tcfg)
            config = {}
            config["Condition"] = trigger["condition"]
            config["Level"] = int(trigger["level"])
            config["Source"] = trigger["source"]
            config["ExtRange"] = trigger["range"]
            config["ExtImpedance"] = impedences[channel["impedance"]]
            config["ExtCoupling"] = couplings[channel["coupling"]]
            config["Relation"] = 0
            for k in tcfg:
                self.logger.info(f"{k}: {tcfg.get(k)} | {config.get(k)}")

            self._pg.set_trigger_config(trigger_index + 1, config)
        # finish
        self._pg.commit()
        self._max_segment_count = self._pg.max_segment_count

    def get_edge_width_count(self) -> int:
        return self._state["edge_width_count"]

    def get_measured_samples(self):
        return self._samples

    def get_measured_segments(self):
        return self._segments

    def get_record_count(self) -> int:
        return self._state["record_count"]

    def get_segment_count(self) -> int:
        return self._state["segment_count"]

    def get_segment_count_limits(self) -> List[int]:
        return [1, self._max_segment_count]

    @async_uses_pygage
    async def _measure(self):
        out = dict()
        # apply state variables
        photon_index = self._state["photon_index"]
        photon_threshold = self._state["photon_threshold"]
        self._pg.set_acquisition_config({"SegmentCount": self._state["segment_count"]})
        self._pg.set_multiple_rec_average_count(self._state["record_count"])
        self._pg.commit()
        self._max_segment_count = self._pg.max_segment_count
        # start capture
        before = time.time()
        self._pg.start_capture()
        # wait for capture to complete
        while True:
            code = self._pg.get_status()
            if acq_status_codes[code] == "ACQ_STATUS_READY":
                break
            await asyncio.sleep(0)
        # read out
        after = time.time()
        segments = {}
        segment_count = self._state["segment_count"]
        record_count = self._state["record_count"]
        for i in range(0, len(self._config["channels"])):
            s = await self._process_single_channel(i, segment_count, record_count)
            segments.update(s)
            await asyncio.sleep(0)
        self._segments = segments
        # get edges
        if self._state["edge_width_count"]:
            gradient = np.gradient(segments["ai3"])
            edges = np.abs(gradient) > 0.1
            edges = np.convolve(edges, np.full(self._state["edge_width_count"], True), mode="same")
        else:
            edges = np.full(segment_count, False)
        await asyncio.sleep(0)
        # get regions
        self._segments["regions"] = np.full(self._state["segment_count"], "", dtype="<U1")
        regions = {k: [] for k in self._config["segment_bins"].keys()}
        for k, v in self._config["segment_bins"].items():
            start = None
            for i, voltage in enumerate(segments["ai3"]):
                if (
                    v["min"] <= voltage <= v["max"]
                    and i != segments["ai3"].size - 1
                    and not edges[i]
                ):
                    if start is None:
                        start = i
                else:
                    if start is not None:
                        sl = slice(start, i)
                        regions[k].append(sl)
                        self._segments["regions"][sl] = k
                        start = None
            await asyncio.sleep(0)
        # segments: dict with keys of channel, values are 1D array of 1D arrays
        # count photon events
        # properties: photon_index, photon_threshold (perhaps dictionary for each channel?)
        counts = np.array([shot > photon_threshold for shot in segments["ai0"]], dtype=bool)
        out["pi0"] = counts.sum()
        # take means
        out["ai0"] = np.mean(segments["ai0"])
        out["ai1"] = np.mean(segments["ai1"])
        out["ai2"] = np.mean(segments["ai2"])
        out["ai3"] = np.mean(segments["ai3"])

        # ai0-derived channels
        # TODO: remove hard-code ai0, put in config
        for phase in "abcd":
            if regions[phase]:
                valid = np.r_[tuple(regions[phase])]
                out[f"pi0_{phase}"] = np.mean(counts[valid])
                out[f"ai0_{phase}"] = np.mean(segments["ai0"][valid])
            else:
                out[f"pi0_{phase}"] = out[f"ai0_{phase}"] = np.nan

        for key in ["pi0", "ai0"]:
            out[f"{key}_diff_abcd"] = (
                out[f"{key}_a"] - out[f"{key}_b"] + out[f"{key}_c"] - out[f"{key}_d"]
            )
            out[f"{key}_diff_ab"] = out[f"{key}_b"] - out[f"{key}_a"]
            out[f"{key}_diff_ad"] = out[f"{key}_d"] - out[f"{key}_a"]
        finished = time.time()
        self.logger.info(f"measurement: {after-before} sec")
        self.logger.info(f"maths: {finished-after} sec")

        return out

    async def _process_single_channel(
        self, channel_index: int, segment_count: int, record_count: int
    ) -> Dict[str, Any]:
        out = dict()
        out[f"ai{channel_index}"] = np.zeros(segment_count, dtype=float)
        system_info = self._pg.get_system_info()
        channel_info = self._pg.get_channel_config(channel_index + 1)
        for segment_index in range(segment_count):
            # samples
            seg = self._pg.transfer_data(
                channel_index=channel_index + 1,
                start_position=0,
                transfer_length=self._config["depth"],
                segment_index=segment_index + 1,
                transfer_mode=transfer_modes["data_32"],
            )[0]
            seg = np.array(seg, dtype=float)
            seg = to_voltage(
                seg,
                record_count,
                system_info["SampleOffset"],
                channel_info["DcOffset"],
                channel_info["InputRange"],
                system_info["SampleResolution"],
            )
            self._samples[f"ai{channel_index}"] = seg

            # signal
            start = self._config["channels"][channel_index]["signal_start_index"]
            stop = self._config["channels"][channel_index]["signal_stop_index"]
            signal = np.average(seg[start:stop])

            # baseline
            if self._config["channels"][channel_index]["use_baseline"]:
                start = self._config["channels"][channel_index]["baseline_start_index"]
                stop = self._config["channels"][channel_index]["baseline_stop_index"]
                baseline = np.average(seg[start:stop])
                out[f"ai{channel_index}"][segment_index] = signal - baseline
            else:
                out[f"ai{channel_index}"][segment_index] = signal

            # invert
            if self._config["channels"][channel_index]["invert"]:
                out[f"ai{channel_index}"][segment_index] *= -1

            await asyncio.sleep(0)

        return out

    def close(self):
        self._pg.free_system()

    def set_edge_width_count(self, count: int) -> None:
        assert count >= 0  # no limits_getter atm
        self._state["edge_width_count"] = count

    def set_record_count(self, count: int) -> None:
        self._state["record_count"] = count

    def set_segment_count(self, count: int) -> None:
        self._state["segment_count"] = count

    def set_photon_threshold(self, threshold) -> None:
        self._state["photon_threshold"] = threshold

    def get_photon_threshold(self) -> float:
        return self._state["photon_threshold"]

    def get_photon_threshold_units(self) -> str:
        return "V"
