"""Python Exceptions for Gage codes."""

from typing import Any, Dict


codes: Dict[int, Any] = dict()


class GageException(Exception):
    pass


class GageWarning(Warning):
    pass


class UnnecessaryOperation(GageWarning):
    pass


codes[0] = UnnecessaryOperation


class NotInitialized(GageException):
    pass


codes[-1] = NotInitialized


class UnableCreateResourceManager(GageException):
    pass


codes[-3] = UnableCreateResourceManager


class InterfaceNotFound(GageException):
    pass


codes[-4] = InterfaceNotFound


class HandleInUse(GageException):
    pass


codes[-5] = HandleInUse


class InvalidHandle(GageException):
    pass


codes[-6] = InvalidHandle


class InvalidRequest(GageException):
    pass


codes[-7] = InvalidRequest


class NoSystemsFound(GageException):
    pass


codes[-8] = NoSystemsFound


class MemoryError(GageException):
    pass


codes[-9] = MemoryError


class LockSystemFailed(GageException):
    pass


codes[-10] = LockSystemFailed


class InvalidStructSize(GageException):
    pass


codes[-11] = InvalidStructSize


class InvalidState(GageException):
    """Invalid action in current state."""

    pass


codes[-12] = InvalidState


class InvalidEvent(GageException):
    pass


codes[-13] = InvalidEvent


class InvalidSharedRegion(GageException):
    """Cannot create shared memory region."""

    pass


codes[-14] = InvalidSharedRegion


class InvalidFilename(GageException):
    pass


codes[-15] = InvalidFilename


class SharedMapUnavaliable(GageException):
    """Cannot map shared memory region."""

    pass


codes[-16] = SharedMapUnavaliable


class InvalidStart(GageException):
    """Invalid start address."""

    pass


codes[-17] = InvalidStart


class InvalidLength(GageException):
    """Invalid buffer length."""

    pass


codes[-18] = InvalidLength


class SocketNotFound(GageException):
    """Windows socket error."""

    pass


codes[-19] = SocketNotFound


class SocketError(GageException):
    """Resource manager communication error."""

    pass


codes[-20] = SocketError


class NoAvaliableSystem(GageException):
    """No digitizer system found with the requested requirements."""

    pass


codes[-21] = NoAvaliableSystem


class NullPointer(GageException):
    pass


codes[-22] = NullPointer


class InvalidChannel(GageException):
    """Invalid channel index."""

    pass


codes[-23] = InvalidChannel


class InvalidTrigger(GageException):
    """Invalid trigger index."""

    pass


codes[-24] = InvalidTrigger


class InvalidEventType(GageException):
    pass


codes[-25] = InvalidEventType


class BufferTooSmall(GageException):
    pass


codes[-26] = BufferTooSmall


class InvalidParameter(GageException):
    pass


codes[-27] = InvalidParameter


class InvalidSampleRate(GageException):
    pass


codes[-28] = InvalidSampleRate


class NoExtClk(GageException):
    pass


codes[-29] = NoExtClk


class SegCountTooBig(GageException):
    """Mulrec: invalid size or count."""

    pass


codes[-30] = SegCountTooBig


class InvalidSegmentSize(GageException):
    pass


codes[-31] = InvalidSegmentSize


class DepthSizeTooBig(GageException):
    pass


codes[-32] = DepthSizeTooBig


class InvalidCalMode(GageException):
    pass


codes[-33] = InvalidCalMode


class InvalidTrigCond(GageException):
    pass


codes[-34] = InvalidTrigCond


class InvalidTrigLevel(GageException):
    pass


codes[-35] = InvalidTrigLevel


class InvalidTrigSource(GageException):
    pass


codes[-36] = InvalidTrigSource
