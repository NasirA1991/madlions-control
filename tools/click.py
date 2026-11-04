"""Move the X pointer and click, for local screenshot automation."""
import sys
import time

from Xlib import X, display
from Xlib.ext import xtest


def click(display_name, x: int, y: int) -> None:
    screen = display.Display(display_name)
    root = screen.screen().root
    xtest.fake_input(screen, X.MotionNotify, x=x, y=y)
    screen.sync()
    time.sleep(0.05)
    xtest.fake_input(screen, X.ButtonPress, 1)
    xtest.fake_input(screen, X.ButtonRelease, 1)
    screen.sync()
    screen.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--display", default=None)
    parser.add_argument("x", type=int)
    parser.add_argument("y", type=int)
    args = parser.parse_args()
    click(args.display, args.x, args.y)
