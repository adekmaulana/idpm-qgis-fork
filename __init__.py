"""
***************************************************************************
    __init__.py
    ---------------------
    Date                 : January 2025
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from __future__ import absolute_import

from qgis.gui import QgisInterface

from .core import IDPMPlugin

__author__ = "Adek Maulana"
__date__ = "January 2025"
__copyright__ = f"(C) 2025, {__author__}"

# This will get replaced with a git SHA1 when you do a git archive
__revision__ = "$Format:%H$"


def classFactory(iface: QgisInterface):
    return IDPMPlugin(iface)
