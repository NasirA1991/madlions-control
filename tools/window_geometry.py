"""Print X Y W H of the largest window named Madlions Control."""
from Xlib import display

d = display.Display()
best = None


def walk(window):
    global best
    try:
        name = window.get_wm_name()
        geo = window.get_geometry()
        if name == "Madlions Control" and geo.width > 400 and geo.height > 300:
            if best is None or geo.width * geo.height > best[2] * best[3]:
                best = (geo.x, geo.y, geo.width, geo.height)
    except Exception:
        pass
    try:
        for child in window.query_tree().children:
            walk(child)
    except Exception:
        pass


walk(d.screen().root)
print(" ".join(str(v) for v in best) if best else "0 0 1180 780")
