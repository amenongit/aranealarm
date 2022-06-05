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
APP_VER = "v1.0.8 (2022.06.05)"
APP_LINK = "github.com/amenongit/aranealarm"
APP_COPYR_PART1 = "© 2022 Ame"
APP_COPYR_PART2 = "▄▄▄"
APP_COPYR_PART3 = "Non"

HISTORY_SIZE_BINLOG = 17
HISTORY_SIZE = 1 << HISTORY_SIZE_BINLOG
HISTORY_SIZE_BINMASK = HISTORY_SIZE - 1

LOG_SIZE_BINLOG = 17
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

DEFAULT_HUSH_INTERVAL = 30 # sec

DEFAULT_ALARM_ROW_HEIGHT = 2 # must be >= 2

ALARM_CAPTION = "A L A R M"
QUIET_CAPTION = "Q U I E T"
DISCONNECT_CAPTION = "disconnect"
DISCONNECTS_CAPTION = "disconnects"
DURATION_CAPTION = "LASTS FOR"
HUSHED_CAPTION = "HUSH"
BEHIND_CAPTION = "Behind"

ALARM_SPEECH = "Alarm"
DISCONNECT_SPEECH = "disconnect"
DISCONNECTS_SPEECH = "disconnects"

DEFAULT_MUSIC_VOLUME = 20

NUMBER_HEADER = "Num"
NUMBER_COL_START = 1
NUMBER_COL_WIDTH = 3

ADDRESS_HEADER = "Address"

ADDRESS_SEP_NODE_COL_WIDTH = 8

NODE_HEADER = "Node"
NODE_COL_START = NUMBER_COL_START + NUMBER_COL_WIDTH + 1
NODE_COL_MAX_WIDTH = 48

RESPONSETIME_HEADER = " RespTime"
RESPONSETIME_DELTA_HEADER = "ΔRespTime"
RESPONSETIME_AVG_HEADER = "μRespTime"
RESPONSETIME_STDDEV_HEADER = "σRespTime"
RESPONSEDATA_HEADER = "RespData"
RESPONSE_COL_WIDTH = 9

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

HELP_ROW_HEIGHT = 3

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


class VoiceQueueMsg(Enum):
	DISCONNECTS_NUM = auto()
	SPEAK = auto()
	HUSH = auto()
	QUIT = auto()


class RespTimeStatsMode(Enum):
	NONE = auto()
	DELTA = auto()
	MAX = auto()
	AVG = auto()
	STDDEV = auto()


class DurationStatsMode(Enum):
	NONE = auto()
	CONN_MAX = auto()
	DISCONN_MAX = auto()


class GeoLoc:
	def __init__(self, lat, lon):
		self.lat, self.lon = lat, lon


	def to_str(self):
		ns = "N" if self.lat >=0 else "S"
		lat_abs = math.fabs(self.lat)
		lat_d = int(math.floor(lat_abs))
		lat_m = int(math.floor(60.0 * (lat_abs - lat_d)))
		lat_s = int(math.floor(3600.0 * (lat_abs - lat_d - lat_m / 60.0)))

		ew = "E" if self.lon >=0 else "W"
		lon_abs = math.fabs(self.lon)
		lon_d = int(math.floor(lon_abs))
		lon_m = int(math.floor(60.0 * (lon_abs - lon_d)))
		lon_s = int(math.floor(3600.0 * (lon_abs - lon_d - lon_m / 60.0)))

		return f"{lat_d}°{lat_m}′{lat_s}″{ns}|{lon_d}°{lon_m}′{lon_s}″{ew}"


class Place:
	def __init__(self, name, geoloc, char):
		self.name, self.geoloc, self.char = name, geoloc, char


def ttl2hops(ttl): # guess, if TTL is a power of 2
	ttl0 = ttl
	while (ttl0 < 255) and (ttl0 & (ttl0 - 1) != 0): # x & (x - 1) = 0 iff x = 2^y
		ttl0 += 1
	return ttl0 - ttl


def ttl2os(ttl): # guess, if TTL is default (Linux - 64, Windows - 128, Mac - 255)
	if ttl > 128:
		return "Mac"
	elif ttl > 64:
		return "Win"
	else:
		return "Lin"


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
		self.prev_response_time = None
		self.peak_response_time = -1
		self.response_times_sum = 0.0
		self.response_times_sqr_sum = 0.0
		self.response_times_num = 0

		self.datas = [] # [["Name1", Value1], ["Name2", Value2], ...]

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

		
	def update_conn(self, connected, response_time, datas):
		if connected:
			self.prev_response_time = self.response_time
			self.response_time = response_time
			self.peak_response_time = max(self.peak_response_time, self.response_time)
			self.response_times_sum += self.response_time
			self.response_times_sqr_sum += self.response_time * self.response_time
			self.response_times_num += 1
			self.datas = datas
	
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


	def update_history_pos(self):
		self.history_pos = (self.history_pos + 1) & HISTORY_SIZE_BINMASK


	def update_peak_durations(self):
		duration = int(time.time()) - self.t_last_change
		if self.connected:
			self.peak_conn_duration = max(self.peak_conn_duration, duration)
		else:
			self.peak_disconn_duration = max(self.peak_disconn_duration, duration)


	def resptime_average(self):
		if self.response_times_num > 0:
			return self.response_times_sum / self.response_times_num
		else:
			return None


	def resptime_stddev(self):
		if self.response_times_num > 1:
			m2 = self.response_times_sqr_sum / self.response_times_num
			m1 = self.response_times_sum / self.response_times_num
			return math.sqrt(self.response_times_num * (m2 - m1 * m1) / (self.response_times_num - 1))
		else:
			return None


