import random
from tempfile import mkdtemp
from multiprocessing import freeze_support
from inspect import getsource

from kivy.clock import Clock
from kivy.lang.builder import Builder
from kivy.properties import BooleanProperty

from ELiDE.game import GameApp, GameScreen, GridBoard


def game_start(engine) -> None:
	from random import randint, shuffle
	import networkx as nx

	# ensure we're on a fresh branch
	if engine.turn != 0 or engine.tick != 0:
		if engine.branch == 'trunk':
			new_branch_name = 'trunk0'
		else:
			new_branch_num = int(engine.branch[5:])
			new_branch_name = 'trunk' + str(new_branch_num)
		engine.turn = 0
		engine.tick = 0
		engine.switch_main_branch(new_branch_name)

	engine.eternal["nonusage-limit"] = 100
	wide = engine.eternal.setdefault("max-pxcor", 36)
	high = engine.eternal.setdefault("max-pycor", 37)
	initworld = nx.grid_2d_graph(wide, high)
	# world wraps vertically
	for x in range(wide):
		initworld.add_edge((x, high - 1), (x, 0))
	# world wraps horizontally
	for y in range(high):
		initworld.add_edge((wide - 1, y), (0, y))

	locs = list(initworld.nodes.keys())
	shuffle(locs)

	for turtle in range(engine.eternal.setdefault("people", 60)):
		initworld.add_node("turtle" + str(turtle),
							awareness=0,
							facing=randint(0, 3),
							location=locs.pop(),
							_image_paths=[
								"atlas://rltiles/base/unknown",
								"atlas://rltiles/body/robe_black"
							])

	for center in range(engine.eternal.setdefault("centers", 20)):
		initworld.add_node(
			"center" + str(center),
			location=locs.pop(),
			nonusage=0,
			_image_paths=["atlas://rltiles/dungeon/dngn_altar_xom"])

	phys = engine.new_character("physical", initworld)
	peep = engine.new_character("people")
	lit = engine.new_character("literature")
	# there really ought to be a way to specify a character's units in its starting data
	for node in phys.thing.values():
		if node.name.startswith("turtle"):
			peep.add_unit(node)
		elif node.name.startswith("center"):
			lit.add_unit(node)

	@peep.unit.rule(always=True)
	def wander(person):
		x, y = person.location.name
		if person["facing"] == 0:
			y += 1
		elif person["facing"] == 1:
			x += 1
		elif person["facing"] == 2:
			y -= 1
		elif person["facing"] == 3:
			x -= 1
		x %= person.engine.eternal["max-pxcor"]
		y %= person.engine.eternal["max-pycor"]
		person["location"] = (x, y)
		person["facing"] = (person["facing"] + person.engine.randint(0, 1) -
							person.engine.randint(0, 1))

	@engine.function
	def has_literature(person):
		for contained in person.location.contents():
			if contained.name.startswith("flyer") or contained.name.startswith(
				"center"):
				return True
		return False

	@peep.unit.rule
	def learn(person):
		person["awareness"] = (person["awareness"] + 1) % 15
		if person["awareness"] < 5:
			image_paths = [
				"atlas://rltiles/base/unknown",
				"atlas://rltiles/body/robe_black"
			]
		elif person["awareness"] < 10:
			image_paths = [
				"atlas://rltiles/base/unknown",
				"atlas://rltiles/body/robe_green"
			]
		elif person["awareness"] < 15:
			image_paths = [
				"atlas://rltiles/base/unknown",
				"atlas://rltiles/body/robe_white_green"
			]
		else:
			image_paths = [
				"atlas://rltiles/base/unknown",
				"atlas://rltiles/body/robe_green_gold"
			]
		if person["_image_paths"] != image_paths:
			person["_image_paths"] = image_paths
		person["last_learned"] = person.engine.turn
		for contained in person.location.contents():
			if contained.name.startswith("flyer") or contained.name.startswith(
				"center"):
				contained["last_read"] = person.engine.turn

	# this would be more pleasant as something like a partial
	@learn.trigger
	def literature_here(person):
		return person.engine.function.has_literature(person)

	@peep.unit.rule
	def unlearn(person):
		person["awareness"] = max((person["awareness"] - 1, 0))

	@unlearn.trigger
	def no_literature_here(person):
		return not person.engine.function.has_literature(person)

	@peep.unit.rule
	def write(person):
		lit_ = person.engine.character["literature"]
		maxnum = 0
		for unit in lit_.units():
			if unit.name.startswith("flyer"):
				maxnum = max((int(unit.name.removeprefix("flyer")), maxnum))
		scroll = person.location.new_thing(
			f"flyer{maxnum:02}",
			nonusage=0,
			_image_paths=["atlas://rltiles/scroll/scroll-0"])
		lit_.add_unit(scroll)

	@write.trigger
	def activist(person):
		return person["awareness"] >= 15

	@peep.unit.rule
	def preach(person):
		for that in person.location.contents():
			if that != person and that.name.startswith("turtle"):
				that["awareness"] = (that["awareness"] + 1) % 15

	@preach.trigger
	def well_informed(person):
		return person["awareness"] >= 10

	@lit.unit.rule
	def disappear(ctr):
		ctr.delete()

	@disappear.trigger
	def unused(ctr):
		return ctr.get(
			"last_read", ctr.engine.turn
		) - ctr.engine.turn > ctr.engine.eternal["nonusage-limit"]


