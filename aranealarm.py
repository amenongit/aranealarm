"""
Aranealarm

An exercise in basic network monitoring (_aranea_ is "spider[web]" in Latin) and TUI,
this cross-platform Python script pings IP nodes periodically in parallel
and displays response time, connection status, some other statistics, and recent history.
If all nodes respond to ping, then quiet background music plays through [pygame](https://pygame.org).
If at least one node becomes disconnected, then music pauses, loud voice synthesized
with [pyttsx3](https://github.com/nateshmbhat/pyttsx3) speaks _alarm_ messages, and part of the screen blinks,
drawing attention of someone dozing on duty (are you?) until all nodes respond to ping again.
When latitude and longitude of nodes and places are given, they are shown on 2D map.
Results of each pass are kept in the log, which can be viewed and saved into a file.
Configuration is done by means of JSONs.

https://github.com/amenongit/aranealarm

Copyright (c) 2022 Ame🇺🇦Non <amenonbox@gmail.com>

Aranealarm is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Aranealarm is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Aranealarm. If not, see <https://www.gnu.org/licenses/>.
"""

import sys
if (sys.version_info[0] < 3) or ((sys.version_info[0] == 3) and (sys.version_info[1] < 6)):
	print("Aranealarm requires Python 3.6 or later, found Python " + str(sys.version_info[0]) + "." + str(sys.version_info[1]))
	exit(1)

try:
	import pygame
except ImportError:
	print("Aranealarm requires \"pygame\" module for music playback.\nInstall it, e.g. \"pip[3] install [--user] pygame\"")
	exit(1)

try:
	import pyttsx3
except ImportError:
	print("Aranealarm requires \"pyttsx3\" module for speech synthesis.\nInstall it, e.g. \"pip[3] install [--user] pyttsx3\"")
	exit(1)

try:
	import curses
except ImportError:
	print("Aranealarm requires \"curses\" module for TUI, which on Windows, in turn, requires \"windows-curses\" module.\nInstall it, e.g. \"pip install [--user] windows-curses\"")
	exit(1)

import datetime
from enum import Enum, auto
import json
import math
import platform
from queue import Queue
import random
import subprocess
from threading import Thread
import time


APP_NAME = "Aranealarm"
APP_VER = "v1.0.2 (2022.05.15)"
APP_COPYR_PART1 = "© 2022 Ame"
APP_COPYR_PART2 = "▄▄▄"
APP_COPYR_PART3 = "Non"

HISTORY_SIZE_BINLOG = 16
HISTORY_SIZE = 1 << HISTORY_SIZE_BINLOG
HISTORY_SIZE_BINMASK = HISTORY_SIZE - 1

LOG_SIZE_BINLOG = 16
LOG_SIZE = 1 << LOG_SIZE_BINLOG
LOG_SIZE_BINMASK = LOG_SIZE - 1

DEFAULT_IP = "127.0.0.1"
DEFAULT_NAME = "localhost"
DEFAULT_SPEECH_NAME = "localhost"
DEFAULT_WAIT_DUR = 500
DEFAULT_ATTEMPTS = 4
DEFAULT_GEOLOC = None

DEFAULT_CHECKRATE = 1.0
DEFAULT_FRAMERATE = 30.0
DEFAULT_BLINKRATE = 4.0
DEFAULT_IDLERATE = 100.0 # main loops idle for 1/idlerate seconds to avoid CPU overusage => overheat...

DEFAULT_ALARM_ROW_HEIGHT = 2

ALARM_CAPTION = "A L A R M"
QUIET_CAPTION = "Q U I E T"
DISCONNECT_CAPTION = "disconnect"
DISCONNECTS_CAPTION = "disconnects"
HUSHED_CAPTION = "HUSHED"

ALARM_SPEECH = "Alarm"
DISCONNECT_SPEECH = "disconnect"
DISCONNECTS_SPEECH = "disconnects"

DEFAULT_MUSIC_VOLUME = 50

NUMBER_HEADER = "Num"
NUMBER_COL_START = 1
NUMBER_COL_WIDTH = 3

ADDRESS_HEADER = "Address"

ADDRESS_SEP_NODE_COL_WIDTH = 8

NODE_HEADER = "Node"
NODE_COL_START = NUMBER_COL_START + NUMBER_COL_WIDTH + 1
NODE_COL_MAX_WIDTH = 48

RESPONSETIME_HEADER = "RespT"
RESPONSETIME_COL_WIDTH = 5

CONNECTED_HEADER = "Conn"
CONNECTED_COL_WIDTH = 4

YES_CAPTION = "YES"
NO_CAPTION = "NO"

DURATION_HEADER = "Lasts for"
DURATION_COL_WIDTH = 9

ISSUES_HEADER = "|—>¦" # → 
ISSUES_COL_WIDTH = 4

HISTORY_HEADER = "yrotsiH"
HISTORY_DISTRIBUTION_HEADER = "History distribution"

DEFAULT_LOG_FILENAME = "aranealarm.log"
DEFAULT_CONFIG_FILENAME = "aranealarm.json"

# OS-dependent constants

if platform.system() in ["Linux", "Darwin"]:
	CCLR_BLACK = 0
	CCLR_DARKRED = 1
	CCLR_DARKGREEN = 2
	CCLR_DARKYELLOW = 3
	CCLR_DARKBLUE = 4
	CCLR_DARKMAGENTA = 5
	CCLR_DARKCYAN = 6
	CCLR_GRAY = 7
	CCLR_DARKGRAY = 8
	CCLR_RED = 9
	CCLR_GREEN = 10
	CCLR_YELLOW = 11
	CCLR_BLUE = 12
	CCLR_MAGENTA = 13
	CCLR_CYAN = 14
	CCLR_WHITE = 15

	HISTORY_CHAR_CONNECT = "•" # for Ubuntu Mono (● is too wide)
	HISTORY_CHAR_DISCONNECT = "▫" # for Ubuntu Mono (□ is too wide)

