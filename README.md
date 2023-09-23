# tacho - Tachometer for your apps

An experimental python tool to measure process runtimes

This is mostly inspired by [hyperfine](https://github.com/sharkdp/hyperfine). Some goals I have with this:

* Good continuous prediction when benchmarking will be finished, even when the process itself takes very long (say hours).
* Plot nice histograms, e.g. with UTF braille or block elements https://en.wikipedia.org/wiki/Block_Elements
* Math: lognormal distribution? show plenty of math information
* colors!
* Just call `perf stat -x ';' -I 500` to get exact data, update whenever we have new data?


## Python Stuff

I'm a python noob, some things that I shouldn't forget:

* `poetry run tacho`
* `poetry run pytest`



# Inspirations

* https://github.com/wasi-master/fastero
* https://github.com/sharkdp/hyperfine
* 