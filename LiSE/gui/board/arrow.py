# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013 Zachary Spector,  zacharyspector@gmail.com
from __future__ import print_function
from math import cos, sin, hypot, atan
from LiSE.util import (
    wedge_offsets_rise_run,
    truncated_line,
    fortyfive)
from kivy.graphics import Line, Color
from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty


class Arrow(Widget):
    """A widget that points from one :class:`~LiSE.gui.board.Spot` to
    another.

    :class:`Arrow`s are the graphical representations of
    :class:`~LiSE.model.Portal`s. They point from the :class:`Spot`
    representing the :class:`Portal`'s origin, to the one representing
    its destination.

    """
    margin = 10
    """When deciding whether a touch collides with me, how far away can
    the touch get before I should consider it a miss?"""
    w = 1
    """The width of the inner, brighter portion of the :class:`Arrow`. The
    whole :class:`Arrow` will end up thicker."""
    board = ObjectProperty()
    """The board on which I am displayed."""
    portal = ObjectProperty()
    """The portal that I represent."""

    def __init__(self, **kwargs):
        """Bind some properties, and put the relevant instructions into the
        canvas--but don't put any point data into the instructions
        just yet. For that, wait until ``on_parent``, when we are
        guaranteed to know the positions of our endpoints.

        """
        Widget.__init__(self, **kwargs)
        self.upd_pos_size()
        orign = unicode(self.portal.origin)
        destn = unicode(self.portal.destination)
        self.board.spotdict[orign].bind(
            pos=self.setter('pos'),
            size=self.realign,
            transform=self.realign)
        self.board.spotdict[destn].bind(
            pos=self.upd_size,
            size=self.realign,
            transform=self.realign)
        self.bind(pos=self.repoint)
        self.bind(size=self.repoint)
        self.bg_color = Color(0.25, 0.25, 0.25)
        self.fg_color = Color(1.0, 1.0, 1.0)
        self.bg_line = Line(width=self.w * 1.4)
        self.fg_line = Line(width=self.w)
        self.canvas.add(self.bg_color)
        self.canvas.add(self.bg_line)
        self.canvas.add(self.fg_color)
        self.canvas.add(self.fg_line)

    def on_parent(self, i, v):
        """Make sure to rearrange myself when I get a new ``pos`` or ``size``.

        This only happens when I have a parent because otherwise I cannot
        possibly have an origin or a destination."""
        v.bind(pos=self.realign, size=self.realign)
        self.realign()

    def __unicode__(self):
        """Return Unicode name of my :class:`Portal`"""
        return unicode(self.portal)

    def __str__(self):
        """Return string name of my :class:`Portal`"""
        return str(self.portal)

    @property
    def reciprocal(self):
        """If it exists, return the edge of the :class:`Portal` that connects
        the same two places that I do, but in the opposite
        direction. Otherwise, return ``None``.

        """
        # Return the edge of the portal that connects the same two
        # places in the opposite direction, supposing it exists
        try:
            return self.portal.reciprocal.arrow
        except KeyError:
            return None

    def get_points(self):
        """Return the coordinates of the points that describe my shape."""
        orig = self.board.spotdict[unicode(self.portal.origin)]
        dest = self.board.spotdict[unicode(self.portal.destination)]
        (ox, oy) = orig.pos
        # orig.size is SUPPOSED to be the same as orig.tex.size but
        # sometimes it isn't, because threading
        try:
            (ow, oh) = orig.tex.size
        except AttributeError:
            (ow, oh) = (0, 0)
        orx = ow / 2
        ory = ow / 2
        ox += orx
        oy += ory
        (dx, dy) = dest.pos
        try:
            (dw, dh) = dest.tex.size
        except AttributeError:
            (dw, dh) = (0, 0)
        drx = dw / 2
        dry = dh / 2
        dx += drx
        dy += dry

        if drx > dry:
            dr = drx
        else:
            dr = dry
        if dy < oy:
            yco = -1
        else:
            yco = 1
        if dx < ox:
            xco = -1
        else:
            xco = 1
        (leftx, boty, rightx, topy) = truncated_line(
            float(ox * xco), float(oy * yco),
            float(dx * xco), float(dy * yco),
            dr + 1)
        taillen = float(self.board.arrowhead_size)
        rise = topy - boty
        run = rightx - leftx
        if rise == 0:
            xoff1 = cos(fortyfive) * taillen
            yoff1 = xoff1
            xoff2 = xoff1
            yoff2 = -1 * yoff1
        elif run == 0:
            xoff1 = sin(fortyfive) * taillen
            yoff1 = xoff1
            xoff2 = -1 * xoff1
            yoff2 = yoff1
        else:
            (xoff1, yoff1, xoff2, yoff2) = wedge_offsets_rise_run(
                rise, run, taillen)
        x1 = (rightx - xoff1) * xco
        x2 = (rightx - xoff2) * xco
        y1 = (topy - yoff1) * yco
        y2 = (topy - yoff2) * yco
        endx = rightx * xco
        endy = topy * yco
        r = [ox, oy,
             endx, endy, x1, y1,
             endx, endy, x2, y2,
             endx, endy]
        for coord in r:
            assert(coord > 0.0)
            assert(coord < 1000.0)
        return r

    def get_slope(self):
        """Return a float of the increase in y divided by the increase in x,
        both from left to right."""
        orig = self.board.spotdict[unicode(self.portal.origin)]
        dest = self.board.spotdict[unicode(self.portal.destination)]
        ox = orig.x
        oy = orig.y
        dx = dest.x
        dy = dest.y
        if oy == dy:
            return 0
        elif ox == dx:
            return None
        else:
            rise = dy - oy
            run = dx - ox
            return rise / run

    def get_b(self):
        """Return my Y-intercept.

        I probably don't really hit the left edge of the window, but
        this is where I would, if I were long enough.

        """
        orig = self.board.spotdict[unicode(self.portal.origin)]
        dest = self.board.spotdict[unicode(self.portal.destination)]
        (ox, oy) = orig.pos
        (dx, dy) = dest.pos
        denominator = dx - ox
        x_numerator = (dy - oy) * ox
        y_numerator = denominator * oy
        return ((y_numerator - x_numerator), denominator)

    def repoint(self, *args):
        """Recalculate all my points and redraw."""
        points = self.get_points()
        self.bg_line.points = points
        self.fg_line.points = points

    def realign(self, *args):
        self.upd_pos_size()
        self.repoint()

    def upd_size(self, i, (x, y)):
        """Set my size so that my upper right corner is at the point given.

        This will, not infrequently, give me a negative size. Don't
        think too hard about it.

        """
        self.width = x - self.x
        self.height = y - self.y

    def upd_pos_size(self, *args):
        """Update my ``pos`` and ``size`` based on the spots at my
        origin and destination.

        This is often necessary because :class:`Spot` is a subclass of
        :class:`Scatter`, which implements high-performance
        drag-and-drop behavior by not really moving the widget, but
        doing a matrix transformation on its texture. This still makes
        the ``pos`` appear with a new value when accessed here, but
        might not trigger an update of variables bound to ``pos``.

        """
        orig = self.board.spotdict[unicode(self.portal.origin)]
        dest = self.board.spotdict[unicode(self.portal.destination)]
        (ox, oy) = orig.pos
        (dx, dy) = dest.pos
        w = dx - ox
        h = dy - oy
        self.pos = (ox, oy)
        self.size = (w, h)

    def collide_point(self, x, y):
        """Return True iff the point falls sufficiently close to my core line
        segment to count as a hit.

        """
        if not super(Arrow, self).collide_point(x, y):
            return False
        orig = self.board.spotdict[unicode(self.portal.origin)]
        dest = self.board.spotdict[unicode(self.portal.destination)]
        (ox, oy) = orig.pos
        (dx, dy) = dest.pos
        if ox == dx:
            return abs(y - dy) <= self.w
        elif oy == dy:
            return abs(x - dx) <= self.w
        else:
            correct_angle_a = atan(dy / dx)
            observed_angle_a = atan(y / x)
            error_angle_a = abs(observed_angle_a - correct_angle_a)
            error_seg_len = hypot(x, y)
            return sin(error_angle_a) * error_seg_len <= self.margin
