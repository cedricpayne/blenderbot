"""Timer-based main-thread execution for Blender.

Blender's Python API (bpy) is not thread-safe. This module provides a queue-based
mechanism to schedule functions for execution on Blender's main thread, inspired
by GenesisCore's Timer pattern.
"""

import bpy
import traceback
from queue import Queue
from typing import Any


class Timer:
    """Executes queued functions on Blender's main thread via bpy.app.timers."""

    _queue = Queue()

    @classmethod
    def put(cls, delegate: Any):
        """Queue a function (or tuple of function + args) for main-thread execution."""
        cls._queue.put(delegate)

    @classmethod
    def run(cls):
        """Timer callback - processes all queued items on the main thread."""
        while not cls._queue.empty():
            item = cls._queue.get()
            try:
                if isinstance(item, (list, tuple)):
                    item[0](*item[1:])
                else:
                    item()
            except Exception:
                traceback.print_exc()
        return 0.016  # ~60fps check rate

    @classmethod
    def wait_run(cls, func):
        """Decorator: call func on the main thread and block until it completes."""
        def wrapper(*args, **kwargs):
            result_queue = Queue()

            def job(q):
                try:
                    result = func(*args, **kwargs)
                    q.put(result)
                except Exception as e:
                    q.put(e)

            cls.put((job, result_queue))
            result = result_queue.get()
            if isinstance(result, Exception):
                raise result
            return result

        return wrapper

    @classmethod
    def wait_run_with_context(cls, func):
        """Like wait_run but provides a VIEW_3D context override for bpy.ops calls."""
        def wrapper(*args, **kwargs):
            result_queue = Queue()

            def job(q):
                try:
                    override = bpy.context.copy()
                    view3d_areas = [a for a in bpy.context.screen.areas if a.type == "VIEW_3D"]
                    if view3d_areas:
                        override["area"] = view3d_areas[0]
                    with bpy.context.temp_override(**override):
                        result = func(*args, **kwargs)
                        q.put(result)
                except Exception as e:
                    q.put(e)

            cls.put((job, result_queue))
            result = result_queue.get()
            if isinstance(result, Exception):
                raise result
            return result

        return wrapper

    @classmethod
    def clear(cls):
        """Drain the queue without executing."""
        while not cls._queue.empty():
            cls._queue.get()

    @classmethod
    def register(cls):
        bpy.app.timers.register(cls.run, persistent=True)

    @classmethod
    def unregister(cls):
        cls.clear()
        try:
            bpy.app.timers.unregister(cls.run)
        except Exception:
            pass
