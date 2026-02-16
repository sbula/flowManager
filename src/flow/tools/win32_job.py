import os
import ctypes
from ctypes import wintypes

# Windows Constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('ReadOperationCount', ctypes.c_ulonglong),
        ('WriteOperationCount', ctypes.c_ulonglong),
        ('OtherOperationCount', ctypes.c_ulonglong),
        ('ReadTransferCount', ctypes.c_ulonglong),
        ('WriteTransferCount', ctypes.c_ulonglong),
        ('OtherTransferCount', ctypes.c_ulonglong)
    ]

class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', ctypes.c_int64),
        ('PerJobUserTimeLimit', ctypes.c_int64),
        ('LimitFlags', ctypes.c_ulong),
        ('MinimumWorkingSetSize', ctypes.c_size_t),
        ('MaximumWorkingSetSize', ctypes.c_size_t),
        ('ActiveProcessLimit', ctypes.c_ulong),
        ('Affinity', ctypes.c_void_p),
        ('PriorityClass', ctypes.c_ulong),
        ('SchedulingClass', ctypes.c_ulong)
    ]

class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ('IoInfo', IO_COUNTERS),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryUsed', ctypes.c_size_t),
        ('PeakJobMemoryUsed', ctypes.c_size_t)
    ]

class WindowsJobObject:
    """
    Manages a Windows Job Object to ensure child processes are killed
    when the parent dies or the job is closed.
    """
    def __init__(self):
        self._job_handle = None
        if os.name == 'nt':
            self._create_job()

    def _create_job(self):
        # Create Job
        self._job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
        if not self._job_handle:
            raise ctypes.WinError()

        # Set Info: Kill on Close
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        # SetInformationJobObject
        success = ctypes.windll.kernel32.SetInformationJobObject(
            self._job_handle,
            JobObjectExtendedLimitInformation,
            ctypes.pointer(info),
            ctypes.sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION)
        )
        if not success:
            raise ctypes.WinError()

    def assign_process(self, process_handle: int):
        """Assigns a process (by handle) to this Job."""
        if not self._job_handle:
            return
        
        success = ctypes.windll.kernel32.AssignProcessToJobObject(
            self._job_handle,
            ctypes.c_void_p(process_handle)
        )
        if not success:
            raise ctypes.WinError()

    def close(self):
        if self._job_handle:
            ctypes.windll.kernel32.CloseHandle(self._job_handle)
            self._job_handle = None
