import re
import os
import sys
import importlib
import os.path

class FileEntry(object):
    path = None
    global_functions = None
    bound_functions = None
    datablocks = None
    
    def __init__(self, path):
        self.path = path
        self.global_functions = [ ]
        self.bound_functions = { }
        self.datablocks = [ ]
    
class Function(object):
    name = None
    parameters = None
    type = None
    filepath = None
    line = None
    
    def __init__(self, name, type, parameters, filepath, line):
        self.name = name
        self.parameters = parameters
        self.filepath = filepath
        self.line = line
        self.type = type
        
class Datablock(object):
    name = None
    type = None
    derived = None
    
    def __init__(self, name, type, derived):
        self.name = name
        self.type = type
        self.derived = derived

class Application(object):
    bound_function_pattern = re.compile("function +(([A-z]|_)+::)([A-z]|_)+\( *(%[A-z]+( *, *%[A-z]+)*)* *\)")
    function_pattern = re.compile("function +([A-z]|_)+\( *(%[A-z]+( *, *%[A-z]+)*)* *\)")
    datablock_pattern = re.compile("datablock +[A-z]+ *( *[A-z]+ *)( *: *[A-z]+)?")
    
    def print_usage(self):
        print("Usage: '%s <target directory> <exporter>'" % sys.argv[0])
        print("Or: '%s exporters' for a list of known exporters." % sys.argv[0])

    def main(self):
        # Load exporters
        exporters = { }
        for root, dirs, files in os.walk("exporters"):
            for filename in files:
                module_name, extension = os.path.splitext(filename)
                
                if (module_name == "__init__"):
                    continue
                
                try:
                    module = importlib.import_module('exporters.%s' % (module_name))
                    exporters[module_name] = module
                except ImportError as e:
                    print(e)
                    
        if (len(sys.argv) < 2):
            self.print_usage()
            return
                
        if (sys.argv[1] == "exporters"):
            print("Available Exporters: ")
            
            for exporter in exporters.keys():
                print("\t- %s" % exporter)
            return
        elif(len(sys.argv) != 3):
            self.print_usage()
            return
        
        exporter = None
        try:
            exporter = exporters[sys.argv[2]]
        except KeyError as e:
            print("Error: No such exporter '%s'." % sys.argv[2])
            self.print_usage()
            return
        
        results = [ ]
        global_aliases = { }
        typed_aliases = { }
        for root, dirs, files in os.walk(sys.argv[1]):
            for filename in files:
                filepath = os.path.join(root, filename)
                
                if (not os.path.isfile(filepath)):
                    continue
                
                with open(filepath, "r") as handle:
                    file_entry = FileEntry(filepath)
                    
                    file_data = handle.read()
                    
                    # Grab Global function definitions
                    for match in re.finditer(self.function_pattern, file_data):
                        line = file_data[0:match.start()].count("\n") + 1
                        match_split = match.group(0).lstrip("function ").split("(")
                        name = match_split[0]
                        
                        match_split = match_split[1].replace(")", "").split(",")
                        
                        parameters = [ ]
                        for parameter in match_split:
                            if (parameter == ""):
                                continue
                            
                            parameters.append(parameter.lstrip().rstrip())
                          
                        file_entry.global_functions.append(Function(name, None, parameters, filepath, line))
                        
                        tracked_name = name.lower()
                        global_aliases.setdefault(tracked_name, (0, filepath, line))
                        
                        occurrence_count, old_filepath, old_line = global_aliases[tracked_name]
                        occurrence_count = occurrence_count + 1
                        global_aliases[tracked_name] = (occurrence_count, old_filepath, old_line)
                        
                        if (occurrence_count != 1):
                            print("Warning: Found a multiple declaration of global function '%s' in %s, line %u! (Original detection: %s, line %u)" % (tracked_name, filepath, line, old_filepath, old_line))
                        
                        
                    # Grab bound function definitions
                    for match in re.finditer(self.bound_function_pattern, file_data):
                        line = file_data[0:match.start()].count("\n") + 1
                        
                        match_split = match.group(0).lstrip("function ").split("::")
                        type = match_split[0]
                        
                        match_split = match_split[1].split("(")
                        name = match_split[0]
                        match_split = match_split[1].replace(")", "").split(",")
                        
                        parameters = [ ]
                        for parameter in match_split:
                            if (parameter == ""):
                                continue
                            parameters.append(parameter.lstrip().rstrip())
                          
                        file_entry.bound_functions.setdefault(type, [])
                        file_entry.bound_functions[type].append(Function(name, type, parameters, filepath, line))
                        
                        tracked_name = name.lower()
                        tracked_type = type.lower()
                        typed_aliases.setdefault(tracked_type, {})
                        typed_aliases[tracked_type].setdefault(tracked_name, (0, filepath, line))
                        
                        occurrence_count, old_filepath, old_line = typed_aliases[tracked_type][tracked_name]
                        occurrence_count = occurrence_count + 1
                        typed_aliases[tracked_type][tracked_name] = (occurrence_count, old_filepath, old_line)
                        
                        if (occurrence_count != 1):
                            print("Warning: Found a multiple declaration of bound function '%s::%s' in %s, line %u! (Original detection: %s, line %u)" % (tracked_type, tracked_name, filepath, line, old_filepath, old_line))
                        
                    # Grab DB definitions
                    for match in re.finditer(self.datablock_pattern, file_data):
                        match_text = match.group(0).lstrip("datablock ")
                        
                        #print(match_text)
 
                    # Stick in results
                    results.append(file_entry)
                    
        # Init the DokuOutput
        output = exporter.Exporter(results)
        output.write()
    
if __name__ == "__main__":
    Application().main()
