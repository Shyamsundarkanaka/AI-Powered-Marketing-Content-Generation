"""Media generation: voiceover audio and rendered video.

Both modules are pure functions of their inputs — they take a script/plan and a
destination path, and know nothing about the database or the job queue. That
keeps them runnable standalone (each has a `__main__` CLI) and testable without
a worker.
"""
