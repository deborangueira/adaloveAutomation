"""Application rules shared by every front-end (terminal menu in cli/main.py,
local web server in cli/server.py). Front-ends own the interaction — prompts
or pages — and call these for the decisions, so both behave the same.

Functions here never construct an AdaloveClient themselves: callers pass
data in, which keeps them pure and lets each front-end keep its own
client/credential handling.
"""
