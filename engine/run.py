import os.path
import sys
from typing import Any, Optional, List
from types import ModuleType

from fileutils import read_source_py
from engine.logs import Log
from engine.tracer import Tracer
from queues import DualMessageQueue
from typed import TRunner, T_tracer_callback_func


__all__ = ['PyRunner']


class DummyLoader:

    def __init__(self, fullname: str, *args: Any) -> None:
        self.fullname = fullname


class PyRunner(TRunner):
    tracer_callbacks: Optional[List[T_tracer_callback_func]] = None
    source: Optional[str] = None

    def __init__(self,
                 source: str,
                 args: List[str],
                 tracer_callbacks: Optional[List[T_tracer_callback_func]],
                 dual_message_queue: DualMessageQueue):
        self.args = args
        self.tracer_callbacks = tracer_callbacks
        self.dmq = dual_message_queue
        if os.path.isabs(source):
            self.source = source
        else:
            for path in [os.curdir] + sys.path:
                if path is None:
                    continue
                f = os.path.join(path, source)
                try:
                    exists = os.path.exists(f)
                except UnicodeError:
                    exists = False
                if exists:
                    self.source = f
                    break

    def _build_module(self, source: str) -> ModuleType:
        mod_ty = ModuleType('__main__')
        mod_ty.__file__ = source
        mod_ty.__loader__ = DummyLoader
        mod_ty.__builtins__ = sys.modules['builtins']
        sys.modules['__main__'] = mod_ty
        return mod_ty

    def _build_args(self, args: List[str], source: str) -> None:
        self.origin_argv = sys.argv
        sys.argv = [source]
        for arg in args:
            sys.argv.append(arg)

    def _resume_args(self) -> None:
        sys.argv = self.origin_argv

    def _run(self, source: str, args: List[str]):
        source_byte = read_source_py(source)
        code: Optional[bytes] = None
        mod = self._build_module(source)
        self._build_args(args, source)
        try:
            code = compile(source_byte, source, "exec", dont_inherit=True)
        except Exception as e:
            Log.error(f"Fail to compile code: {source}", e)
            return
        tracer = Tracer(self.tracer_callbacks, self.dmq)
        tracer.start()
        try:
            exec(code, mod.__dict__)
            tracer.stop()
        except Exception as e:
            tracer.stop()
            Log.error(f"Fail to execute code: {source}", e)
        finally:
            self._resume_args()

    def run(self):
        assert self.source is not None
        self._run(self.source, self.args)
