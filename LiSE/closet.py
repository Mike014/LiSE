# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013 Zachary Spector,  zacharyspector@gmail.com
"""The database backend, with dictionaries of loaded objects.

This is a caching database connector. There are dictionaries for all
objects that can be loaded from the database.

This module does not contain the code used to generate
SQL. That's in util.py, the class SaveableMetaclass.

"""
import os
import re
import sqlite3

import igraph

from gui.board import (
    Board,
    Spot,
    Pawn)
from gui.charsheet import CharSheet, CharSheetView
from gui.menu import Menu
from gui.img import Img
from model.character import Character
from model.dimension import Dimension
from model.event import Implicator
from model.portal import Portal
from model.thing import Thing
from util import (
    row2bone,
    Bone,
    schemata,
    saveables,
    saveable_classes,
    get_bone_during,
    Fabulator,
    Skeleton,
    Timestream,
    TimestreamException)


def noop(*args, **kwargs):
    """Do nothing."""
    pass


class ListItemIterator:
    """Iterate over a list in a way that resembles dict.iteritems().

Indices are considered as keys for this purpose."""
    def __init__(self, l):
        self.l = l
        self.l_iter = iter(l)
        self.i = 0

    def __iter__(self):
        """I'm an iterator"""
        return self

    def __len__(self):
        """Return length of underlying list"""
        return len(self.l)

    def __next__(self):
        it = next(self.l_iter)
        i = self.i
        self.i += 1
        return (i, it)

###
# These regexes serve to parse certain database records that represent
# function calls.
#
# Mainly, that means menu items and Effects.
###
ONE_ARG_RE = re.compile("(.+)")
TWO_ARG_RE = re.compile("(.+), ?(.+)")
ITEM_ARG_RE = re.compile("(.+)\.(.+)")
MAKE_SPOT_ARG_RE = re.compile(
    "(.+)\."
    "(.+),([0-9]+),([0-9]+),?(.*)")
MAKE_PORTAL_ARG_RE = re.compile(
    "(.+)\.(.+)->"
    "(.+)\.(.+)")
MAKE_THING_ARG_RE = re.compile(
    "(.+)\.(.+)@(.+)")
PORTAL_NAME_RE = re.compile(
    "Portal\((.+)->(.+)\)")
NEW_THING_RE = re.compile(
    "new_thing\((.+)+\)")
NEW_PLACE_RE = re.compile(
    "new_place\((.+)\)")


game_bone = Bone.subclass(
    'game_bone',
    [("language", unicode, u"eng"),
     ("seed", int, 0),
     ("branch", int, 0),
     ("tick", int, 0)])


string_bone = Bone.subclass(
    'string_bone',
    [("stringname", unicode, None),
     ("language", unicode, u"eng"),
     ("string", unicode, None)])


