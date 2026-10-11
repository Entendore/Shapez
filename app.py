"""
shapez Local Multiplayer
Split-screen factory building game for 1-4 players on one machine.
No networking required - everything runs in a single process.

Player 1: Mouse + WASD/Arrows
Player 2: Arrow keys cursor + IJKL pan + Enter/Backspace
Player 3: Numpad 8456 cursor + Numpad 79 pan + Numpad 0/.
Player 4: TFGH cursor + YUHJ pan (future)
"""

import pygame
import sys
import math
import time
import random
import copy
import struct
import io
import wave
import os
import json
from collections import defaultdict
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, List, Any

# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS & TYPES  (inline so the file is self-contained)
# ═══════════════════════════════════════════════════════════════════════════════

TILE_SIZE = 48
TICK_RATE = 10
TICK_MS = 1000 // TICK_RATE
FPS = 60
WORLD_SIZE = 80
CONVEYOR_SPEED = 0.5
MAX_UNDO = 100
GOAL_NEED = 5
TOOLBAR_PER_PAGE = 8

class Dir(IntEnum):
    R = 0; D = 1; L = 2; U = 3
    def dx(self): return [1, 0, -1, 0][self]
    def dy(self): return [0, 1, 0, -1][self]
    def cw(self): return Dir((self + 1) % 4)

class Form(IntEnum):
    CIRCLE = 0; SQUARE = 1; TRI = 2; STAR = 3; DIAMOND = 4; HEX = 5; CROSS = 6

class Col(IntEnum):
    RED = 0; GREEN = 1; BLUE = 2; YELLOW = 3; CYAN = 4
    MAGENTA = 5; WHITE = 6; PURPLE = 7; ORANGE = 8; PINK = 9

FORM_NAME = {Form.CIRCLE:"Circle", Form.SQUARE:"Square", Form.TRI:"Triangle",
             Form.STAR:"Star", Form.DIAMOND:"Diamond", Form.HEX:"Hexagon", Form.CROSS:"Cross"}
COL_NAME = {Col.RED:"Red", Col.GREEN:"Green", Col.BLUE:"Blue", Col.YELLOW:"Yellow",
            Col.CYAN:"Cyan", Col.MAGENTA:"Magenta", Col.WHITE:"White", Col.PURPLE:"Purple",
            Col.ORANGE:"Orange", Col.PINK:"Pink"}

COL_RGB = {
    Col.RED:(220,50,50), Col.GREEN:(50,180,50), Col.BLUE:(50,80,220), Col.YELLOW:(230,210,40),
    Col.CYAN:(40,200,210), Col.MAGENTA:(200,50,200), Col.WHITE:(230,230,230), Col.PURPLE:(130,50,180),
    Col.ORANGE:(240,150,30), Col.PINK:(240,120,180),
}

class BType(IntEnum):
    CONVEYOR = 0; MINER = 1; CUTTER = 2; ROTATOR = 3
    STACKER = 4; TRASH = 5; PAINTER = 6; DELIVERY = 7
    SPLITTER = 8; MERGER = 9; BALANCER = 10; INVERTER = 11
    LAYER_SPLIT = 12; COLOR_MIX = 13; FORM_CHANGE = 14; COLOR_STRIP = 15
    COMBINER = 16; CRAFTER = 17; FILTER_FORM = 18; FILTER_COLOR = 19
    SORTER = 20; CSORTER = 21; SPEEDER = 22; STORAGE = 23
    DELAY = 24; COUNTER = 25; BOOSTER = 26; TUNNEL = 27
    SWAPPER = 28; DUPLICATOR = 29; COMPACTOR = 30; MULTI_SPLIT = 31
    COLOR_INVERT = 32; RANDOMIZER = 33; WIRE = 34; GATE_AND = 35
    GATE_OR = 36; EMITTER = 37; ABSORBER = 38; EXTRACTOR = 39
    ENRICHER = 40; STACK_SORT = 41; PALETTE = 42; LAUNCHER = 43
    TRANSFORMER = 44; RECYCLER = 45; QUEUE = 46; SELECTOR = 47

BNAME = {
    BType.CONVEYOR:"Conveyor", BType.MINER:"Miner", BType.CUTTER:"Cutter",
    BType.ROTATOR:"Rotator", BType.STACKER:"Stacker", BType.TRASH:"Trash",
    BType.PAINTER:"Painter", BType.DELIVERY:"Delivery",
    BType.SPLITTER:"Splitter", BType.MERGER:"Merger", BType.BALANCER:"Balancer",
    BType.INVERTER:"Inverter", BType.LAYER_SPLIT:"L-Split", BType.COLOR_MIX:"C-Mix",
    BType.FORM_CHANGE:"F-Change", BType.COLOR_STRIP:"C-Strip", BType.COMBINER:"Combiner",
    BType.CRAFTER:"Crafter", BType.FILTER_FORM:"F-Filter", BType.FILTER_COLOR:"C-Filter",
    BType.SORTER:"Sorter", BType.CSORTER:"C-Sorter", BType.SPEEDER:"Speeder",
    BType.STORAGE:"Storage", BType.DELAY:"Delay", BType.COUNTER:"Counter",
    BType.BOOSTER:"Booster", BType.TUNNEL:"Tunnel",
    BType.SWAPPER:"Swapper", BType.DUPLICATOR:"Duplicator", BType.COMPACTOR:"Compactor",
    BType.MULTI_SPLIT:"M-Split", BType.COLOR_INVERT:"C-Inv", BType.RANDOMIZER:"Random",
    BType.WIRE:"Wire", BType.GATE_AND:"And-Gate", BType.GATE_OR:"Or-Gate",
    BType.EMITTER:"Emitter", BType.ABSORBER:"Absorber", BType.EXTRACTOR:"Extractor",
    BType.ENRICHER:"Enricher", BType.STACK_SORT:"S-Sort", BType.PALETTE:"Palette",
    BType.LAUNCHER:"Launcher", BType.TRANSFORMER:"Transformer", BType.RECYCLER:"Recycler",
    BType.QUEUE:"Queue", BType.SELECTOR:"Selector",
}

BCOLORS = {
    BType.CONVEYOR:(70,72,82), BType.MINER:(50,120,60), BType.CUTTER:(220,120,40),
    BType.ROTATOR:(40,180,220), BType.STACKER:(180,60,200), BType.TRASH:(180,50,50),
    BType.PAINTER:(200,150,60), BType.DELIVERY:(200,180,40),
    BType.SPLITTER:(100,160,100), BType.MERGER:(80,120,180), BType.BALANCER:(180,160,50),
    BType.INVERTER:(140,100,180), BType.LAYER_SPLIT:(180,100,140), BType.COLOR_MIX:(200,120,160),
    BType.FORM_CHANGE:(120,180,120), BType.COLOR_STRIP:(160,160,160), BType.COMBINER:(160,120,200),
    BType.CRAFTER:(180,140,80), BType.FILTER_FORM:(100,180,180), BType.FILTER_COLOR:(180,100,100),
    BType.SORTER:(120,160,120), BType.CSORTER:(160,120,120), BType.SPEEDER:(100,100,160),
    BType.STORAGE:(140,120,80), BType.DELAY:(120,120,140), BType.COUNTER:(160,160,100),
    BType.BOOSTER:(100,200,100), BType.TUNNEL:(80,80,160),
    BType.SWAPPER:(160,130,200), BType.DUPLICATOR:(130,160,200), BType.COMPACTOR:(200,130,130),
    BType.MULTI_SPLIT:(200,180,130), BType.COLOR_INVERT:(180,130,180), BType.RANDOMIZER:(200,200,130),
    BType.WIRE:(130,130,200), BType.GATE_AND:(130,180,130), BType.GATE_OR:(180,180,130),
    BType.EMITTER:(200,150,100), BType.ABSORBER:(200,100,100), BType.EXTRACTOR:(150,200,150),
    BType.ENRICHER:(180,150,200), BType.STACK_SORT:(150,200,200), BType.PALETTE:(200,170,170),
    BType.LAUNCHER:(200,160,80), BType.TRANSFORMER:(160,200,160), BType.RECYCLER:(130,160,130),
    BType.QUEUE:(160,140,120), BType.SELECTOR:(140,160,180),
}

BTOOLS = [BType.CONVEYOR, BType.MINER, BType.CUTTER, BType.ROTATOR,
          BType.STACKER, BType.TRASH, BType.PAINTER, BType.DELIVERY,
          BType.SPLITTER, BType.MERGER, BType.BALANCER, BType.INVERTER,
          BType.LAYER_SPLIT, BType.COLOR_MIX, BType.FORM_CHANGE, BType.COLOR_STRIP,
          BType.COMBINER, BType.CRAFTER, BType.FILTER_FORM, BType.FILTER_COLOR,
          BType.SORTER, BType.CSORTER, BType.SPEEDER, BType.STORAGE,
          BType.DELAY, BType.COUNTER, BType.BOOSTER, BType.TUNNEL,
          BType.SWAPPER, BType.DUPLICATOR, BType.COMPACTOR, BType.MULTI_SPLIT,
          BType.COLOR_INVERT, BType.RANDOMIZER, BType.WIRE, BType.GATE_AND,
          BType.GATE_OR, BType.EMITTER, BType.ABSORBER, BType.EXTRACTOR,
          BType.ENRICHER, BType.STACK_SORT, BType.PALETTE, BType.LAUNCHER,
          BType.TRANSFORMER, BType.RECYCLER, BType.QUEUE, BType.SELECTOR]

TOOLBAR_LABELS = {
    BType.CONVEYOR:"Con", BType.MINER:"Min", BType.CUTTER:"Cut", BType.ROTATOR:"Rot",
    BType.STACKER:"Stk", BType.TRASH:"Del", BType.PAINTER:"Pnt", BType.DELIVERY:"Dlv",
    BType.SPLITTER:"Spl", BType.MERGER:"Mrg", BType.BALANCER:"Bal", BType.INVERTER:"Inv",
    BType.LAYER_SPLIT:"LSp", BType.COLOR_MIX:"CMx", BType.FORM_CHANGE:"FCh", BType.COLOR_STRIP:"CSt",
    BType.COMBINER:"Cmb", BType.CRAFTER:"Crf", BType.FILTER_FORM:"FFi", BType.FILTER_COLOR:"CFi",
    BType.SORTER:"Srt", BType.CSORTER:"CSr", BType.SPEEDER:"Spd", BType.STORAGE:"Sto",
    BType.DELAY:"Dly", BType.COUNTER:"Cnt", BType.BOOSTER:"Bst", BType.TUNNEL:"Tnl",
    BType.SWAPPER:"Swp", BType.DUPLICATOR:"Dup", BType.COMPACTOR:"Cmp",
    BType.MULTI_SPLIT:"MSp", BType.COLOR_INVERT:"CIn", BType.RANDOMIZER:"Rnd",
    BType.WIRE:"Wir", BType.GATE_AND:"And", BType.GATE_OR:"OrG",
    BType.EMITTER:"Emt", BType.ABSORBER:"Abs", BType.EXTRACTOR:"Ext",
    BType.ENRICHER:"Enr", BType.STACK_SORT:"SSr", BType.PALETTE:"Pal",
    BType.LAUNCHER:"Lnc", BType.TRANSFORMER:"Trf", BType.RECYCLER:"Rcy",
    BType.QUEUE:"Que", BType.SELECTOR:"Sel",
}

P_COLORS = [(66,135,245),(245,166,35),(77,208,115),(225,73,73)]
P_NAMES = ["P1","P2","P3","P4"]

WARM = {Col.RED, Col.ORANGE, Col.YELLOW, Col.PINK}
COOL = {Col.BLUE, Col.GREEN, Col.CYAN, Col.PURPLE}

# ═══════════════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Shape:
    tf: Form = Form.CIRCLE; tc: Col = Col.RED
    bf: Optional[Form] = None; bc: Optional[Col] = None
    def layered(self): return self.bf is not None
    def key(self): return (self.tf, self.tc, self.bf, self.bc)
    def __hash__(self): return hash(self.key())
    def __eq__(self, o):
        return isinstance(o, Shape) and self.key() == o.key()
    def label(self):
        parts = []
        if self.bf is not None: parts.append(f"{COL_NAME.get(self.bc,'?')} {FORM_NAME.get(self.bf,'?')}")
        parts.append(f"{COL_NAME.get(self.tc,'?')} {FORM_NAME.get(self.tf,'?')}")
        return " + ".join(parts)

@dataclass
class Building:
    bt: BType; x: int; y: int; d: Dir = Dir.R
    prod: Optional[Shape] = None; pcol: Optional[Col] = None
    target_form: Optional[Form] = None
    recipe_in: Optional[Shape] = None
    recipe_out: Optional[Shape] = None

@dataclass
class BeltShape:
    shape: Shape; x: float; y: float; uid: int = 0

@dataclass
class ResourceNode:
    x: int; y: int; shape: Shape; mined: bool = False

@dataclass
class Goal:
    gid: int; shape: Shape; req: int = GOAL_NEED
    done: int = 0; completed: bool = False; pts: int = 100

@dataclass
class Particle:
    x: float; y: float; vx: float; vy: float
    color: Tuple[int,int,int]; life: float; ml: float = 1.0; sz: int = 3

@dataclass
class EventMsg:
    text: str; color: Tuple[int,int,int] = (220,220,220); time: float = 0

# ═══════════════════════════════════════════════════════════════════════════════
#  WORLD GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def gen_resources(seed=42, count=75):
    rng = random.Random(seed)
    nodes = []
    forms, colors = list(Form), list(Col)
    for _ in range(count * 3):
        if len(nodes) >= count: break
        x = rng.randint(-WORLD_SIZE+5, WORLD_SIZE-5)
        y = rng.randint(-WORLD_SIZE+5, WORLD_SIZE-5)
        if any(abs(n.x-x) < 4 and abs(n.y-y) < 4 for n in nodes): continue
        nodes.append(ResourceNode(x, y, Shape(
            tf=forms[rng.randint(0,len(forms)-1)],
            tc=colors[rng.randint(0,len(colors)-1)])))
    return nodes

def gen_goals(seed=42, count=5):
    rng = random.Random(seed+999)
    forms, colors = list(Form), list(Col)
    goals = []
    for i in range(count):
        diff = i // 2
        s = Shape(tf=forms[rng.randint(0,min(len(forms)-1,2+diff))],
                  tc=colors[rng.randint(0,min(len(colors)-1,3+diff))])
        if diff >= 2 and rng.random() < 0.5:
            s.bf = forms[rng.randint(0,len(forms)-1)]
            s.bc = colors[rng.randint(0,len(colors)-1)]
        goals.append(Goal(gid=i, shape=s, req=GOAL_NEED+diff*2, pts=100+diff*50))
    return goals

# ═══════════════════════════════════════════════════════════════════════════════
#  LOCAL GAME STATE  (shared world, no networking)
# ═══════════════════════════════════════════════════════════════════════════════

