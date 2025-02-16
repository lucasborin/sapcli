"""ADT Object import"""
import os
import glob
import errno
import typing

from sap import get_logger

import sap.errors
import sap.cli.core
import sap.platform.abap.abapgit
from sap.platform.abap.ddic import VSEOCLASS, PROGDIR, TPOOL, VSEOINTERF, DEVC, SUBC_EXECUTABLE_PROGRAM, SUBC_INCLUDE,\
    AREAT, INCLUDES, FUNCTIONS
import sap.adt
import sap.adt.objects
import sap.adt.errors
import sap.adt.wb


def mod_log():
    """ADT Module logger"""

    return get_logger()


class RepoPackage(typing.NamedTuple):
    """Package on file system"""

    name: str
    path: str
    dir_path: str
    parent: typing.Any


class RepoObject(typing.NamedTuple):
    """ADT object of Repository"""

    code: str
    name: str
    path: str
    package: RepoPackage
    files: list


# pylint: disable=too-many-instance-attributes
class Repository:
    """Repository information"""

    def __init__(self, name, config):
        self._name = name
        self._full_fmt = '$%s' if name[0] == '$' else '%s'
        self._pfx_fmt = f'{name}_%s'
        self._config = config

        self._dir_prefix = config.STARTING_FOLDER.split('/')
        if not self._dir_prefix[0]:
            del self._dir_prefix[0]

        if not self._dir_prefix[-1]:
            del self._dir_prefix[-1]

        self._packages = {}
        self._objects = []

        self._pkg_name_bldr = {
            sap.platform.abap.abapgit.FOLDER_LOGIC_FULL: lambda parts: self._full_fmt % (parts[-1]),
            # pylint: disable=unnecessary-lambda
            sap.platform.abap.abapgit.FOLDER_LOGIC_PREFIX: lambda parts: self._pfx_fmt % ('_'.join(parts)),
        }[config.FOLDER_LOGIC]

    @property
    def config(self):
        """Get config"""

        return self._config

    @property
    def packages(self):
        """List of packages"""

        return list(self._packages.values())

    @property
    def objects(self):
        """List of packages"""

        return self._objects

    def find_package_by_path(self, dir_path):
        """Get package based on its path"""

        return self._packages[dir_path]

    def add_object(self, obj_file_name, package):
        """Add new ADT object"""

        obj_id_start = obj_file_name.find('.') + 1

        if obj_id_start + 4 > len(obj_file_name) - 4:
            raise sap.errors.SAPCliError(f'Invalid ABAP file name: {obj_file_name}')

        obj_code = obj_file_name[obj_id_start:(obj_id_start + 4)]
        mod_log().debug('Handling object code: %s (%s)', obj_code, obj_file_name)

        obj_name = obj_file_name[:obj_id_start - 1]

        other_files = []

        obj_file_pattern = os.path.join(package.dir_path, obj_name)
        obj_file_pattern = f'{obj_file_pattern}.{obj_code}.*'

        mod_log().debug('Searching for object files: %s', obj_file_pattern)
        for source_file in glob.glob(obj_file_pattern):
            if source_file.endswith('.xml'):
                continue

            mod_log().debug('Adding file: %s', source_file)
            other_files.append(source_file)

        obj = RepoObject(obj_code, obj_name, os.path.join(package.dir_path, obj_file_name), package, other_files)
        self._objects.append(obj)

        return obj

    def add_package_dir(self, dir_path, parent=None):
        """add new directory package"""

        if parent:
            dir_path = os.path.join(parent.dir_path, dir_path)

        if not dir_path.startswith('./'):
            raise sap.errors.SAPCliError(f'Package dirs must start with "./": {dir_path}')

        pkg_file = os.path.join(dir_path, 'package.devc.xml', )
        if not os.path.isfile(pkg_file):
            raise sap.errors.SAPCliError(f'Not a package directory: {dir_path}')

        mod_log().debug('Adding new package dir: %s', dir_path)

        # Skip the first path part to ignore .
        parts = dir_path.split('/')[1:]
        if len(parts) < len(self._dir_prefix):
            raise sap.errors.SAPCliError(f'Sub-package dir {dir_path} not in starting folder'
                                         f' {self._config.STARTING_FOLDER}')

        for prefix in self._dir_prefix:
            if parts[0] != prefix:
                raise sap.errors.SAPCliError(f'Sub-package dir {dir_path} not in starting folder'
                                             f' {self._config.STARTING_FOLDER}')

            del parts[0]

        if parts and parts[0]:
            pkg_name = self._pkg_name_bldr(parts)
        else:
            pkg_name = self._name

        pkg = RepoPackage(pkg_name, pkg_file, dir_path, parent)
        self._packages[dir_path] = pkg

        return pkg


