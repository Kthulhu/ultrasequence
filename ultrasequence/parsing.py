"""
This module contains functions and classes for parsing files and directories
for file sequences. 

** IMPORTANT **
Currently, the directory scanner skips any links and they will not show up
in any Parser list.
"""

import logging
import os
import sys
from os import walk
from ultrasequence.config import cfg
from ultrasequence.models import File, Sequence


logger = logging.getLogger()

if sys.version_info < (3, 5):
	try:
		from scandir import walk
	except ImportError:
		logger.info('For Python versions < 3.5, scandir module is '
					'recommended. Run \n>>> pip install scandir')


def scan_dir(path):
	"""
	Searches a root directory and returns a list of all files. If 
	cfg.recurse is True, the scanner will descend all child directories.

	:param path: The root path to scan for files
	:return: a list of filenames if cfg.get_stats is False, or a list
			 of tuples (filename, file_stats) if cfg.get_stats is True.
	"""
	file_list = []
	if cfg.recurse:
		for root, dirs, files in walk(path):
			file_list += stat_files(root, files)
	else:
		file_list += stat_files(path, os.listdir(path))
	return file_list


def stat_files(root, files):
	"""
	Assembles a list of files for a single directory.

	:param root: the the root path to the current directory
	:param files: the list of filenames in the directory
	:return: a list of filenames if cfg.get_stats is False, or a list
			 of tuples (filename, file_stats) if cfg.get_stats is True.
	"""
	dir_list = []
	if cfg.get_stats:
		for file in files:
			abspath = os.path.join(root, file)
			if os.path.islink(abspath):
				continue
			dir_list.append((abspath, os.stat(abspath)))
	else:
		dir_list += [os.path.join(root, file) for file in files
					 if os.path.isfile(os.path.join(root, file))]
	return dir_list


class Parser(object):
	def __init__(self, include_exts=cfg.include_exts,
				 exclude_exts=cfg.exclude_exts, get_stats=cfg.get_stats,
				 ignore_padding=cfg.ignore_padding):
		"""
		Main parser object. Sets up config parameters for parsing methods.
		
		:param list include_exts: file extensions to include in parsing
		:param list exclude_exts: file extensinos to explicity exclude in
		                          parsing
		:param bool get_stats: get file stats from os.stats
		:param bool ignore_padding: ignore the number of digits in the
		                            file's frame number section
		"""
		if not include_exts or not isinstance(include_exts, (tuple, list)):
			self.include_exts = set()
		else:
			self.include_exts = set(include_exts)

		if not exclude_exts or not isinstance(exclude_exts, (tuple, list)):
			self.exclude_exts = set()
		else:
			self.exclude_exts = set(exclude_exts)

		cfg.get_stats = get_stats
		self.ignore_padding = ignore_padding
		self._reset()

	def _reset(self):
		""" Clear all parser results """
		self._sequences = {}
		self.sequences = []
		self.single_frames = []
		self.non_sequences = []
		self.excluded = []
		self.collisions = []
		self.parsed = False

	def __str__(self):
		return ('Parser(sequences=%d, single_frames=%d, non_sequences=%d, '
				'excluded=%d, collisions=%d)' %
				(len(self.sequences), len(self.single_frames),
				 len(self.non_sequences), len(self.excluded),
				 len(self.collisions)))

	def __repr__(self):
		return ('<Parser object at %s, parsed=%s>' %
				(hex(id(self)), self.parsed))

	def _cleanup(self):
		""" Moves single frames out of sequences list """
		while self._sequences:
			seq = self._sequences.popitem()[1]
			if seq.frames == 1:
				self.single_frames.append(seq[0])
			else:
				self.sequences.append(seq)
		self.parsed = True

	def _sort_file(self, filepath, stats=None):
		""" Finds matching sequence for given filepath """
		file_ = File(filepath, stats=stats)

		if self.include_exts and file_.ext.lower() not in self.include_exts \
				or file_.ext.lower() in self.exclude_exts:
			self.excluded.append(file_)

		elif file_.frame is None:
			self.non_sequences.append(file_)

		else:
			seq_name = file_.get_seq_key()
			if seq_name in self._sequences:
				try:
					self._sequences[seq_name].append(file_)
				except IndexError:
					self.collisions.append(file_)
			else:
				self._sequences[seq_name] = Sequence(file_)

	def parse_directory(self, directory, recurse=cfg.recurse):
		"""
		Parse a directory on the file system.

		:param str directory: directory path to scan on filesystem
		:param bool recurse: recurse all child directories
		"""
		self._reset()
		cfg.recurse = recurse
		directory = os.path.expanduser(directory)
		if isinstance(directory, str) and os.path.isdir(directory):
			file_list = scan_dir(directory)
			while file_list:  # reduce memory consumption for large lists
				file_ = file_list.pop(0)
				if cfg.get_stats:
					self._sort_file(file_[0], file_[1])
				else:
					self._sort_file(file_)
			self._cleanup()
		else:
			logger.warning('%s is not an available directory.' % directory)

	def parse_file(self, listfile):
		"""
		Parse a text file containing file listings.

		:param str listfile: path to the file containing a file listing
		"""
		listfile = os.path.expanduser(listfile)

		self._reset()
		if isinstance(listfile, str) and os.path.isfile(listfile):
			with open(listfile, 'r') as file_list:
				for file_ in file_list:
					self._sort_file(file_.rstrip())
			self._cleanup()
		else:
			logger.warning('%s is not a valid filepath.' % listfile)