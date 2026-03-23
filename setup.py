#!/usr/bin/env python3
"""Setuptools build customization.

Build metadata is defined in pyproject.toml. This file injects top-level
`configs/` and `resources/` into the package at build time so the repository
keeps a single source of truth.
"""

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class build_py(_build_py):
	"""Copy shared data folders into build package output."""

	def run(self):
		super().run()
		self._copy_data_dir("configs", "hciemu/configs")
		self._copy_data_dir("resources", "hciemu/resources")

	def _copy_data_dir(self, source_rel: str, dest_rel: str) -> None:
		repo_root = Path(__file__).resolve().parent
		source_dir = repo_root / source_rel
		if not source_dir.exists():
			return

		dest_dir = Path(self.build_lib) / dest_rel
		dest_dir.mkdir(parents=True, exist_ok=True)

		for source_path in source_dir.iterdir():
			if source_path.is_file():
				shutil.copy2(source_path, dest_dir / source_path.name)


setup(cmdclass={"build_py": build_py})