def _load_objects(repo):
    # packages
    # ddic
    # interfaces
    # classes
    # programs + includes

    abap_dir = f'.{repo.config.STARTING_FOLDER}'

    mod_log().debug('Loading ABAP dir: %s', abap_dir)

    repo.add_package_dir(abap_dir)

    for root, dirs, files in os.walk(abap_dir):
        mod_log().debug('Analyzing package dir: %s', root)

        package = repo.find_package_by_path(root)

        for obj_file_name in files:
            obj_type, suffix = obj_file_name.split('.')[-2:]
            if suffix != 'xml' or obj_type not in OBJECT_CHECKIN_HANDLERS:
                continue

            repo.add_object(obj_file_name, package)

        for sub_dir in dirs:
            repo.add_package_dir(sub_dir, parent=package)


def _get_config(starting_folder, console):
    conf_file_path = '.abapgit.xml'

    try:
        with open(conf_file_path, 'r', encoding='utf-8') as conf_file:
            conf_file_contents = conf_file.read()
            config = sap.platform.abap.abapgit.DOT_ABAP_GIT.from_xml(conf_file_contents)

            if config.STARTING_FOLDER != starting_folder:
                console.printout(f'Using starting-folder from .abapgit.xml: {config.STARTING_FOLDER}')
    except OSError as ex:
        if ex.errno != errno.ENOENT:
            raise

        if starting_folder is None:
            config = sap.platform.abap.abapgit.DOT_ABAP_GIT.for_new_repo()
        else:
            config = sap.platform.abap.abapgit.DOT_ABAP_GIT.for_new_repo(STARTING_FOLDER=starting_folder)

    return config


def checkin_package(connection, repo_package, args):
    """Checkin repository package"""

    devc = DEVC()
    with open(repo_package.path, encoding='utf-8') as devc_file:
        sap.platform.abap.from_xml(devc, devc_file.read())

    sap.cli.core.printout(f'Creating Package: {repo_package.name} {devc.CTEXT}')

    metadata = sap.adt.ADTCoreData(language='EN', master_language='EN', responsible=connection.user,
                                   description=devc.CTEXT)

    package = sap.adt.Package(connection, repo_package.name.upper(), metadata=metadata)
    package.set_package_type('development')

    if repo_package.parent is not None:
        package.super_package.name = repo_package.parent.name.upper()

    package.set_software_component(args.software_component.upper())
    if args.app_component:
        package.set_app_component(args.app_component.upper())

    if args.transport_layer:
        package.set_transport_layer(args.transport_layer.upper())

    try:
        package.create(args.corrnr)
    except sap.adt.errors.ExceptionResourceAlreadyExists as err:
        mod_log().info(err.message)


def _resolve_dependencies(objects):

    libs = []
    bins = []
    others = []

    for obj in objects:
        if obj.code in ['intf', 'clas']:
            libs.append(obj)
        elif obj.code in ['prog']:
            bins.append(obj)
        else:
            others.append(obj)

    return [libs, bins, others]