class Closet(object):
    """This is where you should get all your LiSE objects from, generally.

A RumorMill is a database connector that can load and generate LiSE
objects. When loaded or generated, the object will be kept in the
RumorMill, even if nowhere else.

There are some special facilities here for the convenience of
particular LiSE objects: Things look up their location here; Items
(including Things) look up their contents here; and Effects look up
their functions here. That means you need to register functions here
when you want Effects to use them. Supply callback
functions for Effects in a list in the keyword argument "effect_cbs".

Supply boolean callback functions for Causes and the like in the
keyword argument "test_cbs".

You need to create a SQLite database file with the appropriate schema
before RumorMill will work. For that, run mkdb.sh.

    """
    working_dicts = [
        "boardhanddict",
        "calendardict",
        "colordict",
        "dimensiondict",
        "boarddict",
        "dimensiondict",
        "boarddict",
        "effectdict",
        "effectdeckdict",
        "imgdict",
        "texturedict",
        "textagdict",
        "menudict",
        "menuitemdict",
        "styledict",
        "tickdict",
        "eventdict",
        "characterdict"]

    @property
    def dimensions(self):
        """Iterate over all dimensions."""
        return self.dimensiondict.itervalues()

    @property
    def characters(self):
        """Iterate over all characters."""
        return self.characterdict.itervalues()

    def __getattribute__(self, attrn):
        try:
            skeleton = super(Closet, self).__getattribute__("skeleton")
            bone = skeleton["game"][0]
            if attrn in bone._fields:
                return getattr(bone, attrn)
            else:
                return super(Closet, self).__getattribute__(attrn)
        except (KeyError, AttributeError):
            return super(Closet, self).__getattribute__(attrn)

    def __setattr__(self, attrn, val):
        if attrn == "branch":
            self.upd_branch(val)
        elif attrn == "tick":
            self.upd_tick(val)
        elif attrn == "language":
            self.upd_lang(val)
        else:
            super(Closet, self).__setattr__(attrn, val)

    def __init__(self, connector, lisepath, USE_KIVY=False, **kwargs):
        """Return a database wrapper around the SQLite database file by the
given name.

        """
        self.branch_listeners = []
        self.tick_listeners = []
        self.time_listeners = []
        self.lang_listeners = []
        self.connector = connector
        self.lisepath = lisepath

        self.c = self.connector.cursor()

        # This dict is special. It contains all the game
        # data--represented only as those types which sqlite3 is
        # capable of storing. All my objects are ultimately just
        # views on this thing.
        self.skeleton = Skeleton()
        for saveable in saveables:
            for tabn in saveable[3]:
                self.skeleton[tabn] = None
        self.c.execute(
            "SELECT language, seed, branch, tick FROM game")
        self.skeleton.update(
            {"game": [row2bone(
                self.c.fetchone(),
                game_bone)]})
        if "language" in kwargs:
            self.language = kwargs["language"]
        # This is a copy of the skeleton as it existed at the time of
        # the last save. I'll be finding the differences between it
        # and the current skeleton in order to decide what to write to
        # disk.
        self.old_skeleton = self.skeleton.copy()

        for wd in self.working_dicts:
            setattr(self, wd, dict())

        if USE_KIVY:
            from gui.kivybits import (
                load_textures,
                load_textures_tagged,
                load_all_textures)
            self.load_textures = lambda names: load_textures(
                self.c, self.skeleton, self.texturedict,
                self.textagdict, names)
            self.load_all_textures = lambda: load_all_textures(
                self.c, self.skeleton, self.texturedict, self.textagdict)
            self.load_textures_tagged = lambda tags: load_textures_tagged(
                self.c, self.skeleton, self.texturedict, self.textagdict,
                tags)
            self.USE_KIVY = True

        self.timestream = Timestream(self)

        self.game_speed = 1
        self.updating = False

        self.timestream = Timestream(self)
        self.time_travel_history = []

        placeholder = (noop, ITEM_ARG_RE)
        if "effect_cbs" in kwargs:
            effect_cb_fabdict = dict(
                [(
                    cls.__name__, self.constructorate(cls))
                 for cls in kwargs["effect_cbs"]])
        else:
            effect_cb_fabdict = {}
        self.get_effect_cb = Fabulator(effect_cb_fabdict)
        if "test_cbs" in kwargs:
            test_cb_fabdict = dict(
                [(
                    cls.__name__, self.constructorate(cls))
                 for cls in kwargs["test_cbs"]])
        else:
            test_cb_fabdict = {}
        self.get_test_cb = Fabulator(test_cb_fabdict)
        if "effect_cb_makers" in kwargs:
            effect_cb_maker_fabdict = dict(
                [(
                    maker.__name__, self.constructorate(maker))
                 for maker in kwargs["effect_makers"]])
        else:
            effect_cb_maker_fabdict = {}
        for (name, cb) in effect_cb_fabdict.iteritems():
            effect_cb_maker_fabdict[name] = lambda: cb
        self.make_effect_cb = Fabulator(effect_cb_maker_fabdict)
        if "test_cb_makers" in kwargs:
            test_cb_maker_fabdict = dict(
                [(
                    maker.__name__, self.constructorate(maker))
                 for maker in kwargs["test_cb_makers"]])
        else:
            test_cb_maker_fabdict = {}
        for (name, cb) in test_cb_fabdict.iteritems():
            test_cb_maker_fabdict[name] = lambda: cb
        self.make_test_cb = Fabulator(test_cb_maker_fabdict)
        self.menu_cbs = {
            'play_speed':
            (self.play_speed, ONE_ARG_RE),
            'back_to_start':
            (self.back_to_start, ''),
            'noop': placeholder,
            'toggle_menu':
            (self.toggle_menu, ONE_ARG_RE),
            'hide_menu':
            (self.hide_menu, ONE_ARG_RE),
            'show_menu':
            (self.show_menu, ONE_ARG_RE),
            'make_generic_place':
            (self.make_generic_place, ''),
            'increment_branch':
            (self.increment_branch, ONE_ARG_RE),
            'time_travel_inc_tick':
            (lambda mi, ticks:
             self.time_travel_inc_tick(int(ticks)), ONE_ARG_RE),
            'time_travel':
            (self.time_travel_menu_item, TWO_ARG_RE),
            'time_travel_inc_branch':
            (lambda mi, branches: self.time_travel_inc_branch(int(branches)),
             ONE_ARG_RE),
            'go':
            (self.go, ""),
            'stop':
            (self.stop, ""),
            'start_new_map': placeholder,
            'open_map': placeholder,
            'save_map': placeholder,
            'quit_map_editor': placeholder,
            'editor_select': placeholder,
            'editor_copy': placeholder,
            'editor_paste': placeholder,
            'editor_delete': placeholder,
            'mi_connect_portal':
            (self.mi_connect_portal, ""),
            'mi_show_popup':
            (self.mi_show_popup, ONE_ARG_RE)}

    def __del__(self):
        """Try to write changes to disk before dying.

        """
        self.c.close()
        self.connector.commit()
        self.connector.close()

    def upd_branch(self, b):
        for listener in self.branch_listeners:
            listener(self, b)
        self.upd_time(b, self.tick)
        self.skeleton["game"][0] = self.skeleton["game"][0]._replace(
            branch=b)

    def upd_tick(self, t):
        for listener in self.tick_listeners:
            listener(self, t)
        self.upd_time(self.branch, t)
        self.skeleton["game"][0] = self.skeleton["game"][0]._replace(
            tick=t)

    def upd_time(self, b, t):
        for listener in self.time_listeners:
            listener(self, b, t)

    def upd_lang(self, l):
        for listener in self.lang_listeners:
            listener(self, l)
        self.skeleton["game"][0] = self.skeleton["game"][0]._replace(
            lang=l)

    def constructorate(self, cls):

        def construct(*args):
            return cls(self, *args)
        return construct

    def insert_bones_table(self, bone, clas, tablename):
        """Insert the given bones into the table of the given name, as
defined by the given class.

For more information, consult SaveableMetaclass in util.py.

        """
        if bone != []:
            clas.dbop['insert'](self, bone, tablename)

    def delete_keydicts_table(self, keydict, clas, tablename):
        """Delete the records identified by the keydicts from the given table,
as defined by the given class.

For more information, consult SaveableMetaclass in util.py.

        """
        if keydict != []:
            clas.dbop['delete'](self, keydict, tablename)

    def detect_keydicts_table(self, keydict, clas, tablename):
        """Return the rows in the given table, as defined by the given class,
matching the given keydicts.

For more information, consult SaveableMetaclass in util.py.

        """
        if keydict != []:
            return clas.dbop['detect'](self, keydict, tablename)
        else:
            return []

    def missing_keydicts_table(self, keydict, clas, tablename):
        """Return rows in the given table, as defined by the given class,
*not* matching any of the given keydicts.

For more information, consult SaveableMetaclass in util.py.

        """
        if keydict != []:
            return clas.dbop['missing'](self, keydict, tablename)
        else:
            return []

    def toggle_menu(self, menuitem, menuname,
                    effect=None, deck=None, event=None):
        window = menuitem.menu.window
        menu = window.menus_by_name[menuname]
        menu.visible = not menu.visible
        menu.tweaks += 1

    def hide_menu(self, menuitem, menuname,
                  effect=None, deck=None, event=None):
        window = menuitem.menu.window
        menu = window.menus_by_name[menuname]
        menu.visible = False
        menu.tweaks += 1

    def show_menu(self, menuitem, menuname,
                  effect=None, deck=None, event=None):
        window = menuitem.menu.window
        menu = window.menus_by_name[menuname]
        menu.visible = True
        menu.tweaks += 1

    def get_text(self, strname):
        """Get the string of the given name in the language set at startup."""
        if strname is None:
            return ""
        elif strname[0] == "@":
            if strname[1:] == "branch":
                return str(self.branch)
            elif strname[1:] == "tick":
                return str(self.tick)
            else:
                assert(strname[1:] in self.skeleton["strings"])
                return self.skeleton["strings"][
                    strname[1:]][self.language].string
        else:
            return strname

    def make_igraph_graph(self, name):
        self.graphdict[name] = igraph.Graph(directed=True)

    def get_igraph_graph(self, name):
        if name not in self.graphdict:
            self.make_igraph_graph(name)
        return self.graphdict[name]

    def save_game(self):
        to_save = self.skeleton - self.old_skeleton
        to_delete = self.old_skeleton - self.skeleton
        for clas in saveable_classes:
            assert(len(clas.tablenames) > 0)
            for tabname in clas.tablenames:
                if tabname in to_delete:
                    clas._delete_keybones_table(
                        self.c, to_delete[tabname].iterbones(), tabname)
                if tabname in to_save:
                    clas._delete_keybones_table(
                        self.c, to_save[tabname].iterbones(), tabname)
                    try:
                        clas._insert_bones_table(
                            self.c, to_save[tabname].iterbones(), tabname)
                    except ValueError:
                        pass
        self.c.execute("DELETE FROM game")
        fields = self.skeleton["game"][0]._fields
        qrystr = "INSERT INTO game ({0}) VALUES ({1})".format(
            ", ".join(fields),
            ", ".join(["?"] * len(fields)))
        self.c.execute(
            qrystr,
            [getattr(self.skeleton["game"][0], k) for k in fields])
        self.old_skeleton = self.skeleton.copy()

    def load_strings(self):
        self.c.execute("SELECT stringname, language, string FROM strings")
        if "strings" not in self.skeleton:
            self.skeleton["strings"] = {}
        for row in self.c:
            bone = row2bone(row, string_bone)
            if bone.stringname not in self.skeleton["strings"]:
                self.skeleton["strings"][bone.stringname] = {}
            self.skeleton["strings"][
                bone.stringname][bone.language] = bone

    def make_generic_place(self, dimension):
        placen = "generic_place_{0}".format(len(dimension.graph.vs))
        return dimension.make_place(placen)

    def make_generic_thing(self, dimension, location):
        if not isinstance(dimension, Dimension):
            dimension = self.get_dimension(dimension)
        thingn = u"generic_thing_{0}".format(len(dimension.thingdict))
        for skel in (
                self.skeleton[u"thing_location"],
                self.skeleton[u"pawn_img"],
                self.skeleton[u"pawn_interactive"]):
            assert(thingn not in skel[unicode(dimension)])
            skel[unicode(dimension)][thingn] = Skeleton()
            skel[unicode(dimension)][thingn][self.branch] = Skeleton()
        dimension.make_thing(thingn, location)
        return dimension.get_thing(thingn)

    def make_spot(self, board, place, x, y):
        spot = Spot(board, place)
        if not hasattr(place, 'spots'):
            place.spots = []
        while len(place.spots) <= int(board):
            place.spots.append(None)
        place.spots[int(board)] = spot
        spot.set_img(self.imgdict['default_spot'])
        spot.set_coords(x, y)

    def make_portal(self, orig, dest):
        return orig.dimension.make_portal(orig, dest)

    def load_charsheet(self, character):
        character = str(character)
        bd = {
            "charsheet": [
                CharSheet.bonetypes.charsheet(character=character)],
            "charsheet_item": [
                CharSheet.bonetypes.charsheet_item(character=character)]}
        self.skeleton.update(
            CharSheet._select_skeleton(self.c, bd))
        return CharSheetView(character=self.get_character(character))

    def load_characters(self, names):
        qtd = {}
        tabns = ("character_things",
                 "character_places",
                 "character_portals",
                 "character_stats",
                 "character_skills",
                 "character_subcharacters")
        for tabn in tabns:
            qtd[tabn] = [
                getattr(Character.bonetypes, tabn)(character=n)
                for n in names]
        self.skeleton.update(
            Character._select_skeleton(self.c, qtd))
        r = {}
        for name in names:
            char = Character(self, name)
            r[name] = char
            self.characterdict[name] = char
        return r

    def get_characters(self, names):
        r = {}
        unhad = set()
        for name in names:
            if isinstance(name, Character):
                r[str(name)] = name
            elif name in self.characterdict:
                r[name] = self.characterdict[name]
            else:
                unhad.add(name)
        if len(unhad) > 0:
            r.update(self.load_characters(names))
        return r

    def get_character(self, name):
        return self.get_characters([str(name)])[str(name)]

    def get_thing(self, dimn, thingn):
        return self.get_dimension(dimn).get_thing(thingn)

    def get_effects(self, names):
        r = {}
        for name in names:
            r[name] = Implicator.make_effect(name)
        return r

    def get_effect(self, name):
        return self.get_effects([name])[name]

    def get_causes(self, names):
        r = {}
        for name in names:
            r[name] = Implicator.make_cause(name)
        return r

    def get_cause(self, cause):
        return self.get_causes([cause])[cause]

    def load_dimensions(self, names):
        # I think it might eventually *make sense* to load the same
        # dimension more than once without unloading it first. Perhaps
        # you want to selectively load the parts of it that the player
        # is interested in at the moment, the game world being too
        # large to practically load all at once.
        dimtd = Portal._select_skeleton(self.c, {
            "portal": [Portal.bonetype(dimension=n) for n in names]})
        dimtd.update(Thing._select_skeleton(self.c, {
            "thing_location": [
                Thing.bonetype(dimension=n) for n in names]}))
        self.skeleton.update(dimtd)
        r = {}
        for name in names:
            r[name] = Dimension(self, name)
        return r

    def load_dimension(self, name):
        return self.load_dimensions([name])[name]

    def get_dimensions(self, names=None):
        if names is None:
            self.c.execute("SELECT name FROM dimension")
            names = [row[0] for row in self.c.fetchall()]
        r = {}
        unhad = set()
        for name in names:
            if name in self.dimensiondict:
                r[name] = self.dimensiondict[name]
            else:
                unhad.add(name)
        if len(unhad) > 0:
            r.update(self.load_dimensions(unhad))
        return r

    def get_dimension(self, name):
        return self.get_dimensions([name])[name]

    def load_board(self, name):
        self.skeleton.update(Board._select_skeleton(self.c, {
            "board": [Board.bonetype(dimension=name)]}))
        self.skeleton.update(Spot._select_skeleton(self.c, {
            "spot_img": [Spot.bonetypes.spot_img(dimension=name)],
            "spot_interactive": [Spot.bonetypes.spot_interactive(
                dimension=name)],
            "spot_coords": [Spot.bonetypes.spot_coords(dimension=name)]}))
        self.skeleton.update(Pawn._select_skeleton(self.c, {
            "pawn_img": [Pawn.bonetypes.pawn_img(dimension=name, layer=None)],
            "pawn_interactive": [
                Pawn.bonetypes.pawn_interactive(
                    dimension=name,
                    layer=None)]}))
        return self.get_board(name)

    def get_board(self, name):
        dim = self.get_dimension(name)
        return Board(closet=self, dimension=dim)

    def get_place(self, dim, placen):
        if not isinstance(dim, Dimension):
            dim = self.get_dimension(dim)
        return dim.get_place(placen)

    def get_portal(self, dim, origin, destination):
        if not isinstance(dim, Dimension):
            dim = self.get_dimension(dim)
        return dim.get_portal(str(origin), str(destination))

    def get_textures(self, imgnames):
        r = {}
        unloaded = set()
        for imgn in imgnames:
            if imgn in self.texturedict:
                r[imgn] = self.texturedict[imgn]
            else:
                unloaded.add(imgn)
        if len(unloaded) > 0:
            r.update(self.load_textures(unloaded))
        return r

    def get_texture(self, imgn):
        return self.get_textures([imgn])[imgn]

    def load_menus(self, names):
        r = {}
        for name in names:
            r[name] = self.load_menu(name)
        return r

    def load_menu(self, name):
        self.load_menu_items(name)
        return Menu(closet=self, name=name)

    def load_menu_items(self, menu):
        bd = {"menu_item": [Menu.bonetypes.menu_item(menu=menu)]}
        r = Menu._select_skeleton(self.c, bd)
        self.skeleton.update(r)
        return r

    def load_timestream(self):
        self.skeleton.update(
            Timestream._select_table_all(self.c, 'timestream'))
        self.timestream = Timestream(self)

    def time_travel_menu_item(self, mi, branch, tick):
        return self.time_travel(branch, tick)

    def time_travel(self, branch, tick):
        if branch > self.timestream.hi_branch + 1:
            raise TimestreamException("Tried to travel too high a branch")
        if branch == self.timestream.hi_branch + 1:
            self.new_branch(self.branch, branch, tick)
        # will need to take other games-stuff into account than the
        # thing_location
        if tick < 0:
            tick = 0
            self.updating = False
        mintick = self.timestream.min_tick(branch, "thing_location")
        if tick < mintick:
            tick = mintick
        self.time_travel_history.append((self.branch, self.tick))
        if tick > self.timestream.hi_tick:
            self.timestream.hi_tick = tick
        self.branch = branch
        self.tick = tick

    def increment_branch(self, branches=1):
        b = self.branch + int(branches)
        mb = self.timestream.max_branch()
        if b > mb:
            # I dunno where you THOUGHT you were going
            self.new_branch(self.branch, self.branch+1, self.tick)
            return self.branch + 1
        else:
            return b

    def new_branch(self, parent, branch, tick):
        for dimension in self.dimensiondict.itervalues():
            dimension.new_branch(parent, branch, tick)
        for board in self.boarddict.itervalues():
            board.new_branch(parent, branch, tick)
        for character in self.characterdict.itervalues():
            character.new_branch(parent, branch, tick)
        self.skeleton["timestream"][branch] = Timestream.bonetype(
            branch=branch, parent=parent)

    def time_travel_inc_tick(self, ticks=1):
        self.time_travel(self.branch, self.tick+ticks)

    def time_travel_inc_branch(self, branches=1):
        self.increment_branch(branches)
        self.time_travel(self.branch+branches, self.tick)

    def go(self, nope=None):
        self.updating = True

    def stop(self, nope=None):
        self.updating = False

    def set_speed(self, newspeed):
        self.game_speed = newspeed

    def play_speed(self, mi, n):
        self.game_speed = int(n)
        self.updating = True

    def back_to_start(self, nope):
        self.stop()
        self.time_travel(self.branch, 0)

    def update(self, *args):
        if self.updating:
            self.time_travel_inc_tick(ticks=self.game_speed)

    def end_game(self):
        self.c.close()
        self.connector.commit()
        self.connector.close()

    def checkpoint(self):
        self.old_skeleton = self.skeleton.copy()

    def uptick_bone(self, bone):
        if hasattr(bone, "branch") and bone.branch > self.timestream.hi_branch:
            self.timestream.hi_branch = bone.branch
        if (
                hasattr(bone, "tick_from") and
                bone.tick_from > self.timestream.hi_tick):
            self.timestream.hi_tick = bone.tick_from
        if hasattr(bone, "tick_to") and bone.tick_to > self.timestream.hi_tick:
            self.timestream.hi_tick = bone.tick_to

    def uptick_skel(self):
        for bone in self.skeleton.iterbones():
            self.uptick_bone(bone)

    def get_present_bone(self, skel):
        return get_bone_during(skel, self.branch, self.tick)

    def mi_show_popup(self, mi, name):
        new_thing_match = re.match(NEW_THING_RE, name)
        if new_thing_match:
            root = mi.get_root_window().children[0]
            return root.show_pawn_picker(
                new_thing_match.groups()[0].split(", "))
        new_place_match = re.match(NEW_PLACE_RE, name)
        if new_place_match:
            root = mi.get_root_window().children[0]
            return root.show_spot_picker(
                new_place_match.groups()[0].split(", "))

    def mi_connect_portal(self, mi):
        pass

    def register_text_listener(self, stringn, listener):
        if stringn == "@branch":
            self.branch_listeners.append(listener)
        elif stringn == "@tick":
            self.tick_listeners.append(listener)
        if stringn[0] == "@" and stringn[1:] in self.skeleton["strings"]:
            self.skeleton["strings"][stringn[1:]].listeners.append(listener)

    def load_img_metadata(self):
        self.skeleton.update(Img._select_table_all(self.c, u"img_tag") +
                             Img._select_table_all(self.c, u"img"))


