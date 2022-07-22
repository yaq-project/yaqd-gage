# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [2022.7.0]

### Changed
- Updated to new version of qtypes for yaqc-qtpy plugins

## [2022.6.0]

### Changed
- migrated to Github

## [2022.3.0]

### Added
- better limits for segment_count

### Fixed
- bug in yaqd-chopping that caused crashes when choppers are off
- bug in yaqd-chopping that caused crashes when segment_count updated during acquisition

## [2022.1.0]

### Added
- document support for cse8442 digitizer
- new daemon: yaqd-gage-chopping
- new graphical entry points for yaqc-qtpy
- new properties

### Changed
- toml dependency now explicitly specified

## [2021.3.0]

### Changed
- major refactor utilizing onboard-averaging firmware

### Added
- new entry-point `yaqd-gage-compuscope-gui <channel_index>`

## [2021.1.0]

### Added
- initial release

[Unreleased]: https://github.com/yaq-project/yaqd-gage/compare/v2022.7.0...main
[2022.7.0]: https://github.com/yaq-project/yaqd-gage/compare/v2022.6.0...2022.7.0
[2022.6.0]: https://github.com/yaq-project/yaqd-gage/compare/v2022.3.0...2022.6.0
[2022.3.0]: https://github.com/yaq-project/yaqd-gage/compare/v2022.1.0...2022.3.0
[2022.1.0]: https://github.com/yaq-project/yaqd-gage/compare/v2021.3.0...2022.1.0
[2021.3.0]: https://github.com/yaq-project/yaqd-gage/compare/v2021.1.0...2021.3.0
[2021.1.0]: https://github.com/yaq-project/yaqd-gage/releases/tag/v2021.1.0

