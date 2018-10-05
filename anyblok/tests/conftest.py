# This file is a part of the AnyBlok project
#
#    Copyright (C) 2018 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#    Copyright (C) 2018 Denis VIVIÈS <dvivies@geoblink.com>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
import logging
from copy import deepcopy

import pytest

from anyblok.blok import BlokManager
from anyblok.config import Configuration
from anyblok.environment import EnvironmentManager
from anyblok.registry import RegistryManager

logger = logging.getLogger(__name__)


def init_registry_with_bloks(bloks, function, **kwargs):
    if bloks is None:
        bloks = []
    if isinstance(bloks, tuple):
        bloks = list(bloks)
    if isinstance(bloks, str):
        bloks = [bloks]

    anyblok_test_name = 'anyblok-test'
    if anyblok_test_name not in bloks:
        bloks.append(anyblok_test_name)

    loaded_bloks = deepcopy(RegistryManager.loaded_bloks)
    if function is not None:
        EnvironmentManager.set('current_blok', anyblok_test_name)
        try:
            function(**kwargs)
        finally:
            EnvironmentManager.set('current_blok', None)
    try:
        registry = RegistryManager.get(
            Configuration.get('db_manager'),
            unittest=False)

        # update required blok
        registry_bloks = registry.get_bloks_by_states('installed', 'toinstall')
        if bloks:
            for blok_to_install in bloks:
                if blok_to_install not in registry_bloks:
                    registry.upgrade(install=[blok_to_install])
                else:
                    registry.upgrade(update=[blok_to_install])
    finally:
        RegistryManager.loaded_bloks = loaded_bloks

    return registry


@pytest.fixture(scope="module")
def bloks_loaded():
    BlokManager.load()
    yield
    BlokManager.unload()