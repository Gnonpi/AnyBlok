# This file is a part of the AnyBlok project
#
#    Copyright (C) 2015 Georges Racinet <gracinet@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
"""Authorization subframework.

The founding principle of authorization handling within Anyblok is to check
authorization explicitely at the edge of the system (for instance,
for applications
exposed over HTTP, that would be in the controllers), because that is where the
idea of user, or slightly more generally, has functional semantics that can
be interpreted in the context of a given action.

In that spirit, we don't pass the user to the core framework and business
layers.
Instead, these provide *policies* to check permissions on records or query
records according to the.

The declarations at the edge will *associate* the policies with the
models. The edge user-aware methods will call the check and query facilities
provided by the core that themselves apply the relevant policies.
"""
from copy import deepcopy
from .declarations import Declarations
from .environment import EnvironmentManager
from .registry import RegistryManager


@Declarations.add_declaration_type(isAnEntry=True,
                                   assemble='assemble_callback')
class AuthorizationPolicyAssociation:
    """Encodes which policy to use per model or (model, permission).

    In the assembly phase, copies of the policy are issued, and the registry
    is set as an attribute on them. This is a bit memory inefficient, but
    otherwise, passing the registry would have to be in all AuthorizationPolicy
    API calls.
    """

    def __new__(cls, model_declaration, policy, permission=None):
        """Declare for given model that policy should be used.

        :param permission: if provided, the policy will apply for this
                           permission only, otherwise, it will act as the
                           default policy for this model.
        """
        cb = EnvironmentManager.get('current_blok')
        model = model_declaration.__registry_name__
        key = (model, permission) if permission is not None else model
        blok_declarations = RegistryManager.loaded_bloks[cb][cls.__name__]
        blok_declarations[key] = policy

    @classmethod
    def assemble_callback(cls, registry):
        policies = {}
        for blok in registry.ordered_loaded_bloks:
            policies.update(RegistryManager.loaded_bloks[blok][cls.__name__])

        # for this registry entry, the list of names is irrelevant pollution:
        del policies['registry_names']
        registry._authz_policies = deepcopy(policies)
        for policy in registry._authz_policies.values():
            policy.registry = registry


class PolicyNotForModelClasses(Exception):
    """Raised by authorization policies that don't make sense on model classes.

    For instance, if a permission check is done on a model class, and the
    policy associations are made with a policy that needs to check attributes,
    then the association must be corrected.
    """

    def __init__(self, policy, model):
        self.policy = policy
        self.model = model
        self.message = "Policy %r cannot be used on a model class (got %r)" % (
            policy, model)


class AuthorizationPolicy:
    """Base class to define the interface and provide some helpers"""

    registry = None
    """Set during assembly phase."""

    def is_declaration(self):
        return self.registry is None

    def check(self, target, principals, permission):
        """Check that one of the principals has permisson on given record.

        :param target: model instance (record) or class. Checking a permission
                       on a model class with a policy that is designed to work
                       on records is considered a configuration error,
                       expressed by :exc:`PolicyNotForModelClasses`.
        :param principals: list, set or tuple of strings
        :rtype: bool

        Must be implemented by concrete subclasses.
        """
        raise NotImplementedError

    def filter(self, model, query, principals, permission):
        """Return a new query with added permission filtering.

        Must be implemented by concrete subclasses.

        :param query: the :class:`Query` instance to modify to express
                      the permission for these principals.
        :param model: the model on which the policy is applied
        :rtype: :class:`Query`)

        It's not necessary that the resulting query expresses fully
        the permission check: this can be complemented if needed
        by postfiltering, notably for conditions that can't be expressed
        conveniently in SQL.

        That being said, if the policy can be expressed totally by query,
        alteration, it's usually the best choice, as it keeps database traffic
        at the lowest.

        The policy also has the possibility to return False, for flat denial
        without even querying the server. That may prove useful in some cases.
        """
        raise NotImplementedError

    postfilter = None
    """Filter by permission records obtained by a filtered query.

    By default, this is ``None``, to indicate that the policy does not perform
    any post filtering, but concrete policies can implement
    a method with the following signature::

        def postfilter(self, record, principals, permission):

    Such implementations can (and usually, for performance, should) assume
    that the query that produced the records was a filtered one.

    The purpose of using the explicit ``None`` marker is to permit some calls
    that don't make sense on a postfiltered operation (such as ``count()``).
    """


class DenyAll(AuthorizationPolicy):

    def check(self, *args):
        return False

    def filter(self, *args):
        return False

deny_all = DenyAll