def checkin_intf(connection, repo_obj, corrnr=None):
    """Checkin ADT Interface"""

    sap.cli.core.printout('Creating Interface:', repo_obj.name)

    if not repo_obj.files:
        raise sap.adt.errors.ExceptionCheckinFailure(f'No source file for interface {repo_obj.name}')

    if len(repo_obj.files) > 1:
        raise sap.adt.errors.ExceptionCheckinFailure(f'Too many source files for interface {repo_obj.name}: %s'
                                                     % (','.join(repo_obj.files)))

    source_file = repo_obj.files[0]

    if not source_file.endswith('.abap'):
        raise sap.adt.errors.ExceptionCheckinFailure(f'No .abap suffix of source file for interface {repo_obj.name}')

    abap_data = VSEOINTERF()
    with open(repo_obj.path, encoding='utf-8') as abap_data_file:
        sap.platform.abap.from_xml(abap_data, abap_data_file.read())

    metadata = sap.adt.ADTCoreData(language='EN', master_language='EN', responsible=connection.user,
                                   description=abap_data.DESCRIPT)
    interface = sap.adt.Interface(connection, repo_obj.name.upper(), package=repo_obj.package.name, metadata=metadata)

    try:
        interface.create(corrnr)
    except sap.adt.errors.ExceptionResourceAlreadyExists as err:
        mod_log().info(err.message)

    sap.cli.core.printout('Writing Interface:', repo_obj.name)
    with open(source_file, 'r', encoding='utf-8') as source:
        with interface.open_editor(corrnr=corrnr) as editor:
            editor.write(source.read())

    return [interface]


def checkin_clas(connection, repo_obj, corrnr=None):
    """Checkin ADT Clas"""

    sap.cli.core.printout('Creating Class:', repo_obj.name)

    if not repo_obj.files:
        raise sap.adt.errors.ExceptionCheckinFailure(f'No source file for class {repo_obj.name}')

    abap_data = VSEOCLASS()
    with open(repo_obj.path, encoding='utf-8') as abap_data_file:
        sap.platform.abap.from_xml(abap_data, abap_data_file.read())

    metadata = sap.adt.ADTCoreData(language='EN', master_language='EN', responsible=connection.user,
                                   description=abap_data.DESCRIPT)
    clas = sap.adt.Class(connection, repo_obj.name.upper(), package=repo_obj.package.name, metadata=metadata)

    try:
        clas.create(corrnr)
    except sap.adt.errors.ExceptionResourceAlreadyExists as err:
        mod_log().info(err.message)

    for source_file in repo_obj.files:
        if not source_file.endswith('.abap'):
            raise sap.adt.errors.ExceptionCheckinFailure(f'No .abap suffix of source file for class {repo_obj.name}:'
                                                         f' {source_file}')

        source_file_parts = source_file.split('.')
        class_parts = {
            'clas': clas,
            'locals_def': clas.definitions,
            'locals_imp': clas.implementations,
            'testclasses': clas.test_classes,
        }

        sub_obj_id = source_file_parts[-2]
        sub_obj = class_parts.get(sub_obj_id, None)
        if sub_obj is None:
            sap.cli.core.printerr(f'Unknown class part {source_file}')
            continue

        sap.cli.core.printout('Writing Clas:', repo_obj.name, sub_obj_id)

        with open(source_file, 'r', encoding='utf-8') as source:
            with sub_obj.open_editor(corrnr=corrnr) as editor:
                editor.write(source.read())

    return [clas]


