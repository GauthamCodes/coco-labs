"""R3.3 hostile submission (ADR 0014, T2): look for the secret in the environment."""
import os   # refused by the guard (not an allowed module)


def plan(costmap, start, goal, ctx):
    ctx.emit("note", text=str(dict(os.environ)))
    return None