class World:
    def __init__(self):
        self.buildings: Dict[Tuple[int,int], Building] = {}
        self.shapes: List[BeltShape] = []
        self.resources = gen_resources()
        self.rmap: Dict[Tuple[int,int], ResourceNode] = {(n.x,n.y):n for n in self.resources}
        self.goals = gen_goals()
        self.next_gid = len(self.goals)
        self.next_uid = 1
        self.miner_cd: Dict[Tuple[int,int], int] = {}
        self.bextra: Dict[Tuple[int,int], dict] = {}
        self.trash = 0
        self.produced = 0
        self.stats: Dict[str, int] = defaultdict(int)
        self.events: List[EventMsg] = []
        self.tick_n = 0

    def _uid(self):
        u = self.next_uid; self.next_uid += 1; return u

    def place(self, bt, x, y, d, pid, pcol=None, target_form=None, recipe_in=None, recipe_out=None):
        if abs(x) >= WORLD_SIZE or abs(y) >= WORLD_SIZE: return False
        if (x,y) in self.buildings: return False
        if bt == BType.MINER:
            n = self.rmap.get((x,y))
            if not n or n.mined: return False
            n.mined = True
            b = Building(bt, x, y, d, prod=Shape(n.shape.tf, n.shape.tc))
        elif bt == BType.PAINTER:
            b = Building(bt, x, y, d, pcol=pcol or Col.RED)
        elif bt == BType.FILTER_FORM:
            b = Building(bt, x, y, d, target_form=target_form or Form.CIRCLE)
        elif bt == BType.FORM_CHANGE:
            b = Building(bt, x, y, d, target_form=target_form or Form.SQUARE)
        elif bt == BType.CRAFTER:
            b = Building(bt, x, y, d,
                         recipe_in=recipe_in or Shape(Form.CIRCLE, Col.RED),
                         recipe_out=recipe_out or Shape(Form.SQUARE, Col.BLUE))
        elif bt == BType.FILTER_COLOR:
            b = Building(bt, x, y, d, pcol=pcol or Col.RED)
        elif bt == BType.EMITTER:
            forms, colors = list(Form), list(Col)
            b = Building(bt, x, y, d, prod=Shape(forms[random.randint(0, len(forms) - 1)],
                                                   colors[random.randint(0, len(colors) - 1)]))
        else:
            b = Building(bt, x, y, d)
        self.buildings[(x,y)] = b
        return True

    def remove(self, x, y, pid):
        b = self.buildings.pop((x,y), None)
        if not b: return None
        if b.bt == BType.MINER:
            n = self.rmap.get((x,y))
            if n: n.mined = False
        self.shapes = [s for s in self.shapes if int(round(s.x))!=x or int(round(s.y))!=y]
        self.miner_cd.pop((x,y), None)
        self.bextra.pop((x,y), None)
        return b

    def rotate(self, x, y):
        b = self.buildings.get((x,y))
        if b: b.d = b.d.cw(); return True
        return False

    def event(self, text, color=(200,200,200)):
        self.events.append(EventMsg(text, color, time.time()))
        if len(self.events) > 50: self.events.pop(0)

    # ── Simulation ──────────────────────────────────────────────────────────

    def tick(self):
        self._mine()
        self._move()
        self._process()
        self.tick_n += 1
        if self.tick_n % 100 == 0:
            done = sum(1 for g in self.goals if g.completed)
            if done >= len(self.goals) - 1:
                self._new_goal()

    def _mine(self):
        for key, b in list(self.buildings.items()):
            if b.bt == BType.EMITTER:
                boosted = False
                for (bx, by), bb in self.buildings.items():
                    if bb.bt == BType.BOOSTER and abs(bx - b.x) <= 3 and abs(by - b.y) <= 3:
                        boosted = True; break
                cd = self.miner_cd.get(key, 0)
                self.miner_cd[key] = max(0, cd - 1)
                if self.miner_cd[key] > 0: continue
                ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
                if self._occ(ox, oy): continue
                if b.prod:
                    self.shapes.append(BeltShape(Shape(b.prod.tf, b.prod.tc), float(ox), float(oy), self._uid()))
                else:
                    forms, colors = list(Form), list(Col)
                    rs = Shape(forms[random.randint(0, len(forms) - 1)], colors[random.randint(0, len(colors) - 1)])
                    self.shapes.append(BeltShape(rs, float(ox), float(oy), self._uid()))
                self.miner_cd[key] = 3 if boosted else 6
                continue
            if b.bt != BType.MINER: continue
            # Check for nearby BOOSTER
            boosted = False
            for (bx, by), bb in self.buildings.items():
                if bb.bt == BType.BOOSTER and abs(bx - b.x) <= 3 and abs(by - b.y) <= 3:
                    boosted = True; break
            cd = self.miner_cd.get(key, 0)
            self.miner_cd[key] = max(0, cd - 1)
            if self.miner_cd[key] > 0:
                continue
            ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
            if self._occ(ox, oy): continue
            self.shapes.append(BeltShape(Shape(b.prod.tf, b.prod.tc), float(ox), float(oy), self._uid()))
            self.miner_cd[key] = 4 if boosted else 8

    def _occ(self, x, y):
        return any(int(round(s.x))==x and int(round(s.y))==y for s in self.shapes)

    def _at(self, x, y):
        return [s for s in self.shapes if int(round(s.x))==x and int(round(s.y))==y]

    def _move(self):
        OK = (BType.CONVEYOR, BType.MINER, BType.CUTTER, BType.ROTATOR, BType.STACKER,
              BType.TRASH, BType.PAINTER, BType.DELIVERY,
              BType.SPLITTER, BType.MERGER, BType.BALANCER, BType.INVERTER,
              BType.LAYER_SPLIT, BType.COLOR_MIX, BType.FORM_CHANGE, BType.COLOR_STRIP,
              BType.COMBINER, BType.CRAFTER, BType.FILTER_FORM, BType.FILTER_COLOR,
              BType.SORTER, BType.CSORTER, BType.SPEEDER, BType.STORAGE,
              BType.DELAY, BType.COUNTER, BType.BOOSTER, BType.TUNNEL,
              BType.SWAPPER, BType.DUPLICATOR, BType.COMPACTOR, BType.MULTI_SPLIT,
              BType.COLOR_INVERT, BType.RANDOMIZER, BType.WIRE, BType.GATE_AND,
              BType.GATE_OR, BType.EMITTER, BType.ABSORBER, BType.EXTRACTOR,
              BType.ENRICHER, BType.STACK_SORT, BType.PALETTE, BType.LAUNCHER,
              BType.TRANSFORMER, BType.RECYCLER, BType.QUEUE, BType.SELECTOR)
        def sk(s):
            b = self.buildings.get((int(round(s.x)), int(round(s.y))))
            d = b.d if b else Dir.R
            return -(s.x*d.dx() + s.y*d.dy())
        for bs in sorted(self.shapes, key=sk):
            ix, iy = int(round(bs.x)), int(round(bs.y))
            b = self.buildings.get((ix, iy))
            if not b or b.bt in (BType.CONVEYOR, BType.SPEEDER, BType.BOOSTER, BType.WIRE):
                dr = b.d if b else None
                if dr is None: continue
                if b and b.bt == BType.WIRE:
                    spd = CONVEYOR_SPEED * 3
                elif b and b.bt == BType.SPEEDER:
                    spd = CONVEYOR_SPEED * 2
                else:
                    spd = CONVEYOR_SPEED
                nx = bs.x + dr.dx() * spd
                ny = bs.y + dr.dy() * spd
                nix, niy = int(round(nx)), int(round(ny))
                if (nix, niy) != (ix, iy):
                    dst = self.buildings.get((nix, niy))
                    if dst and dst.bt not in OK: continue
                    if self._occ(nix, niy): continue
                bs.x, bs.y = nx, ny
        self.shapes = [s for s in self.shapes if abs(s.x) < WORLD_SIZE and abs(s.y) < WORLD_SIZE]

    def _process(self):
        for key, b in list(self.buildings.items()):
            if b.bt == BType.ROTATOR: self._proc_rot(b)
            elif b.bt == BType.CUTTER: self._proc_cut(b)
            elif b.bt == BType.STACKER: self._proc_stk(b)
            elif b.bt == BType.TRASH: self._proc_trash(b)
            elif b.bt == BType.PAINTER: self._proc_paint(b)
            elif b.bt == BType.DELIVERY: self._proc_deliver(b)
            elif b.bt == BType.SPLITTER: self._proc_splitter(b)
            elif b.bt == BType.MERGER: self._proc_merger(b)
            elif b.bt == BType.BALANCER: self._proc_balancer(b)
            elif b.bt == BType.INVERTER: self._proc_inverter(b)
            elif b.bt == BType.LAYER_SPLIT: self._proc_layer_split(b)
            elif b.bt == BType.COLOR_MIX: self._proc_color_mix(b)
            elif b.bt == BType.FORM_CHANGE: self._proc_form_change(b)
            elif b.bt == BType.COLOR_STRIP: self._proc_color_strip(b)
            elif b.bt == BType.COMBINER: self._proc_combiner(b)
            elif b.bt == BType.CRAFTER: self._proc_crafter(b)
            elif b.bt == BType.FILTER_FORM: self._proc_filter_form(b)
            elif b.bt == BType.FILTER_COLOR: self._proc_filter_color(b)
            elif b.bt == BType.SORTER: self._proc_sorter(b)
            elif b.bt == BType.CSORTER: self._proc_csorter(b)
            elif b.bt == BType.STORAGE: self._proc_storage(b)
            elif b.bt == BType.DELAY: self._proc_delay(b)
            elif b.bt == BType.COUNTER: self._proc_counter(b)
            elif b.bt == BType.TUNNEL: self._proc_tunnel(b)
            elif b.bt == BType.SWAPPER: self._proc_swapper(b)
            elif b.bt == BType.DUPLICATOR: self._proc_duplicator(b)
            elif b.bt == BType.COMPACTOR: self._proc_compactor(b)
            elif b.bt == BType.MULTI_SPLIT: self._proc_multi_split(b)
            elif b.bt == BType.COLOR_INVERT: self._proc_color_invert(b)
            elif b.bt == BType.RANDOMIZER: self._proc_randomizer(b)
            elif b.bt == BType.GATE_AND: self._proc_gate_and(b)
            elif b.bt == BType.GATE_OR: self._proc_gate_or(b)
            elif b.bt == BType.ABSORBER: self._proc_absorber(b)
            elif b.bt == BType.EXTRACTOR: self._proc_extractor(b)
            elif b.bt == BType.ENRICHER: self._proc_enricher(b)
            elif b.bt == BType.STACK_SORT: self._proc_stack_sort(b)
            elif b.bt == BType.PALETTE: self._proc_palette(b)
            elif b.bt == BType.LAUNCHER: self._proc_launcher(b)
            elif b.bt == BType.TRANSFORMER: self._proc_transformer(b)
            elif b.bt == BType.RECYCLER: self._proc_recycler(b)
            elif b.bt == BType.QUEUE: self._proc_queue(b)
            elif b.bt == BType.SELECTOR: self._proc_selector(b)
            # BOOSTER has no shape processing — passive effect only

    def _eject(self, bs, b):
        ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            bs.x, bs.y = float(ox), float(oy)

    def _eject_to(self, shape, dx, dy):
        """Eject a new BeltShape to (dx, dy) if free and enterable."""
        if not self._occ(dx, dy) and self._can_enter(dx, dy):
            self.shapes.append(BeltShape(shape, float(dx), float(dy), self._uid()))

    def _can_enter(self, x, y):
        b = self.buildings.get((x, y))
        if b is None: return True
        return b.bt in (BType.CONVEYOR, BType.MINER, BType.CUTTER, BType.ROTATOR,
                        BType.STACKER, BType.TRASH, BType.PAINTER, BType.DELIVERY,
                        BType.SPLITTER, BType.MERGER, BType.BALANCER, BType.INVERTER,
                        BType.LAYER_SPLIT, BType.COLOR_MIX, BType.FORM_CHANGE, BType.COLOR_STRIP,
                        BType.COMBINER, BType.CRAFTER, BType.FILTER_FORM, BType.FILTER_COLOR,
                        BType.SORTER, BType.CSORTER, BType.SPEEDER, BType.STORAGE,
                        BType.DELAY, BType.COUNTER, BType.BOOSTER, BType.TUNNEL,
                        BType.SWAPPER, BType.DUPLICATOR, BType.COMPACTOR, BType.MULTI_SPLIT,
                        BType.COLOR_INVERT, BType.RANDOMIZER, BType.WIRE, BType.GATE_AND,
                        BType.GATE_OR, BType.EMITTER, BType.ABSORBER, BType.EXTRACTOR,
                        BType.ENRICHER, BType.STACK_SORT, BType.PALETTE, BType.LAUNCHER,
                        BType.TRANSFORMER, BType.RECYCLER, BType.QUEUE, BType.SELECTOR)

    # ── All 28 processor methods ────────────────────────────────────────────

    def _proc_rot(self, b):
        """Cycles the shape's form to the next one."""
        sh = self._at(b.x, b.y)
        if not sh: return
        forms = list(Form)
        sh[0].shape.tf = forms[(forms.index(sh[0].shape.tf) + 1) % len(forms)]
        self._eject(sh[0], b)

    def _proc_cut(self, b):
        """Removes shape, outputs 2 halves (different forms) forward + right-side."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        h1 = Shape(o.tf, o.tc)
        forms = list(Form)
        h2 = Shape(forms[(forms.index(o.tf)+2) % len(forms)], o.tc)
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd, side = Dir(b.d), Dir((b.d+1)%4)
        ox, oy = b.x+fwd.dx(), b.y+fwd.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(h1, float(ox), float(oy), self._uid()))
        ox2, oy2 = b.x+side.dx(), b.y+side.dy()
        if not self._occ(ox2, oy2) and self._can_enter(ox2, oy2):
            self.shapes.append(BeltShape(h2, float(ox2), float(oy2), self._uid()))

    def _proc_stk(self, b):
        """Takes 2 inputs, outputs combined (layered) shape forward."""
        sh = self._at(b.x, b.y)
        if len(sh) < 2: return
        c = Shape(sh[0].shape.tf, sh[0].shape.tc, sh[1].shape.tf, sh[1].shape.bc)
        for s in sh[:2]:
            if s in self.shapes: self.shapes.remove(s)
        ox, oy = b.x+b.d.dx(), b.y+b.d.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(c, float(ox), float(oy), self._uid()))

    def _proc_trash(self, b):
        """Destroys shape."""
        for s in self._at(b.x, b.y):
            if s in self.shapes: self.shapes.remove(s); self.trash += 1

    def _proc_paint(self, b):
        """Changes top_color (and bottom if present) to building's pcol."""
        sh = self._at(b.x, b.y)
        if not sh: return
        if b.pcol is not None:
            sh[0].shape.tc = b.pcol
            if sh[0].shape.bc is not None: sh[0].shape.bc = b.pcol
        self._eject(sh[0], b)

    def _proc_deliver(self, b):
        """Accepts shape, checks against goals, awards points."""
        sh = self._at(b.x, b.y)
        if not sh: return
        s = sh[0]
        if s in self.shapes: self.shapes.remove(s)
        for g in self.goals:
            if g.completed: continue
            if s.shape == g.shape:
                g.done += 1
                self.stats[s.shape.label()] += 1
                self.produced += 1
                if g.done >= g.req:
                    g.completed = True
                    self.event(f"GOAL COMPLETE: {g.shape.label()}!", (255,220,50))
                return

    def _proc_splitter(self, b):
        """Takes 1 shape, outputs 2 identical copies (forward + side)."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        c1 = Shape(o.tf, o.tc, o.bf, o.bc)
        c2 = Shape(o.tf, o.tc, o.bf, o.bc)
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(c1, float(ox), float(oy), self._uid()))
        ox2, oy2 = b.x + side.dx(), b.y + side.dy()
        if not self._occ(ox2, oy2) and self._can_enter(ox2, oy2):
            self.shapes.append(BeltShape(c2, float(ox2), float(oy2), self._uid()))

    def _proc_merger(self, b):
        """Takes 2 inputs, outputs first one forward."""
        sh = self._at(b.x, b.y)
        if len(sh) < 1: return
        o = sh[0].shape
        out = Shape(o.tf, o.tc, o.bf, o.bc)
        for s in sh[:min(2, len(sh))]:
            if s in self.shapes: self.shapes.remove(s)
        ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(out, float(ox), float(oy), self._uid()))

    def _proc_balancer(self, b):
        """Alternating: each shape goes forward or side alternately."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        out = Shape(o.tf, o.tc, o.bf, o.bc)
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        key = (b.x, b.y)
        ex = self.bextra.setdefault(key, {"toggle": False})
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        if ex["toggle"]:
            ox, oy = b.x + side.dx(), b.y + side.dy()
            ex["toggle"] = False
        else:
            ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
            ex["toggle"] = True
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(out, float(ox), float(oy), self._uid()))

    def _proc_inverter(self, b):
        """Swaps top/bottom layers of a layered shape."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if o.bf is not None:
            sh[0].shape = Shape(o.bf, o.bc if o.bc else o.tc, o.tf, o.tc)
        self._eject(sh[0], b)

    def _proc_layer_split(self, b):
        """Splits layered shape into two: top layer forward, bottom layer side.
        Unlayered shapes pass through forward unchanged."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        if o.bf is not None:
            top = Shape(o.tf, o.tc)
            bot = Shape(o.bf, o.bc if o.bc else o.tc)
            ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
            if not self._occ(ox, oy) and self._can_enter(ox, oy):
                self.shapes.append(BeltShape(top, float(ox), float(oy), self._uid()))
            ox2, oy2 = b.x + side.dx(), b.y + side.dy()
            if not self._occ(ox2, oy2) and self._can_enter(ox2, oy2):
                self.shapes.append(BeltShape(bot, float(ox2), float(oy2), self._uid()))
        else:
            # Unlayered: pass through forward
            ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
            if not self._occ(ox, oy) and self._can_enter(ox, oy):
                self.shapes.append(BeltShape(Shape(o.tf, o.tc), float(ox), float(oy), self._uid()))
            else:
                # Can't eject, put back on the tile
                self.shapes.append(BeltShape(Shape(o.tf, o.tc), float(b.x), float(b.y), self._uid()))

    def _nearest_col(self, r, g, bl):
        """Find nearest Col to given RGB by Euclidean distance."""
        best = Col.WHITE
        best_d = 999999
        for c in Col:
            cr, cg, cb = COL_RGB[c]
            d = (r - cr)**2 + (g - cg)**2 + (bl - cb)**2
            if d < best_d:
                best_d = d; best = c
        return best

    def _proc_color_mix(self, b):
        """Takes 2 inputs, outputs 1 with mixed color. Form from first shape."""
        sh = self._at(b.x, b.y)
        if len(sh) < 2: return
        s1, s2 = sh[0].shape, sh[1].shape
        c1 = COL_RGB.get(s1.tc, (200, 200, 200))
        c2 = COL_RGB.get(s2.tc, (200, 200, 200))
        mr = (c1[0] + c2[0]) // 2
        mg = (c1[1] + c2[1]) // 2
        mb = (c1[2] + c2[2]) // 2
        mixed = self._nearest_col(mr, mg, mb)
        out = Shape(s1.tf, mixed, s1.bf, s1.bc)
        for s in sh[:2]:
            if s in self.shapes: self.shapes.remove(s)
        ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(out, float(ox), float(oy), self._uid()))

    def _proc_form_change(self, b):
        """Changes shape's form to the building's target_form."""
        sh = self._at(b.x, b.y)
        if not sh: return
        if b.target_form is not None:
            sh[0].shape.tf = b.target_form
        self._eject(sh[0], b)

    def _proc_color_strip(self, b):
        """Removes color from shape, makes it WHITE."""
        sh = self._at(b.x, b.y)
        if not sh: return
        sh[0].shape.tc = Col.WHITE
        if sh[0].shape.bc is not None:
            sh[0].shape.bc = Col.WHITE
        self._eject(sh[0], b)

    def _proc_combiner(self, b):
        """Takes 2 inputs, outputs 1: form from first, color from second, bottom layer from second."""
        sh = self._at(b.x, b.y)
        if len(sh) < 2: return
        s1, s2 = sh[0].shape, sh[1].shape
        out = Shape(s1.tf, s2.tc, s2.bf, s2.bc)
        for s in sh[:2]:
            if s in self.shapes: self.shapes.remove(s)
        ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(out, float(ox), float(oy), self._uid()))

    def _proc_crafter(self, b):
        """If input matches recipe_in, transform to recipe_out. Otherwise pass through."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if b.recipe_in is not None and o == b.recipe_in and b.recipe_out is not None:
            ro = b.recipe_out
            sh[0].shape = Shape(ro.tf, ro.tc, ro.bf, ro.bc)
        self._eject(sh[0], b)

    def _proc_filter_form(self, b):
        """Passes shapes matching target_form forward, others go to side output."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        if b.target_form is not None and o.tf == b.target_form:
            ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
        else:
            ox, oy = b.x + side.dx(), b.y + side.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(o, float(ox), float(oy), self._uid()))

    def _proc_filter_color(self, b):
        """Passes shapes matching pcol top_color forward, others go to side output."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        if b.pcol is not None and o.tc == b.pcol:
            ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
        else:
            ox, oy = b.x + side.dx(), b.y + side.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(o, float(ox), float(oy), self._uid()))

    def _proc_sorter(self, b):
        """Routes by form: circles/squares go forward, all others go right-side."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        if o.tf in (Form.CIRCLE, Form.SQUARE):
            ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
        else:
            ox, oy = b.x + side.dx(), b.y + side.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(o, float(ox), float(oy), self._uid()))

    def _proc_csorter(self, b):
        """Routes by color: warm colors forward, cool colors right-side."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        if o.tc in COOL:
            ox, oy = b.x + side.dx(), b.y + side.dy()
        else:
            # WARM, WHITE, MAGENTA, PINK all go forward
            ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(o, float(ox), float(oy), self._uid()))

    def _proc_storage(self, b):
        """Buffer: stores up to 4 shapes. Ejects oldest when output is free each tick."""
        key = (b.x, b.y)
        ex = self.bextra.setdefault(key, {"items": []})
        items = ex["items"]
        # First, try to eject the oldest
        if items:
            ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
            if not self._occ(ox, oy) and self._can_enter(ox, oy):
                oldest = items.pop(0)
                self.shapes.append(BeltShape(oldest, float(ox), float(oy), self._uid()))
        # Then, absorb arriving shapes
        for s in self._at(b.x, b.y):
            if len(items) < 4:
                items.append(Shape(s.shape.tf, s.shape.tc, s.shape.bf, s.shape.bc))
                if s in self.shapes: self.shapes.remove(s)

    def _proc_delay(self, b):
        """Holds shape for 5 ticks then ejects."""
        key = (b.x, b.y)
        ex = self.bextra.setdefault(key, {"timer": 0, "holding": None})
        sh = self._at(b.x, b.y)
        if ex["holding"] is None:
            # Try to grab a shape
            if sh:
                ex["holding"] = sh[0].shape
                ex["timer"] = 5
                if sh[0] in self.shapes: self.shapes.remove(sh[0])
        else:
            ex["timer"] -= 1
            if ex["timer"] <= 0:
                ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
                if not self._occ(ox, oy) and self._can_enter(ox, oy):
                    self.shapes.append(BeltShape(ex["holding"], float(ox), float(oy), self._uid()))
                else:
                    # Can't eject yet, keep holding but reset timer
                    ex["timer"] = 1
                    return
                ex["holding"] = None

    def _proc_counter(self, b):
        """Counts shapes passing through. Just passes shapes through."""
        sh = self._at(b.x, b.y)
        if not sh: return
        key = (b.x, b.y)
        ex = self.bextra.setdefault(key, {"count": 0})
        ex["count"] += 1
        self._eject(sh[0], b)

    def _proc_tunnel(self, b):
        """Teleports shape to the nearest other TUNNEL in the building's direction (up to 20 tiles)."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        # Search for nearest tunnel in building's direction
        dx, dy = b.d.dx(), b.d.dy()
        found = None
        for dist in range(1, 21):
            tx, ty = b.x + dx * dist, b.y + dy * dist
            tb = self.buildings.get((tx, ty))
            if tb and tb.bt == BType.TUNNEL and (tx, ty) != (b.x, b.y):
                found = tb
                break
        if found:
            # Eject to the tunnel's output tile
            if sh[0] in self.shapes: self.shapes.remove(sh[0])
            ox, oy = found.x + found.d.dx(), found.y + found.d.dy()
            if not self._occ(ox, oy) and self._can_enter(ox, oy):
                self.shapes.append(BeltShape(o, float(ox), float(oy), self._uid()))
            else:
                # Put it on the tunnel tile itself
                self.shapes.append(BeltShape(o, float(found.x), float(found.y), self._uid()))
        else:
            # No partner tunnel, just pass through
            self._eject(sh[0], b)


    def _proc_swapper(self, b):
        """Takes 2 inputs, outputs them swapped: first->side, second->fwd."""
        sh = self._at(b.x, b.y)
        if len(sh) < 2: return
        s1, s2 = sh[0].shape, sh[1].shape
        for s in sh[:2]:
            if s in self.shapes: self.shapes.remove(s)
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(s2, float(ox), float(oy), self._uid()))
        ox2, oy2 = b.x + side.dx(), b.y + side.dy()
        if not self._occ(ox2, oy2) and self._can_enter(ox2, oy2):
            self.shapes.append(BeltShape(s1, float(ox2), float(oy2), self._uid()))

    def _proc_duplicator(self, b):
        """Takes 1 shape, outputs 2 identical copies (fwd + side) with cooldown."""
        key = (b.x, b.y)
        cd = self.miner_cd.get(key, 0)
        self.miner_cd[key] = max(0, cd - 1)
        if self.miner_cd[key] > 0: return
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        c1 = Shape(o.tf, o.tc, o.bf, o.bc)
        c2 = Shape(o.tf, o.tc, o.bf, o.bc)
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(c1, float(ox), float(oy), self._uid()))
        ox2, oy2 = b.x + side.dx(), b.y + side.dy()
        if not self._occ(ox2, oy2) and self._can_enter(ox2, oy2):
            self.shapes.append(BeltShape(c2, float(ox2), float(oy2), self._uid()))
        self.miner_cd[key] = 5

    def _proc_compactor(self, b):
        """Takes 3 identical shapes, outputs 1 layered shape (different form on top)."""
        sh = self._at(b.x, b.y)
        if len(sh) < 3: return
        s = [s.shape for s in sh[:3]]
        if not all(s[0].key() == s[i].key() for i in range(1, 3)): return
        forms = list(Form)
        top_form = forms[(forms.index(s[0].tf) + 2) % len(forms)]
        out = Shape(top_form, s[0].tc, s[0].tf, s[0].tc)
        for bs in sh[:3]:
            if bs in self.shapes: self.shapes.remove(bs)
        ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(out, float(ox), float(oy), self._uid()))

    def _proc_multi_split(self, b):
        """Takes 1 shape, outputs 3 identical copies (fwd, right-side, left-side)."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd = Dir(b.d)
        side_r = Dir((b.d + 1) % 4)
        side_l = Dir((b.d + 3) % 4)
        for dr in [fwd, side_r, side_l]:
            ox, oy = b.x + dr.dx(), b.y + dr.dy()
            if not self._occ(ox, oy) and self._can_enter(ox, oy):
                self.shapes.append(BeltShape(Shape(o.tf, o.tc, o.bf, o.bc),
                                              float(ox), float(oy), self._uid()))

    def _proc_color_invert(self, b):
        """Changes color to its RGB complement (inverted)."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        rgb = COL_RGB.get(o.tc, (200, 200, 200))
        inv = (255 - rgb[0], 255 - rgb[1], 255 - rgb[2])
        sh[0].shape.tc = self._nearest_col(*inv)
        if o.bc is not None:
            rgb2 = COL_RGB.get(o.bc, (200, 200, 200))
            inv2 = (255 - rgb2[0], 255 - rgb2[1], 255 - rgb2[2])
            sh[0].shape.bc = self._nearest_col(*inv2)
        self._eject(sh[0], b)

    def _proc_randomizer(self, b):
        """Randomly changes the shape's form to a different one."""
        sh = self._at(b.x, b.y)
        if not sh: return
        forms = list(Form)
        old = sh[0].shape.tf
        new_f = old
        while new_f == old and len(forms) > 1:
            new_f = forms[random.randint(0, len(forms) - 1)]
        sh[0].shape.tf = new_f
        self._eject(sh[0], b)

    def _proc_gate_and(self, b):
        """Only outputs when 2+ shapes are present; outputs the first one."""
        sh = self._at(b.x, b.y)
        if len(sh) < 2: return
        o = sh[0].shape
        for s in sh[:2]:
            if s in self.shapes: self.shapes.remove(s)
        ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(o, float(ox), float(oy), self._uid()))

    def _proc_gate_or(self, b):
        """Passes a single shape through; if 2+ shapes present, blocks all."""
        sh = self._at(b.x, b.y)
        if not sh: return
        if len(sh) >= 2:
            for s in sh[:2]:
                if s in self.shapes: self.shapes.remove(s)
            return
        self._eject(sh[0], b)

    def _proc_absorber(self, b):
        """Destroys shape and awards 10 points."""
        sh = self._at(b.x, b.y)
        if not sh: return
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        self.produced += 1
        self.event("Shape absorbed! +10 pts", (200, 200, 100))

    def _proc_extractor(self, b):
        """Strips the top layer, outputs only the bottom layer."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if o.bf is not None:
            out = Shape(o.bf, o.bc if o.bc else o.tc)
            if sh[0] in self.shapes: self.shapes.remove(sh[0])
            ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
            if not self._occ(ox, oy) and self._can_enter(ox, oy):
                self.shapes.append(BeltShape(out, float(ox), float(oy), self._uid()))
        else:
            self._eject(sh[0], b)

    def _proc_enricher(self, b):
        """Adds a bottom layer to an unlayered shape (same form, offset color)."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if o.bf is None:
            colors = list(Col)
            bc = colors[(colors.index(o.tc) + 3) % len(colors)]
            sh[0].shape = Shape(o.tf, o.tc, o.tf, bc)
        self._eject(sh[0], b)

    def _proc_stack_sort(self, b):
        """Routes layered shapes forward, unlayered shapes to the side."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        fwd, side = Dir(b.d), Dir((b.d + 1) % 4)
        if o.bf is not None:
            ox, oy = b.x + fwd.dx(), b.y + fwd.dy()
        else:
            ox, oy = b.x + side.dx(), b.y + side.dy()
        if not self._occ(ox, oy) and self._can_enter(ox, oy):
            self.shapes.append(BeltShape(o, float(ox), float(oy), self._uid()))

    def _proc_palette(self, b):
        """Applies a cycling color sequence to passing shapes."""
        sh = self._at(b.x, b.y)
        if not sh: return
        key = (b.x, b.y)
        ex = self.bextra.setdefault(key, {"idx": 0})
        palette = [Col.RED, Col.BLUE, Col.GREEN, Col.YELLOW, Col.MAGENTA, Col.CYAN]
        sh[0].shape.tc = palette[ex["idx"] % len(palette)]
        ex["idx"] += 1
        self._eject(sh[0], b)

    def _proc_launcher(self, b):
        """Launches shape up to 3 tiles forward in the building's direction."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        if sh[0] in self.shapes: self.shapes.remove(sh[0])
        dx, dy = b.d.dx(), b.d.dy()
        landed = False
        for dist in range(3, 0, -1):
            tx, ty = b.x + dx * dist, b.y + dy * dist
            if not self._occ(tx, ty) and self._can_enter(tx, ty):
                self.shapes.append(BeltShape(o, float(tx), float(ty), self._uid()))
                landed = True
                break
        if not landed:
            if not self._occ(b.x, b.y):
                self.shapes.append(BeltShape(o, float(b.x), float(b.y), self._uid()))

    def _proc_transformer(self, b):
        """Changes both the form and color to the next in sequence."""
        sh = self._at(b.x, b.y)
        if not sh: return
        forms, colors = list(Form), list(Col)
        sh[0].shape.tf = forms[(forms.index(sh[0].shape.tf) + 1) % len(forms)]
        sh[0].shape.tc = colors[(colors.index(sh[0].shape.tc) + 1) % len(colors)]
        self._eject(sh[0], b)

    def _proc_recycler(self, b):
        """Converts any shape to a basic red circle."""
        sh = self._at(b.x, b.y)
        if not sh: return
        sh[0].shape = Shape(Form.CIRCLE, Col.RED)
        self._eject(sh[0], b)

    def _proc_queue(self, b):
        """FIFO buffer (max 8 items). Outputs oldest when output is free."""
        key = (b.x, b.y)
        ex = self.bextra.setdefault(key, {"items": []})
        items = ex["items"]
        if items:
            ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
            if not self._occ(ox, oy) and self._can_enter(ox, oy):
                oldest = items.pop(0)
                self.shapes.append(BeltShape(oldest, float(ox), float(oy), self._uid()))
        for s in self._at(b.x, b.y):
            if len(items) < 8:
                items.append(Shape(s.shape.tf, s.shape.tc, s.shape.bf, s.shape.bc))
                if s in self.shapes: self.shapes.remove(s)

    def _proc_selector(self, b):
        """Takes 2 inputs, outputs only the one matching target_form; discards other."""
        sh = self._at(b.x, b.y)
        if not sh: return
        o = sh[0].shape
        for s in sh[:min(2, len(sh))]:
            if s in self.shapes: self.shapes.remove(s)
        if b.target_form is not None and o.tf == b.target_form:
            ox, oy = b.x + b.d.dx(), b.y + b.d.dy()
            if not self._occ(ox, oy) and self._can_enter(ox, oy):
                self.shapes.append(BeltShape(o, float(ox), float(oy), self._uid()))

    def _new_goal(self):
        rng = random.Random(time.time())
        forms, colors = list(Form), list(Col)
        s = Shape(forms[rng.randint(0,len(forms)-1)], colors[rng.randint(0,len(colors)-1)])
        if rng.random() < 0.3:
            s.bf = forms[rng.randint(0,len(forms)-1)]
            s.bc = colors[rng.randint(0,len(colors)-1)]
        self.goals.append(Goal(self.next_gid, s, GOAL_NEED+len(self.goals)//3,
                               pts=100+len(self.goals)*25))
        self.next_gid += 1

    def get_state_snapshot(self):
        """Return a lightweight snapshot of world state for UI/stats display."""
        return {
            "tick": self.tick_n,
            "buildings": len(self.buildings),
            "shapes": len(self.shapes),
            "produced": self.produced,
            "trashed": self.trash,
            "goals_done": sum(1 for g in self.goals if g.completed),
            "goals_total": len(self.goals),
        }

# ═══════════════════════════════════════════════════════════════════════════════
#  PLAYER STATE  (per-player camera, selection, undo, score)
# ═══════════════════════════════════════════════════════════════════════════════

class PlayerState:
    def __init__(self, pid, name, color, has_mouse=False):
        self.pid = pid
        self.name = name
        self.color = color
        self.has_mouse = has_mouse
        # Camera
        self.cam_x = 0.0; self.cam_y = 0.0
        self.cam_zoom = 1.0; self.cam_target_zoom = 1.0
        # Cursor (world tile coords)
        self.cx = 0; self.cy = 0
        # Building selection
        self.sel_btype = BType.CONVEYOR
        self.sel_dir = Dir.R
        self.paint_col = Col.RED
        self.toolbar_page = 0
        # Undo
        self.undo_stack: list = []
        # Score
        self.score = 0; self.placed = 0; self.delivered = 0
        # Input state
        self.dragging = False; self.drag_start = (0,0); self.cam_start = (0.0,0.0)
        self.cursor_move_timer = 0
        self.held_keys: set = set()

    def push_undo(self, action):
        self.undo_stack.append(action)
        if len(self.undo_stack) > MAX_UNDO: self.undo_stack.pop(0)

    def pop_undo(self, world):
        if not self.undo_stack: return False
        a = self.undo_stack.pop()
        if a[0] == "place":
            b = a[1]
            if world.buildings.get((b.x,b.y)) == b:
                world.remove(b.x, b.y, self.pid)
            return True
        elif a[0] == "remove":
            b = a[1]
            if (b.x,b.y) not in world.buildings:
                if b.bt == BType.MINER:
                    n = world.rmap.get((b.x,b.y))
                    if n: n.mined = True
                world.buildings[(b.x,b.y)] = b
            return True
        return False