elif platform.system() == "Windows":
	CCLR_BLACK = 0
	CCLR_DARKBLUE = 1
	CCLR_DARKGREEN = 2
	CCLR_DARKCYAN = 3
	CCLR_DARKRED = 4
	CCLR_DARKMAGENTA = 5
	CCLR_DARKYELLOW = 6
	CCLR_GRAY = 7
	CCLR_DARKGRAY = 8
	CCLR_BLUE = 9
	CCLR_GREEN = 10
	CCLR_CYAN = 11
	CCLR_RED = 12
	CCLR_MAGENTA = 13
	CCLR_YELLOW = 14
	CCLR_WHITE = 15

	HISTORY_CHAR_CONNECT = "●" # for Consolas
	HISTORY_CHAR_DISCONNECT = "□" # for Consolas

else:
	raise SystemError("Unknown OS")


class VoiceQueueMessage(Enum):
	DISCONNECTS_NUM = auto()
	SPEAK = auto()
	QUIT = auto()


class ShowPeaksMode(Enum):
	NONE = auto()
	CONN = auto()
	DISCONN = auto()


class GeoLoc:
	def __init__(self, lat, lon):
		self.lat = lat
		self.lon = lon


	def to_str(self):
		ns = "N" if self.lat >=0 else "S"
		lat_abs = math.fabs(self.lat)
		lat_g = int(math.floor(lat_abs))
		lat_m = int(math.floor(60.0 * (lat_abs - lat_g)))
		ew = "E" if self.lon >=0 else "W"
		lon_abs = math.fabs(self.lon)
		lon_g = int(math.floor(lon_abs))
		lon_m = int(math.floor(60.0 * (lon_abs - lon_g)))
		return f"{lat_g}°{lat_m}′{ns}, {lon_g}°{lon_m}′{ew}"


class Place:
	def __init__(self, name, geoloc, char):
		self.name = name
		self.geoloc = geoloc
		self.char = char


def init_screen(scr):
	scr.nodelay(True)
	curses.curs_set(0)
	if curses.can_change_color():
		try:
			curses.init_color(0, 0, 0, 0)
		except:
			pass
	if curses.has_colors():
		for bc in range(0x10):
			for fc in range(0x10):
				if (bc > 0) or (fc > 0):
					try:
						curses.init_pair((bc << 4) + fc, fc, bc)
					except:
						pass


def ccp(fg=CCLR_GRAY, bg=CCLR_BLACK):
	return curses.color_pair(fg | (bg << 4))


def draw_hline(scr, y, x0, x1, cp):
	x0, x1 = min(x0, x1), max(x0, x1)
	for x in range(x0, x1 + 1):
		try:
			scr.addstr(y, x, "─", cp)
		except:
			pass


def draw_vline(scr, x, y0, y1, cp):
	y0, y1 = min(y0, y1), max(y0, y1)
	for y in range(y0, y1 + 1):
		try:
			scr.addstr(y, x, "│", cp)
		except:
			pass


def draw_fillrect(scr, y0, x0, y1, x1, cp, symb="█"):
	x0, x1 = min(x0, x1), max(x0, x1)
	y0, y1 = min(y0, y1), max(y0, y1)
	for y in range(y0, y1 + 1):
		for x in range(x0, x1 + 1):
			try:
				scr.addstr(y, x, symb, cp)
			except:
				pass


class Node:
	def __init__(self, address, name, speech_name, wait_dur, attempts, geoloc):
		self.address = address
		self.name = name
		self.speech_name = speech_name
		self.wait_dur = wait_dur
		self.attempts = attempts

		self.connected = True
		self.response_time = None # in milliseconds
		self.peak_response_time = -1
		self.t_last_change = int(time.time())
		self.peak_conn_duration = -1
		self.peak_disconn_duration = -1
		self.issues = 0 # number of connected -> disconnected transitions

		self.history = [None] * HISTORY_SIZE # ring buffer
		self.history_pos = 0
		self.history_past_num = 0
		self.history_conn_num = 0

		self.geoloc = geoloc


	def checker(self, index, msg_queue): # runs in a separate thread
		raise NotImplementedError()

		
	def update(self, connected, response_time):
		if connected:
			self.response_time = response_time
			self.peak_response_time = max(self.peak_response_time, self.response_time)
	
		if connected != self.connected:
			self.t_last_change = int(time.time())
			if not connected:
				self.issues += 1
			self.connected = connected

		self.history_past_num = min(HISTORY_SIZE, self.history_past_num + 1)
		curr_rec = self.history[self.history_pos]
		if curr_rec is not None:
			if (not curr_rec) and (self.connected):
				self.history_conn_num += 1
			elif curr_rec and (not self.connected):
				self.history_conn_num -= 1
		else:
			if self.connected:
				self.history_conn_num += 1
		self.history[self.history_pos]  = self.connected
		self.history_pos = (self.history_pos + 1) & HISTORY_SIZE_BINMASK


	def update_peak_durations(self):
		duration = int(time.time()) - self.t_last_change
		if self.connected:
			self.peak_conn_duration = max(self.peak_conn_duration, duration)
		else:
			self.peak_disconn_duration = max(self.peak_disconn_duration, duration)