def checkin_prog(connection, repo_obj, corrnr=None):
    """Checkin ADT Program"""

    sap.cli.core.printout('Creating Program:', repo_obj.name)

    if not repo_obj.files:
        raise sap.adt.errors.ExceptionCheckinFailure(f'No source file for program {repo_obj.name}')

    if len(repo_obj.files) > 1:
        raise sap.adt.errors.ExceptionCheckinFailure(f'Too many source files for program {repo_obj.name}:'
                                                     f' %s' % (','.join(repo_obj.files)))

    source_file = repo_obj.files[0]

    if not source_file.endswith('.abap'):
        raise sap.adt.errors.ExceptionCheckinFailure(f'No .abap suffix of source file for program {repo_obj.name}')

    with open(repo_obj.path, encoding='utf-8') as abap_data_file:
        results = sap.platform.abap.abapgit.from_xml([PROGDIR, TPOOL], abap_data_file.read())

    progdir = results['PROGDIR']
    tpool = results['TPOOL']

    metadata = sap.adt.ADTCoreData(language='EN', master_language='EN', responsible=connection.user)
    if progdir.SUBC == SUBC_EXECUTABLE_PROGRAM:
        program = sap.adt.Program(connection, repo_obj.name, package=repo_obj.package.name, metadata=metadata)
    elif progdir.SUBC == SUBC_INCLUDE:
        sap.cli.core.printout('Creating Include:', repo_obj.name)
        program = sap.adt.Include(connection, repo_obj.name, package=repo_obj.package.name, metadata=metadata)
    else:
        raise sap.adt.errors.ExceptionCheckinFailure(f'Unknown program type {progdir.SUBC}')

    for text in tpool:
        if text.ID == 'R':
            program.description = text.ENTRY

    try:
        program.create(corrnr)
    except sap.adt.errors.ExceptionResourceCreationFailure as err:
        if not str(err).endswith(f'A program or include already exists with the name {repo_obj.name.upper()}'):
            raise

        mod_log().info(err.message)

    sap.cli.core.printout('Writing Program:', repo_obj.name)
    with open(source_file, 'r', encoding='utf-8') as source:
        with program.open_editor(corrnr=corrnr) as editor:
            editor.write(source.read())

    return [program]


def _check_fugr_source_files(repo_obj, functions, includes):
    """Check that all functions and includes have source files"""

    for func in functions:
        function_name = func.FUNCNAME.lower()
        function_file_path = repo_obj.path[:-4] + f'.{function_name}' + '.abap'
        if function_file_path not in repo_obj.files:
            raise sap.adt.errors.ExceptionCheckinFailure(f'No source file for function {function_name}')

    for include in includes:
        include_name = include.lower()
        include_file_path = repo_obj.path[:-4] + f'.{include_name}' + '.abap'
        if include_file_path not in repo_obj.files:
            raise sap.adt.errors.ExceptionCheckinFailure(f'No source file for include {include_name}')


def _write_source_file(source_code, adt_object, corrnr=None):
    with adt_object.open_editor(corrnr=corrnr) as editor:
        editor.write(source_code)


def _write_adt_object_source_file(path_prefix, adt_object, corrnr=None):
    """Write source file for ADT object"""

    adt_object_file_path = path_prefix + f'.{adt_object.name.lower()}' + '.abap'
    with open(adt_object_file_path, 'r', encoding='utf-8') as source:
        _write_source_file(source.read(), adt_object, corrnr)


def _get_parameters_block(source_lines):
    """Get parameters block of function module

    The block is delimited by '*"--' lines.
    Example:
    *"----------------------------------------------------------------------
    *"*"Local Interface:
    ...
    *"----------------------------------------------------------------------
    """

    start_block = 0
    end_block = 0
    for i, line in enumerate(source_lines):
        if line.startswith('*"--'):
            start_block = i
            break

    for i, line in enumerate(source_lines[start_block + 1:]):
        if line.startswith('*"--'):
            end_block = i + start_block + 1
            break

    return start_block, end_block


def _parse_function_parameters(parameters_block):
    """Parse parameters of function module

    From the parameters block:
    ```
        *"----------------------------------------------------------------------
        *"*"Local Interface:
        *"  IMPORTING
        *"     VALUE(IV_PARAM1) TYPE  STRING
        *"  EXPORTING
        *"     VALUE(EV_PARAM2) TYPE  STRING
        *"  TABLES
        *"     ET_PARAM3 STRUCTURE  STRING
        *"----------------------------------------------------------------------
    ```
    The parsed parameters are:
    {
        'IMPORTING': ['VALUE(IV_PARAM1) TYPE STRING'],
        'EXPORTING': ['VALUE(EV_PARAM2) TYPE STRING'],
        'CHANGING': [],
        'TABLES': ['ET_PARAM3 TYPE  STRING'],
        'EXCEPTIONS': []
    }

    Note the change from STRUCTURE to TYPE for TABLES parameters.
    """

    parameters = {
        'IMPORTING': [],
        'EXPORTING': [],
        'CHANGING': [],
        'TABLES': [],
        'EXCEPTIONS': []
    }
    current_param = None
    for line in parameters_block:
        line = line.lstrip('*" ').rstrip()
        if any(param == line for param in parameters):
            current_param = line
        elif current_param is not None:
            param = line
            parameters[current_param].append(param)

    for i, table_param in enumerate(parameters['TABLES']):
        var_name, abap_typing, *abap_type = table_param.split(' ')
        if abap_typing == 'STRUCTURE':
            parameters['TABLES'][i] = f'{var_name} TYPE {" ".join(abap_type)}'

    return parameters