class IPNode(Node):
	def __init__(self, ip=DEFAULT_IP, name=DEFAULT_NAME, speech_name=DEFAULT_SPEECH_NAME, wait_dur=DEFAULT_WAIT_DUR, attempts=DEFAULT_ATTEMPTS, geoloc=DEFAULT_GEOLOC):
		super().__init__(ip, name, speech_name, wait_dur, attempts, geoloc)


	def checker(self, index, msg_queue): # runs in a separate thread
		ping_cmd = {
			"Linux" : ["ping", "-c 1", f"-W {max(1, int(round(0.001 * self.wait_dur)))}", f"{self.address}"],
			"Windows" : f"ping -n 1 -w {self.wait_dur} {self.address}",
			"Darwin" : ["ping", "-c 1", f"-W {self.wait_dur}", f"{self.address}"]
		}[platform.system()]

		connected = False
		response_time = None

		ttl_data = None
		hops_data = None
		os_data = None

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
				for s in ping_out_str_split:
					if s.startswith("TTL=") or s.startswith("ttl="):
						ttl = int(s[4:]) # Linux: "ttl=123" -> 123; Windows: "TTL=123" -> 123; MacOS: ???
						ttl_data = ["TTL", ttl]
						hops_data = ["Hops", ttl2hops(ttl)]
						os_data = ["OS", ttl2os(ttl)]
						break
				break

		if response_time is None:
			response_time = int(1000 * (time.time() - t_start)) # less accurate due to call overhead

		datas = [ttl_data, hops_data, os_data]

		msg_queue.put([index, connected, response_time, datas])


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
		self.t_last_alarm_state_change = 0

		self.hushed = False
		self.hush_interval = DEFAULT_HUSH_INTERVAL

		self.voice_queue = Queue()

		self.pass_num = 0
		self.log = [None] * LOG_SIZE # ring buffer
		self.log_pos = 0
		self.log_needs_update = False
		self.log_row_start = 0

		self.longest_response_time = -1
		self.last_respondents = set()
		self.last_last_respondents = set()

		self.behind = 0
		self.fast_past_scroll = False

		self.page_start = 0
		self.page_size = 1

		self.response_data = 0 # 0 is time, 1-9 are data
		self.resptime_stats_mode = RespTimeStatsMode.NONE
		self.duration_stats_mode = DurationStatsMode.NONE

		self.show_history_distribution = False
		
		self.t_last_render = 0.0

		self.alarm_row_height = max(2, DEFAULT_ALARM_ROW_HEIGHT)
		self.alarm_blink = False
		self.t_last_alarm_blink = False

		self.places = []
		self.map_min_lat, self.map_max_lat = 180.0, -180.0
		self.map_min_lon, self.map_max_lon = 90.0, -90.0
		self.show_map = True

		self.music_filepaths = []
		self.music_current = -1
		self.music_volume = DEFAULT_MUSIC_VOLUME
		self.music_paused = False
		self.music_shuffle = True


	def voice_thread(self):
		speak_engine = pyttsx3.init()
		disconnects_num = 0
		t_last_speech = 0
		speech_interval = 0
		quit = False
		while not quit:
			while not self.voice_queue.empty():
				msg = self.voice_queue.get()
				if msg[0] == VoiceQueueMsg.DISCONNECTS_NUM:
					disconnects_num = msg[1]
					t_last_speech = 0
					if disconnects_num == 0:
						speak_engine.stop()
				elif msg[0] == VoiceQueueMsg.SPEAK:
					speak_engine.say(msg[1])
					t_last_speech = 0
				elif msg[0] == VoiceQueueMsg.HUSH:
					speech_interval = msg[1]
				elif msg[0] == VoiceQueueMsg.QUIT:
					quit = True
				else:
					raise SystemError("Unknown message: \"" + str(msg) + "\"")
			t = time.time()
			if (not quit) and (disconnects_num > 0) and (t - t_last_speech > speech_interval):
					speak_engine.say(f"{ALARM_SPEECH}: {disconnects_num} {DISCONNECTS_SPEECH if disconnects_num > 1 else DISCONNECT_SPEECH}")
					speak_engine.runAndWait()
					t_last_speech = t
			time.sleep(1.0 / self.idlerate)


	def add_node(self, node):
		self.nodes.append(node)


	def load_ip_nodes(self, filepath):
		nodeslist_file = open(filepath, "r")
		nodeslist = json.load(nodeslist_file)
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
		placeslist = json.load(placeslist_file)
		placeslist_file.close()

		for place_descr in placeslist:
			name = place_descr.get("name")
			geoloc = place_descr.get("geoloc")
			geoloc = GeoLoc(geoloc.get("lat"), geoloc.get("lon"))
			char = place_descr.get("char")
			self.places.append(Place(name, geoloc, char))


	def load_config(self, filepath):
		config_file = open(filepath, "r")
		config_descr = json.load(config_file)
		config_file.close()

		ip_nodeslists = config_descr.get("ip", None)
		if ip_nodeslists is not None:
			for fp in ip_nodeslists:
				self.load_ip_nodes(fp)

		placeslists = config_descr.get("place", None)
		if placeslists is not None:
			for fp in placeslists:
				self.load_places(fp)

		self.alarm_row_height = max(2, config_descr.get("alarm_row_height", DEFAULT_ALARM_ROW_HEIGHT))

		self.hush_interval = max(1, config_descr.get("hush_interval", DEFAULT_HUSH_INTERVAL))

		music_filepaths_descr = config_descr.get("music", None)
		if music_filepaths_descr is not None:
			for fp in music_filepaths_descr:
				self.music_filepaths.append(fp)
		self.music_volume = max(0, min(100, config_descr.get("music_volume", DEFAULT_MUSIC_VOLUME)))		


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


	def has_music(self):
		return len(self.music_filepaths) > 0


	def sync_check(self):
		while not self.check_queue.empty():
			i, connected, response_time, datas = self.check_queue.get()
			self.nodes[i].update_conn(connected, response_time, datas)
			self.unchecked_num -= 1
			if connected:
				if response_time > self.longest_response_time:
					self.longest_response_time = response_time
					self.last_respondents.clear()
					self.last_respondents.add(i)
				elif response_time == self.longest_response_time:
					self.last_respondents.add(i)

		for node in self.nodes:
			node.update_peak_durations()

		if self.unchecked_num == 0: # current check pass is finished
			if self.log_needs_update:
				self.pass_num += 1
				self.update_log()
				for node in self.nodes:
					node.update_history_pos()
				if self.behind > 0:
					self.behind += 1
				self.last_last_respondents = self.last_respondents.copy()
				
			t = time.time()
			if t - self.t_last_check > 1.0 / self.checkrate: # start next check pass
				self.t_last_check = t
				self.unchecked_num = len(self.nodes)
				self.log_needs_update = True
				self.longest_response_time = -1
				self.last_respondents.clear()
				for i, node in enumerate(self.nodes):
					Thread(target=node.checker, args=(i, self.check_queue), name=f"thrPing{1+i}", daemon=True).start() # daemonized to avoid waiting until ping ends after exit (what about resource leaks?)


	def sync_alarm(self):
		disconn_nodes_set = self.disconn_nodes_set()
		if disconn_nodes_set != self.last_disconn_nodes_set: # change
			new_disconn_set = disconn_nodes_set - self.last_disconn_nodes_set # may be empty
			for i in new_disconn_set:
				self.voice_queue.put([VoiceQueueMsg.SPEAK, self.nodes[i].speech_name + " " + DISCONNECT_SPEECH])
			self.last_disconn_nodes_set = disconn_nodes_set.copy()
			disconnects = len(disconn_nodes_set)
			if (self.last_disconnects > 0) != (disconnects > 0):
				self.t_last_alarm_state_change = int(time.time())
			self.last_disconnects = disconnects
			self.voice_queue.put([VoiceQueueMsg.DISCONNECTS_NUM, self.last_disconnects])
			if self.has_music():
				if self.last_disconnects > 0:
					if not self.music_paused:
						self.music_paused = True
						pygame.mixer.music.pause()
				else:
					if self.music_paused:
						self.music_paused = False
						pygame.mixer.music.unpause()


	def set_hush(self, hushed, duration=None):
		self.hushed = hushed
		if duration is not None:
			self.hush_interval = duration
		if self.hushed:
			self.voice_queue.put([VoiceQueueMsg.HUSH, self.hush_interval])
		else:
			self.voice_queue.put([VoiceQueueMsg.HUSH, 0])


	def sync_music(self, force_next=False):
		if self.has_music():
			if force_next or ((not self.music_paused) and (not pygame.mixer.music.get_busy())): # current music ended (or no music has been started yet)
				if self.music_current >= 0:
					if force_next:
						pygame.mixer.music.stop()
					pygame.mixer.music.unload()
				if self.music_shuffle:
					self.music_current = random.randrange(len(self.music_filepaths))
				else:
					self.music_current = (self.music_current + 1) % len(self.music_filepaths) if self.music_current >= 0 else 0
				try:
					pygame.mixer.music.load(self.music_filepaths[self.music_current])
				except:
					pass
				pygame.mixer.music.set_volume(self.music_volume / 100)
				try:
					pygame.mixer.music.play()
				except:
					pass
				if self.music_paused:
					pygame.mixer.music.pause()


	def finish_music(self):
		if self.has_music():
			pygame.mixer.music.stop()
			pygame.mixer.music.unload()
			pygame.mixer.quit()
			# pygame.quit()


	def change_music_volume(self, delta):
		self.music_volume = max(0, min(100, self.music_volume + delta))
		if self.has_music():
			pygame.mixer.music.set_volume(self.music_volume / 100)


	def response_time_stats(self):
		t_min, t_max = 0xFFFFFFFF, -1
		t_avg, t_stddev = 0.0, 0.0
		n = 0
		for node in self.nodes:
			if node.connected: # use filter() here?
				n += 1
				t = node.response_time
				t_min, t_max = min(t_min, t), max(t_max, t)
				t_avg += t
				t_stddev += t * t
		if n > 0:
			t_avg /= n
			t_stddev /= n
			t_stddev = math.sqrt(n * (t_stddev - t_avg * t_avg) / max(1, n - 1))
		return t_min, int(round(t_avg)), t_max, int(round(t_stddev))


	def update_log(self):
		self.log[self.log_pos] = LogEntry(datetime.datetime.now(), self.pass_num, self.disconnects(), self.disconn_nodes(), self.response_time_stats())
		self.log_pos = (self.log_pos + 1) & LOG_SIZE_BINMASK
		self.log_needs_update = False


	def write_log(self, filepath):
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
				log_file.write(s + "\n")
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
		y = max(min_y, min(curses.LINES - HELP_ROW_HEIGHT - 2, curses.LINES - HELP_ROW_HEIGHT - 2 - int(round( (geoloc.lat - self.map_min_lat) * (curses.LINES - HELP_ROW_HEIGHT - 2 - min_y) / max(1e-16, self.map_max_lat - self.map_min_lat) ))))
		x = max(1, min(curses.COLS - 2, 1 + int(round( (geoloc.lon - self.map_min_lon) * (curses.COLS - 3) / max(1e-16, self.map_max_lon - self.map_min_lon) ))))
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
			response_col_start = NODE_COL_START + node_col_width + 1
			connected_col_start = response_col_start + RESPONSE_COL_WIDTH + 1
			duration_col_start = connected_col_start + CONNECTED_COL_WIDTH + 1
			issues_col_start = duration_col_start + DURATION_COL_WIDTH + 1
			history_col_start = issues_col_start + ISSUES_COL_WIDTH + 1
			self.page_size = min(len(self.nodes), curses.LINES // 3)

			scr.erase()

			# Borders
			bcp = ccp(CCLR_GRAY, CCLR_BLACK)

			caddstr(0, 0, "╭", bcp)
			caddstr(0, curses.COLS - 1, "╮", bcp)
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

			caddstr(headers_row - 1, response_col_start - 1, "┬", bcp)
			draw_vline(scr, response_col_start - 1, headers_row, headers_row, bcp)
			caddstr(headers_row + 1, response_col_start - 1, "┼", bcp)

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
			caddstr(headers_row + 1, curses.COLS - 1, "┤" if self.show_history_distribution else "╯", bcp)

			nodes_top_row = headers_row + 2

			draw_vline(scr, NUMBER_COL_START - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, NODE_COL_START - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, response_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)		
			draw_vline(scr, connected_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, duration_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, issues_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			draw_vline(scr, history_col_start - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)
			if self.show_history_distribution:
				draw_vline(scr, curses.COLS - 1, nodes_top_row, nodes_top_row - 1 + self.page_size, bcp)

			bottom_border_row = nodes_top_row + self.page_size

			caddstr(bottom_border_row, 0, "├", bcp)
			draw_hline(scr, bottom_border_row, 1, curses.COLS - 1, bcp)
			caddstr(bottom_border_row, curses.COLS - 1, "┤" if self.show_history_distribution else "╮", bcp)

			caddstr(bottom_border_row, NODE_COL_START - 1, "┴", bcp)
			caddstr(bottom_border_row, response_col_start - 1, "┴", bcp)
			caddstr(bottom_border_row, connected_col_start - 1, "┴", bcp)
			caddstr(bottom_border_row, duration_col_start - 1, "┴", bcp)
			caddstr(bottom_border_row, issues_col_start - 1, "┴", bcp)
			caddstr(bottom_border_row, history_col_start - 1, "┴", bcp)

			draw_vline(scr, 0, bottom_border_row + 1, curses.LINES - HELP_ROW_HEIGHT - 2, bcp)
			draw_vline(scr, curses.COLS - 1, bottom_border_row + 1, curses.LINES - HELP_ROW_HEIGHT - 2, bcp)

			caddstr(curses.LINES - HELP_ROW_HEIGHT - 1, 0, "╰", bcp)
			draw_hline(scr, curses.LINES - HELP_ROW_HEIGHT - 1, 1, curses.COLS - 2, bcp)
			caddstr(curses.LINES - HELP_ROW_HEIGHT - 1, curses.COLS - 1, "╯", bcp)

			# Title
			caddstr(0, title_col_start, " " + APP_NAME + " ", ccp(CCLR_BLACK, CCLR_WHITE))

			# Alarm
			alarm_row = (1 + self.alarm_row_height) >> 1
			if self.last_disconnects > 0:
				alarm_fg, alarm_bg = (CCLR_YELLOW, CCLR_DARKRED) if self.alarm_blink else (CCLR_DARKRED, CCLR_YELLOW)
				draw_fillrect(scr, 1, 1, self.alarm_row_height, curses.COLS - 2, ccp(alarm_bg))
				caddstr(alarm_row, (curses.COLS - len(ALARM_CAPTION)) >> 1, ALARM_CAPTION, ccp(alarm_fg, alarm_bg))
				alarm_disconnects_caption = f"{self.last_disconnects} {DISCONNECTS_CAPTION if self.last_disconnects > 1 else DISCONNECT_CAPTION}"
				caddstr(alarm_row + 1, (curses.COLS - len(alarm_disconnects_caption)) >> 1, alarm_disconnects_caption, ccp(alarm_fg, alarm_bg))
				if t - self.t_last_alarm_blink > 1.0 / self.blinkrate:
					self.alarm_blink = not self.alarm_blink
					self.t_last_alarm_blink = t
			else:
				alarm_fg, alarm_bg = (CCLR_GREEN, CCLR_DARKGREEN)
				draw_fillrect(scr, 1, 1, self.alarm_row_height, curses.COLS - 2, ccp(alarm_bg))
				caddstr(alarm_row, (curses.COLS - len(QUIET_CAPTION)) >> 1, QUIET_CAPTION, ccp(alarm_fg, alarm_bg))
				if self.has_music():
					music_filename = self.music_filepaths[self.music_current].split(sep="/")[-1]
					music_caption = f"♪ {music_filename} ♪"
					caddstr(alarm_row + 1, (curses.COLS - len(music_caption)) >> 1, music_caption, ccp(alarm_fg, alarm_bg))
			# Alarm duration
			duration = int(t) - self.t_last_alarm_state_change
			hours, secs = duration // 3600, duration % 3600
			mins, secs = secs // 60, secs % 60
			caddstr(alarm_row, 1, DURATION_CAPTION, ccp(alarm_fg, alarm_bg))
			caddstr(alarm_row + 1, 1, f"{hours:03}:{mins:02}:{secs:02}", ccp(alarm_fg, alarm_bg))
			# Hush
			if self.hushed:
				caddstr(alarm_row, curses.COLS - 1 - len(HUSHED_CAPTION), HUSHED_CAPTION, ccp(alarm_fg, alarm_bg))
				hush_interval_caption = f"{self.hush_interval} s"
				caddstr(alarm_row + 1, curses.COLS - 1 - len(hush_interval_caption), hush_interval_caption, ccp(alarm_fg, alarm_bg))

			# Headers
			headers_cp = ccp(CCLR_GRAY)
			caddstr(headers_row, NUMBER_COL_START, NUMBER_HEADER, headers_cp)
			caddstr(headers_row, NODE_COL_START, ADDRESS_HEADER, headers_cp)
			caddstr(headers_row, NODE_COL_START + node_col_width - len(NODE_HEADER), NODE_HEADER, headers_cp)
			if self.response_data > 0:
				caddstr(headers_row, response_col_start, f"{RESPONSEDATA_HEADER}{self.response_data}", headers_cp)
			else:
				caddstr(headers_row, response_col_start, {
						RespTimeStatsMode.NONE : RESPONSETIME_HEADER,
						RespTimeStatsMode.DELTA : RESPONSETIME_DELTA_HEADER,
						RespTimeStatsMode.AVG : RESPONSETIME_AVG_HEADER,
						RespTimeStatsMode.STDDEV: RESPONSETIME_STDDEV_HEADER,
						RespTimeStatsMode.MAX : RESPONSETIME_HEADER.upper()
					}[self.resptime_stats_mode],
					headers_cp
				)
			caddstr(headers_row, connected_col_start, CONNECTED_HEADER, headers_cp)
			caddstr(headers_row, duration_col_start,
				DURATION_HEADER if self.duration_stats_mode == DurationStatsMode.NONE else DURATION_HEADER.upper(),
				headers_cp | (curses.A_REVERSE if self.duration_stats_mode == DurationStatsMode.DISCONN_MAX else 0)
			)
			caddstr(headers_row, issues_col_start, ISSUES_HEADER)
			caddstr(headers_row, history_col_start, HISTORY_DISTRIBUTION_HEADER if self.show_history_distribution else HISTORY_HEADER)
			if self.behind > 0:
				behind_str = f"{BEHIND_CAPTION} {self.behind}"
				caddstr(headers_row, curses.COLS - 1 - len(behind_str), behind_str, ccp(CCLR_WHITE, CCLR_DARKBLUE))

			# Nodes
			for i, node in enumerate(self.nodes[self.page_start:min(len(self.nodes), self.page_start + self.page_size)]):
				row = nodes_top_row + i
				rev_attr = curses.A_REVERSE if not node.connected else 0 # should be more eye-catching
				node_back_color = CCLR_BLACK if node.connected else CCLR_YELLOW
				node_cp_bright = ccp(CCLR_GREEN, node_back_color) if node.connected else ccp(CCLR_RED, node_back_color)
				node_cp_dark = ccp(CCLR_DARKGREEN, node_back_color) if node.connected else ccp(CCLR_DARKRED, node_back_color)
				# Number
				caddstr(row, NUMBER_COL_START, f"{self.page_start + i + 1:0{NUMBER_COL_WIDTH}}", node_cp_dark | rev_attr)
				# Address
				caddstr(row, NODE_COL_START, node.address, node_cp_dark | rev_attr)
				# Name
				caddstr(row, max(0, NODE_COL_START + node_col_width - len(node.name)), node.name, node_cp_bright | rev_attr)
				if len(node.address) + len(node.name) + 2 < node_col_width:
					draw_fillrect(scr, row, NODE_COL_START + len(node.address) + 1, row, NODE_COL_START + node_col_width - len(node.name) - 2, ccp(CCLR_DARKGRAY), "ˑ") # other fillers: "˒", "˗", "┈", "╴", "·", "▸", "-"
				# Response data: 0 - time or its peak or its average or its stddev, 1-9 - other data
				if self.response_data > 0:
					respdata_cp = ccp(CCLR_DARKGRAY)
					if node.connected and (self.response_data <= len(node.datas)) and (node.datas[self.response_data - 1] is not None):
						respdata = node.datas[self.response_data - 1]
						respdata_name, respdata_value_str = respdata[0], str(respdata[1])
						caddstr(row, response_col_start, respdata_name, respdata_cp)
						caddstr(row, response_col_start + RESPONSE_COL_WIDTH - len(respdata_value_str), respdata_value_str, respdata_cp)
				else:
					resptime_cp = ccp(CCLR_BLUE)
					resptime_str = None
					monotonicity_char = None
					if self.resptime_stats_mode == RespTimeStatsMode.NONE:
						if node.connected and (node.response_time is not None):
							resptime_str = f"{node.response_time}"
							if node.prev_response_time is not None:
								monotonicity_char = "►" if node.response_time > node.prev_response_time else ("◊" if node.response_time == node.prev_response_time else "◄") # or "▲", "▼"
							else:
								monotonicity_char = " "
					elif self.resptime_stats_mode == RespTimeStatsMode.DELTA:
						if node.connected and (node.response_time is not None) and (node.prev_response_time is not None):
							delta = node.response_time - node.prev_response_time
							resptime_str = "0" if delta == 0 else f"{delta:+}"
					elif self.resptime_stats_mode == RespTimeStatsMode.AVG:
						if node.response_times_num > 0:
							resptime_str = f"{int(round(node.resptime_average()))}"
					elif self.resptime_stats_mode == RespTimeStatsMode.STDDEV:
						if node.response_times_num > 1:
							resptime_str = f"{int(round(node.resptime_stddev()))}"
					elif self.resptime_stats_mode == RespTimeStatsMode.MAX:
						if node.peak_response_time >= 0:
							resptime_str = f"{node.peak_response_time}"
					if resptime_str is not None:
						monoton_indent = 0
						if monotonicity_char is not None:
							caddstr(row, response_col_start, monotonicity_char, ccp(CCLR_DARKBLUE) |
								(curses.A_REVERSE if (i in self.last_last_respondents) else 0))
							monoton_indent += 2
						if len(resptime_str) + 1 + monoton_indent < RESPONSE_COL_WIDTH:
							draw_fillrect(scr, row, response_col_start + monoton_indent, row, response_col_start + RESPONSE_COL_WIDTH - len(resptime_str) - 2, ccp(CCLR_DARKGRAY), "ˑ")
						caddstr(row, response_col_start + RESPONSE_COL_WIDTH - len(resptime_str), resptime_str, resptime_cp)
				# Connected?
				caddstr(row, connected_col_start, YES_CAPTION if node.connected else NO_CAPTION, node_cp_bright | rev_attr)
				# Duration of current (dis)connection or its peaks
				if self.duration_stats_mode == DurationStatsMode.NONE:
					duration = int(t) - node.t_last_change
					duration_cp = ccp(CCLR_DARKCYAN) if node.connected else ccp(CCLR_MAGENTA)
				elif self.duration_stats_mode == DurationStatsMode.CONN_MAX:
					duration = node.peak_conn_duration
					duration_cp = ccp(CCLR_DARKCYAN)
				elif self.duration_stats_mode == DurationStatsMode.DISCONN_MAX:
					duration = node.peak_disconn_duration
					duration_cp = ccp(CCLR_MAGENTA)
				if duration >= 0:
					hours, secs = duration // 3600, duration % 3600
					mins, secs = secs // 60, secs % 60
					caddstr(row, duration_col_start, f"{hours:03}:{mins:02}:{secs:02}", duration_cp)
				# Number of connected -> disconnected changes
				caddstr(row, issues_col_start, f"{node.issues:4}", ccp(CCLR_DARKYELLOW))
				# History or its distribution
				if self.show_history_distribution:
					conn_part = (curses.COLS - 1 - history_col_start) * node.history_conn_num // max(1, node.history_past_num)
					if conn_part > 0:
						draw_fillrect(scr, row, history_col_start, row, history_col_start + conn_part - 1, ccp(CCLR_GREEN), symb="▀")
					if conn_part < (curses.COLS - 1 - history_col_start):
						draw_fillrect(scr, row, history_col_start + conn_part, row, curses.COLS - 2, ccp(CCLR_RED), symb="▀")
				else:
					for j in range(max(0, curses.COLS - history_col_start)):
						conn = node.history[(node.history_pos - self.behind - j) & HISTORY_SIZE_BINMASK]
						if conn is not None:
							caddstr(row, history_col_start + j, HISTORY_CHAR_CONNECT if conn else HISTORY_CHAR_DISCONNECT, ccp(CCLR_GREEN) if conn else ccp(CCLR_RED))

			self.log_row_start = bottom_border_row + 1

			# Map or reversed log
			if self.show_map:
				self.update_map_boundbox()
				if (self.map_min_lat <= self.map_max_lat) and (self.map_min_lon <= self.map_max_lon):
					# Places
					place_bright_cp = ccp(CCLR_GRAY)
					place_dark_cp = ccp(CCLR_DARKGRAY)
					for place in self.places:
						y, x = self.geoloc_to_scr_yx(place.geoloc, self.log_row_start)
						if x < curses.COLS >> 1:
							caddstr(y, x, place.char, place_bright_cp)
							caddstr(f" {place.name}", place_dark_cp)
						else: # avoid printing over right edge
							x -= len(place.name) + 1
							caddstr(y, x, f"{place.name} ", place_dark_cp)
							caddstr(place.char, place_bright_cp)
					# Corners
					geo_mins_str = GeoLoc(self.map_min_lat, self.map_min_lon).to_str()
					caddstr(curses.LINES - HELP_ROW_HEIGHT - 2, 1, geo_mins_str, ccp(CCLR_DARKGRAY) | curses.A_REVERSE)
					geo_maxs_str = GeoLoc(self.map_max_lat, self.map_max_lon).to_str()
					caddstr(self.log_row_start, curses.COLS - 1 - len(geo_maxs_str), geo_maxs_str, ccp(CCLR_DARKGRAY) | curses.A_REVERSE)
					# Nodes
					for i, node in enumerate(self.nodes):
						if node.geoloc is not None:
							node_char = HISTORY_CHAR_CONNECT if node.connected else HISTORY_CHAR_DISCONNECT
							node_bright_cp = ccp(CCLR_GREEN) if node.connected else ccp(CCLR_RED)
							node_dark_cp = ccp(CCLR_DARKGREEN) if node.connected else ccp(CCLR_DARKRED)
							y, x = self.geoloc_to_scr_yx(node.geoloc, self.log_row_start)
							if x < curses.COLS >> 1:
								caddstr(y, x, node_char, node_bright_cp)
								caddstr(f"{1 + i}", node_dark_cp | curses.A_REVERSE)
							else: # avoid printing over right edge
								x -= len(str(i))
								caddstr(y, x, f"{1 + i}", node_dark_cp | curses.A_REVERSE)
								caddstr(node_char, node_bright_cp)
			else:
				for i in range(max(0, curses.LINES - HELP_ROW_HEIGHT - 1 - self.log_row_start)):
					entry = self.log[(self.log_pos - self.behind - 1 - i) & LOG_SIZE_BINMASK] # -1: current pass has not finished yet
					if entry is not None:
						caddstr(self.log_row_start + i, 1, "[" + entry.instant.strftime("%H:%M:%S") + "] ", ccp(CCLR_DARKBLUE))
						caddstr(f"Pass {entry.pass_num:6}: ", ccp(CCLR_DARKGREEN) if entry.disconnects == 0 else ccp(CCLR_DARKYELLOW))
						caddstr(f"{entry.disconnects:3} {DISCONNECT_CAPTION if entry.disconnects == 1 else DISCONNECTS_CAPTION}", ccp(CCLR_GREEN) if entry.disconnects == 0 else ccp(CCLR_YELLOW))
						if entry.disconnects > 0:
							caddstr(" (" + str(entry.disconn_nodes).replace(" ", "")[1:-1] + ")", ccp(CCLR_RED))
						caddstr(", ", ccp(CCLR_GREEN) if entry.disconnects == 0 else ccp(CCLR_YELLOW))
						caddstr(f"response time Min {entry.resptime_stats[0]:5}, Avg {entry.resptime_stats[1]:5}, Max {entry.resptime_stats[2]:5}, StdDev {entry.resptime_stats[3]:5}", ccp(CCLR_BLUE))

			# Help
			help_bright_cp = ccp(CCLR_GRAY)
			help_dark_cp = ccp(CCLR_DARKGRAY)
			caddstr(curses.LINES - HELP_ROW_HEIGHT + 0, 0, "|", help_dark_cp)
			caddstr("↑/↓/PgUp/PgDown/Home/End", help_bright_cp)
			caddstr(":scroll nodes|", help_dark_cp)

			caddstr("Shift+PgUp/PgDown/Home/End", help_bright_cp)
			caddstr(":scroll log & history (", help_dark_cp)

			caddstr("F", help_bright_cp)
			caddstr("ast " + ("√" if self.fast_past_scroll else "×") + ")|", help_dark_cp) # Terminal does not display "✓", "✗"...

			caddstr(curses.LINES - HELP_ROW_HEIGHT + 1, 0, "|", help_dark_cp)
			caddstr("0/1-9", help_bright_cp)
			caddstr(":response time/data|", help_dark_cp)
	
			caddstr("R", help_bright_cp)
			caddstr("esponse, ", help_dark_cp)

			caddstr("L", help_bright_cp)
			caddstr("asting time stats|", help_dark_cp)

			caddstr("history ", help_dark_cp)
			caddstr("D", help_bright_cp)
			caddstr("istribution|", help_dark_cp)

			caddstr("</>", help_bright_cp)
			caddstr(":prev/next disconnect|", help_dark_cp)

			caddstr(curses.LINES - HELP_ROW_HEIGHT + 2, 0, "|", help_dark_cp)
			caddstr("Q", help_bright_cp)
			caddstr("uit|", help_dark_cp)

			caddstr("M", help_bright_cp)
			caddstr("ap <-> log|", help_dark_cp)

			caddstr("W", help_bright_cp)
			caddstr("rite log|", help_dark_cp)

			caddstr("H", help_bright_cp)
			caddstr("ush (", help_dark_cp)
			caddstr("[/]/{/}", help_bright_cp)
			caddstr(":interval)|", help_dark_cp)

			if self.has_music():
				caddstr("N", help_bright_cp)
				caddstr("ext music (", help_dark_cp)
				caddstr("S", help_bright_cp)
				caddstr("huffle " + ("√" if self.music_shuffle else "×") + ")|", help_dark_cp)
				caddstr("←/→", help_bright_cp)
				caddstr(f":music volume {self.music_volume:03}|", help_dark_cp)

			# Version & link & copyright
			caddstr(curses.LINES - HELP_ROW_HEIGHT + 0, curses.COLS - 1 - len(APP_VER), APP_VER, ccp(CCLR_DARKGRAY))
			caddstr(curses.LINES - HELP_ROW_HEIGHT + 1, curses.COLS - 1 - len(APP_LINK), APP_LINK, ccp(CCLR_DARKGRAY))
			caddstr(curses.LINES - HELP_ROW_HEIGHT + 2, curses.COLS - 1 - (len(APP_COPYR_PART1) + len(APP_COPYR_PART2) + len(APP_COPYR_PART3)), APP_COPYR_PART1, ccp(CCLR_DARKGRAY))
			caddstr(APP_COPYR_PART2, ccp(CCLR_DARKYELLOW, CCLR_DARKBLUE))
			caddstr(APP_COPYR_PART3, ccp(CCLR_DARKGRAY))

			scr.refresh()
			self.t_last_render = t


	def run(self, scr):
		if len(self.nodes) == 0:
			raise SystemError("Cannot run with no nodes to check")

		Thread(target=self.voice_thread, name="thrVoice", daemon=True).start() # daemonized to avoid waiting until speech ends after exit (what about resource leaks?)

		self.t_last_alarm_state_change = int(time.time())

		init_screen(scr)

		if self.has_music():
			# pygame.init()
			pygame.mixer.init()

		quit = False
		while not quit:
			self.render(scr)
			self.sync_check()
			self.sync_alarm()
			self.sync_music()

			ch = scr.getch()

			# Process input
			if ch == curses.KEY_UP:
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
			elif ch == curses.KEY_SPREVIOUS:
				for _ in range(10 if self.fast_past_scroll else 1):
					self.behind = max(0, self.behind - max(0, curses.LINES - HELP_ROW_HEIGHT - self.log_row_start - 2))
			elif ch == curses.KEY_SNEXT:
				for _ in range(10 if self.fast_past_scroll else 1):
					behind = self.behind + max(0, curses.LINES - HELP_ROW_HEIGHT - self.log_row_start - 2)
					if self.log[(self.log_pos - behind - 1) & LOG_SIZE_BINMASK] is not None:
						self.behind = behind
			elif ch == curses.KEY_SHOME:
				self.behind = 0
			elif ch == curses.KEY_SEND:
				self.behind = max(0, self.log_pos - 1) & LOG_SIZE_BINMASK # doesn't handle wrap properly
			elif ch in [ord('f'), ord('F')]:
				self.fast_past_scroll = not self.fast_past_scroll
			elif ch == ord('0'):
				self.response_data = 0
			elif (ch >= ord('1')) and (ch <= ord('9')):
				self.response_data = 1 + ch - ord('1')
			elif ch in [ord('r'), ord('R')]:
				self.response_data = 0
				self.resptime_stats_mode = { RespTimeStatsMode.NONE : RespTimeStatsMode.DELTA,
					RespTimeStatsMode.DELTA : RespTimeStatsMode.AVG,
					RespTimeStatsMode.AVG : RespTimeStatsMode.STDDEV,
					RespTimeStatsMode.STDDEV : RespTimeStatsMode.MAX,
					RespTimeStatsMode.MAX : RespTimeStatsMode.NONE
				}[self.resptime_stats_mode]
			elif ch in [ord('l'), ord('L')]:
				self.duration_stats_mode = { DurationStatsMode.NONE : DurationStatsMode.CONN_MAX,
					DurationStatsMode.CONN_MAX : DurationStatsMode.DISCONN_MAX,
					DurationStatsMode.DISCONN_MAX : DurationStatsMode.NONE
				}[self.duration_stats_mode]
			elif ch in [ord('d'), ord('D')]:
				self.show_history_distribution = not self.show_history_distribution
			elif ch == ord('<'):
				new_page_start = self.page_start - 1
				while (new_page_start >= 0) and self.nodes[new_page_start].connected:
					new_page_start -= 1
				if new_page_start >= 0:
					self.page_start = new_page_start
			elif ch == ord('>'):
				new_page_start = self.page_start + 1
				while (new_page_start < len(self.nodes)) and self.nodes[new_page_start].connected:
					new_page_start += 1
				if new_page_start < len(self.nodes):
					self.page_start = max(0, min(len(self.nodes) - self.page_size, new_page_start))
			elif ch in [ord('q'), ord('Q')]:
				self.voice_queue.put([VoiceQueueMsg.QUIT])
				quit = True
			elif ch in [ord('m'), ord('M')]:
				self.show_map = not self.show_map			
			elif ch in [ord('w'), ord('W')]:
				self.write_log(DEFAULT_LOG_FILENAME)
			elif ch in [ord('h'), ord('H')]:
				self.set_hush(not self.hushed)
			elif ch == ord('['):
				self.set_hush(True, max(1, self.hush_interval - 1))
			elif ch == ord(']'):
				self.set_hush(True, self.hush_interval + 1)
			elif ch == ord('{'):
				self.set_hush(True, max(1, self.hush_interval - 10))
			elif ch == ord('}'):
				self.set_hush(True, self.hush_interval + 10)
			elif ch in [ord('n'), ord('N')]:
				self.sync_music(True)
			elif ch in [ord('s'), ord('S')]:
				self.music_shuffle = not self.music_shuffle
			elif ch == curses.KEY_LEFT:
				self.change_music_volume(-1)
			elif ch == curses.KEY_RIGHT:
				self.change_music_volume(1)
			elif ch == curses.KEY_SLEFT:
				self.change_music_volume(-10)
			elif ch == curses.KEY_SRIGHT:
				self.change_music_volume(10)	

			time.sleep(1.0 / self.idlerate)

		self.finish_music()


def main():
	aranea = Aranea()
	aranea.load_config(DEFAULT_CONFIG_FILENAME)
	curses.wrapper(aranea.run)


main()
