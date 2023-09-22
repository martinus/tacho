from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

spec = spec_from_loader("tacho", SourceFileLoader("tacho", "src/tacho"))
tacho = module_from_spec(spec)
spec.loader.exec_module(tacho)


def test_main_succeeds():
    tacho.main()