def mkdb(DB_NAME, lisepath):
    def recurse_rltiles(d):
        """Return a list of all bitmaps in the directory, and all levels of
subdirectory therein."""
        bmps = [d + os.sep + bmp
                for bmp in os.listdir(d)
                if bmp[0] != '.' and
                bmp[-4:] == ".bmp"]
        for subdir in os.listdir(d):
            try:
                bmps.extend(recurse_rltiles(d + os.sep + subdir))
            except:
                continue
        return bmps

    def ins_rltiles(curs, dirname):
        """Recurse into the directory, and for each bitmap I find, add records
        to the database describing it.

        Also tag the bitmaps with the names of the folders they are
        in, up to (but not including) the 'rltiles' folder.

        """
        for bmp in recurse_rltiles(dirname):
            qrystr = "insert into img (name, path, rltile, " \
                     "off_x, off_y) values (?, ?, ?, ?, ?)"
            name = bmp.replace(dirname, '').strip(os.sep)
            curs.execute(qrystr, (name, bmp, True, 4, 8))
            tags = name.split(os.sep)[:-1]
            qrystr = "insert into img_tag (img, tag) values (?, ?)"
            for tag in tags:
                curs.execute(qrystr, (name, tag))

    def read_sql(filen):
        """Read all text from the file, and execute it as SQL commands."""
        sqlfile = open(filen, "r")
        sql = sqlfile.read()
        sqlfile.close()
        c.executescript(sql)

    try:
        os.remove(DB_NAME)
    except OSError:
        pass
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "CREATE TABLE game"
        " (language TEXT DEFAULT 'eng',"
        "dimension TEXT DEFAULT 'Physical', "
        "branch INTEGER DEFAULT 0, "
        "tick INTEGER DEFAULT 0,"
        " seed INTEGER DEFAULT 0);")
    c.execute(
        "CREATE TABLE strings (stringname TEXT NOT NULL, language TEXT NOT"
        " NULL DEFAULT 'eng', string TEXT NOT NULL, "
        "PRIMARY KEY(stringname,  language));")

    done = set()
    while saveables != []:
        (demands, provides, prelude,
         tablenames, postlude) = saveables.pop(0)
        print(tablenames)
        breakout = False
        for demand in iter(demands):
            if demand not in done:
                saveables.append(
                    (demands, provides, prelude,
                     tablenames, postlude))
                breakout = True
                break
        if breakout:
            continue
        prelude_todo = list(prelude)
        while prelude_todo != []:
            pre = prelude_todo.pop()
            if isinstance(pre, tuple):
                c.execute(*pre)
            else:
                c.execute(pre)
        if len(tablenames) == 0:
            for post in postlude:
                if isinstance(post, tuple):
                    c.execute(*post)
                else:
                    c.execute(post)
            continue
        prelude_todo = list(prelude)
        try:
            while prelude_todo != []:
                pre = prelude_todo.pop()
                if isinstance(pre, tuple):
                    c.execute(*pre)
                else:
                    c.execute(pre)
        except sqlite3.OperationalError as e:
            saveables.append(
                (demands, provides, prelude_todo, tablenames, postlude))
            continue
        breakout = False
        tables_todo = list(tablenames)
        while tables_todo != []:
            tn = tables_todo.pop(0)
            try:
                c.execute(schemata[tn])
                done.add(tn)
            except sqlite3.OperationalError as e:
                print("OperationalError while creating table {0}:".format(tn))
                print(e)
                breakout = True
                break
        if breakout:
            saveables.append(
                (demands, provides, prelude_todo, tables_todo, postlude))
            continue
        postlude_todo = list(postlude)
        try:
            while postlude_todo != []:
                post = postlude_todo.pop()
                if isinstance(post, tuple):
                    c.execute(*post)
                else:
                    c.execute(post)
        except sqlite3.OperationalError as e:
            print("OperationalError during postlude from {0}:".format(tn))
            print(e)
            import pdb
            pdb.set_trace()
            saveables.append(
                (demands, provides, prelude_todo, tables_todo, postlude_todo))
            continue
        done.update(provides)

    oldhome = os.path.abspath(os.getcwd())
    os.chdir(lisepath + os.sep + 'sql')
    initfiles = sorted(os.listdir(os.getcwd()))
    for initfile in initfiles:
        if initfile[-3:] == "sql":  # weed out automatic backups and so forth
            print("reading SQL from file " + initfile)
            read_sql(initfile)

    os.chdir(oldhome)

    print("indexing the RLTiles")
    ins_rltiles(c, os.path.abspath(lisepath)
                + os.sep + 'gui' + os.sep + 'assets'
                + os.sep + 'rltiles')

    conn.commit()
    return conn


def load_closet(dbfn, lisepath, lang="eng", kivy=False):
    """Construct a ``Closet`` connected to the given database file. Use
the LiSE library in the path given.

If ``kivy`` == True, the closet will be able to load textures using
Kivy's Image widget.

Strings will be loaded for the language ``lang``. Use language codes
from ISO 639-2.

    """
    conn = sqlite3.connect(dbfn)
    r = Closet(connector=conn, lisepath=lisepath, lang=lang, USE_KIVY=kivy)
    r.load_strings()
    r.load_timestream()
    return r
