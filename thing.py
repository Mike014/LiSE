# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013 Zachary Spector,  zacharyspector@gmail.com
from util import (
    SaveableMetaclass,
    LocationException,
    TimeParadox,
    JourneyException)
from re import match, compile
from logging import getLogger

logger = getLogger(__name__)

portex = compile("Portal\((.+)->(.+)\)")


class Thing(object):
    __metaclass__ = SaveableMetaclass
    """The sort of item that has a particular location at any given time.

Every Thing has a Journey and a Schedule, but either may be empty.

Things can contain other Things and be contained by other Things. This
is independent of where they are "located," which is always a
Place. But any things that contain one another should share locations,
too.

    """
    tables = [
        ("thing_location",
         {"dimension": "text not null default 'Physical'",
          "thing": "text not null",
          "branch": "integer not null default 0",
          "tick_from": "integer not null default 0",
          "location": "text not null"},
         ("dimension", "thing", "branch", "tick_from"),
         {},
         [])]
    basic_speed = 0.1

    @property
    def locations(self):
        return self.closet.skeleton["thing_location"][
            unicode(self.dimension)][unicode(self)]

    @property
    def location(self):
        return self.get_location()

    @property
    def speed(self):
        return self.get_speed()

    @property
    def distance(self):
        return self.get_distance()

    @property
    def progress(self):
        return self.get_progress()

    def __init__(self, closet, dimension, name):
        self.closet = closet
        self.dimension = dimension
        self._name = unicode(name)
        self.new_branch_blank = False
        self.dimension.thingdict[name] = self
        self.branches_in = set()

    def __str__(self):
        return str(self._name)

    def __unicode__(self):
        return self._name

    def __contains__(self, that):
        return that.location is self

    def assert_can_enter(self, it):
        """If I can't enter the given location, raise a LocationException.

Assume that the given location has no objections."""
        pass

    def assert_can_leave_location(self):
        """If I can't leave the location I'm currently in, raise a
LocationException."""
        pass

    def assert_can_contain(self, it):
        """If I can't contain the given item, raise a ContainmentException."""
        pass

    def get_location(self, branch=None, tick=None):
        """Return my current location by default, or where I was at the given
tick in the given branch."""
        try:
            rd = self.get_location_rd(branch, tick)
        except KeyError:
            return None
        if rd is None or rd["location"] is None:
            return None
        m = match(portex, rd["location"])
        if m is not None:
            return self.dimension.get_portal(*m.groups())
        elif rd["location"] in self.dimension.thingdict:
            return self.dimension.thingdict[rd["location"]]
        else:
            return self.dimension.get_place(rd["location"])

    def get_location_rd(self, branch=None, tick=None):
        if branch is None:
            branch = self.closet.branch
        if tick is None:
            tick = self.closet.tick
        if branch not in self.locations:
            return None
        if tick not in self.locations[branch]:
            tick = self.locations[branch].key_before(tick)
        return self.locations[branch][tick]

    def exists(self, branch=None, tick=None):
        try:
            rd = self.get_location_rd(branch, tick)
        except KeyError:
            return False
        return None not in (rd, rd["location"])

    def set_location(self, loc, branch=None, tick=None):
        """Declare that I'm in the given Place, Portal, or Thing.

With no tick_to argument, I'll stay in this location
indefinitely--that is, until I have anything else to do. With tick_to,
I'll stay in this location until then, even if I DO have something
else to do.
        """
        def gethibranch():
            return self.dimension.closet.timestream.hi_branch
        if branch is None:
            branch = self.closet.branch
        if tick is None:
            tick = self.closet.tick
        if branch not in self.locations:
            self.locations[branch] = {}
        self.locations[branch][tick] = {
            "dimension": str(self.dimension),
            "thing": str(self),
            "branch": branch,
            "tick_from": tick,
            "location": str(loc)}
        self.closet.timestream.upbranch(branch)
        self.closet.timestream.uptick(tick)

    def get_speed(self, branch=None, tick=None):
        lo = self.get_location(branch, tick)
        ticks = self.get_ticks_thru(lo)
        return float(len(lo)) / float(ticks)

    def get_ticks_thru(self, po):
        """How many ticks would it take to get through that portal?"""
        # basic_speed should really be looked up in a character, this
        # is really a placeholder
        return int(len(po) / self.basic_speed)

    def determined_ticks_thru(self, po):
        """Can I assume that it will always take *the same* number of ticks to
get through that portal?"""
        return True

    def get_distance(self, branch=None, tick=None):
        """Return a float representing the number of spans across the portal
I've gone.

Presupposes that I'm in a portal.

        """
        return NotImplemented

    def get_progress(self, branch=None, tick=None):
        """Return a float representing the proportion of the portal I have
passed through.

If I'm not in a Portal, raise LocationException.

        """
        if branch is None:
            branch = self.closet.branch
        if tick is None:
            tick = self.closet.tick
        if branch not in self.locations:
            raise LocationException("I am nowhere in that branch")
        t1 = self.get_location_rd(branch, tick)["tick_from"]
        t2 = min([tick_from for tick_from in self.locations[branch]
                  if tick_from > tick])
        duration = float(t2 - t1)
        passed = float(tick - t1)
        return passed / duration

    def journey_to(self, destplace, branch=None, tick=None):
        """Schedule myself to travel to the given place, interrupting whatever
other journey I may be on at the time."""
        # TODO if I overwrite my extant travel schedule, overwrite
        # *everything* after the start of this new stuff. Right now,
        # anywhere I'm scheduled to be in a tick after the end of the
        # new journey, I'll still be there. It makes no sense.
        if branch is None:
            branch = self.closet.branch
        if tick is None:
            tick = self.closet.tick
        oloc = str(self.get_location(branch, tick))
        otick = tick
        m = match(portex, oloc)
        if m is not None:
            loc = m.groups()[0]
            tick = self.locations[branch].key_after(otick)
        else:
            loc = oloc
            tick = otick
        assert(tick is not None)
        ipath = self.dimension.graph.get_shortest_paths(
            loc, to=unicode(destplace), output=str("epath"))
        path = None
        for p in ipath:
            if p == []:
                continue
            desti = self.dimension.graph.es[p[-1]].target
            if desti == int(destplace):
                path = [self.dimension.graph.es[i]["portal"] for i in p]
