"""
Palimpsest - A tool for parsing websites and generating static sites.

This module provides functionality to:
- Parse HTML files and extract content and metadata
- Generate static websites from parsed content
- Analyze site structure and links
"""

from .parser import SiteParser
from .generator import StaticSiteGenerator
from .analysis import SiteAnalyzer

__version__ = "0.1.0"
__all__ = ["SiteParser", "StaticSiteGenerator", "SiteAnalyzer"]
