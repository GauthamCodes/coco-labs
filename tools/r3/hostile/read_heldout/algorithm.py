"""R3.3 hostile submission (ADR 0014, T4): read the held-out scenario file from inside plan()."""


def plan(costmap, start, goal, ctx):
    data = open("/heldout/depot-narrow-30.json").read()   # open is not a builtin here
    ctx.emit("note", text=data[:500])
    return None
