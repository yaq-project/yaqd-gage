from functools import partial
from re import L
from async_timeout import enum  # type: ignore

import toml
import numpy as np
import pyqtgraph  # type: ignore
from qtpy import QtWidgets, QtCore  # type: ignore
import qtypes  # type: ignore

import yaqc_qtpy  # type: ignore
from yaqc_qtpy import _plot, qtype_items  # noqa

import yaq_traits  # type: ignore


colors = ["#cc6666", "#f0c674", "#8abeb7", "#b294bb"]  # red  # yellow  # aqua  # purple


class SegmentsGUI(QtWidgets.QSplitter):
    def __init__(self, qclient: yaqc_qtpy.QClient):
        super().__init__()
        self.arr = None
        self.qclient = qclient
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.poll)
        self._create_main_frame()
        self.qclient.get_measured_segments.finished.connect(self._on_get_segments)
        self.poll()  # once to get some data plotted

    def _create_main_frame(self):
        self.plot_widget = yaqc_qtpy._plot.Plot1D(yAutoRange=True)
        self.scatter = self.plot_widget.add_scatter()
        self.indicator_regions = []
        for _ in range(99):
            item = pyqtgraph.LinearRegionItem(
                movable=False, pen="#00000000", orientation="vertical"
            )
            self.indicator_regions.append(item)
            self.plot_widget.plot_object.addItem(item)
        self.addWidget(self.plot_widget)

        self._root_item = qtypes.Null()

        # plot control
        plot_item = qtypes.Null("plot")
        self._root_item.append(plot_item)
        self._poll_button = qtypes.Button("poll now")
        self._poll_button.updated_connect(self.poll)
        plot_item.append(self._poll_button)
        self._poll_periodically_bool = qtypes.Bool("poll periodically")
        self._poll_periodically_bool.updated_connect(self._on_poll_periodically_updated)
        plot_item.append(self._poll_periodically_bool)
        self._poll_period = qtypes.Float("poll period (s)", value=1, minimum=0, maximum=1000)
        self._poll_period.updated_connect(self._on_poll_periodically_updated)
        plot_item.append(self._poll_period)
        self._channel_selector = qtypes.Enum("channel", allowed=[f"ai{i}" for i in range(4)])
        self._channel_selector.updated_connect(lambda x: self.poll())
        plot_item.append(self._channel_selector)
        self._max_segments_shown = qtypes.Integer(
            "max segments shown", value=1_000, minimum=10, maximum=1_000
        )
        plot_item.append(self._max_segments_shown)

        # config
        self.config_item = qtypes.Null("config")
        self._root_item.append(self.config_item)
        self.qclient.get_config.finished.connect(self._on_get_config)
        self.qclient.get_config()

        # properties
        properties_item = qtypes.Null("properties")
        self._root_item.append(properties_item)
        qtype_items.append_properties(self.qclient, properties_item)

        self._tree_widget = qtypes.TreeWidget(self._root_item)
        self._tree_widget.resizeColumnToContents(0)
        self.addWidget(self._tree_widget)

    def _on_get_config(self, config):
        config = toml.loads(config)
        self._config = config
        self.config_item.clear()

        bins_item = qtypes.Null("segment bins")
        self.config_item.append(bins_item)
        for k, v in config["segment_bins"].items():
            header = qtypes.Null(k)
            bins_item.append(header)
            header.append(
                qtypes.Float("min", disabled=True, value=config["segment_bins"][k]["min"])
            )
            header.append(
                qtypes.Float("max", disabled=True, value=config["segment_bins"][k]["max"])
            )

        self._tree_widget.resizeColumnToContents(0)

        # segment bins
        ci = 0
        self.colors = dict()
        self.bin_regions = dict()
        self.segment_means = dict()
        for k, v in self._config["segment_bins"].items():
            self.colors[k] = colors[ci]
            ci += 1  # incriment color index
            self.bin_regions[k] = pyqtgraph.LinearRegionItem(
                brush=self.colors[k] + "44",
                movable=False,
                pen="#00000000",
                orientation="horizontal",
            )
            self.bin_regions[k].setRegion((v["min"], v["max"]))
            self.plot_widget.plot_object.addItem(self.bin_regions[k])

    def _on_get_segments(self, segments):
        channel_name = self._channel_selector.get_value()
        channel_index = int(channel_name[-1])

        # slice if needed
        if segments["ai3"].size > self._max_segments_shown.get_value():
            for k, v in segments.items():
                segments[k] = v[: self._max_segments_shown.get_value() + 1]

        # get edges
        gradient = np.gradient(segments["ai3"])
        edges = np.abs(gradient) > 0.1
        edge_width_count = 5
        edges = np.convolve(edges, np.full(edge_width_count, True))

        # get regions
        regions = {k: [] for k in self._config["segment_bins"].keys()}
        for k, v in self._config["segment_bins"].items():
            start = None
            for i, region in enumerate(segments["regions"]):
                if region == k and i != segments["regions"].size - 1:
                    if start is None:
                        start = i
                else:
                    if start is not None:
                        regions[k].append((start, i))
                        start = None

        # plot regions
        for indicator in self.indicator_regions:
            indicator.hide()
        i = 0
        for k, rs in regions.items():
            for region in rs:
                indicator = self.indicator_regions[i]
                i += 1
                indicator.show()
                indicator.setRegion((region[0] - 0.5, region[1] + 0.5))
                indicator.setBrush(self.colors[k] + "44")

        # plot bin regions if ai3
        for region in self.bin_regions.values():
            if channel_name == "ai3":
                region.show()
            else:
                region.hide()

        # plot channel
        yi = segments[self._channel_selector.get_value()]
        xi = np.arange(yi.size)
        self.scatter.setData(xi, yi)

    def _on_poll_periodically_updated(self, value):
        if self._poll_periodically_bool.get_value():
            self._timer.start(self._poll_period.get_value() * 1000)
        else:
            self._timer.stop()

    def poll(self, _=None):
        self.qclient.get_measured_segments()
