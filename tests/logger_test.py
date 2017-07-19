# -*- coding: utf-8 -*-
"""
Created on Thu Jul 20 03:04:31 2017

@author: scx
"""
import sys, os.path
sys.path.insert(0, os.path.abspath("F:/Git/PredictCode"))
import open_cp.logger
import logging

open_cp.logger.log_to_stdout()
open_cp.logger.log_to_stdout()

logger = logging.getLogger("open_cp.matt")
logger.debug("A message")