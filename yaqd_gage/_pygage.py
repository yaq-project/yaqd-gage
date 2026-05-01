"""Wrapper to normalize PyGage support."""

import sys
from functools import wraps

import numpy as np  # type: ignore

from ._exceptions import CompuScopeException
from ._constants import transfer_modes


def uses_pygage(func):
    """decorator for pygage context management"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        pg: PyGage = getattr(self, "_pg", None)
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            self.logger.exception(f"error in {func.__name__}")
            code = pg.interface.FreeSystem(pg.handle)
            # ignore errors, which are probably from closing when already closed
            if isinstance(code, int) and code < 0:
                self.logger.error(f"{func.__name__} : FreeSystem : code={code}")
            raise e

    return wrapper


def async_uses_pygage(func):
    """decorator for async pygage context management"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        pg: PyGage = getattr(self, "_pg", None)
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            self.logger.exception(f"error in {func.__name__}")
            code = pg.interface.FreeSystem(pg.handle)
            if code != -6:  # ignore -6, which means the system is already freed
                self.logger.error(f"{func.__name__} : FreeSystem : code={code}")
                raise e

    return wrapper


def compuscope_error_handling(func):
    """Decorator to raise Python exception when appropriate."""

    def inner(*args, **kwargs):
        response = func(*args, **kwargs)
        if isinstance(response, int) and response < 0:
            raise CompuScopeException(response)
        return response

    return inner


def to_voltage(adc, repetitions, offset, dc_offset, full_range, resolution):
    """
    converts buffer to voltage values as specified from SDK docs:

    voltage[mV] = (offset - adc_code)/resolution * full_scale_voltage / 2 + dc_offset
    """
    adc *= -1 / repetitions
    adc += offset
    adc *= full_range / 2000 / resolution
    adc += dc_offset
    return adc


class PyGage(object):

    def __init__(self):
        self.initialize()
        self.handle = self.get_system()

    @compuscope_error_handling
    def abort_capture(self):
        """Aborts an acquisition or transfer on the CompuScope system."""
        return self.interface.AbortCapture(self.handle)

    @compuscope_error_handling
    def commit(self):
        """Commit any configuration changes to device."""
        return self.interface.Commit(self.handle)

    @compuscope_error_handling
    def free_system(self):
        """Frees the system associated with the handle"""
        return self.interface.FreeSystem(self.handle)

    @compuscope_error_handling
    def get_acquisition_config(self):
        return self.interface.GetAcquisitionConfig(self.handle)

    @compuscope_error_handling
    def get_channel_config(self, channel_index):
        return self.interface.GetChannelConfig(self.handle, channel_index)

    @compuscope_error_handling
    def get_multiple_rec_average_count(self, count):
        return self.interface.GetMulRecAverageCount(self.handle)

    @compuscope_error_handling
    def get_status(self):
        return self.interface.GetStatus(self.handle)

    @compuscope_error_handling
    def get_trigger_config(self, trigger_index):
        return self.interface.GetTriggerConfig(self.handle, trigger_index)

    @compuscope_error_handling
    def get_system(self):
        # I don't understand what the arguments to this function
        # (the four zeros) do. It's working for me right now.
        # - Blaise 2020-01-09
        handle = self.interface.GetSystem(0, 0, 0, 0)
        return handle

    @compuscope_error_handling
    def get_system_info(self):
        return self.interface.GetSystemInfo(self.handle)

    @compuscope_error_handling
    def initialize(self):
        return self.interface.Initialize()

    @property
    def interface(self) -> object:
        if sys.maxsize > 2**32:
            from . import PyGage3_64 as pg  # type: ignore
        else:
            from . import PyGage3_32 as pg  # type: ignore
        return pg

    @property
    def max_segment_count(self):
        system_info = self.get_system_info()
        acq_info = self.get_acquisition_config()
        out = system_info["MaxMemory"]
        if acq_info["Mode"] >= 0x40000000:
            out //= 32  # bits per sample, assuming firmware averaging
        else:
            out //= system_info["SampleBits"]
        out //= acq_info["Depth"]
        out //= acq_info["Mode"] % 0x40000000  # number of channels
        return out

    @compuscope_error_handling
    def set_acquisition_config(self, config):
        return self.interface.SetAcquisitionConfig(self.handle, config)

    @compuscope_error_handling
    def set_channel_config(self, channel_index, config):
        return self.interface.SetChannelConfig(self.handle, channel_index, config)

    @compuscope_error_handling
    def set_trigger_config(self, trigger_index, config):
        # remember, unlike channels trigger indexes do not correspond to physical assigments
        return self.interface.SetTriggerConfig(self.handle, trigger_index, config)

    @compuscope_error_handling
    def set_multiple_rec_average_count(self, number):
        return self.interface.SetMulRecAverageCount(self.handle, number)

    @compuscope_error_handling
    def start_capture(self):
        return self.interface.StartCapture(self.handle)

    @compuscope_error_handling
    def transfer_data(
        self,
        channel_index,
        start_position,
        transfer_length,
        segment_index=1,
        transfer_mode=transfer_modes["default"],
    ):
        return self.interface.TransferData(
            self.handle,
            channel_index,
            transfer_mode,
            segment_index,
            start_position,
            transfer_length,
        )