class IPNode(Node):
	def __init__(self, ip=DEFAULT_IP, name=DEFAULT_NAME, speech_name=DEFAULT_SPEECH_NAME, wait_dur=DEFAULT_WAIT_DUR, attempts=DEFAULT_ATTEMPTS, geoloc=DEFAULT_GEOLOC):
		super().__init__(ip, name, speech_name, wait_dur, attempts, geoloc)


	def checker(self, index, msg_queue): # runs in a separate thread
		ping_cmd = {
			"Linux" : ["ping", "-c 1", f"-W {max(1, int(0.001 * self.wait_dur))}", f"{self.address}"],
			"Windows" : f"ping -n 1 -w {self.wait_dur} {self.address}",
			"Darwin" : ["ping", "-c 1", f"-W {self.wait_dur}", f"{self.address}"]
		}[platform.system()]

		connected = False
		response_time = None
		t_start = time.time()
		for _ in range(self.attempts):
			ping_run = subprocess.run(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			connected = (ping_run.returncode == 0) and (b"unreachable" not in ping_run.stdout)
			if connected:
				ping_out_str_split = ping_run.stdout.decode("cp437").split()
				for s in ping_out_str_split:
					if s.startswith("time=") or s.startswith("time<"):
						time_value_str = s[5:-2].strip() # Linux: "time=12.3 ms" -> "12.3"; Windows: "time=12ms" -> "12" <> or "time<1ms" -> "1"; MacOS: ???
						try:
							response_time = int(round(float(time_value_str)))
						except ValueError:
							pass
						break
				break
		if response_time is None:
			response_time = int(1000 * (time.time() - t_start)) # less accurate due to call overhead

		msg_queue.put([index, connected, response_time])


class LogEntry:
	def __init__(self, instant, pass_num, disconnects, disconn_nodes, resptime_stats):
		self.instant = instant
		self.pass_num = pass_num
		self.disconnects = disconnects
		self.disconn_nodes = disconn_nodes
		self.resptime_stats = resptime_stats


class Aranea:
	def __init__(self, checkrate=DEFAULT_CHECKRATE, framerate=DEFAULT_FRAMERATE, blinkrate=DEFAULT_BLINKRATE, idlerate=DEFAULT_IDLERATE):
		self.checkrate = checkrate
		self.framerate = framerate
		self.blinkrate = blinkrate
		self.idlerate = idlerate

		self.nodes = []
		self.check_queue = Queue()
		self.t_last_check = 0.0
		self.unchecked_num = 0
		self.last_disconnects = 0 # alarm if > 0
		self.last_disconn_nodes_set = set()
		self.hushed_disconn_nodes_set = set()
		self.pass_num = 0

		self.voice_queue = Queue()

		self.log = [None] * LOG_SIZE # ring buffer
		self.log_pos = 0
		self.log_needs_update = False

		self.page_start = 0
		self.page_size = 1

		self.show_peaks = ShowPeaksMode.NONE
		self.show_history_distribution = False
		
		self.t_last_render = 0.0

		self.alarm_row_height = DEFAULT_ALARM_ROW_HEIGHT
		self.alarm_blink = False
		self.t_last_alarm_blink = False

		self.places = []
		self.map_min_lat = 180.0
		self.map_max_lat = -180.0
		self.map_min_lon = 90.0
		self.map_max_lon = -90.0
		self.show_map = True

		self.music_filepaths = []
		self.music_current = -1
		self.music_volume = DEFAULT_MUSIC_VOLUME
		self.music_paused = False


	def voice_thread(self):
		disconnects_num = 0
		speak_engine = pyttsx3.init()
		quit = False
		while not quit:
			while not self.voice_queue.empty():
				msg = self.voice_queue.get()
				if msg[0] == VoiceQueueMessage.DISCONNECTS_NUM:
					disconnects_num = msg[1]
					if disconnects_num == 0:
						speak_engine.stop()
				elif msg[0] == VoiceQueueMessage.SPEAK:
					speak_engine.say(msg[1])
				elif msg[0] == VoiceQueueMessage.QUIT:
					quit = True
				else:
					raise SystemError("Unknown message: \"" + str(msg) + "\"")
			if (not quit) and disconnects_num > 0:
					speak_engine.say(f"{ALARM_SPEECH}: {disconnects_num} {DISCONNECTS_SPEECH if disconnects_num > 1 else DISCONNECT_SPEECH}")
					speak_engine.runAndWait()
			time.sleep(1.0 / self.idlerate)


	def add_node(self, node):
		self.nodes.append(node)


	def load_ip_nodes(self, filepath):
		nodeslist_file = open(filepath, "r")
		nodeslist = json.loads(nodeslist_file.read())
		nodeslist_file.close()

		for node_descr in nodeslist:
			ip = node_descr.get("ip", DEFAULT_IP)
			name = node_descr.get("name", DEFAULT_NAME)
			speech_name = node_descr.get("speech_name", DEFAULT_SPEECH_NAME)
			wait_dur = node_descr.get("wait_dur", DEFAULT_WAIT_DUR)
			attempts = node_descr.get("attempts", DEFAULT_ATTEMPTS)
			geoloc = node_descr.get("geoloc", DEFAULT_GEOLOC)
			if geoloc is not None:
				geoloc = GeoLoc(geoloc.get("lat"), geoloc.get("lon"))

			self.add_node(IPNode(ip, name, speech_name, wait_dur, attempts, geoloc))


	def load_places(self, filepath):
		placeslist_file = open(filepath, "r")
		placeslist = json.loads(placeslist_file.read())
		placeslist_file.close()

		for place_descr in placeslist:
			name = place_descr.get("name")
			geoloc = place_descr.get("geoloc")
			geoloc = GeoLoc(geoloc.get("lat"), geoloc.get("lon"))
			char = place_descr.get("char")
			self.places.append(Place(name, geoloc, char))


	def load_config(self, filepath):
		config_file = open(filepath, "r")
		config_descr = json.loads(config_file.read())
		config_file.close()

		ip_nodeslists = config_descr.get("ip", None)
		if ip_nodeslists is not None:
			for fp in ip_nodeslists:
				self.load_ip_nodes(fp)

		placeslists = config_descr.get("place", None)
		if placeslists is not None:
			for fp in placeslists:
				self.load_places(fp)

		music_filepaths_descr = config_descr.get("music", None)
		if music_filepaths_descr is not None:
			for fp in music_filepaths_descr:
				self.music_filepaths.append(fp)
		self.music_volume = config_descr.get("music_volume", DEFAULT_MUSIC_VOLUME)

		self.alarm_row_height = config_descr.get("alarm_row_height", DEFAULT_ALARM_ROW_HEIGHT)


	def disconnects(self):
		return sum([1 if node.connected == False else 0 for node in self.nodes])


	def disconn_nodes(self):
		disconn_nodes = []
		for i, node in enumerate(self.nodes):
			if not node.connected:
				disconn_nodes.append(i + 1)
		return disconn_nodes


	def disconn_nodes_set(self):
		s = set()
		for i, node in enumerate(self.nodes):
			if not node.connected:
				s.add(i)
		return s


	def alarm_if_disconnects_change(self, force_update=False):
		disconn_nodes_set = self.disconn_nodes_set()
		if force_update or (disconn_nodes_set != self.last_disconn_nodes_set): # change
			self.last_disconn_nodes_set = disconn_nodes_set.copy()
			self.last_disconnects = len(self.last_disconn_nodes_set)
			self.hushed_disconn_nodes_set.clear()
			self.voice_queue.put([VoiceQueueMessage.DISCONNECTS_NUM, self.last_disconnects])
			if len(self.music_filepaths) > 0:
				if self.last_disconnects > 0:
					self.music_paused = True
					pygame.mixer.music.pause()
				else:
					self.music_paused = False
					pygame.mixer.music.unpause()


	def sync_check(self):
		while not self.check_queue.empty():
			i, connected, response_time = self.check_queue.get()
			node = self.nodes[i]
			if node.connected and (not connected):
				self.voice_queue.put([VoiceQueueMessage.SPEAK, node.speech_name + " " + DISCONNECT_SPEECH])
			node.update(connected, response_time)
			self.unchecked_num -= 1
		if self.unchecked_num == 0: # current check pass is finished
			if self.log_needs_update:
				self.pass_num += 1				
				self.update_log()
			t = time.time()
			if t - self.t_last_check > 1.0 / self.checkrate:
				self.t_last_check = t
				self.unchecked_num = len(self.nodes)
				self.log_needs_update = True
				for i, node in enumerate(self.nodes):
					Thread(target=node.checker, args=(i, self.check_queue), name=f"thrPing{1+i}", daemon=True).start() # daemonized to avoid waiting until ping ends after exit (what about resource leaks?)


	def update_peak_durations(self):
		for node in self.nodes:
			node.update_peak_durations()


	def hush(self):
		self.hushed_disconn_nodes_set = self.disconn_nodes_set()
		self.voice_queue.put([VoiceQueueMessage.DISCONNECTS_NUM, 0]) # force voice to stop


	def sync_music(self, force_next=False):
		if len(self.music_filepaths) > 0:
			if force_next or ((not self.music_paused) and (not pygame.mixer.music.get_busy())): # current music ended (or no music has been started yet)
				if self.music_current >= 0:
					if force_next:
						pygame.mixer.music.stop()
					pygame.mixer.music.unload()
				self.music_current = random.randrange(len(self.music_filepaths))
				pygame.mixer.music.load(self.music_filepaths[self.music_current])
				pygame.mixer.music.set_volume(self.music_volume / 100)
				pygame.mixer.music.play()
				if self.music_paused:
					pygame.mixer.music.pause()


	def finish_music(self):
		if len(self.music_filepaths) > 0:
			pygame.mixer.music.stop()
			pygame.mixer.music.unload()
			pygame.mixer.quit()
			pygame.quit()


	def change_music_volume(self, delta):
		self.music_volume = max(0, min(100, self.music_volume + delta))
		if len(self.music_filepaths) > 0:
			pygame.mixer.music.set_volume(self.music_volume / 100)


	def response_time_stats(self):
		t_min = 0xFFFFFFFF
		t_max = -1
		t_avg = 0.0
		t_stddev = 0.0
		n = 0
		for node in self.nodes:
			if node.connected: # use filter() here?
				n += 1
				t = node.response_time
				t_min = min(t_min, t)
				t_max = max(t_max, t)
				t_avg += t
		if n > 0:
			t_avg /= n
			for node in self.nodes:
				if node.connected:
					t = node.response_time
					t_stddev += (t - t_avg) * (t - t_avg)
			t_stddev = math.sqrt(t_stddev / max(1, n - 1))
		return t_min, int(t_avg), t_max, int(t_stddev)


	def update_log(self):
		self.log[self.log_pos] = LogEntry(datetime.datetime.now(), self.pass_num, self.disconnects(), self.disconn_nodes(), self.response_time_stats())
		self.log_pos = (self.log_pos + 1) & LOG_SIZE_BINMASK
		self.log_needs_update = False


	def save_log(self, filepath):
		log_file = open(filepath, "w")
		i = 0
		while i < LOG_SIZE:
			entry = self.log[(self.log_pos - 1 - i) & LOG_SIZE_BINMASK]
			if entry is not None:
				s = "[" + entry.instant.strftime("%Y.%m.%d %H:%M:%S") + "] "
				s += f"Pass {entry.pass_num}: "
				s += f"{entry.disconnects} {DISCONNECT_CAPTION if entry.disconnects == 1 else DISCONNECTS_CAPTION}"
				if entry.disconnects > 0:
					s += " (" + str(entry.disconn_nodes).replace(" ", "")[1:-1] + ")"
				s += f", response time Min {entry.resptime_stats[0]}, Avg {entry.resptime_stats[1]}, Max {entry.resptime_stats[2]}, StdDev {entry.resptime_stats[3]}"
				s += "\n"
				log_file.write(s)
			else:
				break
			i += 1
		log_file.close()


	def update_map_boundbox(self):
		self.map_min_lat = min([(node.geoloc.lat if node.geoloc is not None else 180.0) for node in self.nodes] + [place.geoloc.lat for place in self.places])
		self.map_max_lat = max([(node.geoloc.lat if node.geoloc is not None else -180.0) for node in self.nodes] + [place.geoloc.lat for place in self.places])
		self.map_min_lon = min([(node.geoloc.lon if node.geoloc is not None else 90.0) for node in self.nodes] + [place.geoloc.lon for place in self.places])
		self.map_max_lon = max([(node.geoloc.lon if node.geoloc is not None else -90.0) for node in self.nodes] + [place.geoloc.lon for place in self.places])


	def geoloc_to_scr_yx(self, geoloc, min_y):
		y = max(min_y, min(curses.LINES - 4, curses.LINES - 4 - int((geoloc.lat - self.map_min_lat) / max(1e-16, self.map_max_lat - self.map_min_lat) * (curses.LINES - 4 - min_y))))
		x = max(1, min(curses.COLS - 2, 1 + int((geoloc.lon - self.map_min_lon) / max(1e-16, self.map_max_lon - self.map_min_lon) * (curses.COLS - 3))))
		return y, x


	def render(self, scr):
		def caddstr(*args): # "c" for "caught": do not exit in case of error (usually write outside screen)
			try:
				scr.addstr(*args)
			except:
				pass

		t = time.time()
		if t - self.t_last_render > 1.0 / self.framerate:
			curses.update_lines_cols()

			node_col_width = min(NODE_COL_MAX_WIDTH, max([len(node.address) for node in self.nodes]) + ADDRESS_SEP_NODE_COL_WIDTH + max([len(node.name) for node in self.nodes]))
			responsetime_col_start = NODE_COL_START + node_col_width + 1
			connected_col_start = responsetime_col_start + RESPONSETIME_COL_WIDTH + 1
			duration_col_start = connected_col_start + CONNECTED_COL_WIDTH + 1
			issues_col_start = duration_col_start + DURATION_COL_WIDTH + 1
			history_col_start = issues_col_start + ISSUES_COL_WIDTH + 1
			self.page_size = min(len(self.nodes), curses.LINES // 3)

			scr.erase()

			# Borders
			bcp = ccp(CCLR_GRAY, CCLR_BLACK)

			caddstr(0, 0, "┌", bcp)
			caddstr(0, curses.COLS - 1, "┐", bcp)
			draw_hline(scr, 0, 1, curses.COLS - 2, bcp)

			title_col_start = (curses.COLS - len(APP_NAME) - 2) >> 1
			caddstr(0, title_col_start - 1, "┤", bcp)
			caddstr(0, title_col_start + len(APP_NAME) + 2, "├", bcp)

			draw_vline(scr, 0, 1, self.alarm_row_height, bcp)
			draw_vline(scr, curses.COLS - 1, 1, self.alarm_row_height, bcp)
			
			headers_row = self.alarm_row_height + 2

			draw_hline(scr, headers_row - 1, 1, curses.COLS - 2, bcp)
			draw_hline(scr, headers_row + 1, 1, curses.COLS - 2, bcp)
			caddstr(headers_row - 1, 0, "├", bcp)
			draw_vline(scr, 0, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, 0, "├", bcp)

			caddstr(headers_row - 1, NODE_COL_START - 1, "┬", bcp)
			draw_vline(scr, NODE_COL_START - 1, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, NODE_COL_START - 1, "┼", bcp)

			caddstr(headers_row - 1, responsetime_col_start - 1, "┬", bcp)
			draw_vline(scr, responsetime_col_start - 1, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, responsetime_col_start - 1, "┼", bcp)

			caddstr(headers_row - 1, connected_col_start - 1, "┬", bcp)
			draw_vline(scr, connected_col_start - 1, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, connected_col_start - 1, "┼", bcp)

			caddstr(headers_row - 1, duration_col_start - 1, "┬", bcp)
			draw_vline(scr, duration_col_start - 1, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, duration_col_start - 1, "┼", bcp)

			caddstr(headers_row - 1, issues_col_start - 1, "┬", bcp)
			draw_vline(scr, issues_col_start - 1, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, issues_col_start - 1, "┼", bcp)

			caddstr(headers_row - 1, history_col_start - 1, "┬", bcp)
			draw_vline(scr, history_col_start - 1, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, history_col_start - 1, "┼", bcp)

			caddstr(headers_row - 1, curses.COLS - 1, "┤", bcp)
			draw_vline(scr, curses.COLS - 1, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, curses.COLS - 1, "┤" if self.show_history_distribution else "┘", bcp)

			nodes_top_row = headers_row + 2

			draw_vline(scr, NUMBER_COL_START - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, NODE_COL_START - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, responsetime_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)		
			draw_vline(scr, connected_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, duration_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, issues_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, history_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			if self.show_history_distribution:
				draw_vline(scr, curses.COLS - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)

			bottom_border_row = nodes_top_row + self.page_size

			caddstr(bottom_border_row, 0, "├", bcp)
			draw_hline(scr, bottom_border_row, 1, curses.COLS - 1, bcp)
			caddstr(bottom_border_row, curses.COLS - 1, "┤" if self.show_history_distribution else "┐", bcp)

			caddstr(bottom_border_row, NODE_COL_START - 1, "┴", bcp)
			caddstr(bottom_border_row, responsetime_col_start - 1, "┴", bcp)
			caddstr(bottom_border_row, connected_col_start - 1, "┴", bcp)
			caddstr(bottom_border_row, duration_col_start - 1, "┴", bcp)
			caddstr(bottom_border_row, issues_col_start - 1, "┴", bcp)
			caddstr(bottom_border_row, history_col_start - 1, "┴", bcp)

			draw_vline(scr, 0, bottom_border_row + 1, curses.LINES - 1, bcp)
			draw_vline(scr, curses.COLS - 1, bottom_border_row + 1, curses.LINES - 4, bcp)

			caddstr(curses.LINES - 3, 0, "├", bcp)
			draw_hline(scr, curses.LINES - 3, 1, curses.COLS - 1, bcp)
			caddstr(curses.LINES - 3, curses.COLS - 1, "┘", bcp)

			# Title
			caddstr(0, title_col_start, " " + APP_NAME + " ", ccp(CCLR_BLACK, CCLR_WHITE))

			# Alarm
			alarm_row = (1 + self.alarm_row_height) >> 1
			if self.last_disconnects > 0:
				fg, bg = (CCLR_YELLOW, CCLR_DARKRED) if self.alarm_blink else (CCLR_DARKRED, CCLR_YELLOW)
				draw_fillrect(scr, 1, 1, self.alarm_row_height, curses.COLS - 2, ccp(bg))
				caddstr(alarm_row, (curses.COLS - len(ALARM_CAPTION)) >> 1, ALARM_CAPTION, ccp(fg, bg))
				if self.alarm_row_height > 1:
					alarm_disconnects_caption = f"{self.last_disconnects} {DISCONNECTS_CAPTION if self.last_disconnects > 1 else DISCONNECT_CAPTION}"
					caddstr(alarm_row + 1, (curses.COLS - len(alarm_disconnects_caption)) >> 1, alarm_disconnects_caption, ccp(fg, bg))
				if len(self.hushed_disconn_nodes_set) > 0:
					caddstr(alarm_row, 1, HUSHED_CAPTION, ccp(fg, bg))
					caddstr(alarm_row, curses.COLS - 1 - len(HUSHED_CAPTION), HUSHED_CAPTION, ccp(fg, bg))
				if t - self.t_last_alarm_blink > 1.0 / self.blinkrate:
					self.alarm_blink = not self.alarm_blink
					self.t_last_alarm_blink = t
			else:
				fg, bg = (CCLR_GREEN, CCLR_DARKGREEN)
				draw_fillrect(scr, 1, 1, self.alarm_row_height, curses.COLS - 2, ccp(bg))
				caddstr(alarm_row, (curses.COLS - len(QUIET_CAPTION)) >> 1, QUIET_CAPTION, ccp(fg, bg))
				if self.alarm_row_height > 1:
					if len(self.music_filepaths) > 0:
						music_filename = self.music_filepaths[self.music_current].split(sep="/")[-1]
						quiet_music_caption = f"♪ {music_filename} ♪"
						caddstr(alarm_row + 1, (curses.COLS - len(quiet_music_caption)) >> 1, quiet_music_caption, ccp(fg, bg))

			# Headers
			headers_color = ccp(CCLR_GRAY)
			caddstr(headers_row, NUMBER_COL_START, NUMBER_HEADER, headers_color)
			caddstr(headers_row, NODE_COL_START, ADDRESS_HEADER, headers_color)
			caddstr(headers_row, NODE_COL_START + node_col_width - len(NODE_HEADER), NODE_HEADER, headers_color)
			caddstr(headers_row, responsetime_col_start, RESPONSETIME_HEADER if self.show_peaks == ShowPeaksMode.NONE else RESPONSETIME_HEADER.upper(), headers_color)
			caddstr(headers_row, connected_col_start, CONNECTED_HEADER, headers_color)
			caddstr(headers_row, duration_col_start,
				DURATION_HEADER if self.show_peaks == ShowPeaksMode.NONE else DURATION_HEADER.upper(),
				headers_color | (curses.A_REVERSE if self.show_peaks == ShowPeaksMode.DISCONN else 0)
			)
			caddstr(headers_row, issues_col_start, ISSUES_HEADER)
			caddstr(headers_row, history_col_start, HISTORY_DISTRIBUTION_HEADER if self.show_history_distribution else HISTORY_HEADER)

			# Nodes
			for i, node in enumerate(self.nodes[self.page_start:min(len(self.nodes), self.page_start + self.page_size)]):
				hush_attr = curses.A_REVERSE if i in self.hushed_disconn_nodes_set else 0

				color_bright = ccp(CCLR_GREEN) if node.connected else ccp(CCLR_RED)
				color_dark = ccp(CCLR_DARKGREEN) if node.connected else ccp(CCLR_DARKRED)
				# Number
				caddstr(nodes_top_row + i, NUMBER_COL_START, f"{self.page_start + i + 1:03}", color_dark | hush_attr)
				# Address
				caddstr(nodes_top_row + i, NODE_COL_START, node.address, color_dark | hush_attr)
				# Name
				caddstr(nodes_top_row + i, max(0, NODE_COL_START + node_col_width - len(node.name)), node.name, color_bright | hush_attr)
				if len(node.address) + len(node.name) < node_col_width:
					draw_fillrect(scr, nodes_top_row + i, NODE_COL_START + len(node.address), nodes_top_row + i, NODE_COL_START + node_col_width - len(node.name) - 1, ccp(CCLR_DARKGRAY), "·")
				# Response time or its peak
				resptime_cp = ccp(CCLR_BLUE)
				if self.show_peaks != ShowPeaksMode.NONE:
					if node.peak_response_time >= 0:
						caddstr(nodes_top_row + i, responsetime_col_start, f"{node.peak_response_time:5}", resptime_cp)
				else:
					if node.connected and (node.response_time is not None):
						caddstr(nodes_top_row + i, responsetime_col_start, f"{node.response_time:5}", resptime_cp)
				# Connected?
				caddstr(nodes_top_row + i, connected_col_start, YES_CAPTION if node.connected else NO_CAPTION, color_bright | hush_attr)
				# Duration of current (dis)connection or its peaks
				if self.show_peaks == ShowPeaksMode.NONE:
					duration = int(t) - node.t_last_change
					duration_cp = ccp(CCLR_DARKCYAN) if node.connected else ccp(CCLR_MAGENTA)
				elif self.show_peaks == ShowPeaksMode.CONN:
					duration = node.peak_conn_duration
					duration_cp = ccp(CCLR_DARKCYAN)
				elif self.show_peaks == ShowPeaksMode.DISCONN:
					duration = node.peak_disconn_duration
					duration_cp = ccp(CCLR_MAGENTA)
				if duration >= 0:
					hours, secs = duration // 3600, duration % 3600
					mins, secs = secs // 60, secs % 60
					caddstr(nodes_top_row + i, duration_col_start, f"{hours:03}:{mins:02}:{secs:02}", duration_cp)
				# Number of connected -> disconnected changes
				caddstr(nodes_top_row + i, issues_col_start, f"{node.issues:4}", ccp(CCLR_DARKYELLOW))
				# History or its distribution
				if self.show_history_distribution:
					conn_part = (curses.COLS - 1 - history_col_start) * node.history_conn_num // max(1, node.history_past_num)
					if conn_part > 0:
						draw_fillrect(scr, nodes_top_row + i, history_col_start, nodes_top_row + i, history_col_start + conn_part - 1, ccp(CCLR_GREEN), symb="▀")
					if conn_part < (curses.COLS - 1 - history_col_start):
						draw_fillrect(scr, nodes_top_row + i, history_col_start + conn_part, nodes_top_row + i, curses.COLS - 2, ccp(CCLR_RED), symb="▀")
				else:
					for j in range(max(0, curses.COLS - history_col_start)):
						conn = node.history[(node.history_pos - 1 - j) & HISTORY_SIZE_BINMASK]
						if conn is not None:
							caddstr(nodes_top_row + i, history_col_start + j, HISTORY_CHAR_CONNECT if conn else HISTORY_CHAR_DISCONNECT, ccp(CCLR_GREEN) if conn else ccp(CCLR_RED)) 

			log_row_start = bottom_border_row + 1

			# Map or reversed log
			if self.show_map:
				self.update_map_boundbox()
				if (self.map_min_lat <= self.map_max_lat) and (self.map_min_lon <= self.map_max_lon):
					# Places
					place_bright_cp = ccp(CCLR_GRAY)
					place_dark_cp = ccp(CCLR_DARKGRAY)
					for place in self.places:
						y, x = self.geoloc_to_scr_yx(place.geoloc, log_row_start)
						if x < curses.COLS >> 1:
							caddstr(y, x, place.char, place_bright_cp)
							caddstr(f" {place.name}", place_dark_cp)
						else: # avoid printing over right edge
							x -= len(place.name) + 1
							caddstr(y, x, f"{place.name} ", place_dark_cp)
							caddstr(place.char, place_bright_cp)
					# Corners
					geo_mins_str = GeoLoc(self.map_min_lat, self.map_min_lon).to_str()
					caddstr(curses.LINES - 4, 1, geo_mins_str, ccp(CCLR_DARKGRAY) | curses.A_REVERSE)
					geo_maxs_str = GeoLoc(self.map_max_lat, self.map_max_lon).to_str()
					caddstr(log_row_start, curses.COLS - 1 - len(geo_maxs_str), geo_maxs_str, ccp(CCLR_DARKGRAY) | curses.A_REVERSE)
					# Nodes
					for i, node in enumerate(self.nodes):
						if node.geoloc is not None:
							node_char = HISTORY_CHAR_CONNECT if node.connected else HISTORY_CHAR_DISCONNECT
							node_bright_cp = ccp(CCLR_GREEN) if node.connected else ccp(CCLR_RED)
							node_dark_cp = ccp(CCLR_DARKGREEN) if node.connected else ccp(CCLR_DARKRED)
							y, x = self.geoloc_to_scr_yx(node.geoloc, log_row_start)
							if x < curses.COLS >> 1:
								caddstr(y, x, node_char, node_bright_cp)
								caddstr(f"{1 + i}", node_dark_cp | curses.A_REVERSE)
							else: # avoid printing over right edge
								x -= len(str(i))
								caddstr(y, x, f"{1 + i}", node_dark_cp | curses.A_REVERSE)
								caddstr(node_char, node_bright_cp)
			else:
				for i in range(max(0, curses.LINES - 3 - log_row_start)):
					entry = self.log[(self.log_pos - 1 - i) & LOG_SIZE_BINMASK]
					if entry is not None:
						caddstr(log_row_start + i, 1, "[" + entry.instant.strftime("%H:%M:%S") + "] ", ccp(CCLR_DARKBLUE))
						caddstr(f"Pass {entry.pass_num:6}: ", ccp(CCLR_DARKGREEN) if entry.disconnects == 0 else ccp(CCLR_DARKYELLOW))
						caddstr(f"{entry.disconnects:3} {DISCONNECT_CAPTION if entry.disconnects == 1 else DISCONNECTS_CAPTION}", ccp(CCLR_GREEN) if entry.disconnects == 0 else ccp(CCLR_YELLOW))
						if entry.disconnects > 0:
							caddstr(" (" + str(entry.disconn_nodes).replace(" ", "")[1:-1] + ")", ccp(CCLR_RED))
						caddstr(", ", ccp(CCLR_GREEN) if entry.disconnects == 0 else ccp(CCLR_YELLOW))
						caddstr(f"response time Min {entry.resptime_stats[0]:5}, Avg {entry.resptime_stats[1]:5}, Max {entry.resptime_stats[2]:5}, StdDev {entry.resptime_stats[3]:5}", ccp(CCLR_BLUE))

			# Help
			help_bright_cp = ccp(CCLR_GRAY)
			help_dark_cp = ccp(CCLR_DARKGRAY)
			caddstr(curses.LINES - 2, 1, "Q", help_bright_cp)
			caddstr(":Quit ", help_dark_cp)
			caddstr("↑/↓/PgUp/PgDown/Home/End", help_bright_cp)
			caddstr(":scroll nodes ", help_dark_cp)
			caddstr("P", help_bright_cp)
			caddstr(":time Peaks ", help_dark_cp)
			caddstr("M", help_bright_cp)
			caddstr(":Map <-> log ", help_dark_cp)

			caddstr(curses.LINES - 1, 1, "D", help_bright_cp)
			caddstr(":history Distribution ", help_dark_cp)
			caddstr("L", help_bright_cp)
			caddstr(":save Log ", help_dark_cp)
			caddstr("H", help_bright_cp)
			caddstr(":Hush ", help_dark_cp)
			caddstr("U", help_bright_cp)
			caddstr(":Unhush ", help_dark_cp)
			if len(self.music_filepaths) > 0:
				caddstr("N", help_bright_cp)
				caddstr(":Next music ", help_dark_cp)
				caddstr("←/→", help_bright_cp)
				caddstr(f":music vol ({self.music_volume:03})", help_dark_cp)

			# Version & copyright
			caddstr(curses.LINES - 2, curses.COLS - 1 - len(APP_VER), APP_VER, ccp(CCLR_DARKGRAY))
			caddstr(curses.LINES - 1, curses.COLS - 1 - (len(APP_COPYR_PART1) + len(APP_COPYR_PART2) + len(APP_COPYR_PART3)), APP_COPYR_PART1, ccp(CCLR_DARKGRAY))
			caddstr(APP_COPYR_PART2, ccp(CCLR_DARKYELLOW, CCLR_DARKBLUE))
			caddstr(APP_COPYR_PART3, ccp(CCLR_DARKGRAY))

			scr.refresh()
			self.t_last_render = t


	def run(self, scr):
		if len(self.nodes) == 0:
			raise SystemError("Cannot run with no nodes to check")

		Thread(target=self.voice_thread, name="thrVoice", daemon=True).start() # daemonized to avoid waiting until speech ends after exit (what about resource leaks?)

		init_screen(scr)

		if len(self.music_filepaths) > 0:
			# pygame.init()
			pygame.mixer.init()

		quit = False
		while not quit:
			self.render(scr)
			self.alarm_if_disconnects_change()
			self.sync_check()
			self.update_peak_durations()
			self.sync_music()

			ch = scr.getch()

			# Process input
			if ch in [ord('q'), ord('Q')]:
				self.voice_queue.put([VoiceQueueMessage.QUIT])
				quit = True
			elif ch == curses.KEY_UP:
				self.page_start = max(0, self.page_start - 1)
			elif ch == curses.KEY_DOWN:
				self.page_start = max(0, min(len(self.nodes) - self.page_size, self.page_start + 1))
			elif ch == curses.KEY_PPAGE:
				self.page_start = max(0, self.page_start - self.page_size + 1)
			elif ch == curses.KEY_NPAGE:
				self.page_start = max(0, min(len(self.nodes) - self.page_size, self.page_start + self.page_size - 1))
			elif ch == curses.KEY_HOME:
				self.page_start = 0
			elif ch == curses.KEY_END:
				self.page_start = max(0, len(self.nodes) - self.page_size)				
			elif ch in [ord('p'), ord('P')]:
				self.show_peaks = { ShowPeaksMode.NONE : ShowPeaksMode.CONN,
					ShowPeaksMode.CONN : ShowPeaksMode.DISCONN,
					ShowPeaksMode.DISCONN : ShowPeaksMode.NONE
				}[self.show_peaks]
			elif ch in [ord('m'), ord('M')]:
				self.show_map = not self.show_map
			elif ch in [ord('d'), ord('D')]:
				self.show_history_distribution = not self.show_history_distribution
			elif ch in [ord('l'), ord('L')]:
				self.save_log(DEFAULT_LOG_FILENAME)
			elif ch in [ord('h'), ord('H')]:
				self.hush()
			elif ch in [ord('u'), ord('U')]:
				self.alarm_if_disconnects_change(True)
			elif ch in [ord('n'), ord('N')]:
				self.sync_music(True)
			elif ch == curses.KEY_LEFT:
				self.change_music_volume(-1)
			elif ch == curses.KEY_RIGHT:
				self.change_music_volume(1)

			time.sleep(1.0 / self.idlerate)

		self.finish_music()


def main():
	aranea = Aranea()
	aranea.load_config(DEFAULT_CONFIG_FILENAME)
	curses.wrapper(aranea.run)


main()