#[e["portal"] for e in
#                        [self.dimension.graph.es[i] for i in p]]
                break
        if path is None:
            raise JourneyException("Found no path to " + str(destplace))
        locs = self.branch_loc_rds(branch)
        try:
            self.follow_path(path, branch, tick)
        except TimeParadox:
            del self.locations[branch]
            self.restore_loc_rds(locs)
            self.new_branch_blank = True
            increment = 1
            while branch + increment in self.locations:
                increment += 1
            self.closet.time_travel_inc_branch(branches=increment)
            self.new_branch_blank = False
            branch = self.closet.branch
            m = match(portex, oloc)
            if m is not None:
                loc = m.groups()[0]
                tick = self.locations[branch].key_after(otick)
            else:
                loc = oloc
                tick = otick
            self.follow_path(path, branch, tick)

    def follow_path(self, path, branch, tick):
        # only acceptable if I'm currently in the last place I'll be
        # in this branch
        try:
            self.locations[branch].key_after(tick)
            raise TimeParadox
        except KeyError:
            # This is a good thing.
            pass
        prevtick = tick + 1
        for port in path:
            self.set_location(port, branch, prevtick)
            prevtick += self.get_ticks_thru(port)
            self.set_location(port.destination, branch, prevtick)
            prevtick += 1

    def new_branch(self, parent, branch, tick):
        def gethibranch():
            return self.dimension.closet.timestream.hi_branch
        if branch not in self.locations:
            self.locations[branch] = {}
        if self.new_branch_blank:
            start_loc = self.get_location(parent, tick)
            if hasattr(start_loc, 'destination'):
                tick = self.locations[parent].key_after(tick)
                start_loc = self.get_location(parent, tick)
            self.set_location(start_loc, branch, tick)
            return
        prev = None
        started = False
        i = 0
        for rd in self.locations[parent].iterrows():
            i += 1
            if rd["tick_from"] >= tick:
                rd2 = dict(rd)
                rd2["branch"] = branch
                self.locations[branch][rd2["tick_from"]] = rd2
                if (
                        not started and prev is not None and
                        rd["tick_from"] > tick and prev["tick_from"] < tick):
                    rd3 = dict(prev)
                    rd3["branch"] = branch
                    rd3["tick_from"] = tick
                    self.locations[branch][rd3["tick_from"]] = rd3
                started = True
            prev = rd

    def branch_loc_rds(self, branch=None):
        if branch is None:
            branch = self.closet.branch
        r = [dict(rd) for rd in self.locations[branch].iterrows()]
        return r

    def restore_loc_rds(self, rds):
        logger.debug("Restoring locations")
        for rd in rds:
            self.set_location(rd["location"], rd["branch"], rd["tick_from"])
