from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader
import inspect
import os

script_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) 
spec = spec_from_loader("tacho", SourceFileLoader("tacho", f"{script_dir}/../src/tacho"))
tacho = module_from_spec(spec)
spec.loader.exec_module(tacho)


def test_perf():
    app = tacho.Perf(['ls', '-l'])
    result = app.run()
    assert result
