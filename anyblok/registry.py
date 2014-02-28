# -*- coding: utf-8 -*-
import AnyBlok
from anyblok._argsparse import ArgsParseManager
from anyblok._imp import ImportManager
from anyblok.blok import BlokManager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session


class RegistryManagerException(Exception):
    """ Simple Exception for Registry """


class RegistryManager:
    """ Manage the global registry

    Add new entry::

        RegistryManager.declare_entry('newEntry')
        RegistryManager.init_blok('newBlok')
        AnyBlok.current_blok = 'newBlok'
        RegistryManager.add_entry_in_target_registry(
            'newEntry', 'oneKey', cls_)
        AnyBlok.current_blok = None

    Remove an existing entry::

        if RegistryManager.has_entry_in_target_registry('newBlok', 'newEntry',
                                                        'oneKey'):
            RegistryManager.remove_entry_in_target_registry(
                'newBlok', 'newEntry', 'oneKey', cls_)

    """

    loaded_bloks = {}
    declared_entries = []
    mustbeload_declared_entries = []
    callback_declared_entries = {}
    registries = {}
    scoped_fnct = None

    @classmethod
    def has_blok(cls, blok):
        """ Return True if the blok is already loaded

        :param blok: name of the blok
        :rtype: boolean
        """
        return blok in cls.loaded_bloks

    @classmethod
    def clear(cls):
        """ Clear the registry dict to forced the creation of new registry """
        for registry in cls.registries.values():
            registry.close()
        cls.registries = {}

    @classmethod
    def get(cls, dbname):
        """ Return an existing Registry

        If the Registry does'nt exist then the Registry are created and add to
        registries dict

        :param dbname: the name of the database link with this registry
        :rtype: ``Registry``
        """
        if dbname in cls.registries:
            return cls.registries[dbname]

        registry = Registry(dbname, cls.scoped_fnct)
        cls.registries[dbname] = registry
        return registry

    @classmethod
    def reload(cls, blok):
        """ Reload the blok

        The purpose is to reload python module to get change in python file

        :param blok: the name of the blok to reload
        """
        mod = ImportManager.get(blok)
        AnyBlok.current_blok = blok
        try:
            mod.imports()
            mod.reload()
        finally:
            AnyBlok.current_blok = None

        registry2remove = []
        for dbname, registry in cls.registries.items():
            installed = registry.installed_bloks()

            if not installed:
                continue

            if blok in installed:
                registry2remove.append(dbname)

        for dbname in registry2remove:
            cls.registries[dbname].close()
            del cls.registries[dbname]

    @classmethod
    def declare_entry(cls, entry, mustbeload=False, callback=None):
        """ Add new entry in the declared entry

        :param entry: entry name
        :param mustbeload: If true the The registry must be load the entry
        :type mustbeload: bool
        :param callback: function callback to call to load it
        """
        if entry not in cls.declared_entries:
            cls.declared_entries.append(entry)

            if mustbeload:
                if entry not in cls.mustbeload_declared_entries:
                    cls.mustbeload_declared_entries.append(entry)

            if callback:
                cls.callback_declared_entries[entry] = callback

    @classmethod
    def init_blok(cls, blokname):
        """ init one blok to be know by RegistryManager

        All bloks loaded must be initialize because the registry will be create
        with this information

        :param blokname: name of the blok
        """
        blok = {
            'Core': {
                'Base': [],
                'SqlBase': [],
                'Session': [],
            }
        }
        for de in cls.declared_entries:
            blok[de] = {'registry_names': []}

        cls.loaded_bloks[blokname] = blok

    @classmethod
    def has_core_in_target_registry(cls, blok, core):
        """ Return True if One Class exist in this blok for this core

        :param blok: name of the blok
        :param core: is the existing core name
        """
        return len(cls.loaded_bloks[blok]['Core'][core]) > 0

    @classmethod
    def add_core_in_target_registry(cls, core, cls_):
        """ Load core in blok

        warning the global var AnyBlok.current_blok must be field on the
        good blok

        :param core: is the existing core name
        :param ``cls_``: Class of the Core to save in loaded blok target registry
        """
        cls.loaded_bloks[AnyBlok.current_blok]['Core'][core].append(cls_)

    @classmethod
    def remove_core_in_target_registry(cls, blok, core, cls_):
        """ Remove Class in blok and in core

        :param blok: name of the blok
        :param core: is the existing core name
        :param ``cls_``: Class of the Core to remove in loaded blok target
                        registry
        """
        cls.loaded_bloks[blok]['Core'][core].remove(cls_)

    @classmethod
    def has_entry_in_target_registry(cls, blok, entry, key):
        """ Return True if One Class exist in this blok for this entry

        :param blok: name of the blok
        :param entry: is the existing entry name
        :param key: is the existing key in the entry
        """
        if entry not in cls.loaded_bloks[blok]:
            return False

        if key not in cls.loaded_bloks[blok][entry]:
            return False

        return len(cls.loaded_bloks[blok][entry][key]['bases']) > 0

    @classmethod
    def add_entry_in_target_registry(cls, entry, key, cls_, **kwargs):
        """ Load entry in blok

        warning the global var AnyBlok.current_blok must be field on the
        good blok
        :param entry: is the existing entry name
        :param key: is the existing key in the entry
        :param ``cls_``: Class of the entry / key to remove in loaded blok
        """
        bases = []

        for base in cls_.__bases__:
            if base is not object:
                bases.append(base)

        setattr(cls_, '__anyblok_bases__', bases)

        cb = AnyBlok.current_blok

        if key not in cls.loaded_bloks[cb][entry]:
            cls.loaded_bloks[cb][entry][key] = {
                'bases': [],
                'properties': {},
            }

        cls.loaded_bloks[cb][entry][key]['properties'].update(kwargs)
        # Add before in registry because it is the same order than the
        # inheritance __bases__ and __mro__
        cls.loaded_bloks[cb][entry][key]['bases'].insert(0, cls_)

        if key not in cls.loaded_bloks[cb][entry]['registry_names']:
            cls.loaded_bloks[cb][entry]['registry_names'].append(key)

    @classmethod
    def remove_entry_in_target_registry(cls, blok, entry, key, cls_, **kwargs):
        """ Remove Class in blok and in entry

        :param blok: name of the blok
        :param entry: is the existing entry name
        :param key: is the existing key in the entry
        :param ``cls_``: Class of the entry / key to remove in loaded blok
        """
        cls.loaded_bloks[blok][entry][key]['bases'].remove(cls_)
        cls.loaded_bloks[blok][entry][key]['properties'].update(kwargs)


