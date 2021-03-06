#
# rpi_3.py
#
# Copyright (C) 2016 Kano Computing Ltd.
# License: http://www.gnu.org/licenses/gpl-2.0.txt GNU GPL v2
#
# Board specific settings for Raspberry Pi 3
#

DEFAULT_CONFIG = {
    'Overclocking': _("Standard")
}

CLOCKING = {
    'modes': [_("Standard")],
    'default': _("Standard"),
    'warning': [],
    'values': {
        _("Standard"): {
            'arm_freq': 1200,
            'core_freq': 400,
            'sdram_freq': 450,
            'over_voltage': 0
        }
    }
}