class MainGame(GameScreen):

	def on_parent(self, *args):
		if 'game' not in self.ids:
			Clock.schedule_once(self.on_parent, 0)
			return
		self.set_up()
		self.ids.game.board = GridBoard(
			character=self.engine.character['physical'])

	def set_up(self):
		"""Regenerate the whole map"""
		branch = self.engine.branch
		try:
			branchidx = int(branch.removeprefix("branch")) + 1
			branch = f"branch{branchidx:02}"
		except ValueError:
			branch = f"branch01"
		self.engine.turn = 0
		self.engine.tick = 0
		self.engine.switch_main_branch(branch)
		self.engine.game_start()
		app = GameApp.get_running_app()
		self.ids.people.value = app.engine.eternal["people"]
		self.ids.centers.value = app.engine.eternal["centers"]
		self.ids.nonusage.value = app.engine.eternal["nonusage-limit"]


class AwarenessApp(GameApp):
	play = BooleanProperty(False)
	placing_centers = BooleanProperty(False)
	inspector = True

	def on_play(self, *args):
		if self.play:
			self._scheduled = Clock.schedule_interval(self._next_turn,
														self.turn_length)
			print(self._scheduled)
		elif self._scheduled:
			Clock.unschedule(self._next_turn)
			del self._scheduled

	def _next_turn(self, *args):
		self.engine.next_turn()
		print(self.engine.turn)


kv = """
<ScreenManager>:
	MainGame:
		name: 'play'
<MainGame>:
	BoxLayout:
		orientation: 'horizontal'
		BoxLayout:
			id: sidebar
			orientation: 'vertical'
			width: 333
			size_hint_x: None
			BoxLayout:
				id: controls
				orientation: 'vertical'
				size_hint_y: 0.3
				BoxLayout:
					id: toprow
					Button:
						id: setup
						text: 'setup'
						on_release: root.set_up()
					Slider:
						id: people
						min: 0
						max: 300
						step: 1
						Label:
							text: 'people'
							x: people.x
							y: people.y
							size: self.texture_size
							size_hint: None, None
						Label:
							text: str(int(people.value))
							x: people.right - self.texture_size[0]
							y: people.y
							size: self.texture_size
							size_hint: None, None
					ToggleButton:
						text: 'place centers'
						on_release: root.placing_centers = self.state
				BoxLayout:
					id: midrow	
					ToggleButton:
						id: play
						text: 'Go'
						on_state: app.play = self.state == 'down'
					Slider:
						id: centers
						min: 0
						max: 100
						step: 1
						Label:
							text: 'centers'
							size: self.texture_size
							pos: self.parent.pos
						Label:
							text: str(int(self.parent.value))
							size: self.texture_size
							center_x: self.parent.center_x
							y: self.parent.y
					Widget:
						id: filler0
				Slider:
					id: nonusage
					min: 0
					max: 500
					step: 1
					Label:
						text: 'non-usage limit'
						size: self.texture_size
						pos: nonusage.pos
					Label:
						text: '{:d} ticks'.format(int(nonusage.value))
						size: self.texture_size
						x: nonusage.right - self.texture_size[0]
						y: nonusage.y
			Widget:
				id: filler
		Widget:
			id: gamebox
			size_hint_x: 0.7
			GridBoardView:
				id: game
				character: root.engine.character['physical'] if root.engine and 'physical' in root.engine.character else None		
				pos: gamebox.pos
				size: gamebox.size
"""

Builder.load_string(kv)

if __name__ == "__main__":
	freeze_support()
	d = mkdtemp()
	with open(d + '/game_start.py', 'w', encoding='utf-8') as outf:
		outf.write(getsource(game_start))
	AwarenessApp(prefix=d).run()
	print("Files are in " + d)