def _format_function(source_code):
    """Format parameters of function

    Original source code:
    ```
        FUNCTION ztest_function.
        *"----------------------------------------------------------------------
        *"*"Local Interface:
        *"  IMPORTING
        *"     VALUE(IV_PARAM1) TYPE  STRING
        *"  EXPORTING
        *"     VALUE(EV_PARAM2) TYPE  STRING
        *"----------------------------------------------------------------------
        ...
        ENDFUNCTION.
    ```
    Formatted source code:
    ```
        FUNCTION ztest_function
        IMPORTING
        VALUE(IV_PARAM1) TYPE STRING
        EXPORTING
        VALUE(EV_PARAM2) TYPE STRING
        .
        ...
        ENDFUNCTION.
    ```
    """

    source_lines = source_code.split('\n')
    start_block, end_block = _get_parameters_block(source_lines)
    if end_block == 0:
        # Source code is in ADT format
        return '\n'.join(source_lines)

    source_lines[0] = source_lines[0].replace('.', '')  # Remove dot at the end of first line
    parameters = _parse_function_parameters(source_lines[start_block:end_block])
    adt_parameters_block = []
    for param_type, params in parameters.items():
        if not params:
            continue

        adt_parameters_block.append(f'{param_type}')
        adt_parameters_block += params

    adt_parameters_block.append('.')  # Add dot at the end of the parameters block
    source_lines[start_block:end_block + 1] = adt_parameters_block
    return '\n'.join(source_lines)


def _write_function_source_code(path_prefix, adt_object, corrnr=None):
    """Write source code for function. If function is in ababGit format, change it to ADT format"""

    source_file_path = path_prefix + f'.{adt_object.name.lower()}' + '.abap'
    with open(source_file_path, 'r', encoding='utf-8') as source:
        source_code = source.read()

    source_code = _format_function(source_code)
    _write_source_file(source_code, adt_object, corrnr)


def checkin_fugr(connection, repo_obj, corrnr=None):
    """Checkin ADT Function Group"""

    sap.cli.core.printout('Creating Function Group:', repo_obj.name)
    with open(repo_obj.path, encoding='utf-8') as abap_data_file:
        results = sap.platform.abap.abapgit.from_xml([AREAT, INCLUDES, FUNCTIONS], abap_data_file.read())

    includes = results['INCLUDES']
    functions = results['FUNCTIONS']

    _check_fugr_source_files(repo_obj, functions, includes)

    metadata = sap.adt.ADTCoreData(language='EN', master_language='EN', responsible=connection.user)
    function_group = sap.adt.FunctionGroup(connection, repo_obj.name.upper(), package=repo_obj.package.name,
                                           metadata=metadata)
    function_group.description = results['AREAT']

    try:
        function_group.create(corrnr)
    except sap.adt.errors.ExceptionResourceAlreadyExists as err:
        mod_log().info(err.message)

    abap_objs_inactive = [function_group]

    for include in includes:
        include_obj = sap.adt.FunctionInclude(connection, include, function_group.name, metadata=metadata)
        abap_objs_inactive.append(include_obj)

        sap.cli.core.printout('Creating Function Group Include:', include_obj.name)
        try:
            include_obj.create(corrnr)
        except sap.adt.errors.ExceptionResourceCreationFailure as err:
            if not str(err).endswith('already exists'):
                raise

            mod_log().info(err.message)

        sap.cli.core.printout('Writing Function Group Include:', include_obj.name)
        _write_adt_object_source_file(repo_obj.path[:-4], include_obj, corrnr=corrnr)

    for func in functions:
        function_module = sap.adt.FunctionModule(connection, func.FUNCNAME, function_group.name, metadata=metadata)
        function_module.description = func.SHORT_TEXT
        abap_objs_inactive.append(function_module)

        sap.cli.core.printout('Creating Function Module:', function_module.name)
        try:
            function_module.create(corrnr)
        except sap.adt.errors.ExceptionResourceAlreadyExists as err:
            mod_log().info(err.message)

        sap.cli.core.printout('Writing Function Module:', function_module.name)
        _write_function_source_code(repo_obj.path[:-4], function_module, corrnr=corrnr)

    return abap_objs_inactive


