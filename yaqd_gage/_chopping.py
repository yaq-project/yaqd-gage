__all__ = ["CompuScope"]


import asyncio
import time

import numpy as np

from ._pygage import PyGage, uses_pygage, async_uses_pygage
from ._lib import GaGeSynchronous


impedences = {"fifty": 50, "onemeg": 1_000_000}
couplings = {"DC": 1, "AC": 2}
acq_mode = {"quad": 4, "dual": 2, "single": 1}


class CompuScope(GaGeSynchronous):
    _kind = "gage-chopping"

    def __init__(self, name, config, config_filepath):
        super().__init__(name, config, config_filepath)
        self._pg = PyGage()
        self._channel_names = []
        self._max_segment_count = None  # redefined in _config_pygage
        self._tail_size = None
        self._config_pygage()
        for pre in "ap":
            seed = f"{pre}i{self._config["signal_channel"]}"
            self._channel_names += [
                f"{seed}",
                f"{seed}_a",
                f"{seed}_b",
                f"{seed}_c",
                f"{seed}_d",
                f"{seed}_diff_abcd",
                f"{seed}_diff_ab",
                f"{seed}_diff_ad",
            ]
        self._channel_units = {k: "V" if k.startswith("a") else None for k in self._channel_names}
        self._samples: dict[str, np.ndarray] = dict()
        self._segments: dict[str, np.ndarray] = dict()

    @uses_pygage
    def _config_pygage(self):
        acq = self._pg.get_acquisition_config()
        self.logger.info(acq)
        # acqusition config
        config = {}
        config["Mode"] = acq_mode[self._config["mode"]]
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
        for k in config:
            self.logger.info(f"{k}: {acq.get(k)} | {config.get(k)}")
        config["SegmentCount"] = self._state["segment_count"]
        self._pg.set_acquisition_config(config)
        # channel config
        for channel_index, channel in enumerate(self._config["channels"]):
            self.logger.info(f"{channel_index=}")
            # cfg = self._pg.get_channel_config(channel_index)
            # self.logger.info(cfg)
            config = {}
            config["InputRange"] = channel["range"]
            config["Coupling"] = couplings[channel["coupling"]]
            config["Impedance"] = impedences[channel["impedance"]]
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
        self._tail_size = self._pg.get_segment_tail_size()
        self._max_segment_count = self._pg.max_segment_count

    def get_edge_width_count(self) -> int:
        return self._state["edge_width_count"]

    def get_measured_segments(self):
        return self._segments

    @async_uses_pygage
    async def _measure(self):
        out = dict()
        # apply state variables
        photon_threshold = self._state["photon_threshold"]
        segment_count = self._state["segment_count"]
        self._pg.set_acquisition_config({"SegmentCount": segment_count})
        self._pg.commit()
        self._max_segment_count = self._pg.max_segment_count
        # start capture
        i_sig = self._config["signal_channel"]
        i_chop = self._config["chop_channel"]
        ch_indices = set([i_sig, i_chop])
        shots = await self._capture_and_fetch(ch_indices, segment_count)

        self._segments = shots
        t_start = time.time()
        # get edges
        if self._state["edge_width_count"]:
            gradient = np.gradient(shots[f"ai{i_chop}"])
            edges = np.abs(gradient) > 0.1
            edges = np.convolve(edges, np.full(self._state["edge_width_count"], True), mode="same")
        else:
            edges = np.full(segment_count, False)
        # get regions
        self._segments["regions"] = np.full(self._state["segment_count"], "", dtype="<U1")
        regions = {k: [] for k in self._config["segment_bins"].keys()}
        for k, v in self._config["segment_bins"].items():
            start = None
            for i, voltage in enumerate(shots[f"ai{i_chop}"]):
                if (
                    v["min"] <= voltage <= v["max"]
                    and i != shots[f"ai{i_chop}"].size - 1
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
        counts = np.array([shot > photon_threshold for shot in shots[f"ai{i_sig}"]], dtype=bool)
        out[f"pi{i_sig}"] = counts.sum()
        # take mean
        out[f"ai{i_sig}"] = np.mean(shots[f"ai{i_sig}"])

        # chopping-derived channels
        for phase in "abcd":
            if regions[phase]:
                valid = np.r_[tuple(regions[phase])]
                out[f"pi{i_sig}_{phase}"] = np.mean(counts[valid])
                out[f"ai{i_sig}_{phase}"] = np.mean(shots[f"ai{i_sig}"][valid])
            else:
                out[f"pi0_{phase}"] = out[f"ai0_{phase}"] = np.nan

        for key in [f"pi{i_sig}", f"ai{i_sig}"]:
            out[f"{key}_diff_abcd"] = (
                out[f"{key}_a"] - out[f"{key}_b"] + out[f"{key}_c"] - out[f"{key}_d"]
            )
            out[f"{key}_diff_ab"] = out[f"{key}_b"] - out[f"{key}_a"]
            out[f"{key}_diff_ad"] = out[f"{key}_d"] - out[f"{key}_a"]
        t_processed = time.time()
        self.logger.info(f"processing: {t_processed-t_start} sec")

        return out

    def set_edge_width_count(self, count: int) -> None:
        assert count >= 0  # no limits_getter atm
        self._state["edge_width_count"] = count

    def set_photon_threshold(self, threshold) -> None:
        self._state["photon_threshold"] = threshold

    def get_photon_threshold(self) -> float:
        return self._state["photon_threshold"]

    def get_photon_threshold_units(self) -> str:
        return "V"