class Registry:
    """ Define one registry

    A registry is link with a database, a have the definition of the installed
    Blok, Model, Mixin for this database::

        registry = Registry.get('My database')
    """

    def __init__(self, dbname, scoped_fnct=None):
        self.dbname = dbname
        self.scoped_fnct = scoped_fnct
        url = ArgsParseManager.get_url(dbname=dbname)
        self.engine = create_engine(url)
        self.loaded_namespaces = {}
        self.Session = None

        self.load()

    def get(self, namespace):
        if namespace not in self.loaded_namespaces:
            raise RegistryManagerException(
                "No namespace %r loaded" % namespace)

        return self.loaded_namespaces[namespace]

    def installed_bloks(self, gettoinstall=False):
        """ Return the list of the installed blok

        :rtype: Return the list or None if anyblok-core not installed
        """
        if not hasattr(self, 'System'):
            return None

        if not hasattr(self.System, 'Blok'):
            return None

        states = ['installed']
        if gettoinstall:
            states.extend(['to install', 'to_update'])

        return self.System.Blok.list_by_state(*states)

    def load(self):
        declarativebase = declarative_base(class_registry=dict(
            registry=self))
        toload = self.installed_bloks(gettoinstall=True)
        if toload is None:
            toload = set()

        toload.update(BlokManager.auto_install)

        loaded_registries = {'model_names': []}
        registry_base = type("RegistryBase", tuple(), {'registry': self})
        loaded_cores = {'Base': [], 'SqlBase': [], 'Session': [
            registry_base]}
        ordered_loaded_bloks = []
        loaded_bloks = {}
        self.loaded_namespaces = {}

        def load_entry(blok, entry):
            _entry = RegistryManager.loaded_bloks[blok][entry]
            for key in _entry['registry_names']:
                v = _entry[key]
                if key not in loaded_registries:
                    loaded_registries[key] = {'properties': {}, 'bases': []}

                loaded_registries[key]['properties'].update(v['properties'])
                old_bases = [] + loaded_registries[key]['bases']
                loaded_registries[key]['bases'] = v['bases']
                loaded_registries[key]['bases'] += old_bases

                if entry in RegistryManager.mustbeload_declared_entries:
                    if entry == 'Model':
                        loaded_registries['model_names'].append(key)
                    elif entry in RegistryManager.callback_declared_entries:
                        #TODO
                        pass

        def load_core(blok, core):
            bases = RegistryManager.loaded_bloks[blok]['Core'][core]
            bases.reverse()
            for base in bases:
                loaded_cores[core].insert(0, base)

        def load_blok(blok):
            if blok in ordered_loaded_bloks:
                return True

            if blok not in BlokManager.bloks:
                return False

            b = BlokManager.bloks[blok](self)
            for required in b.required:
                if not load_blok(required):
                    raise RegistryManagerException(
                        "Required blok not found")

            for optional in b.optional:
                load_blok(optional)

            for core in ('Base', 'SqlBase', 'Session'):
                load_core(blok, core)

            for entry in RegistryManager.declared_entries:
                load_entry(blok, entry)

            loaded_bloks[blok] = b
            ordered_loaded_bloks.append(b)
            return True

        def has_sql_fields(bases):
            from AnyBlok import Field
            for base in bases:
                for p in dir(base):
                    if hasattr(getattr(base, p), '__class__'):
                        if Field in getattr(base, p).__class__.__mro__:
                            return True

            return False

        def get_fields(base):
            from AnyBlok import Field
            fields = {}
            for p in dir(base):
                if hasattr(getattr(base, p), '__class__'):
                    if Field in getattr(base, p).__class__.__mro__:
                        fields[p] = getattr(base, p)
            return fields

        def declare_field(name, field, tablename, properties):
            if name in properties:
                return

            from sqlalchemy.ext.declarative import declared_attr

            def wrapper(cls):
                return field.get_sqlalchemy_mapping(
                    self, tablename, name, properties)

            properties[name] = declared_attr(wrapper)

        def add_in_registry(namespace, base):
            namespace = namespace.split('.')[2:]

            def update_namespace(parent, child):
                if hasattr(parent, 'children_namespaces'):
                    parent.children_namespaces.append(child)
                elif hasattr(parent, child):
                    other_base = get_namespace(parent, child)
                    setattr(parent, child, base)
                    for cns in other_base.children_namespaces:
                        setattr(child, cns.__name__, cns)
                else:
                    setattr(parent, child, base)

            def get_namespace(parent, child):
                if hasattr(parent, child):
                    return getattr(parent, child)

                child = type(child, tuple(), {'children_namespaces': []})
                setattr(parent, child.__name__, child)
                return child

            def update_namespaces(parent, namespaces):
                if len(namespaces) == 1:
                    update_namespace(parent, namespaces[0])
                else:
                    new_parent = get_namespace(parent, namespaces[0])
                    update_namespaces(new_parent, namespaces[1:])

            update_namespaces(self, namespace)

        def load_namespace(namespace):
            if namespace in self.loaded_namespaces:
                return [self.loaded_namespaces[namespace]], {}

            bases = []
            properties = {}
            ns = loaded_registries[namespace]

            for b in ns['bases']:
                bases.append(b)
                p = ns['properties']
                p.update(properties)
                properties.update(p)

                for b_ns in b.__anyblok_bases__:
                    bs, ps = load_namespace(b_ns.__registry_name__)
                    bases += bs
                    ps.update(properties)
                    properties.update(ps)

            if namespace in loaded_registries['model_names']:
                tablename = properties['__tablename__']
                if has_sql_fields(bases):
                    bases += loaded_cores['SqlBase']
                    bases += [declarativebase]

                bases += loaded_cores['Base'] + [registry_base]
                for b in bases:
                    for p, f in get_fields(b).items():
                        declare_field(p, f, tablename, properties)

                bases = [type(tablename, tuple(bases), properties)]
                properties = {}
                add_in_registry(namespace, bases[0])
                self.loaded_namespaces[namespace] = bases[0]

            return bases, properties

        for blok in toload:
            load_blok(blok)

        for namespace in loaded_registries['model_names']:
            load_namespace(namespace)

        declarativebase.metadata.create_all(self.engine)

        Session = type('Session', tuple(loaded_cores['Session']), {})
        self.Session = scoped_session(
            sessionmaker(bind=self.engine, class_=Session), self.scoped_fnct)

        Blok = self.System.Blok
        Blok.update_list()
        Blok.apply_state(*ordered_loaded_bloks)

    def close(self):
        """Release the session, connection and engin"""

        session = self.Session()
        session.rollback()
        session.close_all()
        self.engine.dispose()

    def __getattr__(self, attribute):
        if self.Session:
            session = self.Session()
            if attribute == 'session':
                return session
            if hasattr(session, attribute):
                return getattr(session, attribute)

        else:
            super(Registry, self).__getattr__(attribute)

    def upgrade(self, install=None, update=None, uninstall=None):
        """ Upgrade the current registry

        :param install: list of the blok to install
        :param update: list of the blok to update
        :param uninstall: list of the blok to uninstall
        """
        #TODO