OBJECT_CHECKIN_HANDLERS = {
    'intf': checkin_intf,
    'clas': checkin_clas,
    'prog': checkin_prog,
    'fugr': checkin_fugr,
}


def _checkin_dependency_group(connection, group, console, corrnr):
    inactive_objects = sap.adt.objects.ADTObjectReferences()

    for repo_obj in group:
        obj_handler = OBJECT_CHECKIN_HANDLERS.get(repo_obj.code)

        if obj_handler is None:
            console.printerr(f'Object not supported: {repo_obj.path}')
            continue

        try:
            abap_objs = obj_handler(connection, repo_obj, corrnr)
            for abap_obj in abap_objs:
                inactive_objects.add_object(abap_obj)

        except sap.adt.errors.ExceptionCheckinFailure:
            console.printout(f'Object handled without activation: {repo_obj.path}')

    return inactive_objects


def _activate(connection, inactive_objects, console):
    messages = sap.adt.wb.try_mass_activate(connection, inactive_objects)

    if not messages:
        return

    error = False
    for msg in messages:
        if msg.is_error:
            error = True

        console.printout(f'* {msg.obj_descr} ::')
        console.printout(f'| {msg.typ}: {msg.short_text}')

    if error:
        raise sap.errors.SAPCliError('Aborting because of activation errors')


def do_checkin(connection, args):
    """Synchronize directory structure with ABAP package structure"""

    console = sap.cli.core.get_console()

    top_dir = '.'
    if args.starting_folder:
        top_dir = os.path.join(top_dir, args.starting_folder)

    if not os.path.isdir(top_dir):
        console.printerr(f'Cannot check-in ABAP objects from "{top_dir}": not a directory')
        return 1

    config = _get_config(args.starting_folder, console)
    repo = Repository(args.name, config)

    try:
        _load_objects(repo)

        console.printout('Creating packages ...')
        for package in repo.packages:
            checkin_package(connection, package, args)

        groups = _resolve_dependencies(repo.objects)

        for activation_group in groups:
            console.printout('Creating objects ...')
            inactive_objects = _checkin_dependency_group(connection, activation_group, console, args.corrnr)

            if inactive_objects.references:
                console.printout('Activating objects ...')
                _activate(connection, inactive_objects, console)
    except sap.errors.SAPCliError as ex:
        console.printerr(f'Checkin failed: {ex}')
        return 1

    return 0


class CommandGroup(sap.cli.core.CommandGroup):
    """Commands for importing ADT objects"""

    def __init__(self):
        super().__init__('checkin')

    # pylint: disable=arguments-differ
    def install_parser(self, arg_parser):
        arg_parser.add_argument('--starting-folder', default=None)
        arg_parser.add_argument('--software-component', type=str, default='LOCAL')
        arg_parser.add_argument('--app-component', type=str, default=None)
        arg_parser.add_argument('--transport-layer', type=str, default=None)
        arg_parser.add_argument('corrnr', type=str, nargs='?', default=None)
        arg_parser.add_argument('name')
        arg_parser.set_defaults(execute=do_checkin)