# ═══════════════════════════════════════════════════════════════════════════════
#  SOUND GENERATOR  (procedural, no audio files)
# ═══════════════════════════════════════════════════════════════════════════════

class SFX:
    def __init__(self):
        self.ok = False
        self.sounds = {}
        try:
            pygame.mixer.init(22050, -16, 1, 512)
            self.ok = True
        except: pass

    def _mk(self, samples, vol=0.3):
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            d = b''.join(struct.pack('<h', max(-32767,min(32767,int(s*32767*vol)))) for s in samples)
            w.writeframes(d)
        buf.seek(0)
        return pygame.mixer.Sound(buf)

    def init(self):
        if not self.ok: return
        sr = 22050
        # place
        t = [i/sr for i in range(int(sr*0.05))]
        self.sounds['place'] = self._mk([math.sin(2*math.pi*800*ti)*max(0,1-ti*20) for ti in t], 0.15)
        # remove
        t = [i/sr for i in range(int(sr*0.07))]
        self.sounds['remove'] = self._mk([math.sin(2*math.pi*300*ti)*max(0,1-ti*15) for ti in t], 0.2)
        # rotate
        t = [i/sr for i in range(int(sr*0.04))]
        self.sounds['rotate'] = self._mk([math.sin(2*math.pi*1200*ti)*max(0,1-ti*25) for ti in t], 0.12)
        # error
        t = [i/sr for i in range(int(sr*0.1))]
        self.sounds['error'] = self._mk([math.sin(2*math.pi*200*ti)*0.5 for ti in t], 0.15)
        # deliver
        t = [i/sr for i in range(int(sr*0.25))]
        self.sounds['deliver'] = self._mk([math.sin(2*math.pi*(400+ti*2000)*ti)*max(0,1-ti*4)*0.5 for ti in t], 0.25)
        # goal
        t = [i/sr for i in range(int(sr*0.45))]
        self.sounds['goal'] = self._mk([math.sin(2*math.pi*(500+ti*800+math.sin(ti*30)*100)*ti)*max(0,1-ti*2.2)*0.4 for ti in t], 0.3)

    def play(self, name):
        if self.ok and name in self.sounds:
            self.sounds[name].play()

# ═══════════════════════════════════════════════════════════════════════════════
#  PARTICLES
# ═══════════════════════════════════════════════════════════════════════════════

class Particles:
    def __init__(self):
        self.ps: List[Particle] = []

    def emit(self, x, y, color, n=5, spread=2.0, life=0.6):
        for _ in range(n):
            a = random.uniform(0, 2*math.pi)
            sp = random.uniform(0.5, spread)
            self.ps.append(Particle(x, y, math.cos(a)*sp, math.sin(a)*sp,
                                    color, life, life, random.randint(2,4)))

    def update(self, dt):
        alive = []
        for p in self.ps:
            p.x += p.vx*dt; p.y += p.vy*dt; p.vy += 3*dt; p.life -= dt
            if p.life > 0: alive.append(p)
        self.ps = alive

    def draw(self, surf, cam, rect):
        """Draw particles clipped to rect."""
        ox, oy = rect.x, rect.y
        for p in self.ps:
            sx = int((p.x - cam.cam_x) * TILE_SIZE * cam.cam_zoom + rect.w / 2) + ox
            sy = int((p.y - cam.cam_y) * TILE_SIZE * cam.cam_zoom + rect.h / 2) + oy
            if not (0 <= sx < rect.right and 0 <= sy < rect.bottom): continue
            alpha = max(0, p.life / p.ml)
            r = max(1, int(p.sz * alpha))
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*p.color, int(255*alpha)), (r, r), r)
            surf.blit(s, (sx-r, sy-r))

# ═══════════════════════════════════════════════════════════════════════════════
#  RENDERER  (renders a viewport for one player)
# ═══════════════════════════════════════════════════════════════════════════════

