"""Public TraceLogger module required by the project structure.

Runtime code imports trace_logger because the Python standard library also
defines a trace module that test runners may preload.
"""

from trace_logger import TraceLogger

__all__ = ["TraceLogger"]
