# beipack

`beipack` is a collection of utilities to assist with packaging and launching Python programs in unusual ways.

The motivating force behind this project is the desire to execute a complex multi-module Python program — specifically, [Cockpit](https://github.com/cockpit-project/cockpit) — on a computer where it's not installed.  `beipack` is being developed as a freestanding project in hopes that it might be helpful to others.

Some key goals:

 - ability to package large multi-file or multi-module Python programs into a single standard Python file (`beipack`)
 - ability to send and execute this file via the stdin of the Python interpreter in another environment, via `ssh`, `flatpak-spawn`, or other container tools
 - scripts compatible with the Python REPL, which allows injecting them to `python -i`, without sending EOF, allowing stdin to be used by the script, after it has been sent
 - self-replicating ability: the target script should have access to its own source code, so that it can send itself on to further invocations
 - no requirement for any ability to write to disk (and no temporary files) but an optional ability to cache the sent program in `~/.cache/` to avoid the need to send large files over slow connections on future invocations
 - support for compressing Python programs to reduce the amount of data to be sent over slow connections

The intent is to develop the above features in a way that's as modular as possible, to allow mix-and-match of the required functionalities.
