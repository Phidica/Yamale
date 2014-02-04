import sys

from .. import syntax
from . import util
from .data import Data
from schemata import validators as val


class Schema(dict):
    """
    Makes a Schema object from a schema dict.
    Still acts like a dict. #NeverGrowUp
    """
    def __init__(self, schema_dict, name=''):
        schema = util.flatten(schema_dict)
        dict.__init__(self, schema)
        self._process_schema(self)
        self.dict = schema_dict
        self.name = name
        self.includes = {}

    def add_include(self, type_dict):
        for include_name, custom_type in type_dict.items():
            t = Schema(custom_type, name=include_name)
            self.includes[include_name] = t

    def _process_schema(self, schema):
        '''
        Warning: this method mutates input.

        Go through a schema and construct validators.
        '''
        for key, expression in schema.items():
            try:
                schema[key] = syntax.parse(expression)
            except SyntaxError, e:
                # Tack on some more context and rethrow.
                raise SyntaxError(e.message + ' at \'%s\'' % key)

    def validate(self, data):
        errors = []

        for pos, validator in self.items():
            errors += self._validate(validator, data, position=pos, includes=self.includes)

        if errors:
            header = '\nError validating data %s with schema %s' % (data.name, self.name)
            error_str = '\n\t' + '\n\t'.join(errors)
            raise ValueError(header + error_str)

    def _validate(self, validator, data, position='', includes=None):
        '''
        Run through a schema and a data structure,
        validating along the way.

        Ignores fields that are in the data structure, but not in the schema.

        Returns an array of errors.
        '''

        errors = []

        try:  # Pull value out of data. Data can be a map or a list/sequence
            data_item = data[position]
        except KeyError:  # Oops, that field didn't exist.
            if validator.is_optional:  # Optional? Who cares.
                return errors
            # SHUT DOWN EVERTYHING
            errors.append('%s: Required field missing' % position)
            return errors

        errors += self._validate_primitive(validator, data_item, position)

        if errors:
            return errors

        if isinstance(validator, val.Include):
            return self._validate_include(validator, data_item, includes, position)

        elif isinstance(validator, val.List):
            return self._validate_list(validator, data_item, includes, position)

        return errors

    def _validate_list(self, validator, data, includes, position):
        errors = []

        if not validator.validators:
            return errors  # No validators, user just wanted a list.

        for i, d in enumerate(data):
            derrors = []
            for v in validator.validators:
                derrors += self._validate(v, data, i, includes)
            if len(derrors) == len(validator.validators):
                # All failed, add to errors
                errors += derrors

        return errors

    def _validate_include(self, validator, data, includes, position):
        errors = []

        include_schema = includes.get(validator.include_name)
        if not include_schema:
            errors.append('Include \'%s\' has not been defined.' % validator.include_name)
            return errors

        for pos, validator in include_schema.items():
            errors += include_schema._validate(validator, data, includes=includes, position=pos)

        return errors

    def _validate_primitive(self, validator, data, position):
        errors = []
        if not validator.is_valid(data):
            errors.append('%s: \'%s\' is not a %s.' % (position, data, validator.__tag__))
        return errors