class Viewport:
    def __init__(self, w, h):
        self.w = w; self.h = h
        self.surf = pygame.Surface((w, h))
        self.ft = pygame.font.SysFont("consolas", 10)
        self.fs = pygame.font.SysFont("consolas", 12)
        self.fm = pygame.font.SysFont("consolas", 14, bold=True)
        self.fl = pygame.font.SysFont("consolas", 18, bold=True)
        self.ftitle = pygame.font.SysFont("consolas", 24, bold=True)
        self.ftiny = pygame.font.SysFont("consolas", 9)
        self.t = 0.0
        # Toolbar arrow rects (set during _hud)
        self._page_left_rect = pygame.Rect(0, 0, 0, 0)
        self._page_right_rect = pygame.Rect(0, 0, 0, 0)

    def s2w(self, sx, sy, cam):
        wx = (sx - self.w/2) / (TILE_SIZE * cam.cam_zoom) + cam.cam_x
        wy = (sy - self.h/2) / (TILE_SIZE * cam.cam_zoom) + cam.cam_y
        return wx, wy

    def w2s(self, wx, wy, cam):
        sx = int((wx - cam.cam_x) * TILE_SIZE * cam.cam_zoom + self.w/2)
        sy = int((wy - cam.cam_y) * TILE_SIZE * cam.cam_zoom + self.h/2)
        return sx, sy

    def wrect(self, wx, wy, ww, wh, cam):
        sx, sy = self.w2s(wx, wy, cam)
        return pygame.Rect(sx, sy, int(ww*TILE_SIZE*cam.cam_zoom), int(wh*TILE_SIZE*cam.cam_zoom))

    def ts(self, cam):
        return max(1, int(TILE_SIZE * cam.cam_zoom))

    def on_scr(self, r):
        return r.right > -50 and r.left < self.w+50 and r.bottom > -50 and r.top < self.h+50

    def render(self, world, cam, player, all_players, particles, show_ghost=True):
        self.surf.fill((18, 20, 26))
        self._grid(cam)
        for n in world.resources:
            self._res(n, cam)
        for b in world.buildings.values():
            self._bldg(b, cam, world)
        for s in world.shapes:
            self._bshape(s, cam)
        particles.draw(self.surf, cam, pygame.Rect(0, 0, self.w, self.h))
        # Other player cursors
        for p in all_players:
            if p.pid != player.pid:
                self._cursor(p, False, cam)
        # Own cursor
        self._cursor(player, True, cam)
        # Ghost
        if show_ghost:
            self._ghost(player, cam, world)
        # HUD
        self._hud(player, cam, world)
        # Minimap
        self._minimap(world, cam, player, all_players)
        # Goals
        self._goals(world)
        # Stats
        self._stats(world)
        # Events
        self._events(world)

    def _grid(self, cam):
        ts = self.ts(cam)
        if ts < 4: return
        wx0, wy0 = self.s2w(0, 0, cam)
        wx1, wy1 = self.s2w(self.w, self.h, cam)
        x0, y0 = int(math.floor(wx0))-1, int(math.floor(wy0))-1
        x1, y1 = int(math.ceil(wx1))+1, int(math.ceil(wy1))+1
        gc, oc = (30,32,40), (55,57,68)
        for x in range(x0, x1):
            s1 = self.w2s(x, y0, cam); s2 = self.w2s(x, y1, cam)
            pygame.draw.line(self.surf, oc if x==0 else gc, s1, s2)
        for y in range(y0, y1):
            s1 = self.w2s(x0, y, cam); s2 = self.w2s(x1, y, cam)
            pygame.draw.line(self.surf, oc if y==0 else gc, s1, s2)

    def _res(self, n, cam):
        r = self.wrect(n.x-0.45, n.y-0.45, 0.9, 0.9, cam)
        if not self.on_scr(r): return
        c = COL_RGB.get(n.shape.tc, (200,200,200))
        p = 0.8+0.2*math.sin(self.t*3+n.x*0.5)
        a = int((60 if n.mined else 180)*p)
        s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(s, (*c, a), (0,0,r.w,r.h), border_radius=max(1,r.w//4))
        pygame.draw.rect(s, (*c, int((100 if n.mined else 200)*p)), (0,0,r.w,r.h),
                         width=max(1,r.w//10), border_radius=max(1,r.w//4))
        self.surf.blit(s, r.topleft)
        cx, cy = r.centerx, r.centery
        self._sicon(cx, cy, max(3, r.w//5), n.shape.tf, (*c, int(200*p)))

    def _bldg(self, b, cam, world=None):
        r = self.wrect(b.x-0.5, b.y-0.5, 1, 1, cam)
        if not self.on_scr(r): return
        ts = self.ts(cam)
        label = TOOLBAR_LABELS.get(b.bt, BNAME.get(b.bt, "?")[:3])

        if b.bt == BType.CONVEYOR:
            self._conv(r, b.d, cam)
        elif b.bt == BType.MINER:
            self._miner(r, b, cam)
        elif b.bt == BType.PAINTER:
            self._painter(r, b, cam)
        elif b.bt == BType.DELIVERY:
            self._delivery(r, b, cam)
        elif b.bt == BType.SPEEDER:
            self._speeder(r, b.d, cam)
        elif b.bt == BType.STORAGE:
            self._storage_bldg(r, b, cam, world)
        elif b.bt == BType.COUNTER:
            self._counter_bldg(r, b, cam, world)
        elif b.bt == BType.DELAY:
            self._delay_bldg(r, b, cam, world)
        elif b.bt == BType.BOOSTER:
            self._booster_bldg(r, b, cam)
        elif b.bt == BType.TUNNEL:
            self._tunnel_bldg(r, b, cam)
        elif b.bt == BType.FILTER_FORM:
            self._filter_form_bldg(r, b, cam)
        elif b.bt == BType.FILTER_COLOR:
            self._filter_color_bldg(r, b, cam)
        elif b.bt == BType.CRAFTER:
            self._crafter_bldg(r, b, cam)
        elif b.bt == BType.WIRE:
            self._wire_bldg(r, b.d, cam)
        elif b.bt == BType.EMITTER:
            self._emitter_bldg(r, b, cam)
        elif b.bt == BType.QUEUE:
            self._queue_bldg(r, b, cam, world)
        elif b.bt == BType.SELECTOR:
            self._selector_bldg(r, b, cam)
        elif b.bt == BType.PALETTE:
            self._palette_bldg(r, b, cam, world)
        else:
            self._proc_bldg(r, b, cam, BCOLORS.get(b.bt,(100,100,100)), label)

        if b.bt != BType.CONVEYOR and b.bt != BType.SPEEDER and b.bt != BType.BOOSTER and b.bt != BType.WIRE and ts > 10:
            cx, cy = r.centerx, r.centery
            al = max(3, ts//3)
            pygame.draw.line(self.surf, (200,200,200), (cx,cy),
                             (cx+b.d.dx()*al, cy+b.d.dy()*al), max(1,ts//16))

    def _conv(self, r, d, cam):
        ts = self.ts(cam)
        pygame.draw.rect(self.surf, (55,57,68), r, border_radius=max(1,ts//8))
        pygame.draw.rect(self.surf, (75,78,90), r, width=max(1,ts//24), border_radius=max(1,ts//8))
        if ts < 10: return
        cx, cy = r.centerx, r.centery; cs = max(2, ts//6); cc = (95,98,112)
        off = (self.t*3)%1.0; dx, dy = d.dx(), d.dy()
        for i in range(-1, 3):
            px = cx+int((dx*(i-off)*ts*0.3)); py = cy+int((dy*(i-off)*ts*0.3))
            if dx:
                pygame.draw.line(self.surf, cc, (px-cs//2*dx, py-cs), (px, py), max(1,ts//20))
                pygame.draw.line(self.surf, cc, (px-cs//2*dx, py+cs), (px, py), max(1,ts//20))
            else:
                pygame.draw.line(self.surf, cc, (px-cs, py-cs//2*dy), (px, py), max(1,ts//20))
                pygame.draw.line(self.surf, cc, (px+cs, py-cs//2*dy), (px, py), max(1,ts//20))

    def _speeder(self, r, d, cam):
        """Conveyor look with double chevrons for 2x speed."""
        ts = self.ts(cam)
        pygame.draw.rect(self.surf, (60,60,95), r, border_radius=max(1,ts//8))
        pygame.draw.rect(self.surf, (80,80,120), r, width=max(1,ts//24), border_radius=max(1,ts//8))
        if ts < 10: return
        cx, cy = r.centerx, r.centery; cs = max(2, ts//6)
        cc1 = (110,110,155); cc2 = (90,90,135)
        off = (self.t*6)%1.0; dx, dy = d.dx(), d.dy()
        for i in range(-1, 3):
            px = cx+int((dx*(i-off)*ts*0.3)); py = cy+int((dy*(i-off)*ts*0.3))
            if dx:
                pygame.draw.line(self.surf, cc1, (px-cs//2*dx, py-cs), (px, py), max(1,ts//20))
                pygame.draw.line(self.surf, cc1, (px-cs//2*dx, py+cs), (px, py), max(1,ts//20))
            else:
                pygame.draw.line(self.surf, cc1, (px-cs, py-cs//2*dy), (px, py), max(1,ts//20))
                pygame.draw.line(self.surf, cc1, (px+cs, py-cs//2*dy), (px, py), max(1,ts//20))
        # Second set of chevrons (double speed indicator)
        off2 = (self.t*6 + 0.5)%1.0
        for i in range(-1, 3):
            px = cx+int((dx*(i-off2)*ts*0.3)); py = cy+int((dy*(i-off2)*ts*0.3))
            if dx:
                pygame.draw.line(self.surf, cc2, (px-cs//3*dx, py-cs*2//3), (px, py), max(1,ts//22))
                pygame.draw.line(self.surf, cc2, (px-cs//3*dx, py+cs*2//3), (px, py), max(1,ts//22))
            else:
                pygame.draw.line(self.surf, cc2, (px-cs*2//3, py-cs//3*dy), (px, py), max(1,ts//22))
                pygame.draw.line(self.surf, cc2, (px+cs*2//3, py-cs//3*dy), (px, py), max(1,ts//22))

    def _miner(self, r, b, cam):
        ts = self.ts(cam)
        p = 0.85+0.15*math.sin(self.t*4)
        pygame.draw.rect(self.surf, (int(45*p),int(115*p),int(55*p)), r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, (65,160,75), r, width=max(1,ts//16), border_radius=max(1,ts//6))
        if ts > 10:
            cx, cy = r.centerx, r.centery; rad = max(3, ts//4)
            for a in range(6):
                aa = self.t*2+a*math.pi/3
                pygame.draw.line(self.surf, (200,200,100), (cx,cy),
                                 (cx+int(math.cos(aa)*rad*0.7), cy+int(math.sin(aa)*rad*0.7)), max(1,ts//14))
            pygame.draw.circle(self.surf, (200,200,100), (cx,cy), max(2,rad//3))

    def _painter(self, r, b, cam):
        ts = self.ts(cam)
        pc = COL_RGB.get(b.pcol, (200,200,200))
        pygame.draw.rect(self.surf, (pc[0]//3, pc[1]//3, pc[2]//3), r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, (min(255,pc[0]+60), min(255,pc[1]+60), min(255,pc[2]+60)),
                         r, width=max(1,ts//14), border_radius=max(1,ts//6))
        if ts > 10:
            cx, cy = r.centerx, r.centery; rad = max(3, ts//3)
            sr = rad*(0.8+0.2*math.sin(self.t*5))
            s = pygame.Surface((int(rad*2+4), int(rad*2+4)), pygame.SRCALPHA)
            pygame.draw.circle(s, (*pc, 180), (rad+2, rad+2), int(sr))
            pygame.draw.circle(s, (*pc, 255), (rad+2, rad+2), int(sr*0.5))
            self.surf.blit(s, (cx-rad-2, cy-rad-2))

    def _delivery(self, r, b, cam):
        ts = self.ts(cam)
        p = 0.8+0.2*math.sin(self.t*2.5)
        gc = (int(200*p), int(180*p), int(40*p))
        pygame.draw.rect(self.surf, gc, r, border_radius=max(1,ts//5))
        pygame.draw.rect(self.surf, (255,230,80), r, width=max(1,ts//12), border_radius=max(1,ts//5))
        if ts > 8:
            cx, cy = r.centerx, r.centery; rad = max(3, ts//4)
            pts = [(cx+math.cos(math.pi/2+i*math.pi/5)*(rad if i%2==0 else rad*0.4),
                    cy-math.sin(math.pi/2+i*math.pi/5)*(rad if i%2==0 else rad*0.4)) for i in range(10)]
            pygame.draw.polygon(self.surf, (255,240,120), pts)

    def _storage_bldg(self, r, b, cam, world):
        ts = self.ts(cam)
        count = 0
        if world:
            ex = world.bextra.get((b.x, b.y))
            if ex: count = len(ex.get("items", []))
        c = BCOLORS.get(BType.STORAGE, (140,120,80))
        pygame.draw.rect(self.surf, c, r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, tuple(min(255,x+35) for x in c), r,
                         width=max(1,ts//16), border_radius=max(1,ts//6))
        if ts > 10:
            t = self.fs.render(f"Sto", True, (255,255,255))
            self.surf.blit(t, t.get_rect(center=(r.centerx, r.centery - max(2, ts//8))))
            ct = self.ftiny.render(f"{count}/4", True, (220,220,150))
            self.surf.blit(ct, ct.get_rect(center=(r.centerx, r.centery + max(4, ts//5))))

    def _counter_bldg(self, r, b, cam, world):
        ts = self.ts(cam)
        count = 0
        if world:
            ex = world.bextra.get((b.x, b.y))
            if ex: count = ex.get("count", 0)
        c = BCOLORS.get(BType.COUNTER, (160,160,100))
        pygame.draw.rect(self.surf, c, r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, tuple(min(255,x+35) for x in c), r,
                         width=max(1,ts//16), border_radius=max(1,ts//6))
        if ts > 10:
            t = self.ftiny.render(f"Cnt:{count}", True, (255,255,255))
            self.surf.blit(t, t.get_rect(center=r.center))

    def _delay_bldg(self, r, b, cam, world):
        ts = self.ts(cam)
        timer = 0
        holding = False
        if world:
            ex = world.bextra.get((b.x, b.y))
            if ex:
                timer = ex.get("timer", 0)
                holding = ex.get("holding") is not None
        c = BCOLORS.get(BType.DELAY, (120,120,140))
        if holding:
            # Flash when holding
            p = 0.7 + 0.3 * math.sin(self.t * 8)
            c = (int(c[0]*p), int(c[1]*p), int(c[2]*p))
        pygame.draw.rect(self.surf, c, r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, tuple(min(255,x+35) for x in BCOLORS.get(BType.DELAY, (120,120,140))), r,
                         width=max(1,ts//16), border_radius=max(1,ts//6))
        if ts > 10:
            t = self.ftiny.render(f"Dly:{timer}" if holding else "Dly", True, (255,255,255))
            self.surf.blit(t, t.get_rect(center=r.center))

    def _booster_bldg(self, r, b, cam):
        ts = self.ts(cam)
        p = 0.7 + 0.3 * math.sin(self.t * 3)
        c = BCOLORS.get(BType.BOOSTER, (100,200,100))
        pygame.draw.rect(self.surf, (int(c[0]*p), int(c[1]*p), int(c[2]*p)), r, border_radius=max(1,ts//5))
        pygame.draw.rect(self.surf, c, r, width=max(1,ts//12), border_radius=max(1,ts//5))
        if ts > 10:
            cx, cy = r.centerx, r.centery; rad = max(3, ts//4)
            # Simple glow effect
            glow_r = int(rad * (1.2 + 0.3 * math.sin(self.t * 5)))
            gs = pygame.Surface((glow_r*2+4, glow_r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*c, 40), (glow_r+2, glow_r+2), glow_r)
            self.surf.blit(gs, (cx - glow_r - 2, cy - glow_r - 2))
            # Lightning bolt
            bolt = [(cx-rad*0.2, cy-rad*0.7), (cx+rad*0.3, cy-rad*0.1),
                    (cx-rad*0.05, cy-rad*0.1), (cx+rad*0.2, cy+rad*0.7),
                    (cx-rad*0.3, cy+rad*0.1), (cx+rad*0.05, cy+rad*0.1)]
            pygame.draw.polygon(self.surf, (255,255,180), bolt)

    def _tunnel_bldg(self, r, b, cam):
        ts = self.ts(cam)
        c = BCOLORS.get(BType.TUNNEL, (80,80,160))
        pygame.draw.rect(self.surf, c, r, border_radius=max(1,ts//5))
        # Portal-like effect
        if ts > 8:
            cx, cy = r.centerx, r.centery; rad = max(3, ts//3)
            # Animated rings
            for i in range(3):
                phase = (self.t * 2 + i * 0.7) % 2.0
                ring_r = int(rad * (0.3 + phase * 0.4))
                alpha = max(0, int(200 * (1.0 - phase / 2.0)))
                rs = pygame.Surface((ring_r*2+4, ring_r*2+4), pygame.SRCALPHA)
                pygame.draw.circle(rs, (120, 120, 255, alpha), (ring_r+2, ring_r+2), ring_r, max(1, ts//16))
                self.surf.blit(rs, (cx - ring_r - 2, cy - ring_r - 2))
            # Center dot
            pygame.draw.circle(self.surf, (180, 180, 255), (cx, cy), max(2, rad//4))
        pygame.draw.rect(self.surf, (100,100,200), r, width=max(1,ts//14), border_radius=max(1,ts//5))

    def _filter_form_bldg(self, r, b, cam):
        ts = self.ts(cam)
        c = BCOLORS.get(BType.FILTER_FORM, (100,180,180))
        pygame.draw.rect(self.surf, c, r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, tuple(min(255,x+35) for x in c), r,
                         width=max(1,ts//16), border_radius=max(1,ts//6))
        if ts > 10:
            fn = FORM_NAME.get(b.target_form, "???")[:3] if b.target_form is not None else "???"
            t = self.ftiny.render(f"FFi", True, (255,255,255))
            self.surf.blit(t, t.get_rect(center=(r.centerx, r.centery - max(2, ts//8))))
            t2 = self.ftiny.render(fn, True, (200,255,255))
            self.surf.blit(t2, t2.get_rect(center=(r.centerx, r.centery + max(3, ts//6))))

    def _filter_color_bldg(self, r, b, cam):
        ts = self.ts(cam)
        c = BCOLORS.get(BType.FILTER_COLOR, (180,100,100))
        pygame.draw.rect(self.surf, c, r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, tuple(min(255,x+35) for x in c), r,
                         width=max(1,ts//16), border_radius=max(1,ts//6))
        if ts > 10:
            pc = COL_RGB.get(b.pcol, (200,200,200))
            cx, cy = r.centerx, r.centery; rad = max(2, ts//5)
            s = pygame.Surface((rad*2+4, rad*2+4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*pc, 200), (rad+2, rad+2), rad)
            self.surf.blit(s, (cx-rad-2, cy-rad-2))

    def _crafter_bldg(self, r, b, cam):
        ts = self.ts(cam)
        c = BCOLORS.get(BType.CRAFTER, (180,140,80))
        pygame.draw.rect(self.surf, c, r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, tuple(min(255,x+35) for x in c), r,
                         width=max(1,ts//16), border_radius=max(1,ts//6))
        if ts > 10:
            t = self.ftiny.render("Crf", True, (255,255,255))
            self.surf.blit(t, t.get_rect(center=(r.centerx, r.centery - max(2, ts//8))))
            # Show arrow: in -> out
            if b.recipe_in and b.recipe_out:
                arr = "->"
                t2 = self.ftiny.render(arr, True, (255,220,150))
                self.surf.blit(t2, t2.get_rect(center=(r.centerx, r.centery + max(3, ts//6))))


    def _wire_bldg(self, r, d, cam):
        """Ultra-fast conveyor with triple chevrons."""
        ts = self.ts(cam)
        pygame.draw.rect(self.surf, (50, 50, 90), r, border_radius=max(1, ts // 8))
        pygame.draw.rect(self.surf, (70, 70, 130), r, width=max(1, ts // 20), border_radius=max(1, ts // 8))
        if ts < 8: return
        cx, cy = r.centerx, r.centery; cs = max(2, ts // 5)
        cc = (120, 120, 200)
        off = (self.t * 9) % 1.0; dx, dy = d.dx(), d.dy()
        for layer in range(3):
            loff = (off + layer * 0.33) % 1.0
            alpha_c = tuple(max(0, c - layer * 30) for c in cc)
            for i in range(-1, 3):
                px = cx + int((dx * (i - loff) * ts * 0.3))
                py = cy + int((dy * (i - loff) * ts * 0.3))
                if dx:
                    pygame.draw.line(self.surf, alpha_c,
                                     (px - cs // 2 * dx, py - cs), (px, py), max(1, ts // 22))
                    pygame.draw.line(self.surf, alpha_c,
                                     (px - cs // 2 * dx, py + cs), (px, py), max(1, ts // 22))
                else:
                    pygame.draw.line(self.surf, alpha_c,
                                     (px - cs, py - cs // 2 * dy), (px, py), max(1, ts // 22))
                    pygame.draw.line(self.surf, alpha_c,
                                     (px + cs, py - cs // 2 * dy), (px, py), max(1, ts // 22))

    def _emitter_bldg(self, r, b, cam):
        """Auto-generating building with pulsing glow."""
        ts = self.ts(cam)
        p = 0.7 + 0.3 * math.sin(self.t * 3)
        ec = BCOLORS.get(BType.EMITTER, (200, 150, 100))
        pygame.draw.rect(self.surf, (int(ec[0] * p), int(ec[1] * p), int(ec[2] * p)), r,
                         border_radius=max(1, ts // 5))
        pygame.draw.rect(self.surf, ec, r, width=max(1, ts // 10), border_radius=max(1, ts // 5))
        if ts > 10:
            cx, cy = r.centerx, r.centery
            for i in range(3):
                phase = (self.t * 2 + i * 0.8) % 2.0
                ring_r = int(ts * 0.15 * (0.5 + phase * 0.5))
                alpha = max(0, int(180 * (1.0 - phase / 2.0)))
                rs = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(rs, (255, 220, 150, alpha), (ring_r + 2, ring_r + 2), ring_r, max(1, ts // 20))
                self.surf.blit(rs, (cx - ring_r - 2, cy - ring_r - 2))
            t = self.ftiny.render("Emt", True, (255, 255, 255))
            self.surf.blit(t, t.get_rect(center=r.center))

    def _queue_bldg(self, r, b, cam, world):
        ts = self.ts(cam)
        count = 0
        if world:
            ex = world.bextra.get((b.x, b.y))
            if ex: count = len(ex.get("items", []))
        qc = BCOLORS.get(BType.QUEUE, (160, 140, 120))
        pygame.draw.rect(self.surf, qc, r, border_radius=max(1, ts // 6))
        pygame.draw.rect(self.surf, tuple(min(255, x + 35) for x in qc), r,
                         width=max(1, ts // 16), border_radius=max(1, ts // 6))
        if ts > 10:
            t = self.ftiny.render(f"Que:{count}/8", True, (255, 255, 255))
            self.surf.blit(t, t.get_rect(center=r.center))

    def _selector_bldg(self, r, b, cam):
        ts = self.ts(cam)
        sc = BCOLORS.get(BType.SELECTOR, (140, 160, 180))
        pygame.draw.rect(self.surf, sc, r, border_radius=max(1, ts // 6))
        pygame.draw.rect(self.surf, tuple(min(255, x + 35) for x in sc), r,
                         width=max(1, ts // 16), border_radius=max(1, ts // 6))
        if ts > 10:
            fn = FORM_NAME.get(b.target_form, "???")[:3] if b.target_form is not None else "???"
            t = self.ftiny.render(f"Sel:{fn}", True, (255, 255, 255))
            self.surf.blit(t, t.get_rect(center=r.center))

    def _palette_bldg(self, r, b, cam, world):
        ts = self.ts(cam)
        pc = BCOLORS.get(BType.PALETTE, (200, 170, 170))
        pygame.draw.rect(self.surf, pc, r, border_radius=max(1, ts // 6))
        pygame.draw.rect(self.surf, tuple(min(255, x + 35) for x in pc), r,
                         width=max(1, ts // 16), border_radius=max(1, ts // 6))
        if ts > 10:
            palette_cols = [Col.RED, Col.BLUE, Col.GREEN, Col.YELLOW, Col.MAGENTA, Col.CYAN]
            idx = 0
            if world:
                ex = world.bextra.get((b.x, b.y))
                if ex: idx = ex.get("idx", 0)
            sw = max(3, ts // 8)
            sx_start = r.centerx - len(palette_cols) * sw // 2
            cy = r.centery
            for i, pc2 in enumerate(palette_cols):
                rgb = COL_RGB.get(pc2, (200, 200, 200))
                if i == idx % len(palette_cols):
                    pygame.draw.rect(self.surf, rgb, (sx_start + i * sw, cy - sw // 2, sw - 1, sw - 1))
                else:
                    s = pygame.Surface((sw - 1, sw - 1), pygame.SRCALPHA)
                    pygame.draw.rect(s, (*rgb, 100), (0, 0, sw - 1, sw - 1))
                    self.surf.blit(s, (sx_start + i * sw, cy - sw // 2))

    def _proc_bldg(self, r, b, cam, c, label):
        """Generic building renderer for processors that don't need special visuals."""
        ts = self.ts(cam)
        pygame.draw.rect(self.surf, c, r, border_radius=max(1,ts//6))
        pygame.draw.rect(self.surf, tuple(min(255,x+35) for x in c), r,
                         width=max(1,ts//16), border_radius=max(1,ts//6))
        if ts > 10:
            t = self.fs.render(label, True, (255,255,255))
            self.surf.blit(t, t.get_rect(center=r.center))

    def _bshape(self, bs, cam):
        sx, sy = self.w2s(bs.x, bs.y, cam)
        ts = self.ts(cam)
        if not (-ts < sx < self.w+ts and -ts < sy < self.h+ts): return
        r = max(3, ts//3)
        if bs.shape.bf is not None:
            self._sicon(sx+1, sy+1, int(r*0.8), bs.shape.bf, COL_RGB.get(bs.shape.bc,(180,180,180)))
        self._sicon(sx, sy, r, bs.shape.tf, COL_RGB.get(bs.shape.tc,(220,220,220)))

    def _sicon(self, cx, cy, r, form, color):
        rgb = color[:3]; dk = tuple(max(0,c-50) for c in rgb)
        if form == Form.CIRCLE:
            pygame.draw.circle(self.surf, color, (cx,cy), r)
            pygame.draw.circle(self.surf, dk, (cx,cy), r, max(1,r//5))
        elif form == Form.SQUARE:
            rc = pygame.Rect(cx-r, cy-r, r*2, r*2)
            pygame.draw.rect(self.surf, color, rc, border_radius=max(1,r//5))
            pygame.draw.rect(self.surf, dk, rc, max(1,r//5), border_radius=max(1,r//5))
        elif form == Form.TRI:
            pts = [(cx,cy-r),(cx-r,cy+r),(cx+r,cy+r)]
            pygame.draw.polygon(self.surf, color, pts)
            pygame.draw.polygon(self.surf, dk, pts, max(1,r//5))
        elif form == Form.STAR:
            pts = [(cx+math.cos(math.pi/2+i*math.pi/5)*(r if i%2==0 else r*0.45),
                    cy-math.sin(math.pi/2+i*math.pi/5)*(r if i%2==0 else r*0.45)) for i in range(10)]
            pygame.draw.polygon(self.surf, color, pts)
            pygame.draw.polygon(self.surf, dk, pts, max(1,r//5))
        elif form == Form.DIAMOND:
            pts = [(cx,cy-r),(cx+r,cy),(cx,cy+r),(cx-r,cy)]
            pygame.draw.polygon(self.surf, color, pts)
            pygame.draw.polygon(self.surf, dk, pts, max(1,r//5))
        elif form == Form.HEX:
            pts = [(cx+math.cos(math.pi/3*i+math.pi/6)*r, cy+math.sin(math.pi/3*i+math.pi/6)*r) for i in range(6)]
            pygame.draw.polygon(self.surf, color, pts)
            pygame.draw.polygon(self.surf, dk, pts, max(1,r//5))
        elif form == Form.CROSS:
            w = max(2, r//3)
            pygame.draw.rect(self.surf, color, (cx-w, cy-r, w*2, r*2))
            pygame.draw.rect(self.surf, color, (cx-r, cy-w, r*2, w*2))

    def _cursor(self, p, is_self, cam):
        sx, sy = self.w2s(p.cx, p.cy, cam)
        if not (0 <= sx < self.w and 0 <= sy < self.h): return
        pulse = 1+0.2*math.sin(self.t*4)
        pr = int((8 if is_self else 6)*pulse)
        pygame.draw.circle(self.surf, p.color, (sx, sy), pr, 2)
        if is_self: pygame.draw.circle(self.surf, p.color, (sx, sy), pr+5, 1)
        t = self.ft.render(p.name, True, p.color)
        self.surf.blit(t, (sx+pr+4, sy-8))

    def _ghost(self, p, cam, world):
        r = self.wrect(p.cx-0.5, p.cy-0.5, 1, 1, cam)
        s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        ok = (p.cx, p.cy) not in world.buildings
        if p.sel_btype == BType.MINER: ok = ok and (p.cx, p.cy) in world.rmap
        c = (100,255,100,70) if ok else (255,80,80,70)
        bc = (100,255,100,160) if ok else (255,80,80,160)
        pygame.draw.rect(s, c, (0,0,r.w,r.h), border_radius=max(1,r.w//8))
        pygame.draw.rect(s, bc, (0,0,r.w,r.h), width=2, border_radius=max(1,r.w//8))
        self.surf.blit(s, r.topleft)

    def _hud(self, p, cam, world):
        bh = 36
        bs = pygame.Surface((self.w, bh), pygame.SRCALPHA)
        pygame.draw.rect(bs, (12,14,20,210), (0,0,self.w,bh))
        self.surf.blit(bs, (0,0))
        pygame.draw.circle(self.surf, p.color, (14, 18), 6)
        self.surf.blit(self.fm.render(p.name, True, (220,220,220)), (24, 10))
        self.surf.blit(self.fm.render(f"Score: {p.score}", True, (255,220,80)), (140, 10))

        # Paginated Toolbar
        total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
        page = p.toolbar_page % total_pages if total_pages > 0 else 0
        page_start = page * TOOLBAR_PER_PAGE
        page_end = min(page_start + TOOLBAR_PER_PAGE, len(BTOOLS))
        page_tools = BTOOLS[page_start:page_end]

        th = 62
        ty = self.h - th
        ts = pygame.Surface((self.w, th), pygame.SRCALPHA)
        pygame.draw.rect(ts, (12,14,20,220), (0,0,self.w,th))
        pygame.draw.line(ts, (45,47,58), (0,0), (self.w,0))
        self.surf.blit(ts, (0, ty))

        iw, gap = 72, 4
        tw = len(page_tools)*iw + (len(page_tools)-1)*gap
        sx = (self.w - tw) // 2
        for i, bt in enumerate(page_tools):
            x = sx + i*(iw+gap)
            sel = bt == p.sel_btype
            c = BCOLORS.get(bt, (100,100,100))
            label = TOOLBAR_LABELS.get(bt, BNAME.get(bt, "?")[:3])
            if sel:
                pygame.draw.rect(self.surf, c, (x, ty+4, iw, 44), border_radius=4)
                tc = (255,255,255)
            else:
                s2 = pygame.Surface((iw, 44), pygame.SRCALPHA)
                pygame.draw.rect(s2, (*c, 50), (0,0,iw,44), border_radius=4)
                pygame.draw.rect(s2, (*c, 100), (0,0,iw,44), width=1, border_radius=4)
                self.surf.blit(s2, (x, ty+4))
                tc = (170,172,185)
            self.surf.blit(self.ftiny.render(str(i+1), True, tc), (x+3, ty+6))
            self.surf.blit(self.ftiny.render(label, True, tc), (x+3, ty+18))

        # Page indicator and arrows
        page_text = f"Page {page+1}/{total_pages}"
        pt = self.ftiny.render(page_text, True, (140,142,155))
        self.surf.blit(pt, (sx - pt.get_width() - 24, ty + 14))
        # < > arrows
        arrow_y = ty + 14
        self._page_left_rect = pygame.Rect(sx - 24 - pt.get_width() - 18, arrow_y - 2, 18, 18)
        self._page_right_rect = pygame.Rect(sx + tw + 6, arrow_y - 2, 18, 18)
        lt = self.fs.render("<", True, (180,180,200) if page > 0 else (80,80,100))
        self.surf.blit(lt, (self._page_left_rect.x + 2, self._page_left_rect.y))
        rt = self.fs.render(">", True, (180,180,200) if page < total_pages - 1 else (80,80,100))
        self.surf.blit(rt, (self._page_right_rect.x + 2, self._page_right_rect.y))

        # Direction
        dn = ["\u2192","\u2193","\u2190","\u2191"]
        self.surf.blit(self.fs.render(f"Dir:{dn[p.sel_dir]}", True, (140,142,155)),
                       (sx+tw+28, ty+8))

        # Controls hint
        if p.has_mouse:
            hint = "LMB:Place RMB:Remove R:Rotate Q:Color E:Form Tab:Page Ctrl+Z:Undo Scroll:Zoom"
        else:
            hint = "Enter:Place Bksp:Remove /:Rotate .:Color P:Undo +/-:Zoom"
        self.surf.blit(self.ftiny.render(hint, True, (70,72,85)), (sx, ty+52))

    def _minimap(self, world, cam, player, all_players):
        ms = 120; mx = self.w-ms-6; my = 42
        sc = ms / (WORLD_SIZE*2)
        mm = pygame.Surface((ms, ms), pygame.SRCALPHA)
        pygame.draw.rect(mm, (10,12,18,180), (0,0,ms,ms), border_radius=3)
        pygame.draw.rect(mm, (50,52,65), (0,0,ms,ms), width=1, border_radius=3)
        def w2m(wx, wy): return int((wx+WORLD_SIZE)*sc), int((wy+WORLD_SIZE)*sc)
        for rx, ry in world.rmap:
            px, py = w2m(rx, ry)
            if 0<=px<ms and 0<=py<ms: mm.set_at((px,py), (70,70,50))
        for (bx,by), b in world.buildings.items():
            px, py = w2m(bx, by)
            if 0<=px<ms and 0<=py<ms: mm.set_at((px,py), BCOLORS.get(b.bt,(100,100,100)))
        for s in world.shapes:
            px, py = w2m(int(s.x), int(s.y))
            if 0<=px<ms and 0<=py<ms: mm.set_at((px,py), (200,200,80))
        for p in all_players:
            px, py = w2m(p.cx, p.cy)
            c = (255,255,255) if p.pid==player.pid else p.color
            if 0<=px<ms and 0<=py<ms:
                pygame.draw.circle(mm, c, (px,py), 3 if p.pid==player.pid else 2)
        # Viewport rect
        wx0, wy0 = self.s2w(0, 0, cam)
        wx1, wy1 = self.s2w(self.w, self.h, cam)
        vx0, vy0 = w2m(wx0, wy0); vx1, vy1 = w2m(wx1, wy1)
        pygame.draw.rect(mm, (255,255,255,80),
                         pygame.Rect(min(vx0,vx1), min(vy0,vy1), abs(vx1-vx0), abs(vy1-vy0)), 1)
        self.surf.blit(mm, (mx, my))
        self.surf.blit(self.ftiny.render("MAP", True, (70,72,85)), (mx+3, my-10))

    def _goals(self, world):
        pw, lh = 180, 18; hh = 18; vis = [g for g in world.goals if not g.completed][:3]
        done = sum(1 for g in world.goals if g.completed)
        th = hh + len(vis)*lh + 4; px, py = 4, 42
        s = pygame.Surface((pw, th), pygame.SRCALPHA)
        pygame.draw.rect(s, (10,12,18,180), (0,0,pw,th), border_radius=4)
        pygame.draw.rect(s, (50,52,65), (0,0,pw,th), width=1, border_radius=4)
        s.blit(self.ft.render(f"GOALS ({done} done)", True, (220,200,80)), (4,2))
        for i, g in enumerate(vis):
            gy = hh+2+i*lh; bx, by, bw, bh2 = 4, gy, pw-8, 14
            pygame.draw.rect(s, (30,32,40), (bx,by,bw,bh2), border_radius=2)
            fw = int(bw*min(1.0, g.done/max(1, g.req)))
            if fw > 0:
                gc = COL_RGB.get(g.shape.tc, (200,200,100))
                pygame.draw.rect(s, gc, (bx,by,fw,bh2), border_radius=2)
            pct = min(100, int(100*g.done/max(1,g.req)))
            s.blit(self.ftiny.render(f"{g.shape.label()} {g.done}/{g.req} ({pct}%)", True, (240,240,240)), (bx+3, by+2))
        self.surf.blit(s, (px, py))

    def _stats(self, world):
        pw, ph = 140, 90; px, py = 4, 42 + 18 + 3*18 + 8
        s = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(s, (10,12,18,160), (0,0,pw,ph), border_radius=4)
        pygame.draw.rect(s, (50,52,65), (0,0,pw,ph), width=1, border_radius=4)
        s.blit(self.ft.render("STATS", True, (160,200,160)), (4,2))
        snap = world.get_state_snapshot()
        lines = [f"Buildings: {snap['buildings']}", f"Shapes: {snap['shapes']}",
                 f"Produced: {snap['produced']}", f"Trashed: {snap['trashed']}",
                 f"Products: {len(world.stats)}"]
        for i, l in enumerate(lines):
            s.blit(self.ftiny.render(l, True, (170,172,185)), (6, 18+i*14))
        self.surf.blit(s, (px, py))

    def _events(self, world):
        if not world.events: return
        y = 38
        for ev in reversed(world.events[-5:]):
            age = time.time() - ev.time
            if age > 8: continue
            alpha = max(0, min(1, (8-age)/2))
            s = self.ftiny.render(ev.text, True, (*ev.color, int(255*alpha)))
            s.set_alpha(int(255*alpha))
            self.surf.blit(s, (self.w//2 - s.get_width()//2, y))
            y -= 14

# ═══════════════════════════════════════════════════════════════════════════════
#  INPUT HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

def handle_mouse(p, ev, mpos, vp, world, sfx, particles):
    if not vp: return
    total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
    th = 62
    ty = vp.h - th
    if ev.button == 1:
        # Check page arrows first
        if hasattr(vp, '_page_left_rect') and vp._page_left_rect.collidepoint(mpos):
            p.toolbar_page = (p.toolbar_page - 1) % total_pages
            sfx.play('rotate')
            return
        if hasattr(vp, '_page_right_rect') and vp._page_right_rect.collidepoint(mpos):
            p.toolbar_page = (p.toolbar_page + 1) % total_pages
            sfx.play('rotate')
            return
        # Toolbar click
        page = p.toolbar_page % total_pages if total_pages > 0 else 0
        page_start = page * TOOLBAR_PER_PAGE
        page_end = min(page_start + TOOLBAR_PER_PAGE, len(BTOOLS))
        page_tools = BTOOLS[page_start:page_end]
        iw, gap = 72, 4
        tw = len(page_tools)*iw + (len(page_tools)-1)*gap
        sx = (vp.w - tw) // 2
        if mpos[1] >= ty and mpos[0] >= sx:
            for idx in range(len(page_tools)):
                ix = sx + idx*(iw+gap)
                if ix <= mpos[0] <= ix+iw:
                    p.sel_btype = page_tools[idx]; sfx.play('rotate'); return
        if mpos[1] > 36 and mpos[1] < ty:
            wx, wy = vp.s2w(mpos[0], mpos[1], p)
            gx, gy = int(round(wx)), int(round(wy))
            old = world.buildings.get((gx, gy))
            msg = {"btype": p.sel_btype, "x": gx, "y": gy, "d": p.sel_dir}
            if p.sel_btype == BType.PAINTER: msg["pcol"] = p.paint_col
            elif p.sel_btype == BType.FILTER_COLOR: msg["pcol"] = p.paint_col
            elif p.sel_btype == BType.FILTER_FORM: msg["target_form"] = Form.CIRCLE
            elif p.sel_btype == BType.FORM_CHANGE: msg["target_form"] = Form.SQUARE
            elif p.sel_btype == BType.SELECTOR: msg["target_form"] = Form.CIRCLE
            ok = do_place(world, p, msg)
            if ok:
                sfx.play('place')
                particles.emit(gx+0.5, gy+0.5, (100,255,100), 6, 2.0, 0.4)
                p.placed += 1
            else:
                sfx.play('error')
    elif ev.button == 3:
        wx, wy = vp.s2w(mpos[0], mpos[1], p)
        gx, gy = int(round(wx)), int(round(wy))
        old = world.remove(gx, gy, p.pid)
        if old:
            p.push_undo(("remove", copy.deepcopy(old)))
            sfx.play('remove')
            particles.emit(gx+0.5, gy+0.5, (200,60,60), 8, 3.0, 0.5)
        else:
            sfx.play('error')
    elif ev.button == 2:
        p.dragging = True
        p.drag_start = mpos
        p.cam_start = (p.cam_x, p.cam_y)


def handle_p1_key(p, ev, vp, world, sfx, particles):
    if ev.key == pygame.K_r:
        p.sel_dir = p.sel_dir.cw()
        world.rotate(p.cx, p.cy)
        sfx.play('rotate')
    elif ev.key == pygame.K_q:
        cols = list(Col)
        p.paint_col = cols[(cols.index(p.paint_col)+1) % len(cols)]
        # Update painter color on selected building at cursor
        b = world.buildings.get((p.cx, p.cy))
        if b and b.bt == BType.PAINTER:
            b.pcol = p.paint_col
        elif b and b.bt == BType.FILTER_COLOR:
            b.pcol = p.paint_col
        sfx.play('rotate')
    elif ev.key == pygame.K_e:
        # Cycle form target for FILTER_FORM, FORM_CHANGE, CRAFTER
        b = world.buildings.get((p.cx, p.cy))
        if b:
            forms = list(Form)
            if b.bt == BType.FILTER_FORM and b.target_form is not None:
                b.target_form = forms[(forms.index(b.target_form) + 1) % len(forms)]
                sfx.play('rotate')
            elif b.bt == BType.FORM_CHANGE and b.target_form is not None:
                b.target_form = forms[(forms.index(b.target_form) + 1) % len(forms)]
                sfx.play('rotate')
            elif b.bt == BType.CRAFTER and b.recipe_in is not None and b.recipe_out is not None:
                forms_ri = list(Form)
                b.recipe_out.tf = forms_ri[(forms_ri.index(b.recipe_out.tf) + 1) % len(forms_ri)]
                sfx.play('rotate')
    elif ev.key == pygame.K_z and (ev.mod & pygame.KMOD_CTRL):
        if p.pop_undo(world): sfx.play('remove')
        else: sfx.play('error')
    elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                    pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8):
        total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
        page = p.toolbar_page % total_pages if total_pages > 0 else 0
        page_start = page * TOOLBAR_PER_PAGE
        idx = ev.key - pygame.K_1
        global_idx = page_start + idx
        if global_idx < len(BTOOLS):
            p.sel_btype = BTOOLS[global_idx]; sfx.play('rotate')
    elif ev.key == pygame.K_TAB:
        total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
        if ev.mod & pygame.KMOD_SHIFT:
            p.toolbar_page = (p.toolbar_page - 1) % total_pages
        else:
            p.toolbar_page = (p.toolbar_page + 1) % total_pages
        sfx.play('rotate')
    elif ev.key == pygame.K_LEFTBRACKET:
        # [ key: previous page (alternative to Shift+Tab)
        total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
        p.toolbar_page = (p.toolbar_page - 1) % total_pages
        sfx.play('rotate')
    elif ev.key == pygame.K_RIGHTBRACKET:
        # ] key: next page (alternative to Tab)
        total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
        p.toolbar_page = (p.toolbar_page + 1) % total_pages
        sfx.play('rotate')
    elif ev.key == pygame.K_HOME:
        p.cam_x, p.cam_y = 0.0, 0.0; p.cam_target_zoom = 1.0


def handle_kb_player(p, ev, world, sfx, particles):
    """Handle keyboard input for non-mouse players (P2+)."""
    # Place
    if ev.key == p._k_place:
        msg = {"btype": p.sel_btype, "x": p.cx, "y": p.cy, "d": p.sel_dir}
        if p.sel_btype == BType.PAINTER: msg["pcol"] = p.paint_col
        elif p.sel_btype == BType.FILTER_COLOR: msg["pcol"] = p.paint_col
        elif p.sel_btype == BType.FILTER_FORM: msg["target_form"] = Form.CIRCLE
        elif p.sel_btype == BType.FORM_CHANGE: msg["target_form"] = Form.SQUARE
        elif p.sel_btype == BType.SELECTOR: msg["target_form"] = Form.CIRCLE
        ok = do_place(world, p, msg)
        if ok:
            sfx.play('place')
            p.placed += 1
        else: sfx.play('error')
    # Remove
    elif ev.key == p._k_remove:
        old = world.remove(p.cx, p.cy, p.pid)
        if old:
            p.push_undo(("remove", copy.deepcopy(old)))
            sfx.play('remove')
        else: sfx.play('error')
    # Rotate
    elif ev.key == p._k_rotate:
        p.sel_dir = p.sel_dir.cw()
        world.rotate(p.cx, p.cy)
        sfx.play('rotate')
    # Painter color
    elif ev.key == p._k_pcol:
        cols = list(Col)
        p.paint_col = cols[(cols.index(p.paint_col)+1) % len(cols)]
        b = world.buildings.get((p.cx, p.cy))
        if b and b.bt == BType.PAINTER:
            b.pcol = p.paint_col
        elif b and b.bt == BType.FILTER_COLOR:
            b.pcol = p.paint_col
        sfx.play('rotate')
    # Undo
    elif ev.key == p._k_undo:
        if p.pop_undo(world): sfx.play('remove')
    # Zoom
    elif ev.key == p._k_zin:
        p.cam_target_zoom = min(4.0, p.cam_target_zoom * 1.2)
    elif ev.key == p._k_zout:
        p.cam_target_zoom = max(0.2, p.cam_target_zoom / 1.2)
    # Building select
    elif ev.key in p._k_tools:
        total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
        page = p.toolbar_page % total_pages if total_pages > 0 else 0
        page_start = page * TOOLBAR_PER_PAGE
        idx = p._k_tools.index(ev.key)
        global_idx = page_start + idx
        if global_idx < len(BTOOLS):
            p.sel_btype = BTOOLS[global_idx]; sfx.play('rotate')
    # Pan
    elif ev.key in p._k_pan:
        dx, dy = p._k_pan[ev.key]
        pan = 3 / p.cam_zoom
        p.cam_x += dx * pan; p.cam_y += dy * pan
    # Page switching
    elif hasattr(p, '_k_page_prev') and ev.key == p._k_page_prev:
        total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
        p.toolbar_page = (p.toolbar_page - 1) % total_pages
        sfx.play('rotate')
    elif hasattr(p, '_k_page_next') and ev.key == p._k_page_next:
        total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
        p.toolbar_page = (p.toolbar_page + 1) % total_pages
        sfx.play('rotate')
    # Form cycling
    elif hasattr(p, '_k_form') and ev.key == p._k_form:
        b = world.buildings.get((p.cx, p.cy))
        if b:
            forms = list(Form)
            if b.bt == BType.FILTER_FORM and b.target_form is not None:
                b.target_form = forms[(forms.index(b.target_form) + 1) % len(forms)]
                sfx.play('rotate')
            elif b.bt == BType.FORM_CHANGE and b.target_form is not None:
                b.target_form = forms[(forms.index(b.target_form) + 1) % len(forms)]
                sfx.play('rotate')
            elif b.bt == BType.CRAFTER and b.recipe_in is not None and b.recipe_out is not None:
                forms_ri = list(Form)
                b.recipe_out.tf = forms_ri[(forms_ri.index(b.recipe_out.tf) + 1) % len(forms_ri)]
                sfx.play('rotate')


def do_place(world, p, msg):
    """Place a building and push undo."""
    bt, x, y, d = msg["btype"], msg["x"], msg["y"], Dir(msg["d"])
    pcol = msg.get("pcol")
    target_form = msg.get("target_form")
    recipe_in = msg.get("recipe_in")
    recipe_out = msg.get("recipe_out")
    if world.place(bt, x, y, d, p.pid, pcol, target_form, recipe_in, recipe_out):
        b = world.buildings.get((x, y))
        if b: p.push_undo(("place", copy.deepcopy(b)))
        return True
    return False


# ── Setup keyboard bindings for P2+ ────────────────────────────────────────

def setup_kb_bindings(p, player_idx):
    """Assign keyboard controls based on player index."""
    if player_idx == 1:
        p._k_up = pygame.K_UP
        p._k_down = pygame.K_DOWN
        p._k_left = pygame.K_LEFT
        p._k_right = pygame.K_RIGHT
        p._k_place = pygame.K_RETURN
        p._k_remove = pygame.K_BACKSPACE
        p._k_rotate = pygame.K_SLASH
        p._k_pcol = pygame.K_PERIOD
        p._k_undo = pygame.K_p
        p._k_zin = pygame.K_EQUALS
        p._k_zout = pygame.K_MINUS
        p._k_tools = [pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4,
                      pygame.K_F5, pygame.K_F6, pygame.K_F7, pygame.K_F8]
        p._k_pan = {pygame.K_i: (0, -1), pygame.K_k: (0, 1),
                    pygame.K_j: (-1, 0), pygame.K_l: (1, 0)}
        p._k_page_prev = pygame.K_COMMA
        p._k_page_next = pygame.K_SEMICOLON
        p._k_form = pygame.K_QUOTE
    elif player_idx == 2:
        p._k_up = pygame.K_KP8
        p._k_down = pygame.K_KP2
        p._k_left = pygame.K_KP4
        p._k_right = pygame.K_KP6
        p._k_place = pygame.K_KP0
        p._k_remove = pygame.K_KP_PERIOD
        p._k_rotate = pygame.K_KP_ENTER
        p._k_pcol = pygame.K_KP_MULTIPLY
        p._k_undo = pygame.K_KP_MINUS
        p._k_zin = pygame.K_KP_PLUS
        p._k_zout = pygame.K_KP_MINUS
        p._k_tools = [pygame.K_KP1, pygame.K_KP2, pygame.K_KP3, pygame.K_KP4,
                      pygame.K_KP5, pygame.K_KP6, pygame.K_KP7, pygame.K_KP8]
        p._k_pan = {pygame.K_KP7: (0, -1), pygame.K_KP9: (0, 1),
                    pygame.K_KP1: (-1, 0), pygame.K_KP3: (1, 0)}
        p._k_page_prev = pygame.K_KP_DIVIDE
        p._k_page_next = pygame.K_KP_MULTIPLY
        p._k_form = pygame.K_KP_ENTER
    elif player_idx == 3:
        p._k_up = pygame.K_t
        p._k_down = pygame.K_g
        p._k_left = pygame.K_f
        p._k_right = pygame.K_h
        p._k_place = pygame.K_r
        p._k_remove = pygame.K_e
        p._k_rotate = pygame.K_y
        p._k_pcol = pygame.K_u
        p._k_undo = pygame.K_i
        p._k_zin = pygame.K_o
        p._k_zout = pygame.K_n
        p._k_tools = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                      pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8]
        p._k_pan = {}
        p._k_page_prev = pygame.K_LEFTBRACKET
        p._k_page_next = pygame.K_RIGHTBRACKET
        p._k_form = pygame.K_BACKSLASH


# ═══════════════════════════════════════════════════════════════════════════════
#  MENU SCREEN
# ═══════════════════════════════════════════════════════════════════════════════

def menu_screen(screen, clock):
    """Show player count selection. Returns int or None."""
    ft = pygame.font.SysFont("consolas", 36, bold=True)
    fm = pygame.font.SysFont("consolas", 18)
    fs = pygame.font.SysFont("consolas", 14)
    selected = 2
    t = 0

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: return None
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE: return None
                if ev.key == pygame.K_LEFT: selected = max(1, selected - 1)
                if ev.key == pygame.K_RIGHT: selected = min(4, selected + 1)
                if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return selected
            if ev.type == pygame.MOUSEBUTTONDOWN:
                sw, sh = screen.get_size()
                cx = sw // 2
                for i in range(1, 5):
                    bx = cx - 100 + (i-1) * 70
                    by = sh // 2 + 60
                    if bx <= ev.pos[0] <= bx + 50 and by <= ev.pos[1] <= by + 50:
                        selected = i
                        return selected
            if ev.type == pygame.MOUSEWHEEL:
                selected = max(1, min(4, selected + ev.y))

        sw, sh = screen.get_size()
        screen.fill((18, 20, 28))

        # Title
        pulse = 0.7 + 0.3 * math.sin(t * 2)
        title_color = (int(100 + 155 * pulse), int(200 + 55 * pulse), int(80 + 175 * pulse))
        title = ft.render("shapez", True, title_color)
        screen.blit(title, title.get_rect(center=(sw//2, sh//4 - 10)))
        sub = fm.render("LOCAL MULTIPLAYER", True, (120, 180, 220))
        screen.blit(sub, sub.get_rect(center=(sw//2, sh//4 + 30)))

        # Player count selector
        prompt = fm.render("Select number of players:", True, (180, 182, 195))
        screen.blit(prompt, prompt.get_rect(center=(sw//2, sh//2 + 20)))

        cx = sw // 2
        for i in range(1, 5):
            bx = cx - 100 + (i-1) * 70
            by = sh//2 + 60
            is_sel = i == selected
            c = P_COLORS[i-1]
            if is_sel:
                # Glowing selection
                glow = pygame.Surface((60, 60), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*c, 40), (0, 0, 60, 60), border_radius=8)
                screen.blit(glow, (bx-5, by-5))
                pygame.draw.rect(screen, c, (bx, by, 50, 50), border_radius=6)
                txt_c = (255, 255, 255)
            else:
                s = pygame.Surface((50, 50), pygame.SRCALPHA)
                pygame.draw.rect(s, (*c, 40), (0, 0, 50, 50), border_radius=6)
                pygame.draw.rect(s, (*c, 100), (0, 0, 50, 50), width=2, border_radius=6)
                screen.blit(s, (bx, by))
                txt_c = (*c,)
            num = ft.render(str(i), True, txt_c)
            screen.blit(num, num.get_rect(center=(bx+25, by+25)))

        # Controls info
        y0 = sh//2 + 140
        controls = [
            ("Player 1: Mouse + WASD/Arrows + 1-8 + Tab/Q/E", P_COLORS[0]),
            ("Player 2: Arrows + IJKL + Enter/Bksp + F1-F8 + ,/;/'", P_COLORS[1]),
            ("Player 3: Numpad 8456 + 7913 + Numpad 0", P_COLORS[2]),
            ("Player 4: TFGH + [/]/\\", P_COLORS[3]),
        ]
        for i, (txt, c) in enumerate(controls):
            if i >= selected: break
            alpha = 255 if i < selected else 100
            ct = fs.render(txt, True, c)
            ct.set_alpha(alpha)
            screen.blit(ct, ct.get_rect(center=(sw//2, y0 + i * 22)))

        # Start hint
        blink = int(t * 2) % 2 == 0
        if blink:
            hint = fm.render("Press ENTER or click to start", True, (140, 142, 155))
            screen.blit(hint, hint.get_rect(center=(sw//2, sh - 60)))

        # Shape decorations
        for i in range(12):
            angle = t * 0.3 + i * math.pi / 6
            dx = math.cos(angle) * (sw * 0.35)
            dy = math.sin(angle) * (sh * 0.3)
            sx = int(sw/2 + dx)
            sy = int(sh/2 + dy)
            c = COL_RGB.get(list(Col)[i % len(Col)], (200,200,200))
            form = list(Form)[i % len(Form)]
            r = 12
            if form == Form.CIRCLE:
                pygame.draw.circle(screen, c, (sx, sy), r, 2)
            elif form == Form.SQUARE:
                pygame.draw.rect(screen, c, (sx-r, sy-r, r*2, r*2), 2)
            elif form == Form.TRI:
                pygame.draw.polygon(screen, c, [(sx, sy-r), (sx-r, sy+r), (sx+r, sy+r)], 2)
            elif form == Form.STAR:
                pts = [(sx+math.cos(math.pi/2+j*math.pi/5)*(r if j%2==0 else r*0.4),
                        sy-math.sin(math.pi/2+j*math.pi/5)*(r if j%2==0 else r*0.4)) for j in range(10)]
                pygame.draw.polygon(screen, c, pts, 2)

        pygame.display.flip()


# ═══════════════════════════════════════════════════════════════════════════════
#  VIEWPORT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def build_viewports(n, sw, sh):
    vps = []
    if n == 1:
        vps.append(Viewport(sw, sh))
    elif n == 2:
        hw = sw // 2
        vps.append(Viewport(hw - 2, sh))
        vps.append(Viewport(hw - 2, sh))
    else:
        hw, hh = sw // 2, sh // 2
        for _ in range(n):
            vps.append(Viewport(hw - 2, hh - 2))
    return vps


def blit_viewports(screen, vps, players, n, sw, sh):
    if n == 1:
        screen.blit(vps[0].surf, (0, 0))
    elif n == 2:
        hw = sw // 2
        screen.blit(vps[0].surf, (0, 0))
        screen.blit(vps[1].surf, (hw + 4, 0))
        pygame.draw.line(screen, (60, 62, 75), (hw, 0), (hw, sh), 4)
        for i in range(2):
            screen.blit(vps[i].fm.render(players[i].name, True, players[i].color),
                        (4 + i * (hw + 10), sh - 22))
    else:
        hw, hh = sw // 2, sh // 2
        pos = [(0,0), (hw+4,0), (0,hh+4), (hw+4,hh+4)]
        for i in range(min(n, 4)):
            screen.blit(vps[i].surf, pos[i])
        pygame.draw.line(screen, (60, 62, 75), (hw, 0), (hw, sh), 4)
        pygame.draw.line(screen, (60, 62, 75), (0, hh), (sw, hh), 4)
        for i in range(min(n, 4)):
            ox, oy = pos[i]
            screen.blit(vps[0].fs.render(players[i].name, True, players[i].color),
                        (ox + 6, oy + 3))


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN GAME LOOP
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN MENU WITH EDITOR OPTION
# ═══════════════════════════════════════════════════════════════════════════════

def main_menu_with_editor(screen, clock):
    """Enhanced menu with editor option. Returns int (player count), 'editor', filename str, or None."""
    ft = pygame.font.SysFont("consolas", 36, bold=True)
    fm = pygame.font.SysFont("consolas", 18)
    fs = pygame.font.SysFont("consolas", 14)
    selected = 0  # 0-3: player count, 4: editor
    t = 0
    num_players = 2

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: return None
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE: return None
                if ev.key == pygame.K_LEFT: selected = max(0, selected - 1)
                if ev.key == pygame.K_RIGHT: selected = min(4, selected + 1)
                if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if selected < 4:
                        return selected + 1  # 1-4 players
                    else:
                        return "editor"
                if ev.key == pygame.K_e:
                    return "editor"
            if ev.type == pygame.MOUSEBUTTONDOWN:
                sw, sh = screen.get_size()
                cx = sw // 2
                for i in range(5):
                    bx = cx - 175 + (i - 2) * 90
                    by = sh // 2 + 60
                    if bx <= ev.pos[0] <= bx + 70 and by <= ev.pos[1] <= by + 50:
                        if i < 4:
                            return i + 1
                        else:
                            return "editor"
            if ev.type == pygame.MOUSEWHEEL:
                selected = max(0, min(4, selected + ev.y))

        sw, sh = screen.get_size()
        screen.fill((18, 20, 28))
        pulse = 0.7 + 0.3 * math.sin(t * 2)
        title_color = (int(100 + 155 * pulse), int(200 + 55 * pulse), int(80 + 175 * pulse))
        title = ft.render("shapez", True, title_color)
        screen.blit(title, title.get_rect(center=(sw // 2, sh // 4 - 10)))
        sub = fm.render("LOCAL MULTIPLAYER", True, (120, 180, 220))
        screen.blit(sub, sub.get_rect(center=(sw // 2, sh // 4 + 30)))

        prompt = fm.render("Select number of players or open editor:", True, (180, 182, 195))
        screen.blit(prompt, prompt.get_rect(center=(sw // 2, sh // 2 + 20)))

        cx = sw // 2
        for i in range(5):
            bx = cx - 175 + (i - 2) * 90
            by = sh // 2 + 60
            is_sel = i == selected
            if i < 4:
                c = P_COLORS[i]
                label = str(i + 1)
            else:
                c = (100, 200, 255)
                label = "E"
            if is_sel:
                glow = pygame.Surface((60, 60), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*c, 40), (0, 0, 60, 60), border_radius=8)
                screen.blit(glow, (bx - 5, by - 5))
                pygame.draw.rect(screen, c, (bx, by, 50, 50), border_radius=6)
                txt_c = (255, 255, 255)
            else:
                s = pygame.Surface((50, 50), pygame.SRCALPHA)
                pygame.draw.rect(s, (*c, 40), (0, 0, 50, 50), border_radius=6)
                pygame.draw.rect(s, (*c, 100), (0, 0, 50, 50), width=2, border_radius=6)
                screen.blit(s, (bx, by))
                txt_c = c
            num = ft.render(label, True, txt_c)
            screen.blit(num, num.get_rect(center=(bx + 25, by + 20)))
            if i == 4:
                el = fs.render("Editor", True, txt_c)
                screen.blit(el, el.get_rect(center=(bx + 25, by + 42)))

        y0 = sh // 2 + 130
        controls = [
            ("1-4: Start game with N players  |  E: Level Editor", (140, 142, 155)),
            ("P1: Mouse + WASD + 1-8 + Tab/Q/E/R", P_COLORS[0]),
        ]
        for i, (txt, c) in enumerate(controls):
            ct = fs.render(txt, True, c)
            ct.set_alpha(200)
            screen.blit(ct, ct.get_rect(center=(sw // 2, y0 + i * 22)))

        blink = int(t * 2) % 2 == 0
        if blink:
            hint = fm.render("Press ENTER or click to start", True, (140, 142, 155))
            screen.blit(hint, hint.get_rect(center=(sw // 2, sh - 60)))

        for i in range(12):
            angle = t * 0.3 + i * math.pi / 6
            dx = math.cos(angle) * (sw * 0.35)
            dy = math.sin(angle) * (sh * 0.3)
            sx = int(sw / 2 + dx)
            sy = int(sh / 2 + dy)
            c = COL_RGB.get(list(Col)[i % len(Col)], (200, 200, 200))
            r = 12
            form = list(Form)[i % len(Form)]
            if form == Form.CIRCLE:
                pygame.draw.circle(screen, c, (sx, sy), r, 2)
            elif form == Form.SQUARE:
                pygame.draw.rect(screen, c, (sx - r, sy - r, r * 2, r * 2), 2)
            elif form == Form.TRI:
                pygame.draw.polygon(screen, c, [(sx, sy - r), (sx - r, sy + r), (sx + r, sy + r)], 2)
            elif form == Form.STAR:
                pts = [(sx + math.cos(math.pi / 2 + j * math.pi / 5) * (r if j % 2 == 0 else r * 0.4),
                        sy - math.sin(math.pi / 2 + j * math.pi / 5) * (r if j % 2 == 0 else r * 0.4)) for j in range(10)]
                pygame.draw.polygon(screen, c, pts, 2)

        pygame.display.flip()


def run_editor_flow(screen, clock, sfx):
    """Run the editor menu + editor. Returns 'quit', ('test', world), or 'back'."""
    result = editor_menu_screen(screen, clock)
    if result is None:
        return "back"
    if result == "new":
        editor = LevelEditor(screen, clock, sfx)
        try:
            editor.run_editor()
        except ReturnToMenu:
            return "back"
        except TestPlayRequest:
            return ("test", editor.get_test_world())
        return "back"
    elif isinstance(result, str) and result.endswith('.json'):
        # Load existing level into editor
        editor = LevelEditor(screen, clock, sfx)
        try:
            editor.load_level(result)
            editor.run_editor()
        except ReturnToMenu:
            return "back"
        except TestPlayRequest:
            return ("test", editor.get_test_world())
        return "back"
    return "back"


def run_game_with_world(screen, clock, sfx, world, num_players):
    """Run the game loop with a pre-built world (for testing levels)."""
    players: List[PlayerState] = []
    for i in range(num_players):
        p = PlayerState(i, P_NAMES[i], P_COLORS[i], has_mouse=(i == 0))
        if i < len(world.resources):
            idx = (i * 13) % len(world.resources)
            p.cam_x = float(world.resources[idx].x)
            p.cam_y = float(world.resources[idx].y)
            p.cx = world.resources[idx].x
            p.cy = world.resources[idx].y
        if not p.has_mouse:
            setup_kb_bindings(p, i)
        players.append(p)

    viewports: List[Viewport] = []
    particles = Particles()
    running = True
    sim_accum = 0.0
    prev_goals_done = 0
    need_resize = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()
        sw, sh = screen.get_size()
        if need_resize:
            need_resize = False
            viewports = build_viewports(num_players, sw, sh)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: running = False
            elif ev.type == pygame.VIDEORESIZE: need_resize = True
            elif ev.type == pygame.MOUSEWHEEL:
                players[0].cam_target_zoom = max(0.2, min(4.0,
                    players[0].cam_target_zoom * (1.12 if ev.y > 0 else 1 / 1.12)))
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if players[0].has_mouse and viewports:
                    handle_mouse(players[0], ev, mouse_pos, viewports[0], world, sfx, particles)
            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 2: players[0].dragging = False
            elif ev.type == pygame.MOUSEMOTION:
                if players[0].dragging and viewports:
                    v = viewports[0]
                    dx = (ev.pos[0] - players[0].drag_start[0]) / (TILE_SIZE * players[0].cam_zoom)
                    dy = (ev.pos[1] - players[0].drag_start[1]) / (TILE_SIZE * players[0].cam_zoom)
                    players[0].cam_x = players[0].cam_start[0] - dx
                    players[0].cam_y = players[0].cam_start[1] - dy
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE: running = False
                if players[0].has_mouse:
                    handle_p1_key(players[0], ev, viewports[0] if viewports else None, world, sfx, particles)
                for p in players[1:]:
                    handle_kb_player(p, ev, world, sfx, particles)

        keys = pygame.key.get_pressed()
        pan = 10 / players[0].cam_zoom * dt
        if keys[pygame.K_a]: players[0].cam_x -= pan
        if keys[pygame.K_d]: players[0].cam_x += pan
        if keys[pygame.K_w]: players[0].cam_y -= pan
        if keys[pygame.K_s]: players[0].cam_y += pan

        if viewports:
            v = viewports[0]
            wx, wy = v.s2w(mouse_pos[0], mouse_pos[1], players[0])
            players[0].cx, players[0].cy = int(round(wx)), int(round(wy))

        for p in players[1:]:
            p.cursor_move_timer += dt
            if p.cursor_move_timer > 0.06:
                p.cursor_move_timer = 0
                if keys.get(p._k_up, False): p.cy -= 1
                if keys.get(p._k_down, False): p.cy += 1
                if keys.get(p._k_left, False): p.cx -= 1
                if keys.get(p._k_right, False): p.cx += 1
            dx = p.cx - p.cam_x; dy = p.cy - p.cam_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 6:
                p.cam_x += dx * 0.06
                p.cam_y += dy * 0.06

        for p in players:
            d = p.cam_target_zoom - p.cam_zoom
            if abs(d) > 0.01: p.cam_zoom += d * min(1, dt * 12)

        sim_accum += dt
        steps = 0
        while sim_accum >= TICK_MS / 1000.0 and steps < 5:
            world.tick(); sim_accum -= TICK_MS / 1000.0; steps += 1

        gd = sum(1 for g in world.goals if g.completed)
        if gd > prev_goals_done: sfx.play('goal'); prev_goals_done = gd

        particles.update(dt)

        screen.fill((10, 10, 14))
        for i, (p, v) in enumerate(zip(players, viewports)):
            v.t += dt
            v.render(world, p, p, players, particles)
        blit_viewports(screen, viewports, players, num_players, sw, sh)

        fps_t = viewports[0].ftiny.render(f"FPS:{int(clock.get_fps())} Ticks:{world.tick_n} TEST MODE - ESC to exit", True, (255, 200, 80))
        screen.blit(fps_t, (sw - 300, 4))

        pygame.display.flip()


LEVELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")

# ═══════════════════════════════════════════════════════════════════════════════
#  LEVEL DATA  (serialization for save/load)
# ═══════════════════════════════════════════════════════════════════════════════

class LevelData:
    """Serializes/deserializes a level to/from JSON."""
    def __init__(self):
        self.name = "Untitled Level"
        self.author = "Anonymous"
        self.description = ""
        self.version = 1
        self.resources: List[dict] = []
        self.goals: List[dict] = []
        self.buildings: List[dict] = []
        self.world_size = WORLD_SIZE

    def from_world(self, world, name="Untitled Level", author="Anonymous"):
        self.name = name
        self.author = author
        self.resources = []
        for n in world.resources:
            self.resources.append({
                "x": n.x, "y": n.y,
                "tf": int(n.shape.tf), "tc": int(n.shape.tc),
                "bf": int(n.shape.bf) if n.shape.bf is not None else None,
                "bc": int(n.shape.bc) if n.shape.bc is not None else None,
            })
        self.goals = []
        for g in world.goals:
            self.goals.append({
                "tf": int(g.shape.tf), "tc": int(g.shape.tc),
                "bf": int(g.shape.bf) if g.shape.bf is not None else None,
                "bc": int(g.shape.bc) if g.shape.bc is not None else None,
                "req": g.req, "pts": g.pts,
            })
        self.buildings = []
        for (bx, by), b in world.buildings.items():
            bd = {"bt": int(b.bt), "x": b.x, "y": b.y, "d": int(b.d)}
            if b.prod: bd["prod"] = {"tf": int(b.prod.tf), "tc": int(b.prod.tc)}
            if b.pcol is not None: bd["pcol"] = int(b.pcol)
            if b.target_form is not None: bd["target_form"] = int(b.target_form)
            if b.recipe_in: bd["recipe_in"] = {"tf": int(b.recipe_in.tf), "tc": int(b.recipe_in.tc)}
            if b.recipe_out: bd["recipe_out"] = {"tf": int(b.recipe_out.tf), "tc": int(b.recipe_out.tc),
                                                   "bf": int(b.recipe_out.bf) if b.recipe_out.bf else None,
                                                   "bc": int(b.recipe_out.bc) if b.recipe_out.bc else None}
            self.buildings.append(bd)
        self.world_size = WORLD_SIZE
        return self

    def to_world(self):
        w = World()
        w.resources = []
        w.rmap = {}
        for rd in self.resources:
            s = Shape(Form(rd["tf"]), Col(rd["tc"]),
                      Form(rd["bf"]) if rd.get("bf") is not None else None,
                      Col(rd["bc"]) if rd.get("bc") is not None else None)
            n = ResourceNode(rd["x"], rd["y"], s)
            w.resources.append(n)
            w.rmap[(n.x, n.y)] = n
        w.goals = []
        for i, gd in enumerate(self.goals):
            s = Shape(Form(gd["tf"]), Col(gd["tc"]),
                      Form(gd["bf"]) if gd.get("bf") is not None else None,
                      Col(gd["bc"]) if gd.get("bc") is not None else None)
            w.goals.append(Goal(i, s, gd.get("req", GOAL_NEED), 0, False, gd.get("pts", 100)))
        w.next_gid = len(w.goals)
        for bd in self.buildings:
            bt = BType(bd["bt"])
            d = Dir(bd["d"])
            pcol = Col(bd["pcol"]) if bd.get("pcol") is not None else None
            tf = Form(bd["target_form"]) if bd.get("target_form") is not None else None
            ri = ro = None
            if bd.get("recipe_in"):
                ri = Shape(Form(bd["recipe_in"]["tf"]), Col(bd["recipe_in"]["tc"]))
            if bd.get("recipe_out"):
                ro = Shape(Form(bd["recipe_out"]["tf"]), Col(bd["recipe_out"]["tc"]),
                           Form(bd["recipe_out"]["bf"]) if bd["recipe_out"].get("bf") else None,
                           Col(bd["recipe_out"]["bc"]) if bd["recipe_out"].get("bc") else None)
            if bt == BType.MINER:
                n = w.rmap.get((bd["x"], bd["y"]))
                if n:
                    n.mined = True
                    prod = Shape(n.shape.tf, n.shape.tc)
                    b = Building(bt, bd["x"], bd["y"], d, prod=prod)
                else:
                    continue
            elif bt == BType.PAINTER:
                b = Building(bt, bd["x"], bd["y"], d, pcol=pcol or Col.RED)
            elif bt == BType.FILTER_FORM:
                b = Building(bt, bd["x"], bd["y"], d, target_form=tf or Form.CIRCLE)
            elif bt == BType.FORM_CHANGE:
                b = Building(bt, bd["x"], bd["y"], d, target_form=tf or Form.SQUARE)
            elif bt == BType.CRAFTER:
                b = Building(bt, bd["x"], bd["y"], d, recipe_in=ri, recipe_out=ro)
            elif bt == BType.FILTER_COLOR:
                b = Building(bt, bd["x"], bd["y"], d, pcol=pcol or Col.RED)
            elif bt == BType.EMITTER:
                forms, colors = list(Form), list(Col)
                b = Building(bt, bd["x"], bd["y"], d,
                             prod=Shape(Form(bd.get("prod", {}).get("tf", 0)),
                                        Col(bd.get("prod", {}).get("tc", 0))))
            else:
                b = Building(bt, bd["x"], bd["y"], d)
            w.buildings[(bd["x"], bd["y"])] = b
        return w

    def to_json(self):
        return json.dumps({
            "name": self.name, "author": self.author,
            "description": self.description, "version": self.version,
            "resources": self.resources, "goals": self.goals,
            "buildings": self.buildings, "world_size": self.world_size,
        }, indent=2)

    @staticmethod
    def from_json(s):
        d = json.loads(s)
        ld = LevelData()
        ld.name = d.get("name", "Untitled")
        ld.author = d.get("author", "Anonymous")
        ld.description = d.get("description", "")
        ld.version = d.get("version", 1)
        ld.resources = d.get("resources", [])
        ld.goals = d.get("goals", [])
        ld.buildings = d.get("buildings", [])
        ld.world_size = d.get("world_size", WORLD_SIZE)
        return ld

    def save_to_file(self, filename):
        os.makedirs(LEVELS_DIR, exist_ok=True)
        path = os.path.join(LEVELS_DIR, filename)
        with open(path, 'w') as f:
            f.write(self.to_json())
        return path

    @staticmethod
    def load_from_file(filename):
        path = os.path.join(LEVELS_DIR, filename)
        with open(path, 'r') as f:
            return LevelData.from_json(f.read())

    @staticmethod
    def list_files():
        if not os.path.isdir(LEVELS_DIR):
            return []
        return sorted(f for f in os.listdir(LEVELS_DIR) if f.endswith('.json'))


# ═══════════════════════════════════════════════════════════════════════════════
#  LEVEL EDITOR
# ═══════════════════════════════════════════════════════════════════════════════

class EditorTool(IntEnum):
    SELECT = 0; RESOURCE = 1; BUILDING = 2; GOAL = 3
    ERASE = 4; PAN = 5; FILL = 6; EYEDROPPER = 7

ETOOL_NAME = {
    EditorTool.SELECT: "Select", EditorTool.RESOURCE: "Resource",
    EditorTool.BUILDING: "Building", EditorTool.GOAL: "Goal",
    EditorTool.ERASE: "Erase", EditorTool.PAN: "Pan",
    EditorTool.FILL: "Fill Area", EditorTool.EYEDROPPER: "Eyedrop",
}
ETOOL_KEY = {
    EditorTool.SELECT: "V", EditorTool.RESOURCE: "R", EditorTool.BUILDING: "B",
    EditorTool.GOAL: "G", EditorTool.ERASE: "X", EditorTool.PAN: "H",
    EditorTool.FILL: "F", EditorTool.EYEDROPPER: "I",
}

class LevelEditor:
    def __init__(self, screen, clock, sfx):
        self.screen = screen
        self.clock = clock
        self.sfx = sfx
        self.world = World()
        self.vp = Viewport(screen.get_width(), screen.get_height())
        self.particles = Particles()

        # Camera (reuse player state fields)
        self.cam_x = 0.0; self.cam_y = 0.0
        self.cam_zoom = 1.0; self.cam_target_zoom = 1.0
        self.cx = 0; self.cy = 0  # cursor tile

        # Editor state
        self.tool = EditorTool.RESOURCE
        self.sel_dir = Dir.R
        self.paint_col = Col.RED
        self.sel_form = Form.CIRCLE
        self.sel_btype = BType.CONVEYOR
        self.toolbar_page = 0
        self.level_name = "Untitled Level"
        self.level_author = "Anonymous"
        self.unsaved = False

        # Undo
        self.undo_stack: list = []
        self.redo_stack: list = []

        # Selection
        self.sel_rect_start = None  # (wx, wy) world coords
        self.sel_rect_end = None
        self.selected_tiles: set = set()  # set of (x, y) for selected buildings
        self.dragging = False
        self.drag_start = (0, 0)
        self.cam_start = (0.0, 0.0)
        self.panning = False

        # Goal editor
        self.goal_form = Form.CIRCLE
        self.goal_col = Col.RED
        self.goal_layered = False
        self.goal_bf = Form.SQUARE
        self.goal_bc = Col.BLUE
        self.goal_req = GOAL_NEED

        # Fill tool
        self.brush_size = 1

        # UI state
        self.show_grid = True
        self.show_resources = True
        self.show_buildings = True
        self.status_msg = "Level Editor - Select a tool to begin"
        self.status_time = time.time()
        self.dialog = None  # ("save", ...) or ("load", ...) or ("name", ...) or ("goal_edit", ...)
        self.dialog_input = ""
        self.dialog_cursor = 0
        self.file_list = []
        self.file_scroll = 0
        self._goal_btn_rects = []
        self._dialog_hover_rect = None

        # Properties panel - selected building info
        self.prop_building = None  # building at cursor
        self._pending_action = None

        # Time
        self.t = 0.0

    def set_status(self, msg):
        self.status_msg = msg
        self.status_time = time.time()

    def push_undo(self, action):
        self.undo_stack.append(action)
        if len(self.undo_stack) > 200: self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.unsaved = True

    def pop_undo(self):
        if not self.undo_stack: return False
        a = self.undo_stack.pop()
        self.redo_stack.append(a)
        self._apply_undo_action(a, True)
        self.unsaved = True
        return True

    def pop_redo(self):
        if not self.redo_stack: return False
        a = self.redo_stack.pop()
        self.undo_stack.append(a)
        self._apply_undo_action(a, False)
        self.unsaved = True
        return True

    def _apply_undo_action(self, action, is_undo):
        """Apply or reverse an undo action."""
        atype = action[0]
        if atype == "place_resource":
            x, y, data = action[1], action[2], action[3]
            if is_undo:
                # Remove the resource
                if (x, y) in self.world.rmap:
                    n = self.world.rmap[(x, y)]
                    self.world.resources.remove(n)
                    del self.world.rmap[(x, y)]
            else:
                # Re-add
                s = Shape(data["tf"], data["tc"],
                          Form(data["bf"]) if data.get("bf") is not None else None,
                          Col(data["bc"]) if data.get("bc") is not None else None)
                n = ResourceNode(x, y, s)
                if (x, y) not in self.world.rmap:
                    self.world.resources.append(n)
                    self.world.rmap[(x, y)] = n
        elif atype == "remove_resource":
            x, y, data = action[1], action[2], action[3]
            if is_undo:
                s = Shape(data["tf"], data["tc"],
                          Form(data["bf"]) if data.get("bf") is not None else None,
                          Col(data["bc"]) if data.get("bc") is not None else None)
                n = ResourceNode(x, y, s)
                if (x, y) not in self.world.rmap:
                    self.world.resources.append(n)
                    self.world.rmap[(x, y)] = n
            else:
                if (x, y) in self.world.rmap:
                    n = self.world.rmap[(x, y)]
                    self.world.resources.remove(n)
                    del self.world.rmap[(x, y)]
        elif atype == "place_building":
            x, y = action[1], action[2]
            if is_undo:
                b = self.world.buildings.pop((x, y), None)
                if b and b.bt == BType.MINER:
                    n = self.world.rmap.get((x, y))
                    if n: n.mined = False
            else:
                b = action[3]
                if (x, y) not in self.world.buildings:
                    self.world.buildings[(x, y)] = b
                    if b.bt == BType.MINER:
                        n = self.world.rmap.get((x, y))
                        if n: n.mined = True
        elif atype == "remove_building":
            x, y = action[1], action[2]
            if is_undo:
                b = action[3]
                if (x, y) not in self.world.buildings:
                    self.world.buildings[(x, y)] = b
                    if b.bt == BType.MINER:
                        n = self.world.rmap.get((x, y))
                        if n: n.mined = True
            else:
                b = self.world.buildings.pop((x, y), None)
                if b and b.bt == BType.MINER:
                    n = self.world.rmap.get((x, y))
                    if n: n.mined = False
        elif atype == "place_goal":
            idx = action[1]
            gdata = action[2]
            if is_undo:
                if idx < len(self.world.goals):
                    self.world.goals.pop(idx)
            else:
                s = Shape(gdata["tf"], gdata["tc"],
                          Form(gdata["bf"]) if gdata.get("bf") is not None else None,
                          Col(gdata["bc"]) if gdata.get("bc") is not None else None)
                g = Goal(gdata["gid"], s, gdata["req"], 0, False, gdata["pts"])
                self.world.goals.insert(idx, g)
                self.world.next_gid = max(self.world.next_gid, g.gid + 1)
        elif atype == "remove_goal":
            idx = action[1]
            gdata = action[2]
            if is_undo:
                s = Shape(gdata["tf"], gdata["tc"],
                          Form(gdata["bf"]) if gdata.get("bf") is not None else None,
                          Col(gdata["bc"]) if gdata.get("bc") is not None else None)
                g = Goal(gdata["gid"], s, gdata["req"], 0, False, gdata["pts"])
                self.world.goals.insert(idx, g)
                self.world.next_gid = max(self.world.next_gid, g.gid + 1)
            else:
                if idx < len(self.world.goals):
                    self.world.goals.pop(idx)
        elif atype == "clear_all":
            old_resources = action[1]
            old_buildings = action[2]
            old_goals = action[3]
            if is_undo:
                self.world.resources = old_resources
                self.world.rmap = {(n.x, n.y): n for n in old_resources}
                self.world.buildings = old_buildings
                self.world.goals = old_goals
                self.world.next_gid = len(old_goals)
            # redo of clear is already done
        elif atype == "fill_resources":
            tiles = action[1]  # list of (x, y, data)
            if is_undo:
                for x, y, data in tiles:
                    if (x, y) in self.world.rmap:
                        n = self.world.rmap[(x, y)]
                        self.world.resources.remove(n)
                        del self.world.rmap[(x, y)]
            else:
                for x, y, data in tiles:
                    if (x, y) not in self.world.rmap:
                        s = Shape(data["tf"], data["tc"],
                                  Form(data["bf"]) if data.get("bf") is not None else None,
                                  Col(data["bc"]) if data.get("bc") is not None else None)
                        n = ResourceNode(x, y, s)
                        self.world.resources.append(n)
                        self.world.rmap[(x, y)] = n

    def do_place_resource(self, x, y):
        if abs(x) >= WORLD_SIZE or abs(y) >= WORLD_SIZE: return False
        if (x, y) in self.world.rmap: return False
        s = Shape(self.sel_form, self.paint_col)
        n = ResourceNode(x, y, s)
        self.world.resources.append(n)
        self.world.rmap[(x, y)] = n
        data = {"tf": int(s.tf), "tc": int(s.tc), "bf": None, "bc": None}
        self.push_undo(("place_resource", x, y, data))
        self.set_status(f"Placed {FORM_NAME[s.tf]} ({COL_NAME[s.tc]}) at ({x},{y})")
        return True

    def do_erase_tile(self, x, y):
        """Erase whatever is at (x,y): resource or building."""
        # Try building first
        b = self.world.buildings.get((x, y))
        if b:
            self.push_undo(("remove_building", x, y, copy.deepcopy(b)))
            if b.bt == BType.MINER:
                n = self.world.rmap.get((x, y))
                if n: n.mined = False
            del self.world.buildings[(x, y)]
            self.world.miner_cd.pop((x, y), None)
            self.world.bextra.pop((x, y), None)
            self.set_status(f"Removed {BNAME.get(b.bt, '?')} at ({x},{y})")
            return True
        # Try resource
        n = self.world.rmap.get((x, y))
        if n and not n.mined:
            data = {"tf": int(n.shape.tf), "tc": int(n.shape.tc),
                    "bf": int(n.shape.bf) if n.shape.bf else None,
                    "bc": int(n.shape.bc) if n.shape.bc else None}
            self.push_undo(("remove_resource", x, y, data))
            self.world.resources.remove(n)
            del self.world.rmap[(x, y)]
            self.set_status(f"Removed resource at ({x},{y})")
            return True
        return False

    def do_place_building(self, x, y):
        bt = self.sel_btype
        d = self.sel_dir
        if abs(x) >= WORLD_SIZE or abs(y) >= WORLD_SIZE: return False
        if (x, y) in self.world.buildings: return False
        if bt == BType.MINER:
            n = self.world.rmap.get((x, y))
            if not n or n.mined: return False
            n.mined = True
            b = Building(bt, x, y, d, prod=Shape(n.shape.tf, n.shape.tc))
        elif bt == BType.PAINTER:
            b = Building(bt, x, y, d, pcol=self.paint_col)
        elif bt == BType.FILTER_FORM:
            b = Building(bt, x, y, d, target_form=self.sel_form)
        elif bt == BType.FORM_CHANGE:
            b = Building(bt, x, y, d, target_form=self.sel_form)
        elif bt == BType.FILTER_COLOR:
            b = Building(bt, x, y, d, pcol=self.paint_col)
        elif bt == BType.CRAFTER:
            b = Building(bt, x, y, d,
                         recipe_in=Shape(Form.CIRCLE, Col.RED),
                         recipe_out=Shape(self.sel_form, self.paint_col))
        elif bt == BType.EMITTER:
            b = Building(bt, x, y, d, prod=Shape(self.sel_form, self.paint_col))
        elif bt == BType.SELECTOR:
            b = Building(bt, x, y, d, target_form=self.sel_form)
        else:
            b = Building(bt, x, y, d)
        self.world.buildings[(x, y)] = b
        self.push_undo(("place_building", x, y, copy.deepcopy(b)))
        self.set_status(f"Placed {BNAME.get(bt, '?')} at ({x},{y})")
        return True

    def do_add_goal(self):
        bf = self.goal_bf if self.goal_layered else None
        bc = self.goal_bc if self.goal_layered else None
        s = Shape(self.goal_form, self.goal_col, bf, bc)
        g = Goal(self.world.next_gid, s, self.goal_req, 0, False, 100)
        gdata = {"gid": g.gid, "tf": int(s.tf), "tc": int(s.tc),
                 "bf": int(s.bf) if s.bf else None, "bc": int(s.bc) if s.bc else None,
                 "req": g.req, "pts": g.pts}
        self.world.goals.append(g)
        self.world.next_gid += 1
        self.push_undo(("place_goal", len(self.world.goals) - 1, gdata))
        self.set_status(f"Added goal: {s.label()} x{self.goal_req}")

    def do_remove_goal(self, idx):
        if 0 <= idx < len(self.world.goals):
            g = self.world.goals[idx]
            gdata = {"gid": g.gid, "tf": int(g.shape.tf), "tc": int(g.shape.tc),
                     "bf": int(g.shape.bf) if g.shape.bf else None,
                     "bc": int(g.shape.bc) if g.shape.bc else None,
                     "req": g.req, "pts": g.pts}
            self.push_undo(("remove_goal", idx, gdata))
            self.world.goals.pop(idx)
            self.set_status(f"Removed goal #{idx}")

    def do_clear_all(self):
        old_res = copy.deepcopy(self.world.resources)
        old_bld = copy.deepcopy(self.world.buildings)
        old_goals = copy.deepcopy(self.world.goals)
        self.push_undo(("clear_all", old_res, old_bld, old_goals))
        self.world.resources = []
        self.world.rmap = {}
        self.world.buildings = {}
        self.world.goals = []
        self.world.shapes = []
        self.world.bextra = {}
        self.world.miner_cd = {}
        self.world.next_gid = 0
        self.selected_tiles.clear()
        self.set_status("Cleared all")

    def do_fill_area(self, cx, cy):
        """Fill an area with resources using brush_size."""
        tiles = []
        half = self.brush_size // 2
        for dx in range(-half, half + 1):
            for dy in range(-half, half + 1):
                x, y = cx + dx, cy + dy
                if abs(x) >= WORLD_SIZE or abs(y) >= WORLD_SIZE: continue
                if (x, y) in self.world.rmap: continue
                if (x, y) in self.world.buildings: continue
                s = Shape(self.sel_form, self.paint_col)
                n = ResourceNode(x, y, s)
                self.world.resources.append(n)
                self.world.rmap[(x, y)] = n
                tiles.append((x, y, {"tf": int(s.tf), "tc": int(s.tc), "bf": None, "bc": None}))
        if tiles:
            self.push_undo(("fill_resources", tiles))
            self.set_status(f"Filled {len(tiles)} tiles with resources")

    def do_eyedrop(self, x, y):
        """Pick the shape from a resource or building at cursor."""
        b = self.world.buildings.get((x, y))
        if b:
            if b.prod:
                self.sel_form = b.prod.tf
                self.paint_col = b.prod.tc
                self.set_status(f"Picked: {FORM_NAME[self.sel_form]} {COL_NAME[self.paint_col]} (from {BNAME.get(b.bt,'?')})")
                return
            if b.pcol is not None:
                self.paint_col = b.pcol
                self.set_status(f"Picked color: {COL_NAME[self.paint_col]}")
                return
            if b.target_form is not None:
                self.sel_form = b.target_form
                self.set_status(f"Picked form: {FORM_NAME[self.sel_form]}")
                return
        n = self.world.rmap.get((x, y))
        if n and not n.mined:
            self.sel_form = n.shape.tf
            self.paint_col = n.shape.tc
            if n.shape.bf:
                self.goal_layered = True
                self.goal_bf = n.shape.bf
                self.goal_bc = n.shape.bc or n.shape.tc
            self.set_status(f"Picked: {n.shape.label()}")

    def save_level(self, filename):
        ld = LevelData().from_world(self.world, self.level_name, self.level_author)
        path = ld.save_to_file(filename)
        self.unsaved = False
        self.set_status(f"Saved to {filename}")
        return path

    def load_level(self, filename):
        ld = LevelData.load_from_file(filename)
        self.world = ld.to_world()
        self.level_name = ld.name
        self.level_author = ld.author
        self.unsaved = False
        self.selected_tiles.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.set_status(f"Loaded {filename}")

    def get_test_world(self):
        """Return a copy of the world for testing (play mode)."""
        ld = LevelData().from_world(self.world, self.level_name, self.level_author)
        return ld.to_world()

    # ── Rendering ────────────────────────────────────────────────────────────

    def render(self):
        sw, sh = self.screen.get_size()
        self.vp = Viewport(sw, sh)
        self.vp.t = self.t

        # Create a fake player state for rendering
        class FakePlayer:
            pass
        fp = FakePlayer()
        fp.pid = 0; fp.name = "Editor"; fp.color = (100, 220, 255)
        fp.cx = self.cx; fp.cy = self.cy
        fp.sel_btype = self.sel_btype; fp.sel_dir = self.sel_dir
        fp.paint_col = self.paint_col; fp.toolbar_page = self.toolbar_page
        fp.has_mouse = True

        class FakeCam:
            pass
        fc = FakeCam()
        fc.cam_x = self.cam_x; fc.cam_y = self.cam_y
        fc.cam_zoom = self.cam_zoom

        # Render world
        self.vp.render(self.world, fc, fp, [fp], self.particles, show_ghost=False)

        # Editor overlays
        self._draw_selection_overlay(fc)
        self._draw_tool_panel()
        self._draw_properties_panel()
        self._draw_top_menu()
        self._draw_bottom_bar()
        self._draw_cursor(fc)
        self._draw_ghost(fc)

        # Dialog
        if self.dialog:
            self._draw_dialog()

    def _draw_cursor(self, cam):
        sx, sy = self.vp.w2s(self.cx, self.cy, cam)
        if not (0 <= sx < self.vp.w and 0 <= sy < self.vp.h): return
        pulse = 1 + 0.2 * math.sin(self.t * 4)
        pr = int(8 * pulse)
        c = (100, 220, 255)
        pygame.draw.rect(self.vp.surf, c, (sx - pr, sy - pr, pr * 2, pr * 2), 2, border_radius=2)

    def _draw_ghost(self, cam):
        r = self.vp.wrect(self.cx - 0.5, self.cy - 0.5, 1, 1, cam)
        if not self.vp.on_scr(r): return
        s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        if self.tool == EditorTool.RESOURCE:
            ok = (self.cx, self.cy) not in self.world.rmap and (self.cx, self.cy) not in self.world.buildings
        elif self.tool == EditorTool.BUILDING:
            ok = (self.cx, self.cy) not in self.world.buildings
            if self.sel_btype == BType.MINER:
                ok = ok and (self.cx, self.cy) in self.world.rmap and not self.world.rmap[(self.cx, self.cy)].mined
        elif self.tool == EditorTool.ERASE:
            ok = (self.cx, self.cy) in self.world.buildings or (self.cx, self.cy) in self.world.rmap
        else:
            ok = False
        c = (100, 255, 100, 60) if ok else (255, 80, 80, 60)
        bc = (100, 255, 100, 140) if ok else (255, 80, 80, 140)
        pygame.draw.rect(s, c, (0, 0, r.w, r.h), border_radius=max(1, r.w // 8))
        pygame.draw.rect(s, bc, (0, 0, r.w, r.h), width=2, border_radius=max(1, r.w // 8))

        # Show brush size for fill tool
        if self.tool == EditorTool.FILL:
            half = self.brush_size // 2
            for dx in range(-half, half + 1):
                for dy in range(-half, half + 1):
                    if dx == 0 and dy == 0: continue
                    bx, by = self.cx + dx, self.cy + dy
                    br = self.vp.wrect(bx - 0.5, by - 0.5, 1, 1, cam)
                    if not self.vp.on_scr(br): continue
                    bs = pygame.Surface((br.w, br.h), pygame.SRCALPHA)
                    occ = (bx, by) in self.world.rmap or (bx, by) in self.world.buildings
                    bc2 = (255, 80, 80, 80) if occ else (100, 255, 100, 50)
                    pygame.draw.rect(bs, bc2, (0, 0, br.w, br.h))
                    self.vp.surf.blit(bs, br.topleft)

        self.vp.surf.blit(s, r.topleft)

    def _draw_selection_overlay(self, cam):
        """Draw selection rectangle and highlight selected buildings."""
        # Highlight selected tiles
        for (tx, ty) in self.selected_tiles:
            r = self.vp.wrect(tx - 0.5, ty - 0.5, 1, 1, cam)
            if not self.vp.on_scr(r): continue
            s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            pygame.draw.rect(s, (100, 200, 255, 60), (0, 0, r.w, r.h))
            pygame.draw.rect(s, (100, 200, 255, 180), (0, 0, r.w, r.h), width=2)
            self.vp.surf.blit(s, r.topleft)

        # Selection rectangle (while dragging)
        if self.sel_rect_start and self.sel_rect_end and self.tool == EditorTool.SELECT:
            x0 = min(self.sel_rect_start[0], self.sel_rect_end[0])
            y0 = min(self.sel_rect_start[1], self.sel_rect_end[1])
            x1 = max(self.sel_rect_start[0], self.sel_rect_end[0])
            y1 = max(self.sel_rect_start[1], self.sel_rect_end[1])
            s0 = self.vp.w2s(x0, y0, cam)
            s1 = self.vp.w2s(x1 + 1, y1 + 1, cam)
            rect = pygame.Rect(s0[0], s0[1], s1[0] - s0[0], s1[1] - s0[1])
            s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.rect(s, (100, 200, 255, 30), (0, 0, rect.w, rect.h))
            pygame.draw.rect(s, (100, 200, 255, 200), (0, 0, rect.w, rect.h), width=2)
            self.vp.surf.blit(s, rect.topleft)

    def _draw_tool_panel(self):
        """Left-side tool palette."""
        pw = 56
        ph = len(EditorTool) * 34 + 12
        px, py = 4, 44
        s = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(s, (12, 14, 20, 220), (0, 0, pw, ph), border_radius=4)
        pygame.draw.rect(s, (50, 52, 65), (0, 0, pw, ph), width=1, border_radius=4)
        s.blit(self.vp.ftiny.render("TOOLS", True, (180, 182, 195)), (4, 2))
        for i, et in enumerate(EditorTool):
            y = 16 + i * 34
            sel = et == self.tool
            c = (80, 180, 255) if sel else (60, 62, 75)
            if sel:
                pygame.draw.rect(s, (*c, 80), (2, y, pw - 4, 30), border_radius=3)
                pygame.draw.rect(s, c, (2, y, pw - 4, 30), width=1, border_radius=3)
            name = ETOOL_NAME[et]
            key = ETOOL_KEY[et]
            tc = (255, 255, 255) if sel else (140, 142, 155)
            s.blit(self.vp.ftiny.render(name[:6], True, tc), (4, y + 2))
            s.blit(self.vp.ftiny.render(f"[{key}]", True, (90, 92, 105)), (4, y + 15))
        self.vp.surf.blit(s, (px, py))

    def _draw_properties_panel(self):
        """Right-side properties panel showing context-dependent info."""
        pw = 180
        ph = 300
        px = self.vp.w - pw - 4
        py = 44
        s = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(s, (12, 14, 20, 220), (0, 0, pw, ph), border_radius=4)
        pygame.draw.rect(s, (50, 52, 65), (0, 0, pw, ph), width=1, border_radius=4)

        y = 4
        s.blit(self.vp.ft.render("PROPERTIES", True, (180, 182, 195)), (4, y)); y += 18

        # Cursor position
        s.blit(self.vp.ftiny.render(f"Cursor: ({self.cx}, {self.cy})", True, (140, 142, 155)), (4, y)); y += 14

        # Selected tool info
        s.blit(self.vp.ftiny.render(f"Tool: {ETOOL_NAME[self.tool]}", True, (100, 220, 255)), (4, y)); y += 16

        # Resource at cursor
        n = self.world.rmap.get((self.cx, self.cy))
        if n and not n.mined:
            s.blit(self.vp.ftiny.render("Resource:", True, (180, 200, 100)), (4, y)); y += 13
            s.blit(self.vp.ftiny.render(f" {n.shape.label()}", True, (200, 200, 200)), (4, y)); y += 14
        # Building at cursor
        b = self.world.buildings.get((self.cx, self.cy))
        if b:
            s.blit(self.vp.ftiny.render("Building:", True, (180, 200, 100)), (4, y)); y += 13
            s.blit(self.vp.ftiny.render(f" {BNAME.get(b.bt, '?')} Dir:{['>','v','<','^'][b.d]}", True, (200, 200, 200)), (4, y)); y += 14
            if b.pcol is not None:
                c = COL_RGB.get(b.pcol, (200, 200, 200))
                s.blit(self.vp.ftiny.render(f" Color: {COL_NAME[b.pcol]}", True, c), (4, y)); y += 14
            if b.target_form is not None:
                s.blit(self.vp.ftiny.render(f" Form: {FORM_NAME[b.target_form]}", True, (200, 200, 200)), (4, y)); y += 14
            if b.prod:
                s.blit(self.vp.ftiny.render(f" Prod: {b.prod.label()}", True, (200, 200, 200)), (4, y)); y += 14

        y += 4
        # Current selections
        pygame.draw.line(s, (50, 52, 65), (4, y), (pw - 4, y)); y += 6
        s.blit(self.vp.ftiny.render("Current:", True, (180, 182, 195)), (4, y)); y += 14

        if self.tool in (EditorTool.RESOURCE, EditorTool.FILL, EditorTool.GOAL):
            fc = COL_RGB.get(self.paint_col, (200, 200, 200))
            s.blit(self.vp.ftiny.render(f"Shape: {FORM_NAME[self.sel_form]}", True, (200, 200, 200)), (4, y)); y += 13
            s.blit(self.vp.ftiny.render(f"Color: {COL_NAME[self.paint_col]}", True, fc), (4, y)); y += 13
            # Color swatch
            pygame.draw.rect(s, fc, (4, y, 20, 12), border_radius=2)
            y += 16
            if self.tool == EditorTool.FILL:
                s.blit(self.vp.ftiny.render(f"Brush: {self.brush_size}x{self.brush_size}", True, (200, 200, 200)), (4, y)); y += 14
        elif self.tool == EditorTool.BUILDING:
            s.blit(self.vp.ftiny.render(f"Building: {BNAME.get(self.sel_btype, '?')}", True, (200, 200, 200)), (4, y)); y += 14
            s.blit(self.vp.ftiny.render(f"Dir: {['>','v','<','^'][self.sel_dir]}", True, (200, 200, 200)), (4, y)); y += 14
        elif self.tool == EditorTool.GOAL:
            s.blit(self.vp.ftiny.render(f"Req: {self.goal_req}", True, (200, 200, 200)), (4, y)); y += 13
            s.blit(self.vp.ftiny.render(f"Layered: {self.goal_layered}", True, (200, 200, 200)), (4, y)); y += 14

        # Selection count
        if self.selected_tiles:
            y += 4
            pygame.draw.line(s, (50, 52, 65), (4, y), (pw - 4, y)); y += 6
            s.blit(self.vp.ftiny.render(f"Selected: {len(self.selected_tiles)} tiles", True, (100, 200, 255)), (4, y))

        # Undo/Redo info
        y = ph - 30
        pygame.draw.line(s, (50, 52, 65), (4, y), (pw - 4, y)); y += 6
        s.blit(self.vp.ftiny.render(f"Undo:{len(self.undo_stack)} Redo:{len(self.redo_stack)}", True, (90, 92, 105)), (4, y))

        self.vp.surf.blit(s, (px, py))

    def _draw_top_menu(self):
        """Top menu bar."""
        mh = 24
        s = pygame.Surface((self.vp.w, mh), pygame.SRCALPHA)
        pygame.draw.rect(s, (16, 18, 26, 230), (0, 0, self.vp.w, mh))
        pygame.draw.line(s, (50, 52, 65), (0, mh - 1), (self.vp.w, mh - 1))

        # Level name
        unsaved_marker = " *" if self.unsaved else ""
        s.blit(self.vp.ftiny.render(f"Level: {self.level_name}{unsaved_marker}", True, (255, 220, 80)), (6, 6))

        # Menu items
        items = [
            ("New[N]", 200), ("Save[S]", 270), ("Load[L]", 340),
            ("Test[F5]", 410), ("Back[ESC]", 490),
        ]
        for text, x in items:
            s.blit(self.vp.ftiny.render(text, True, (140, 180, 220)), (x, 6))

        # View toggles
        vx = 590
        if self.show_grid:
            s.blit(self.vp.ftiny.render("Grid[1]", True, (100, 220, 100)), (vx, 6))
        else:
            s.blit(self.vp.ftiny.render("Grid[1]", True, (100, 100, 100)), (vx, 6))
        vx += 70
        if self.show_resources:
            s.blit(self.vp.ftiny.render("Res[2]", True, (100, 220, 100)), (vx, 6))
        else:
            s.blit(self.vp.ftiny.render("Res[2]", True, (100, 100, 100)), (vx, 6))
        vx += 60
        if self.show_buildings:
            s.blit(self.vp.ftiny.render("Bld[3]", True, (100, 220, 100)), (vx, 6))
        else:
            s.blit(self.vp.ftiny.render("Bld[3]", True, (100, 100, 100)), (vx, 6))

        # Stats
        stats_text = f"Resources:{len(self.world.resources)} Buildings:{len(self.world.buildings)} Goals:{len(self.world.goals)}"
        st = self.vp.ftiny.render(stats_text, True, (90, 92, 105))
        s.blit(st, (self.vp.w - st.get_width() - 6, 6))

        self.vp.surf.blit(s, (0, 0))

    def _draw_bottom_bar(self):
        """Bottom status bar and hints."""
        bh = 32
        ty = self.vp.h - bh
        s = pygame.Surface((self.vp.w, bh), pygame.SRCALPHA)
        pygame.draw.rect(s, (12, 14, 20, 230), (0, 0, self.vp.w, bh))
        pygame.draw.line(s, (50, 52, 65), (0, 0), (self.vp.w, 0))

        # Status message
        s.blit(self.vp.ftiny.render(self.status_msg, True, (180, 220, 180)), (6, 4))

        # Controls hints based on tool
        hints = {
            EditorTool.SELECT: "LClick:Select LDrag:BoxSel Del:DeleteSelected Ctrl+A:SelectAll",
            EditorTool.RESOURCE: "LClick:Place Q:Color E:Form R:Rotate(miner)",
            EditorTool.BUILDING: "LClick:Place R:Rotate Q:Color E:Form Tab:Page 1-8:Tool",
            EditorTool.GOAL: "Click panel below to add. L/R arrows adjust. Del removes last.",
            EditorTool.ERASE: "LClick:Erase tile Shift+Click:Drag erase",
            EditorTool.PAN: "LClick+Drag or MMB:Pan Scroll:Zoom",
            EditorTool.FILL: "LClick:Fill [ ]:BrushSize Q:Color E:Form",
            EditorTool.EYEDROPPER: "LClick:Pick shape/color from tile",
        }
        hint = hints.get(self.tool, "")
        s.blit(self.vp.ftiny.render(hint, True, (70, 72, 85)), (6, 18))

        # Undo/Redo hints
        ur = "Ctrl+Z:Undo Ctrl+Y:Redo"
        ut = self.vp.ftiny.render(ur, True, (70, 72, 85))
        s.blit(ut, (self.vp.w - ut.get_width() - 6, 18))

        self.vp.surf.blit(s, (0, ty))

        # Goal editor bar (when GOAL tool selected)
        if self.tool == EditorTool.GOAL:
            self._draw_goal_bar(ty - 70)

    def _draw_goal_bar(self, y):
        """Draw goal editing sub-panel above bottom bar."""
        pw = self.vp.w - 8
        ph = 66
        px = 4
        s = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(s, (12, 14, 20, 230), (0, 0, pw, ph), border_radius=4)
        pygame.draw.rect(s, (50, 52, 65), (0, 0, pw, ph), width=1, border_radius=4)

        s.blit(self.vp.ftiny.render("GOAL EDITOR", True, (255, 220, 80)), (6, 2))

        # Current goal shape preview
        preview_x = 6
        preview_y = 16
        fc = COL_RGB.get(self.goal_col, (200, 200, 200))
        # Draw shape icon
        r = 10
        form = self.goal_form
        if form == Form.CIRCLE:
            pygame.draw.circle(s, fc, (preview_x + r, preview_y + r), r)
        elif form == Form.SQUARE:
            pygame.draw.rect(s, fc, (preview_x, preview_y, r * 2, r * 2))
        elif form == Form.TRI:
            pygame.draw.polygon(s, fc, [(preview_x + r, preview_y), (preview_x, preview_y + r * 2), (preview_x + r * 2, preview_y + r * 2)])
        else:
            pygame.draw.circle(s, fc, (preview_x + r, preview_y + r), r)
        if self.goal_layered:
            bc = COL_RGB.get(self.goal_bc, (180, 180, 180))
            pygame.draw.circle(s, bc, (preview_x + r - 2, preview_y + r - 2), r - 2)

        # Info
        info_x = preview_x + r * 2 + 10
        label = f"{FORM_NAME[self.goal_form]} {COL_NAME[self.goal_col]}"
        if self.goal_layered:
            label += f" + {FORM_NAME[self.goal_bf]} {COL_NAME[self.goal_bc]}"
        s.blit(self.vp.ftiny.render(label, True, (200, 200, 200)), (info_x, preview_y))
        s.blit(self.vp.ftiny.render(f"x{self.goal_req}  Layered:{self.goal_layered}", True, (160, 162, 175)), (info_x, preview_y + 13))

        # Buttons
        btn_y = preview_y + 30
        btns = [
            ("+Add Goal", 6, (60, 160, 60)),
            ("Form[L/R]", 90, (60, 100, 160)),
            ("Color[Q]", 175, (160, 100, 60)),
            (f"Req[+/-]:{self.goal_req}", 255, (100, 100, 140)),
            ("Layer[T]", 375, (120, 100, 140)),
            ("DelLast[Del]", 445, (160, 60, 60)),
        ]
        self._goal_btn_rects = []
        for text, bx, color in btns:
            bw = self.vp.ftiny.size(text)[0] + 10
            rect = pygame.Rect(bx, btn_y, bw, 18)
            pygame.draw.rect(s, (*color, 150), rect, border_radius=3)
            pygame.draw.rect(s, color, rect, width=1, border_radius=3)
            s.blit(self.vp.ftiny.render(text, True, (220, 220, 220)), (bx + 5, btn_y + 3))
            self._goal_btn_rects.append(rect)

        # Existing goals list
        gx = 580
        s.blit(self.vp.ftiny.render("Goals:", True, (180, 182, 195)), (gx, 16))
        for i, g in enumerate(self.world.goals[-3:]):
            real_i = len(self.world.goals) - 3 + i
            if real_i < 0: continue
            gc = COL_RGB.get(g.shape.tc, (200, 200, 100))
            gt = f"#{real_i}: {g.shape.label()} x{g.req}"
            if g.completed:
                gt += " DONE"
            s.blit(self.vp.ftiny.render(gt, True, gc), (gx, 30 + i * 13))

        self.vp.surf.blit(s, (px, y))

    def _draw_dialog(self):
        """Draw modal dialog overlay."""
        dw, dh = 450, 350
        dx = (self.vp.w - dw) // 2
        dy = (self.vp.h - dh) // 2
        # Dim background
        dim = pygame.Surface((self.vp.w, self.vp.h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        self.vp.surf.blit(dim, (0, 0))

        s = pygame.Surface((dw, dh), pygame.SRCALPHA)
        pygame.draw.rect(s, (20, 22, 32, 245), (0, 0, dw, dh), border_radius=6)
        pygame.draw.rect(s, (80, 82, 100), (0, 0, dw, dh), width=2, border_radius=6)

        dtype = self.dialog[0]
        y = 12
        if dtype == "save":
            s.blit(self.vp.fm.render("Save Level", True, (255, 220, 80)), (12, y)); y += 28
            s.blit(self.vp.ftiny.render(f"Filename (in levels/ folder):", True, (180, 182, 195)), (12, y)); y += 16
            # Input box
            self._dialog_rect = pygame.Rect(12, y, dw - 24, 24)
            pygame.draw.rect(s, (30, 32, 45), self._dialog_rect, border_radius=3)
            pygame.draw.rect(s, (100, 200, 255), self._dialog_rect, width=1, border_radius=3)
            cursor_blink = int(time.time() * 2) % 2 == 0
            display_text = self.dialog_input
            if cursor_blink:
                display_text = display_text[:self.dialog_cursor] + "|" + display_text[self.dialog_cursor:]
            s.blit(self.vp.fs.render(display_text, True, (220, 220, 220)), (16, y + 4))
            y += 34
            s.blit(self.vp.ftiny.render("Enter: Confirm | Esc: Cancel", True, (120, 122, 135)), (12, y))
            y += 20
            if not self.dialog_input.endswith('.json'):
                s.blit(self.vp.ftiny.render("(will add .json if missing)", True, (100, 102, 115)), (12, y))

        elif dtype == "load":
            s.blit(self.vp.fm.render("Load Level", True, (255, 220, 80)), (12, y)); y += 28
            self.file_list = LevelData.list_files()
            if not self.file_list:
                s.blit(self.vp.fs.render("No saved levels found.", True, (160, 162, 175)), (12, y))
                s.blit(self.vp.ftiny.render(f"Create levels/ folder: {LEVELS_DIR}", True, (100, 102, 115)), (12, y + 20))
            else:
                s.blit(self.vp.ftiny.render("Click to select, Enter to load, Esc to cancel:", True, (180, 182, 195)), (12, y))
                y += 18
                self._file_rects = []
                max_visible = min(10, len(self.file_list) - self.file_scroll)
                for i in range(max_visible):
                    fi = i + self.file_scroll
                    if fi >= len(self.file_list): break
                    fname = self.file_list[fi]
                    fr = pygame.Rect(12, y + i * 22, dw - 24, 20)
                    hover = self._dialog_hover_rect and fr.collidepoint(self._dialog_hover_rect.topleft)
                    c = (40, 42, 58) if hover else (28, 30, 42)
                    pygame.draw.rect(s, c, fr, border_radius=3)
                    pygame.draw.rect(s, (60, 62, 78), fr, width=1, border_radius=3)
                    s.blit(self.vp.ftiny.render(fname, True, (200, 200, 210)), (16, y + i * 22 + 3))
                    self._file_rects.append((fr, fname))
                if len(self.file_list) > 10:
                    s.blit(self.vp.ftiny.render(f"Scroll: {self.file_scroll + 1}-{min(self.file_scroll + 10, len(self.file_list))}/{len(self.file_list)}", True, (90, 92, 105)), (12, y + max_visible * 22 + 4))

        elif dtype == "name":
            s.blit(self.vp.fm.render("Set Level Name", True, (255, 220, 80)), (12, y)); y += 28
            s.blit(self.vp.ftiny.render("Level name:", True, (180, 182, 195)), (12, y)); y += 16
            self._dialog_rect = pygame.Rect(12, y, dw - 24, 24)
            pygame.draw.rect(s, (30, 32, 45), self._dialog_rect, border_radius=3)
            pygame.draw.rect(s, (100, 200, 255), self._dialog_rect, width=1, border_radius=3)
            cursor_blink = int(time.time() * 2) % 2 == 0
            display_text = self.dialog_input
            if cursor_blink:
                display_text = display_text[:self.dialog_cursor] + "|" + display_text[self.dialog_cursor:]
            s.blit(self.vp.fs.render(display_text, True, (220, 220, 220)), (16, y + 4))
            y += 34
            s.blit(self.vp.ftiny.render("Enter: Confirm | Esc: Cancel", True, (120, 122, 135)), (12, y))

        elif dtype == "confirm":
            msg = self.dialog[1]
            s.blit(self.vp.fm.render("Confirm", True, (255, 100, 80)), (12, y)); y += 30
            # Word wrap the message
            words = msg.split()
            line = ""
            for w in words:
                test = line + " " + w if line else w
                if self.vp.fs.size(test)[0] < dw - 30:
                    line = test
                else:
                    s.blit(self.vp.fs.render(line, True, (200, 200, 210)), (16, y)); y += 18
                    line = w
            if line:
                s.blit(self.vp.fs.render(line, True, (200, 200, 210)), (16, y)); y += 28
            s.blit(self.vp.ftiny.render("Enter/Y: Confirm | Esc/N: Cancel", True, (120, 122, 135)), (16, y))

        self.vp.surf.blit(s, (dx, dy))

    # ── Main Editor Loop ─────────────────────────────────────────────────────

    def run_editor(self):
        """Main editor loop. Returns True to test-play, False to go back to menu."""
        self._dialog_hover_rect = None
        self._goal_btn_rects = []

        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.t += dt
            sw, sh = self.screen.get_size()
            mouse_pos = pygame.mouse.get_pos()

            # Smooth zoom
            d = self.cam_target_zoom - self.cam_zoom
            if abs(d) > 0.01: self.cam_zoom += d * min(1, dt * 12)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    if self.unsaved:
                        self.dialog = ("confirm", "Unsaved changes! Discard and quit?")
                    else:
                        return False
                elif ev.type == pygame.VIDEORESIZE:
                    pass  # Handled each frame

                # ── Dialog input ──────────────────────────────────────────
                elif self.dialog:
                    dtype = self.dialog[0]
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_ESCAPE:
                            self.dialog = None
                        elif ev.key == pygame.K_RETURN:
                            if dtype == "save":
                                fn = self.dialog_input.strip()
                                if not fn: fn = self.level_name.replace(" ", "_")
                                if not fn.endswith('.json'): fn += '.json'
                                self.save_level(fn)
                                self.dialog = None
                            elif dtype == "name":
                                self.level_name = self.dialog_input.strip() or "Untitled"
                                self.dialog = None
                                self.unsaved = True
                            elif dtype == "confirm":
                                return False
                        elif dtype in ("save", "name"):
                            if ev.key == pygame.K_BACKSPACE:
                                if self.dialog_cursor > 0:
                                    self.dialog_input = self.dialog_input[:self.dialog_cursor - 1] + self.dialog_input[self.dialog_cursor:]
                                    self.dialog_cursor -= 1
                            elif ev.key == pygame.K_DELETE:
                                self.dialog_input = self.dialog_input[:self.dialog_cursor] + self.dialog_input[self.dialog_cursor + 1:]
                            elif ev.key == pygame.K_LEFT:
                                self.dialog_cursor = max(0, self.dialog_cursor - 1)
                            elif ev.key == pygame.K_RIGHT:
                                self.dialog_cursor = min(len(self.dialog_input), self.dialog_cursor + 1)
                            elif ev.key == pygame.K_HOME:
                                self.dialog_cursor = 0
                            elif ev.key == pygame.K_END:
                                self.dialog_cursor = len(self.dialog_input)
                            elif ev.key == pygame.K_a and (ev.mod & pygame.KMOD_CTRL):
                                self.dialog_cursor = 0
                                # Select all - just move cursor
                            elif ev.unicode and ev.unicode.isprintable():
                                self.dialog_input = self.dialog_input[:self.dialog_cursor] + ev.unicode + self.dialog_input[self.dialog_cursor:]
                                self.dialog_cursor += 1
                    elif ev.type == pygame.MOUSEBUTTONDOWN and dtype == "load":
                        if hasattr(self, '_file_rects'):
                            for fr, fname in self._file_rects:
                                if fr.collidepoint(ev.pos):
                                    self.load_level(fname)
                                    self.dialog = None
                                    break
                    elif ev.type == pygame.MOUSEMOTION:
                        self._dialog_hover_rect = ev.pos
                    continue  # Skip normal input while dialog open

                # ── Normal editor input ───────────────────────────────────
                elif ev.type == pygame.MOUSEWHEEL:
                    # Check if over file list in dialog
                    self.cam_target_zoom = max(0.15, min(5.0,
                        self.cam_target_zoom * (1.12 if ev.y > 0 else 1 / 1.12)))

                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    # Middle mouse = pan
                    if ev.button == 2:
                        self.panning = True
                        self.drag_start = ev.pos
                        self.cam_start = (self.cam_x, self.cam_y)
                    elif ev.button == 1:
                        self._handle_left_click(ev.pos, ev.mod)
                    elif ev.button == 3:
                        # Right click = context action based on tool
                        self._handle_right_click(ev.pos)

                elif ev.type == pygame.MOUSEBUTTONUP:
                    if ev.button == 2:
                        self.panning = False
                    elif ev.button == 1:
                        if self.tool == EditorTool.SELECT and self.sel_rect_start:
                            # Finalize selection
                            x0 = min(self.sel_rect_start[0], self.sel_rect_end[0]) if self.sel_rect_end else self.sel_rect_start[0]
                            y0 = min(self.sel_rect_start[1], self.sel_rect_end[1]) if self.sel_rect_end else self.sel_rect_start[1]
                            x1 = max(self.sel_rect_start[0], self.sel_rect_end[0]) if self.sel_rect_end else self.sel_rect_start[0]
                            y1 = max(self.sel_rect_start[1], self.sel_rect_end[1]) if self.sel_rect_end else self.sel_rect_start[1]
                            self.selected_tiles = set()
                            for (bx, by) in self.world.buildings:
                                if x0 <= bx <= x1 and y0 <= by <= y1:
                                    self.selected_tiles.add((bx, by))
                            self.sel_rect_start = None
                            self.sel_rect_end = None
                            if self.selected_tiles:
                                self.set_status(f"Selected {len(self.selected_tiles)} buildings")

                elif ev.type == pygame.MOUSEMOTION:
                    if self.panning:
                        dx = (ev.pos[0] - self.drag_start[0]) / (TILE_SIZE * self.cam_zoom)
                        dy = (ev.pos[1] - self.drag_start[1]) / (TILE_SIZE * self.cam_zoom)
                        self.cam_x = self.cam_start[0] - dx
                        self.cam_y = self.cam_start[1] - dy
                    elif self.tool == EditorTool.SELECT and self.sel_rect_start and pygame.mouse.get_pressed()[0]:
                        wx, wy = self.vp.s2w(ev.pos[0], ev.pos[1], self)
                        self.sel_rect_end = (int(wx), int(wy))
                    elif self.tool == EditorTool.ERASE and pygame.mouse.get_pressed()[0] and (ev.mod & pygame.KMOD_SHIFT):
                        wx, wy = self.vp.s2w(ev.pos[0], ev.pos[1], self)
                        gx, gy = int(round(wx)), int(round(wy))
                        self.do_erase_tile(gx, gy)

                elif ev.type == pygame.KEYDOWN:
                    self._handle_key(ev)

            # ── WASD panning ─────────────────────────────────────────────
            keys = pygame.key.get_pressed()
            pan = 12 / self.cam_zoom * dt
            if keys[pygame.K_a]: self.cam_x -= pan
            if keys[pygame.K_d]: self.cam_x += pan
            if keys[pygame.K_w]: self.cam_y -= pan
            if keys[pygame.K_s]: self.cam_y += pan

            # ── Arrow key cursor ─────────────────────────────────────────
            if keys[pygame.K_LEFT]: self.cx -= 1
            if keys[pygame.K_RIGHT]: self.cx += 1
            if keys[pygame.K_UP]: self.cy -= 1
            if keys[pygame.K_DOWN]: self.cy += 1

            # ── Mouse -> cursor ──────────────────────────────────────────
            if sw > 0 and sh > 0:
                wx, wy = self.vp.s2w(mouse_pos[0], mouse_pos[1], self)
                self.cx, self.cy = int(round(wx)), int(round(wy))

            # ── Particles ────────────────────────────────────────────────
            self.particles.update(dt)

            # ── Render ───────────────────────────────────────────────────
            self.screen.fill((10, 10, 14))
            self.render()
            self.screen.blit(self.vp.surf, (0, 0))

            # FPS
            fps_t = self.vp.ftiny.render(f"FPS:{int(self.clock.get_fps())}", True, (50, 52, 65))
            self.screen.blit(fps_t, (sw - 70, 26))

            pygame.display.flip()

    def _handle_left_click(self, pos, mod):
        """Handle left mouse click in editor."""
        sw, sh = self.screen.get_size()

        # Check top menu clicks
        if pos[1] < 24:
            mx = pos[0]
            if 200 <= mx <= 260:  # New
                if self.unsaved:
                    self.dialog = ("confirm", "Start a new level? Unsaved changes will be lost.")
                    self._pending_action = "new"
                else:
                    self._do_new()
                return
            if 270 <= mx <= 330:  # Save
                self.dialog = ("save",)
                self.dialog_input = self.level_name.replace(" ", "_") + ".json"
                self.dialog_cursor = len(self.dialog_input)
                return
            if 340 <= mx <= 400:  # Load
                self.dialog = ("load",)
                self.file_scroll = 0
                return
            if 410 <= mx <= 470:  # Test
                self._save_temp_and_test()
                return
            if 490 <= mx <= 570:  # Back
                if self.unsaved:
                    self.dialog = ("confirm", "Go back? Unsaved changes will be lost.")
                    self._pending_action = "back"
                else:
                    return  # Will return False from run_editor
                return
            # View toggles
            if 590 <= mx <= 650:
                self.show_grid = not self.show_grid; return
            if 660 <= mx <= 710:
                self.show_resources = not self.show_resources; return
            if 720 <= mx <= 770:
                self.show_buildings = not self.show_buildings; return
            return

        # Check goal editor buttons
        if self.tool == EditorTool.GOAL and hasattr(self, '_goal_btn_rects'):
            for i, rect in enumerate(self._goal_btn_rects):
                if rect.collidepoint(pos):
                    self._handle_goal_btn(i)
                    return

        # Check toolbar area (bottom)
        th = 32
        if pos[1] > sh - th:
            return

        # World click
        wx, wy = self.vp.s2w(pos[0], pos[1], self)
        gx, gy = int(round(wx)), int(round(wy))

        if self.tool == EditorTool.SELECT:
            self.sel_rect_start = (gx, gy)
            self.sel_rect_end = (gx, gy)
            if not (mod & pygame.KMOD_SHIFT):
                self.selected_tiles.clear()
        elif self.tool == EditorTool.RESOURCE:
            if self.do_place_resource(gx, gy):
                self.sfx.play('place')
                self.particles.emit(gx + 0.5, gy + 0.5, (100, 255, 100), 4, 1.5, 0.3)
            else:
                self.sfx.play('error')
        elif self.tool == EditorTool.BUILDING:
            if self.do_place_building(gx, gy):
                self.sfx.play('place')
                self.particles.emit(gx + 0.5, gy + 0.5, (100, 255, 100), 4, 1.5, 0.3)
            else:
                self.sfx.play('error')
        elif self.tool == EditorTool.ERASE:
            if self.do_erase_tile(gx, gy):
                self.sfx.play('remove')
                self.particles.emit(gx + 0.5, gy + 0.5, (255, 80, 80), 5, 2.0, 0.4)
            else:
                self.sfx.play('error')
        elif self.tool == EditorTool.FILL:
            self.do_fill_area(gx, gy)
            self.sfx.play('place')
        elif self.tool == EditorTool.EYEDROPPER:
            self.do_eyedrop(gx, gy)
            self.sfx.play('rotate')

    def _handle_right_click(self, pos):
        """Right click: pick building type from existing building, or quick actions."""
        wx, wy = self.vp.s2w(pos[0], pos[1], self)
        gx, gy = int(round(wx)), int(round(wy))
        b = self.world.buildings.get((gx, gy))
        if b:
            # Pick this building type
            self.sel_btype = b.bt
            self.sel_dir = b.d
            self.tool = EditorTool.BUILDING
            self.set_status(f"Picked {BNAME.get(b.bt, '?')} (now in Building tool)")
            self.sfx.play('rotate')

    def _handle_goal_btn(self, idx):
        """Handle clicks on goal editor buttons."""
        if idx == 0:  # Add Goal
            self.do_add_goal()
            self.sfx.play('place')
        elif idx == 1:  # Cycle form
            forms = list(Form)
            if not self.goal_layered:
                self.goal_form = forms[(forms.index(self.goal_form) + 1) % len(forms)]
            else:
                self.goal_form = forms[(forms.index(self.goal_form) + 1) % len(forms)]
            self.sfx.play('rotate')
        elif idx == 2:  # Cycle color
            colors = list(Col)
            self.goal_col = colors[(colors.index(self.goal_col) + 1) % len(colors)]
            self.sfx.play('rotate')
        elif idx == 3:  # Cycle req
            self.goal_req = max(1, self.goal_req + 1)
            self.sfx.play('rotate')
        elif idx == 4:  # Toggle layered
            self.goal_layered = not self.goal_layered
            self.sfx.play('rotate')
        elif idx == 5:  # Delete last goal
            if self.world.goals:
                self.do_remove_goal(len(self.world.goals) - 1)
                self.sfx.play('remove')

    def _handle_key(self, ev):
        """Handle keyboard input in editor."""
        if ev.key == pygame.K_ESCAPE:
            if self.selected_tiles:
                self.selected_tiles.clear()
                self.set_status("Selection cleared")
            else:
                if self.unsaved:
                    self.dialog = ("confirm", "Go back? Unsaved changes will be lost.")
                    self._pending_action = "back"
                else:
                    raise ReturnToMenu()

        # Tool shortcuts
        elif ev.key == pygame.K_v: self.tool = EditorTool.SELECT; self.selected_tiles.clear()
        elif ev.key == pygame.K_r: self.tool = EditorTool.RESOURCE
        elif ev.key == pygame.K_b: self.tool = EditorTool.BUILDING
        elif ev.key == pygame.K_g: self.tool = EditorTool.GOAL
        elif ev.key == pygame.K_x: self.tool = EditorTool.ERASE
        elif ev.key == pygame.K_h: self.tool = EditorTool.PAN
        elif ev.key == pygame.K_f and not (ev.mod & pygame.KMOD_CTRL): self.tool = EditorTool.FILL
        elif ev.key == pygame.K_i: self.tool = EditorTool.EYEDROPPER

        # Building placement keys (same as game)
        elif ev.key == pygame.K_r and ev.mod & pygame.KMOD_CTRL:
            pass  # Don't trigger tool change on Ctrl+R
        elif self.tool == EditorTool.BUILDING:
            if ev.key == pygame.K_r:
                self.sel_dir = self.sel_dir.cw()
                self.sfx.play('rotate')
            elif ev.key == pygame.K_q:
                cols = list(Col)
                self.paint_col = cols[(cols.index(self.paint_col) + 1) % len(cols)]
                self.sfx.play('rotate')
            elif ev.key == pygame.K_e:
                forms = list(Form)
                self.sel_form = forms[(forms.index(self.sel_form) + 1) % len(forms)]
                self.sfx.play('rotate')
            elif ev.key == pygame.K_TAB:
                total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
                if ev.mod & pygame.KMOD_SHIFT:
                    self.toolbar_page = (self.toolbar_page - 1) % total_pages
                else:
                    self.toolbar_page = (self.toolbar_page + 1) % total_pages
                self.sfx.play('rotate')
            elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                            pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8):
                total_pages = (len(BTOOLS) + TOOLBAR_PER_PAGE - 1) // TOOLBAR_PER_PAGE
                page = self.toolbar_page % total_pages if total_pages > 0 else 0
                page_start = page * TOOLBAR_PER_PAGE
                idx = ev.key - pygame.K_1
                global_idx = page_start + idx
                if global_idx < len(BTOOLS):
                    self.sel_btype = BTOOLS[global_idx]
                    self.sfx.play('rotate')
        elif self.tool == EditorTool.RESOURCE or self.tool == EditorTool.FILL:
            if ev.key == pygame.K_q:
                cols = list(Col)
                self.paint_col = cols[(cols.index(self.paint_col) + 1) % len(cols)]
                self.sfx.play('rotate')
            elif ev.key == pygame.K_e:
                forms = list(Form)
                self.sel_form = forms[(forms.index(self.sel_form) + 1) % len(forms)]
                self.sfx.play('rotate')
            elif ev.key == pygame.K_LEFTBRACKET:
                self.brush_size = max(1, self.brush_size - 1)
                self.set_status(f"Brush size: {self.brush_size}x{self.brush_size}")
            elif ev.key == pygame.K_RIGHTBRACKET:
                self.brush_size = min(9, self.brush_size + 1)
                self.set_status(f"Brush size: {self.brush_size}x{self.brush_size}")

        # Goal tool keys
        elif self.tool == EditorTool.GOAL:
            if ev.key == pygame.K_LEFT:
                forms = list(Form)
                if not self.goal_layered:
                    self.goal_form = forms[(forms.index(self.goal_form) - 1) % len(forms)]
                else:
                    self.goal_bf = forms[(forms.index(self.goal_bf) - 1) % len(forms)]
                self.sfx.play('rotate')
            elif ev.key == pygame.K_RIGHT:
                forms = list(Form)
                if not self.goal_layered:
                    self.goal_form = forms[(forms.index(self.goal_form) + 1) % len(forms)]
                else:
                    self.goal_bf = forms[(forms.index(self.goal_bf) + 1) % len(forms)]
                self.sfx.play('rotate')
            elif ev.key == pygame.K_q:
                colors = list(Col)
                if not self.goal_layered:
                    self.goal_col = colors[(colors.index(self.goal_col) + 1) % len(colors)]
                else:
                    self.goal_bc = colors[(colors.index(self.goal_bc) + 1) % len(colors)]
                self.sfx.play('rotate')
            elif ev.key == pygame.K_EQUALS or ev.key == pygame.K_PLUS:
                self.goal_req = min(99, self.goal_req + 1)
                self.sfx.play('rotate')
            elif ev.key == pygame.K_MINUS:
                self.goal_req = max(1, self.goal_req - 1)
                self.sfx.play('rotate')
            elif ev.key == pygame.K_t:
                self.goal_layered = not self.goal_layered
                self.sfx.play('rotate')
            elif ev.key == pygame.K_DELETE or ev.key == pygame.K_BACKSPACE:
                if self.world.goals:
                    self.do_remove_goal(len(self.world.goals) - 1)
                    self.sfx.play('remove')

        # Common keys
        elif ev.key == pygame.K_n:
            if self.unsaved:
                self.dialog = ("confirm", "Start a new level? Unsaved changes will be lost.")
                self._pending_action = "new"
            else:
                self._do_new()
        elif ev.key == pygame.K_s and (ev.mod & pygame.KMOD_CTRL):
            self.dialog = ("save",)
            self.dialog_input = self.level_name.replace(" ", "_") + ".json"
            self.dialog_cursor = len(self.dialog_input)
        elif ev.key == pygame.K_l:
            self.dialog = ("load",)
            self.file_scroll = 0
        elif ev.key == pygame.K_F5:
            self._save_temp_and_test()
        elif ev.key == pygame.K_F2:
            self.dialog = ("name",)
            self.dialog_input = self.level_name
            self.dialog_cursor = len(self.dialog_input)
        elif ev.key == pygame.K_z and (ev.mod & pygame.KMOD_CTRL):
            if ev.mod & pygame.KMOD_SHIFT:
                if self.pop_redo(): self.sfx.play('remove')
            else:
                if self.pop_undo(): self.sfx.play('remove')
        elif ev.key == pygame.K_y and (ev.mod & pygame.KMOD_CTRL):
            if self.pop_redo(): self.sfx.play('place')
        elif ev.key == pygame.K_DELETE:
            if self.selected_tiles:
                for (tx, ty) in list(self.selected_tiles):
                    self.do_erase_tile(tx, ty)
                self.selected_tiles.clear()
                self.set_status(f"Deleted {len(self.selected_tiles)} buildings")
                self.sfx.play('remove')
        elif ev.key == pygame.K_a and (ev.mod & pygame.KMOD_CTRL):
            self.selected_tiles = set(self.world.buildings.keys())
            self.set_status(f"Selected all {len(self.selected_tiles)} buildings")

        # View toggles
        elif ev.key == pygame.K_1 and not self.tool == EditorTool.BUILDING:
            self.show_grid = not self.show_grid
        elif ev.key == pygame.K_2 and not self.tool == EditorTool.BUILDING:
            self.show_resources = not self.show_resources
        elif ev.key == pygame.K_3 and not self.tool == EditorTool.BUILDING:
            self.show_buildings = not self.show_buildings

        # Confirm dialog actions
        elif ev.key == pygame.K_RETURN or ev.key == pygame.K_y:
            if self.dialog and self.dialog[0] == "confirm":
                action = getattr(self, '_pending_action', None)
                self.dialog = None
                if action == "new":
                    self._do_new()
                elif action == "back":
                    raise ReturnToMenu()

    def _do_new(self):
        self.world = World()
        self.selected_tiles.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.level_name = "Untitled Level"
        self.unsaved = False
        self.set_status("New level created")

    def _save_temp_and_test(self):
        """Save temp and return signal to test-play."""
        try:
            ld = LevelData().from_world(self.world, self.level_name, "Editor")
            os.makedirs(LEVELS_DIR, exist_ok=True)
            ld.save_to_file("_editor_test_temp.json")
        except Exception as e:
            self.set_status(f"Error saving for test: {e}")
        raise TestPlayRequest()


class ReturnToMenu(Exception):
    pass

class TestPlayRequest(Exception):
    pass


def editor_menu_screen(screen, clock):
    """Level editor entry screen. Returns 'new', filename, or None (back)."""
    ft = pygame.font.SysFont("consolas", 36, bold=True)
    fm = pygame.font.SysFont("consolas", 18)
    fs = pygame.font.SysFont("consolas", 14)
    t = 0
    selected = 0  # 0=New, 1=Load, 2=Back
    file_list = LevelData.list_files()
    file_scroll = 0
    load_mode = False
    load_selected = 0

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: return None
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    if load_mode:
                        load_mode = False
                    else:
                        return None
                if not load_mode:
                    if ev.key == pygame.K_UP: selected = max(0, selected - 1)
                    if ev.key == pygame.K_DOWN: selected = min(2, selected + 1)
                    if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if selected == 0: return "new"
                        elif selected == 1: load_mode = True; file_scroll = 0; load_selected = 0
                        elif selected == 2: return None
                else:
                    if ev.key == pygame.K_UP: load_selected = max(0, load_selected - 1)
                    if ev.key == pygame.K_DOWN: load_selected = min(len(file_list) - 1, load_selected + 1)
                    if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if 0 <= load_selected < len(file_list):
                            return file_list[load_selected]
                    if ev.key == pygame.K_LEFTBRACKET or (ev.key == pygame.K_PAGEUP):
                        file_scroll = max(0, file_scroll - 1)
                        load_selected = max(file_scroll, load_selected - 1)
                    if ev.key == pygame.K_RIGHTBRACKET or (ev.key == pygame.K_PAGEDOWN):
                        file_scroll = min(max(0, len(file_list) - 12), file_scroll + 1)
                        load_selected = min(len(file_list) - 1, load_selected + 1)
            if ev.type == pygame.MOUSEWHEEL:
                if load_mode:
                    file_scroll = max(0, min(max(0, len(file_list) - 12), file_scroll - ev.y))
            if ev.type == pygame.MOUSEBUTTONDOWN:
                sw, sh = screen.get_size()
                cx = sw // 2
                if not load_mode:
                    for i in range(3):
                        by = sh // 2 - 20 + i * 60
                        bx = cx - 120
                        if bx <= ev.pos[0] <= bx + 240 and by <= ev.pos[1] <= by + 45:
                            if i == 0: return "new"
                            elif i == 1: load_mode = True; file_scroll = 0; load_selected = 0
                            elif i == 2: return None
                else:
                    # Check file list clicks
                    base_y = sh // 2 - 100
                    for i in range(min(12, len(file_list) - file_scroll)):
                        fi = i + file_scroll
                        if fi >= len(file_list): break
                        by = base_y + i * 24
                        if cx - 160 <= ev.pos[0] <= cx + 160 and by <= ev.pos[1] <= by + 22:
                            return file_list[fi]
                    # Back button
                    back_y = base_y + min(12, len(file_list) - file_scroll) * 24 + 20
                    if cx - 60 <= ev.pos[0] <= cx + 60 and back_y <= ev.pos[1] <= back_y + 30:
                        load_mode = False

        sw, sh = screen.get_size()
        screen.fill((18, 20, 28))

        # Title
        pulse = 0.7 + 0.3 * math.sin(t * 2)
        title_color = (int(80 + 175 * pulse), int(180 + 75 * pulse), int(220 + 35 * pulse))
        title = ft.render("LEVEL EDITOR", True, title_color)
        screen.blit(title, title.get_rect(center=(sw // 2, sh // 4 - 10)))
        sub = fm.render("Create, edit, and test custom levels", True, (120, 140, 160))
        screen.blit(sub, sub.get_rect(center=(sw // 2, sh // 4 + 30)))

        if not load_mode:
            # Main options
            options = [
                ("New Level", "Start with an empty canvas", (60, 180, 60)),
                ("Load Level", f"Browse saved levels ({len(file_list)} found)", (60, 120, 180)),
                ("Back to Menu", "Return to main menu", (140, 80, 80)),
            ]
            cx = sw // 2
            for i, (label, desc, c) in enumerate(options):
                by = sh // 2 - 20 + i * 60
                bx = cx - 120
                is_sel = i == selected
                if is_sel:
                    glow = pygame.Surface((250, 50), pygame.SRCALPHA)
                    pygame.draw.rect(glow, (*c, 30), (0, 0, 250, 50), border_radius=8)
                    screen.blit(glow, (bx - 5, by - 3))
                    pygame.draw.rect(screen, c, (bx, by, 240, 45), border_radius=6)
                    tc = (255, 255, 255)
                else:
                    s = pygame.Surface((240, 45), pygame.SRCALPHA)
                    pygame.draw.rect(s, (*c, 30), (0, 0, 240, 45), border_radius=6)
                    pygame.draw.rect(s, (*c, 80), (0, 0, 240, 45), width=2, border_radius=6)
                    screen.blit(s, (bx, by))
                    tc = (*c,)
                screen.blit(fm.render(label, True, tc), (bx + 12, by + 5))
                screen.blit(fs.render(desc, True, (140, 142, 155)), (bx + 12, by + 26))
        else:
            # File list
            cx = sw // 2
            screen.blit(fm.render("Select a level to load:", True, (200, 200, 220)),
                        (cx - 160, sh // 2 - 130))
            base_y = sh // 2 - 100
            file_list = LevelData.list_files()
            max_vis = min(12, len(file_list) - file_scroll)
            for i in range(max_vis):
                fi = i + file_scroll
                if fi >= len(file_list): break
                by = base_y + i * 24
                is_sel = fi == load_selected
                c = (100, 200, 255) if is_sel else (60, 62, 78)
                s = pygame.Surface((320, 22), pygame.SRCALPHA)
                pygame.draw.rect(s, (*c, 40 if not is_sel else 80), (0, 0, 320, 22), border_radius=3)
                if is_sel:
                    pygame.draw.rect(s, c, (0, 0, 320, 22), width=1, border_radius=3)
                screen.blit(s, (cx - 160, by))
                screen.blit(fs.render(file_list[fi], True, (220, 220, 230) if is_sel else (170, 172, 185)),
                            (cx - 150, by + 4))
            # Back button
            back_y = base_y + max_vis * 24 + 20
            pygame.draw.rect(screen, (80, 50, 50), (cx - 60, back_y, 120, 30), border_radius=5)
            screen.blit(fm.render("Back [Esc]", True, (220, 150, 150)),
                        (cx - 45, back_y + 5))

        # Decorations
        for i in range(8):
            angle = t * 0.2 + i * math.pi / 4
            dx = math.cos(angle) * (sw * 0.35)
            dy = math.sin(angle) * (sh * 0.3)
            sx = int(sw / 2 + dx)
            sy = int(sh / 2 + dy)
            c = COL_RGB.get(list(Col)[i % len(Col)], (200, 200, 200))
            pygame.draw.circle(screen, c, (sx, sy), 8, 2)

        # Hint
        blink = int(t * 2) % 2 == 0
        if blink:
            if not load_mode:
                hint = fs.render("Use Arrow keys + Enter, or click to select", True, (100, 102, 115))
            else:
                hint = fs.render("Click a file or use arrows + Enter. Esc to go back.", True, (100, 102, 115))
            screen.blit(hint, hint.get_rect(center=(sw // 2, sh - 40)))

        pygame.display.flip()


def run():
    pygame.init()
    pygame.key.set_repeat(300, 80)
    sw, sh = 1280, 800
    screen = pygame.display.set_mode((sw, sh), pygame.RESIZABLE)
    pygame.display.set_caption("shapez Local Multiplayer")
    clock = pygame.time.Clock()

    sfx = SFX()
    sfx.init()

    # ── Main menu with editor option ─────────────────────────────────────
    while True:
        menu_choice = main_menu_with_editor(screen, clock)
        if menu_choice is None:
            pygame.quit(); return
        elif isinstance(menu_choice, int):
            # Play mode
            num_players = menu_choice
            break
        elif menu_choice == "editor":
            # Enter editor
            editor_result = run_editor_flow(screen, clock, sfx)
            if editor_result == "quit":
                pygame.quit(); return
            elif isinstance(editor_result, tuple) and editor_result[0] == "test":
                # Test play
                test_world = editor_result[1]
                run_game_with_world(screen, clock, sfx, test_world, 1)
                continue
            else:
                continue  # Back to menu
        elif isinstance(menu_result := menu_choice, str) and menu_choice.endswith('.json'):
            # Load and play a level
            try:
                ld = LevelData.load_from_file(menu_choice)
                test_world = ld.to_world()
                num_players = 1
                # Will use test_world instead of fresh World()
                run_game_with_world(screen, clock, sfx, test_world, num_players)
                continue
            except Exception as e:
                print(f"Error loading level: {e}")
                continue

    # Original game flow for normal play
    world = World()
    players: List[PlayerState] = []
    for i in range(num_players):
        p = PlayerState(i, P_NAMES[i], P_COLORS[i], has_mouse=(i == 0))
        if i < len(world.resources):
            idx = (i * 13) % len(world.resources)
            p.cam_x = float(world.resources[idx].x)
            p.cam_y = float(world.resources[idx].y)
            p.cx = world.resources[idx].x
            p.cy = world.resources[idx].y
        # Setup keyboard bindings for non-mouse players
        if not p.has_mouse:
            setup_kb_bindings(p, i)
        players.append(p)

    viewports: List[Viewport] = []
    particles = Particles()
    running = True
    sim_accum = 0.0
    prev_goals_done = 0
    need_resize = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        sw, sh = screen.get_size()
        if need_resize:
            need_resize = False
            viewports = build_viewports(num_players, sw, sh)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: running = False
            elif ev.type == pygame.VIDEORESIZE: need_resize = True
            elif ev.type == pygame.MOUSEWHEEL:
                players[0].cam_target_zoom = max(0.2, min(4.0,
                    players[0].cam_target_zoom * (1.12 if ev.y > 0 else 1/1.12)))
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if players[0].has_mouse and viewports:
                    handle_mouse(players[0], ev, mouse_pos, viewports[0], world, sfx, particles)
            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 2: players[0].dragging = False
            elif ev.type == pygame.MOUSEMOTION:
                if players[0].dragging and viewports:
                    v = viewports[0]
                    dx = (ev.pos[0]-players[0].drag_start[0])/(TILE_SIZE*players[0].cam_zoom)
                    dy = (ev.pos[1]-players[0].drag_start[1])/(TILE_SIZE*players[0].cam_zoom)
                    players[0].cam_x = players[0].cam_start[0]-dx
                    players[0].cam_y = players[0].cam_start[1]-dy
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE: running = False
                if players[0].has_mouse:
                    handle_p1_key(players[0], ev, viewports[0] if viewports else None, world, sfx, particles)
                for p in players[1:]:
                    handle_kb_player(p, ev, world, sfx, particles)

        # P1 WASD panning
        keys = pygame.key.get_pressed()
        pan = 10 / players[0].cam_zoom * dt
        if keys[pygame.K_a]: players[0].cam_x -= pan
        if keys[pygame.K_d]: players[0].cam_x += pan
        if keys[pygame.K_w]: players[0].cam_y -= pan
        if keys[pygame.K_s]: players[0].cam_y += pan

        # P1 mouse -> cursor
        if viewports:
            v = viewports[0]
            wx, wy = v.s2w(mouse_pos[0], mouse_pos[1], players[0])
            players[0].cx, players[0].cy = int(round(wx)), int(round(wy))

        # P2+ keyboard cursor + auto-pan
        for p in players[1:]:
            p.cursor_move_timer += dt
            if p.cursor_move_timer > 0.06:
                p.cursor_move_timer = 0
                if keys.get(p._k_up, False): p.cy -= 1
                if keys.get(p._k_down, False): p.cy += 1
                if keys.get(p._k_left, False): p.cx -= 1
                if keys.get(p._k_right, False): p.cx += 1
            dx = p.cx - p.cam_x; dy = p.cy - p.cam_y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 6:
                p.cam_x += dx * 0.06
                p.cam_y += dy * 0.06

        # Smooth zoom
        for p in players:
            d = p.cam_target_zoom - p.cam_zoom
            if abs(d) > 0.01: p.cam_zoom += d * min(1, dt * 12)

        # Simulation
        sim_accum += dt
        steps = 0
        while sim_accum >= TICK_MS / 1000.0 and steps < 5:
            world.tick(); sim_accum -= TICK_MS / 1000.0; steps += 1

        # Goal check
        gd = sum(1 for g in world.goals if g.completed)
        if gd > prev_goals_done: sfx.play('goal'); prev_goals_done = gd

        particles.update(dt)

        # ── Render ─────────────────────────────────────────────────────────
        screen.fill((10, 10, 14))
        for i, (p, v) in enumerate(zip(players, viewports)):
            v.t += dt
            v.render(world, p, p, players, particles)
        blit_viewports(screen, viewports, players, num_players, sw, sh)

        # FPS
        fps_t = viewports[0].ftiny.render(f"FPS:{int(clock.get_fps())} Ticks:{world.tick_n}", True, (50,52,65))
        screen.blit(fps_t, (sw-120, 4))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    run()