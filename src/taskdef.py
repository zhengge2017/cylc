#!/usr/bin/env python

# NOT YET IMPLEMENTED OR DOCUMENTED FROM bin/_taskgen:
#   - conditional prerequisites
#   - task inheritance
#   - asynch stuff, output_patterns
#   - no longer interpolate ctime in env vars or scripting 
#     (not needed since cylcutil?) 
#
#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

import os, re, string
from OrderedDict import OrderedDict

class Error( Exception ):
    """base class for exceptions in this module."""
    pass

class DefinitionError( Error ):
    """
    Exception raise for errors in taskdef initialization.
    Attributes:
        element - taskdef element causing the problem
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg

class taskdef:
    allowed_types = [ 'free', 'tied' ]
    allowed_modifiers = [ 'sequential', 'oneoff', 'dummy', 'contact', 'catchup_contact' ]

    allowed_keys = [ 'LOGFILES', 'TASK', 'OWNER', 'HOURS',
            'COMMAND', 'REMOTE_HOST', 'DIRECTIVES', 'SCRIPTING',
            'ENVIRONMENT', 'INTERCYCLE', 'PREREQUISITES',
            'COLDSTART_PREREQUISITES', 'SUICIDE_PREREQUISITES',
            'OUTPUTS', 'N_RESTART_OUTPUTS', 'TYPE', 'CONTACT_DELAY',
            'DESCRIPTION', 'OUTPUT_PATTERNS', 'FOLLOW_ON', 'FAMILY',
            'MEMBERS', 'MEMBER_OF' ]

    task_init_def_args = 'c_time, initial_state, startup = False'
    #task_inherit_super_args = 'c_time, initial_state, startup'
    task_init_args = 'initial_state'

    task_class_preamble = '''
#!/usr/bin/env python

#         __________________________
#         |____C_O_P_Y_R_I_G_H_T___|
#         |                        |
#         |  (c) NIWA, 2008-2010   |
#         | Contact: Hilary Oliver |
#         |  h.oliver@niwa.co.nz   |
#         |    +64-4-386 0461      |
#         |________________________|

# THIS FILE WAS AUTO-GENERATED BY CYLC

from daemon import daemon
from asynchronous import asynchronous
from cycling_daemon import cycling_daemon
from tied import tied
from free import free
from family import family
from mod_oneoff import oneoff
from mod_sequential import sequential
from mod_contact import contact
from mod_catchup_contact import catchup_contact
from prerequisites_fuzzy import fuzzy_prerequisites
from prerequisites import prerequisites
from outputs import outputs
from time import sleep
from task_output_logs import logfiles
import cycle_time
import task_state
from OrderedDict import OrderedDict
from collections import deque

'''

    def __init__( self, name, shortname=None ):
        self.check_name( name )
        self.name = name
        # IGNORING SHORT NAME FOR NOW
        #self.shortname = shortname

        self.classfile = '__' + name + '.py'

        self.type = None
        self.owner = None
        self.host = None

        self.intercycle = False
        self.hours = []
        self.logfiles = []
        self.description = []

        self.members = []
        self.member_of = None
        self.follow_on_task = None

        self.modifiers = []

        # use dicts quantities that may be conditional on cycle hour
        # keyed on condition
        self.n_restart_outputs = {}            # int
        self.contact_offset = {}               # float hours
        self.prerequisites = {}                # list of messages
        self.suicide_prerequisites = {}        #  "
        self.coldstart_prerequisites = {}      #  "
        self.conditional_prerequisites = {}    #  "
        self.outputs = OrderedDict()           #  "
        self.commands = OrderedDict()          # list of commands
        self.scripting = {}                    # list of lines
        self.environment = {}                  # OrderedDict() of var = value
        self.directives = {}                   # OrderedDict() of var = value

        self.indent = ''
        self.indent_unit = '  '

    def dump( self ):
        print 'NAME'
        print  '  ', self.name

        print 'DESCRIPTION'
        for line in self.description:
            print '  ', line

        print 'TYPE'
        types = [ self.type ] + self.modifiers
        print '  ', ', '.join( types )

        if self.owner:
            print 'OWNER'
            print '  ', self.owner

        if self.host:
            print 'HOST'
            print '  ', self.host

        self.dump_conditional_list( self.commands,      'COMMAND'       )
        self.dump_conditional_list( self.prerequisites, 'PREREQUISITES' )
        self.dump_conditional_list( self.outputs,       'OUTPUTS'       )
        self.dump_conditional_dict( self.environment,   'ENVIRONMENT'   )
        self.dump_conditional_list( self.scripting,     'SCRIPTING'     )
        self.dump_conditional_dict( self.directives,    'DIRECTIVES'    )

    def dump_conditional_list( self, foo, name ):
        # print out foo[condition] = []
        print name
        for condition in foo:
            print '  ', condition
            values = foo[condition]
            if len( values ) == 0:
                print '  ', '  ', "(none)"
            else:
                for value in values:
                    print '  ', '  ', value

    def dump_conditional_dict( self, foo, name ):
        # print out foo[condition][var] = value
        print name
        for condition in foo:
            print '  ', condition
            vars = foo[condition].keys()
            if len( vars ) == 0:
                print '  ', '  ', "(none)"
            else:
                for var in vars:
                    print '  ', '  ', foo[condition][var]

    def check_name( self, name ):
        if re.search( '[^\w]', name ):
            raise DefinitionError( 'Task names may contain only a-z,A-Z,0-9,_' )
 
    def check_type( self, type ): 
        if type not in self.__class__.allowed_types:
            raise DefinitionError( 'Illegal task type: ' + type )

    def check_modifier( self, modifier ):
        if modifier not in self.__class__.allowed_modifiers:
            raise DefinitionError( 'Illegal task type modifier: ' + modifier )

    def check_set_hours( self, hours ):
        for hr in hours:
            hour = int( hr )
            if hour < 0 or hour > 23:
                raise DefinitionError( 'Hour must be 0<hour<23' )
            self.hours.append( hour )

    def check_consistency( self ):
        if len( self.hours ) == 0:
            raise DefinitionError( 'no hours specified' )

        if 'contact' in self.modifiers:
            if len( self.contact_offset.keys() ) == 0:
                raise DefinitionError( 'contact tasks must specify a time offset' )

        if self.type == 'tied' and self.n_restart_outputs == 0:
            raise DefinitionError( 'tied tasks must specify number of restart outputs' )

        if 'oneoff' not in self.modifiers and self.intercycle:
            if not self.follow_on_task:
                raise DefinitionError( 'oneoff intercycle tasks must specify a follow-on task' )

        if self.member_of and len( self.members ) > 0:
            raise DefinitionError( 'nested task families are not allowed' )

    def check_key_not_conditional( self, key, condition ):
        if condition != 'any':
            raise DefinitionError( key + ' cannot be conditional')

    def append_to_condition_list( self, parameter, condition, value ):
        if condition in parameter.keys():
            parameter[condition].append( value )
        else:
            parameter[condition] = [ value ]

    def add_to_condition_dict( self, parameter, condition, var, value ):
        if condition in parameter.keys():
            parameter[condition][var] = value
        else:
            parameter[condition] = {}
            parameter[condition][var] = value

    def indent_more( self ):
        self.indent += self.indent_unit

    def indent_less( self ):
        self.indent = re.sub( self.indent_unit, '',  self.indent, 1 )

    def load_from_taskdef_file( self, file ):
        print 'Loading', file
        DEF = open( file, 'r' )
        lines = DEF.readlines()
        DEF.close()

        # PARSE THE TASKDEF FILE----------------------------
        current_key = None
        ###coms = []
        for lline in lines:
            line = string.strip( lline )
            # skip blank lines
            if re.match( '^\s*$', line ):
                continue
            # skip comment lines
            if re.match( '^\s*#.*', line ):
                continue
            # detect conditionals:
            m = re.match( '^\s*if HOUR in \s*([\d,]+)\s*:', lline )
            if m:
                #print '!   ', condition
                condition = m.groups()[0]
                continue
 
            # warn of possible illegal trailing comments
            if re.search( '#', line ):
                print 'WARNING: possible illegal trailing comment detected:'
                print '   --> ', line
                print "(OK if '#' is in a string or shell variable expansion)"
       
            if re.match( '^\s*%.*', line ):
                # NEW KEY IDENTIFIED
                # default condition is 'any' (any hour)
                condition = 'any'
                current_key = string.lstrip( line, '%' )
                # always define an 'any' key
                if current_key not in self.__class__.allowed_keys:
                    raise DefintionError( 'ILLEGAL KEY: ' + key )

            else:
                # process data associated with current key
                value = line

                if current_key == 'TYPE':
                    self.check_key_not_conditional( current_key, condition )
                    typelist = re.split( r', *', value )
                    type = typelist[0]
                    self.check_type( type )
                    self.type = type
                    if len( typelist ) > 1:
                        for modifier in typelist[1:]:
                            self.check_modifier( modifier )
                            self.modifiers.append( modifier )

                elif current_key == 'DESCRIPTION':
                    self.description.append( line )

                elif current_key == 'OWNER':
                    self.owner = value

                elif current_key == 'REMOTE_HOST':
                    self.host = value

                elif current_key == 'HOURS':
                    hours = re.split( ',\s*', value )
                    self.check_set_hours( hours )
 
                elif current_key == 'FAMILY':
                    self.check_key_not_conditional( current_key, condition )
                    self.member_of = value
 
                elif current_key == 'MEMBERS':
                    self.check_key_not_conditional( current_key, condition )
                    self.members.append( value )

                elif current_key == 'INTERCYCLE':
                    self.check_key_not_conditional( current_key, condition )
                    if value == 'True' or value == 'true':
                        self.intercycle = True

                elif current_key == 'LOGFILES':
                    self.check_key_not_conditional( current_key, condition )
                    self.logs.append( value )

                elif current_key == 'FOLLOW_ON':
                    self.check_key_not_conditional( current_key, condition )
                    self.follow_on_task = value

                elif current_key == 'CONTACT_DELAY':
                    self.check_key_not_conditional( current_key, condition )
                    self.contact_offset[ condition ] = self.time_trans( value, hours=True )

                elif current_key == 'N_RESTART_OUTPUTS':
                    try:
                        self.n_restart_outputs[ condition ] = int( value )
                    except ValueError:
                        raise DefinitionError( 'N_RESTART_OUTPUTS must be integer valued' )

                elif current_key == 'COMMAND':
                    self.append_to_condition_list( self.commands, condition, value ) 

                elif current_key == 'SCRIPTING':
                    self.append_to_condition_list( self.scripting, condition, value )

                elif current_key == 'ENVIRONMENT':
                    evar, evalue = value.split( ' ', 1 )
                    self.add_to_condition_dict( self.environment, condition, evar, evalue )

                elif current_key == 'DIRECTIVES':
                    evar, evalue = value.split( ' ', 1 )
                    self.add_to_condition_dict( self.directives, condition, evar, evalue )

                elif current_key == 'PREREQUISITES':
                    stripped = self.require_quotes( value )
                    self.append_to_condition_list( self.prerequisites, condition, stripped )

                elif current_key == 'OUTPUTS':
                    stripped = self.require_quotes( value )
                    self.append_to_condition_list( self.outputs, condition, stripped )

                elif current_key == 'COLDSTART_PREREQUISITES':
                    stripped = self.require_quotes( value )
                    self.append_to_condition_list( self.coldstart_prerequisites, condition, stripped )

                elif current_key == 'SUICIDE_PREREQUISITES':
                    stripped = self.require_quotes( value )
                    self.append_to_condition_list( self.suicide_prerequisites, condition, stripped )
                    self.add_suicide_prerequisite( value )

                # TO DO TO DO 
                #elif current_key == 'CONDITIONAL_PREREQUISITES':
                #    label, message = value.split( ' ', 1 )
                #    self.add_conditional_prerequisite( label, message )
        
        self.check_consistency()
        self.check_commandlines()
        self.interpolate_conditional_list( self.prerequisites )
        self.interpolate_conditional_list( self.suicide_prerequisites )
        self.interpolate_conditional_list( self.coldstart_prerequisites )
        self.interpolate_conditional_list( self.outputs )

    def check_commandlines( self ):
        # concatenate any commandlines ending in '\'
        for condition in self.commands.keys():
            oldc = self.commands[ condition ]
            newc = []
            cat = ''
            for t in oldc:
                if t[-1] == '\\':
                    cat += t[0:-1]
                    continue
                if cat != '':
                    newc.append( cat + t )
                    cat = ''
                else:
                    newc.append( t )
            self.commands[ condition ] = newc

    def write_task_class( self, dir ):
        outfile = os.path.join( dir, self.classfile )

        # TO DO: EXCEPTION HANDLING FOR DIR NOT FOUND ...
        OUT = open( outfile, 'w' )

        OUT.write( self.__class__.task_class_preamble )

        # task class multiple inheritance
        # this assumes the order of modifiers does not matter
        derived_from = self.type
        if len( self.modifiers ) >= 1:
            derived_from = ','.join( self.modifiers ) + ', ' + derived_from

        OUT.write( 'class ' + self.name + '(' + derived_from + '):\n' )

        OUT.write( self.indent + '# AUTO-GENERATED BY CYLC\n\n' )  
 
        OUT.write( self.indent + 'name = \'' + self.name + '\'\n' )
        #OUT.write( self.indent + 'short_name = \'' + self.short_name + '\'\n' )

        OUT.write( self.indent + 'instance_count = 0\n\n' )

        OUT.write( self.indent + 'description = []\n' )
        for line in self.description:
            OUT.write( self.indent + 'description.append("' + self.escape_quotes(line) + '")\n' )
            OUT.write( '\n' )
 
        if self.owner:
            OUT.write( self.indent + 'owner = \'' + self.owner + '\'\n' )
        else:
            OUT.write( self.indent + 'owner = None\n' )

        if self.host:
            OUT.write( self.indent + 'remote_host = \'' + self.host + '\'\n' )
        else:
            OUT.write( self.indent + 'remote_host = None\n' )

        # can this be moved into task base class?
        OUT.write( self.indent + 'job_submit_method = None\n' )

        OUT.write( self.indent + 'valid_hours = [' )
        for hour in self.hours:
            OUT.write( ', ' + str(hour) )
        OUT.write( self.indent + ']\n\n' )

        if self.intercycle:
            OUT.write( self.indent + 'intercycle = ' + str(self.intercycle) + '\n\n' )

        if self.follow_on_task:
            OUT.write( self.indent + 'follow_on = "' + self.follow_on_task + '"\n\n' )

        # class init function
        OUT.write( self.indent + 'def __init__( self, ' + self.__class__.task_init_def_args + ' ):\n\n' )

        self.indent_more()

        OUT.write( self.indent + '# adjust cycle time to next valid for this task\n' )
        OUT.write( self.indent + 'self.c_time = self.nearest_c_time( c_time )\n' )
        OUT.write( self.indent + 'self.tag = self.c_time\n' )
        OUT.write( self.indent + 'self.id = self.name + \'%\' + self.c_time\n' )
        #### FIXME ASYNC
        OUT.write( self.indent + 'hour = self.c_time[8:10]\n\n' )

        # external task
        OUT.write( self.indent + 'self.external_tasks = deque()\n' )

        for condition in self.commands:
            for command in self.commands[ condition ]:
                if condition == 'any':
                    OUT.write( self.indent + 'self.external_tasks.append( \'' + command + '\')\n' )
                else:
                    hours = re.split( ',\s*', condition )
                    for hour in hours:
                        OUT.write( self.indent + 'if int( hour ) == ' + hour + ':\n' )
                        self.indent_more()
                        OUT.write( self.indent + 'self.external_tasks.append( \'' + command + '\')\n' )
                        self.indent_less()
 
        if 'contact' in self.modifiers:
            for condition in self.contact_offset:
                offset = self.contact_offset[ condition ]
                if condition == 'any':
                    OUT.write( self.indent + 'self.real_time_delay = ' +  str( offset ) + '\n' )
                else:
                    hours = re.split( ',\s*', condition )
                    for hour in hours:
                        OUT.write( self.indent + 'if int( hour ) == ' + hour + ':\n' )
                        self.indent_more()
                        OUT.write( self.indent + 'self.real_time_delay = ' + str( offset ) + '\n' )
                        self.indent_less()
 
            OUT.write( '\n' )

        self.write_requisites( OUT, 'prerequisites', self.prerequisites )
        self.write_requisites( OUT, 'suicide_prerequisites', self.suicide_prerequisites )
        self.write_requisites( OUT, 'outputs', self.outputs )

        if self.type == 'tied':
            for condition in self.n_restart_outputs.keys():
                n = self.n_restart_outputs[ condition ]
                if condition == 'any':
                    OUT.write( self.indent + 'self.register_restart_requisites(' + str(n) +')\n' )
                else:
                    hours = re.split( ', *', condition )
                    for hour in hours:
                        OUT.write( self.indent + 'if int( hour ) == ' + hour + ':\n' )
                        self.indent_more()
                        OUT.write( self.indent + 'self.register_restart_requisites(' + str( n ) + ')\n' )
                        self.indent_less()
 
        OUT.write( self.indent + 'self.outputs.register()\n\n' )

        # override the above with any coldstart prerequisites
        self.write_requisites( OUT, 'coldstart_prerequisites', self.coldstart_prerequisites )

        OUT.write( '\n' + self.indent + 'self.env_vars = OrderedDict()\n' )
        OUT.write( self.indent + "self.env_vars['TASK_NAME'] = self.name\n" )
        OUT.write( self.indent + "self.env_vars['TASK_ID'] = self.id\n" )
        OUT.write( self.indent + "self.env_vars['CYCLE_TIME'] = self.c_time\n" )
       
        for condition in self.environment.keys():
            envdict = self.environment[ condition ]
            for var in envdict.keys():
                val = envdict[ var ]
                if condition == 'any':
                    OUT.write( indent + 'self.env_vars[' + var + '] = ' + val + '\n' )
                else:
                    hours = re.split( ', *', condition )
                    for hour in hours:
                        OUT.write( self.indent + 'if int( hour ) == ' + hour + ':\n' )
                        self.indent_more()
                        OUT.write( indent + 'self.env_vars[' + var + '] = ' + val + '\n' )
                        self.indent_less()
 
        OUT.write( '\n' + self.indent + 'self.directives = OrderedDict()\n' )
        for condition in self.directives.keys():
            dirdict = self.directives[ condition ]
            for var in dirdict.keys():
                val = dirdict[ var ]
                if condition == 'any':
                    OUT.write( self.indent + 'self.directives[' + var + '] = ' + val + '\n' )
                else:
                    hours = re.split( ', *', condition )
                    for hour in hours:
                        OUT.write( self.indent + 'if int( hour ) == ' + hour + ':\n' )
                        self.indent_more()
                        OUT.write( self.indent + 'self.directives[' + var + '] = ' + val + '\n' )
                        self.indent_less()
 
        OUT.write( '\n' + self.indent + 'self.extra_scripting = []\n' )

        for condition in self.scripting.keys():
            lines = self.scripting[ condition ]
            for line in lines:
                if condition == 'any':
                    OUT.write( self.indent + 'self.extra_scripting.append(' + line + ')\n' )
                else:
                    hours = re.split( ', *', condition )
                    for hour in hours:
                        OUT.write( self.indent + 'if int( hour ) == ' + hour + ':\n' )
                        self.indent_more()
                        OUT.write( self.indent + 'self.extra_scripting.append(' + line + ')\n' )
                        self.indent_less()
 
        OUT.write( '\n' )

        if 'catchup_contact' in self.modifiers:
            OUT.write( self.indent + 'catchup_contact.__init__( self )\n\n' )
 
            OUT.write( self.indent + task_type + '.__init__( self, ' + self.__class__.task_init_args + ' )\n\n' )

        self.indent_less()
        self.indent_less()

        OUT.close()
 



    def write_requisites( self, FILE, req_name, requisites ):
        for condition in requisites:
            reqs = requisites[ condition ]
            if condition == 'any':
                for req in reqs:
                    FILE.write( self.indent + 'self.' + req_name + '.add(' +  req + ')\n' )
            else:
                hours = re.split( ',\s*', condition )
                for hour in hours:
                    FILE.write( self.indent + 'if int( hour ) == ' + hour + ':\n' )
                    self.indent_more()
                    FILE.write( self.indent + 'self.' + req_name + '.add(' + req + ')\n' )
                    self.indent_less()

    def escape_quotes( self, strng ):
        return re.sub( '([\\\'"])', r'\\\1', strng )

    def interpolate_conditional_list( self, foo ):
        for condition in foo.keys():
            old_values = foo[ condition ]
            new_values = []
            for value in old_values:
                new_values.append( self.interpolate_cycle_times( value ) )
            foo[condition] = new_values

    def interpolate_cycle_times( self, strng ):
        # interpolate $(CYCLE_TIME [+/-N]) in a string
        # strng = 'a string'  (SINGLE QUOTES REQUIRED)

        # strip leading spaces
        strng = re.sub( "^'\s+", "'", strng )

        # replace "$(CYCLE_TIME)"
        strng = re.sub( "^'\$\(CYCLE_TIME\)'$",   "self.c_time",     strng ) # alone
        strng = re.sub( "^'\$\(CYCLE_TIME\)",     "self.c_time + '", strng ) # start line
        strng = re.sub( "\$\(CYCLE_TIME\)'$", "' + self.c_time"   ,  strng ) # end line
        strng = re.sub( "\$\(CYCLE_TIME\)" , "'  + self.c_time + '", strng ) # mid line

        # replace "$(CYCLE_TIME - XX )"
        m = re.search( '\$\(\s*CYCLE_TIME\s*-\s*(\d+)\s*\)', strng )
        if m:
            strng = re.sub( "^'\$\(\s*CYCLE_TIME.*\)'$",   "cycle_time.decrement( self.c_time, " + m.group(1) + ")",     strng ) # alone
            strng = re.sub( "^'\$\(\s*CYCLE_TIME.*\)",     "cycle_time.decrement( self.c_time, " + m.group(1) + ") + '", strng ) # start line
            strng = re.sub( "\$\(\s*CYCLE_TIME.*\)'$", "' + cycle_time.decrement( self.c_time, " + m.group(1) + ")",     strng ) # mid line
            strng = re.sub( "\$\(\s*CYCLE_TIME.*\)",   "' + cycle_time.decrement( self.c_time, " + m.group(1) + ") + '", strng ) # end line

        # replace "$(CYCLE_TIME + XX )"
        m = re.search( '\$\(\s*CYCLE_TIME\s*\+\s*(\d+)\s*\)', strng )
        if m:
            strng = re.sub( "^'\$\(\s*CYCLE_TIME.*\)'$",   "cycle_time.increment( self.c_time, " + m.group(1) + ")",     strng ) # alone
            strng = re.sub( "^'\$\(\s*CYCLE_TIME.*\)",     "cycle_time.increment( self.c_time, " + m.group(1) + ") + '", strng ) # start line
            strng = re.sub( "\$\(\s*CYCLE_TIME.*\)'$", "' + cycle_time.increment( self.c_time, " + m.group(1) + ")",     strng ) # mid line
            strng = re.sub( "\$\(\s*CYCLE_TIME.*\)",   "' + cycle_time.increment( self.c_time, " + m.group(1) + ") + '", strng ) # end line

        # now check for any environment variable $CYCLE_TIME or ${CYCLE_TIME}
        m = re.search( '\$CYCLE_TIME', strng )
        n = re.search( '\$\{CYCLE_TIME\}', strng )
        if m:
            strng = re.sub( "^'\$CYCLE_TIME",     "self.c_time + '", strng ) # start line
            strng = re.sub( "\$CYCLE_TIME'$", "' + self.c_time"   ,  strng ) # end line
            strng = re.sub( "\$CYCLE_TIME" , "'  + self.c_time + '", strng ) # mid line
        if n:
            strng = re.sub( "^'\$\{CYCLE_TIME\}",     "self.c_time + '", strng ) # start line
            strng = re.sub( "\$\{CYCLE_TIME\}'$", "' + self.c_time"   ,  strng ) # end line
            strng = re.sub( "\$\{CYCLE_TIME\}" , "'  + self.c_time + '", strng ) # mid line
    
        return strng

    def time_trans( self, strng, hours=False ):
        # translate a time of the form:
        #  x sec, y min, z hr
        # into float MINUTES or HOURS,
    
        if not re.search( '^\s*(.*)\s*min\s*$', strng ) and \
            not re.search( '^\s*(.*)\s*sec\s*$', strng ) and \
            not re.search( '^\s*(.*)\s*hr\s*$', strng ):
                print "ERROR: missing time unit on " + strng
                sys.exit(1)
    
        m = re.search( '^\s*(.*)\s*min\s*$', strng )
        if m:
            [ mins ] = m.groups()
            if hours:
                return str( float( mins / 60.0 ) )
            else:
                return str( float(mins) )
    
        m = re.search( '^\s*(.*)\s*sec\s*$', strng )
        if m:
            [ secs ] = m.groups()
            if hours:
                return str( float(secs)/3600.0 )
            else:
                return str( float(secs)/60.0 )
    
        m = re.search( '^\s*(.*)\s*hr\s*$', strng )
        if m:
            [ hrs ] = m.groups()
            if hours:
                #return str( float(hrs) )
                return float(hrs)
            else:
                #return str( float(hrs)*60.0 )
                return float(hrs)*60.0
    
    def require_quotes( self, strng ):
        # require enclosing double quotes, then strip them off
    
        # first strip any whitespace
        str = string.strip( strng )

        m = re.match( '^".*"$', str )
        if m:
            stripped = string.strip( str, '"' )
        else:
            print 'ERROR: string must be enclosed in double quotes:'
            print strng
            sys.exit(1)

        return "'" + stripped + "'"


