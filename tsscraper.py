import re
import os
import sys
import multiprocessing
import importlib
import os.path
import timeit

import cProfile


class FileEntry(object):
    """
        Class representing a file in the mod directory. This
        contains all processed nodes within the file data.
    """
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
    """
        Class representing a Function entity in the game code tree
        that the parse stage produces.
    """
    name = None
    parameters = None
    type = None
    filepath = None
    line = None
    
    aliases = None
    comments = None
    
    def __init__(self, name, type, parameters, filepath, line):
        self.name = name
        self.parameters = parameters
        self.filepath = filepath
        self.line = line
        self.aliases = [ ]
        self.type = type

class Global(object):
    """
        Class representing a global variable. This is currently unused
        in the coding.
    """
    name = None
    
    def __init__(self, name):
        self.name = name
        
    def __repr__(self):
        return "$%s" % self.name
        
class Datablock(object):
    """
        Class representing a datablock entry. It contains the type, derived
        datablock name, the datablock name itself and all assigned properties.
    """
    name = None
    type = None
    derived = None
    line = None
    
    aliases = None
    properties = None
    filepath = None
    comments = None
    
    def __init__(self, name, type, properties, filepath, line, derived):
        self.name = name
        self.type = type
        self.derived = derived
        self.line = line
        self.aliases = [ ]
        self.properties = properties
        self.filepath = filepath
        
def scrape_file(input):
    """
        This method is a performance critical code segment in the scraper.
        It is what performs the initial parsing step to produce a sort of
        high level representation of the mod for later steps to process
        and eventually output.
    """
    filepath, parameter_split, combined_pattern = input

    key_value_pattern = re.compile("(?<!.)\s*[A-z]+\s*=\s*(\S+);")
    
    global_usages = re.compile("\{.*\$[A-z]+(::([A-z]+))*?.*\}")
    global_pattern = re.compile("(?<!.)\s*$[A-z]+(::([A-z]+))*?")
    
    parameter_split = re.compile("\s*,\s*")
    assignment_split = re.compile("\s*=\s*")
    
    with open(filepath, "r") as handle:
        result = FileEntry(filepath)
        file_data = handle.read()
                   
        # Parse for all sequences now
        for match in re.finditer(combined_pattern, file_data):
            line = file_data[0:match.start()].count("\n") + 1
            
            match_text = match.group(0).strip()
            if (match_text[0:8] == "function"):
                # :: Can't occur correctly in TS in just the function body, so we determine bound functions via the
                # presence of ::
                
                if ("::" in match_text):
                    match_split = match.group(0).strip()[9:].split("::")
                    type = match_split[0].lower()
                                
                    match_split = match_split[1].split("(")
                    name = match_split[0].lower()
                    match_split = match_split[1].replace(")", "").split(",")
                                
                    parameters = [ ]
                    for parameter in match_split:
                        if (parameter == ""):
                            continue
                    
                    parameters.append(parameter.lstrip().rstrip())
                            
                    result.bound_functions.setdefault(type, [])
                    result.bound_functions[type].append(Function(name, type, parameters, filepath, line))
                else:
                    match_split = match.group(0).strip()[9:].split("(")
                    name = match_split[0].lower()
                    
                    match_split = re.split(parameter_split, match_split[1].replace(")", ""))
                                
                    parameters = [ ]
                    for parameter in match_split:
                        if (parameter == ""):
                            continue
                                    
                        parameters.append(parameter.strip())
            else:
                line = file_data[0:match.start()].count("\n") + 1
                match_text = match.group(0).lstrip().rstrip()
                          
                header = match_text[0:match_text.find("{")]                        
                type = header[10:header.find("(")].strip().lower()
                name = header[header.find("(") + 1:header.find(")")].strip().lower()
                            
                # Inherited?
                inherited = None
                inheritor = header.find(":")
                if (inheritor != -1):
                    inherited = header[inheritor + 1:].strip().lower()
                            
                # Blow through key, values
                properties = { }
                for property_match in re.finditer(key_value_pattern, match_text):
                    property_text = property_match.group(0)
                                
                    key, value = re.split(assignment_split, property_text, 1)
                    key = key.lstrip().lower()
                                
                    value = value.rstrip().rstrip(";")
                                
                    # Global reference
                    if (value[0] == "$"):
                        value = Global(value[1:])
                    # String
                    elif (value[0] == "\""):
                        value = value[1:value.rfind("\"")]                                
                    # Numerics
                    else:
                        try:
                            value = float(value)
                        except ValueError as e:
                    # If this was raised, treat it as a string
                            pass
                                
                    properties[key] = value
                    
                result.datablocks.append(Datablock(name, type, properties, filepath, line, inherited))
                         
        return result      

class TSScraper(object):
    _process_count = None
    _target_directories = None
    _dependencies = None
    
    _combined_pattern = re.compile("(?<!.)\s*function\s+(([A-z]|_))+(::([A-z]|_)+)*\(\s*(%[A-z]+(\s*,\s*%[A-z]+)*)*\s*\)|((?<!.)\s*datablock\s+[A-z]+\s*\(\s*\S+\s*\)\s*(:\s*[A-z]+)?\s*(//.*)?\s*\{(\s|\S)*?\s*(?<!.)\};)")
        
    bound_function_pattern = re.compile("(?<!.)\s*function\s+(([A-z]|_)+::)([A-z]|_)+\(\s*(%[A-z]+(\s*,\s*%[A-z]+)*)*\s*\)")
    function_pattern = re.compile("(?<!.)\s*function\s+([A-z]|_)+\(\s*(%[A-z]+(\w*,\s*%[A-z]+)*)*\s*\)")
    
    function_pattern = re.compile("(?<!.)\s*function\s+(([A-z]|_)+::)([A-z]|_)+\(\s*(%[A-z]+(\w*,\s*%[A-z]+)*)*\s*\)")
    
    datablock_pattern = re.compile("(?<!.)\s*datablock\s+[A-z]+\s*\(\s*\S+\s*\)\s*(:\s*[A-z]+)?\s*(//.*)?\s*\{(\s|\S)*?\s*(?<!.)\};")

    key_value_pattern = re.compile("(?<!.)\s*[A-z]+\s*=\s*(\S+);")
    
    #block_iterator = re.compile("function\s+[A-z]+\s*\(\s*(%[A-z]+(\w*,\s*%[A-z]+)*)*\s*\)\{\S*\}")
    
    # (?<!{)\s*\$[A-z]+(::([A-z]+))*?\s*(?!})
    global_usages = re.compile("\{.*\$[A-z]+(::([A-z]+))*?.*\}")
    global_pattern = re.compile("(?<!.)\s*$[A-z]+(::([A-z]+))*?")
    
    parameter_split = re.compile("\s*,\s*")
    assignment_split = re.compile("\s*=\s*")
    
    
    _log_lines = None
    
    # Rules for verifying datablock information
    _datablock_rules = {
        "tracerprojectiledata": {
            "references": ["splash", "explosion", "sound"],
            "declared": [ ],
            "checks": {
                "fizzletimems": (lambda x: x >= 0, "Cannot use negative fizzle time!")
            }
        },
        
        "shapebaseimagedata": {
            "references": [ ],
            "declared": [ ],
            "checks": { 
            }
        },
            
        "itemdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { "pickupradius": (lambda x: x > 0, "Items should have >= 1 pickup radius.")
            }
        },
        
        "audioprofile": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "simdatablock": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "jeteffectdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
                   
        "hovervehicledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },   
                
        "stationfxpersonaldata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "cameradata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
                
        "triggerdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "wheeledvehicledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "tsshapeconstructor": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "bombprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
                
        "stationfxvehicledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "staticshapedata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "decaldata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
                
        "repairprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "explosiondata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "linearprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "elfprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "linearflareprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "sensordata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "forcefieldbaredata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "particledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "particleemitterdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
     
        "playerdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "turretdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
                
        "turretimagedata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
                        
        "shockwavedata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "seekerprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
                
        "debrisdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "grenadeprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "sniperprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "sniperprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "flyingvehicledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "splashdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "energyprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "flareprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "targetprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "shocklanceprojectiledata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "effectprofile": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "precipitationdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
        },
        
        "commandericondata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
       },
        
        "missionmarkerdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
       },
        
       "particleemissiondummydata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
      },
       
      "fireballatmospheredata": {
            "references": [ ],
            "declared": [ ],
            "checks": { },
      },
      
      "audiodescription": {
          "references": [ ],
          "declared": [ ],
          "checks": { },
      },
      
      
      "lightningdata": {
          "references": [ ],
          "declared": [ ],
          "checks": { },
      },
      
      "audioenvironment": {
          "references": [ ],
          "declared": [ ],
          "checks": { },
      },
    }
    
    def __init__(self, target_directories, process_count = 0):
        self._process_count = process_count
        self._target_directories = target_directories
        
        self._log_lines = [ ]
        
    def get_file_list(self, directory):
        output = [ ]
        
        previous_working_directory = os.getcwd()
        os.chdir(directory)
        
        for root, dirs, files in os.walk("."):
            for filename in files:                    
                relative_path = os.path.join(root, filename)
                
                if (not os.path.isfile(relative_path)):
                    continue
                
                absolute_path = os.path.realpath(relative_path)     
               
                # Only check TS files
                name, extension = os.path.splitext(filename)
                if (extension != ".cs"):
                    continue  

                output.append((absolute_path, relative_path.lower()))
        
        os.chdir(previous_working_directory)
        return output
    
    def _parse_stage(self, target_files):
        results = None
        if (self._process_count > 0):
            # Create a list with all the required data for the multi-process
            input = [ ]
            
            for target_file in target_files:
                input.append((target_file, self.parameter_split, self._combined_pattern))
                
            pool = multiprocessing.Pool(processes=self._process_count)
            results = pool.map(scrape_file, input)
        else:
            results = [ ]

            for target_file in target_files:
                results.append(scrape_file((target_file, self.parameter_split, self._combined_pattern)))
        
        return results
        
    def _declaration_stage(self, parse_results):
         # Entries we've already processed
        processed_entries = { }
        
        # For each file entry
        known_datablocks = { }
        for file in parse_results:            
            # For each global function
            for global_function in file.global_functions:
                processed_entries.setdefault(global_function.name, global_function)
                
                # Check for declarations
                if (processed_entries[global_function.name] is not global_function):
                    known_entry = processed_entries[global_function.name]
                    
                    # Redeclaration with different param count
                    if (len(known_entry.parameters) != len(global_function.parameters)):
                        global_function.aliases.append(known_entry)
                        known_entry.aliases.append(global_function)
                        print("Warning: Global function '%s' redeclared with %u parameters in %s, line %u! (Original declaration in %s, line %u with %u parameters)" % (known_entry.name, len(global_function.parameters), global_function.filepath, global_function.line, known_entry.filepath, known_entry.line, len(known_entry.parameters)))
                    # Regular Redeclaration
                    else:
                        global_function.aliases.append(known_entry)
                        known_entry.aliases.append(global_function)
                        print("Warning: Global function '%s' redeclared in %s, line %u! (Original declaration in %s, line %u)" % (known_entry.name, global_function.filepath, global_function.line, known_entry.filepath, known_entry.line))
            
            processed_entries = { }
            
            # For each bound function
            for bound_type in file.bound_functions.keys():
                for bound_function in file.bound_functions[bound_type]:
                    processed_entries.setdefault(bound_function.type, {})
                    processed_entries[bound_function.type].setdefault(bound_function.name, bound_function)
                    
                    # Check for declarations
                    if (processed_entries[bound_function.type][bound_function.name] is not bound_function):
                        known_entry = processed_entries[bound_function.type][bound_function.name]
                        
                        # Redeclaration with different param count
                        if (len(known_entry.parameters) != len(bound_function.parameters)):
                            bound_function.aliases.append(known_entry)
                            known_entry.aliases.append(bound_function)
                            print("Warning: Bound function '%s::%s' redeclared with %u parameters in %s, line %u! (Original declaration in %s, line %u with %u parameters)" % (known_entry.type, known_entry.name, len(bound_function.parameters), bound_function.filepath, bound_function.line, known_entry.filepath, known_entry.line, len(known_entry.parameters)))
                        # Regular Redeclaration
                        else:
                            bound_function.aliases.append(known_entry)
                            known_entry.aliases.append(bound_function)
                            print("Warning: Bound function '%s::%s' redeclared in %s, line %u! (Original declaration in %s, line %u)" % (known_entry.type, known_entry.name, bound_function.filepath, bound_function.line, known_entry.filepath, known_entry.line))
            
            processed_entries = { }
            
            # For each datablock
            for datablock in file.datablocks:
                processed_entries.setdefault(datablock.name, datablock)
                
                known_datablocks.setdefault(datablock.name, [])
                known_datablocks[datablock.name].append(datablock)
                
                # Check for declarations
                if (processed_entries[datablock.name] is not datablock):
                    known_entry = processed_entries[datablock.name]
                    
                    # Redeclaration with different parent
                    if (known_entry.derived != datablock.derived):
                        known_entry.aliases.append(datablock)
                        datablock.aliases.append(known_entry)
                        print("Warning: Datablock '%s' redeclared in %s, line %u with parent '%s'! (Original declaration in %s, line %u with parent '%s')" % (datablock.name, datablock.filepath, datablock.line, datablock.derived, known_entry.filepath, known_entry.line, known_entry.derived))
                    # Regular Redeclaration
                    else:
                        known_entry.aliases.append(datablock)
                        datablock.aliases.append(known_entry)
                        print("Warning: Datablock '%s' redeclared in %s, line %u! (Original declaration in %s, line %u" % (datablock.name, datablock.filepath, datablock.line, known_entry.filepath, known_entry.line))
         
        return known_datablocks
    
    def _inheritance_stage(self, parse_results, datablock_list):      
        # For each file entry
        for file in parse_results:
            # For each datablock
            for datablock in file.datablocks:
                if (datablock.derived is not None and datablock.derived.lower() not in datablock_list.keys()):
                    print("Warning: Datablock '%s' derives from non-existent parent '%s'! (Declaration in %s, line %u)" % (datablock.name, datablock.derived, datablock.filepath, datablock.line))
                elif (datablock.derived is not None):
                    datablock.derived = datablock_list[datablock.derived]
    
    def _reference_stage(self, parse_results, datablock_list):
        # For each file entry
        for file in parse_results:
            # For each datablock
            for datablock in file.datablocks:
                if (datablock.type in self._datablock_rules):
                    # Flip through each reference in the table
                    for reference in self._datablock_rules[datablock.type]["references"]:
                        if (reference not in datablock.properties):
                            print("Reference Warning: %s datablock '%s' has no '%s' declaration! (Declaration in %s, line %u)" % (datablock.type, datablock.name, reference, datablock.filepath, datablock.line))
                        else:
                            if (datablock.properties[reference].lower() not in datablock_list.keys()):
                                print("Reference Warning: %s Datablock '%s' references '%s' in property '%s', which does not exist! (Declaration in %s, line %u)" % (datablock.type, datablock.name, datablock.properties[reference], reference, datablock.filepath, datablock.line))
                    
                    # Check each declaration
                    for declaration in self._datablock_rules[datablock.type]["declared"]:
                        if (declaration not in datablock.properties):
                            print("Declaration Warning: %s Datablock '%s' required property '%s' not declared! (Declaration in %s, line %u)" % (datablock.type, datablock.name, declaration, datablock.filepath, datablock.line))
                        
                    # Run custom checks
                    for check in self._datablock_rules[datablock.type]["checks"].keys():
                        # Is it declared?
                        if (check not in datablock.properties):
                            print("Property Warning: %s Datablock %s '%s' property not declared! (Declaration in %s, line %u)" % (datablock.type, datablock.name, check, datablock.filepath, datablock.line))
                        else:
                            method, message = self._datablock_rules[datablock.type]["checks"][check]
                            if (not method(datablock.properties[check])):
                                print("Property Warning (Datablock '%s', type %s. Declaration in %s, line %u): %s" % (datablock.name, datablock.type, datablock.filepath, datablock.line, message))
                else:
                    print("Program Error: Unknown datablock type '%s'! This means the software does not know how to check this datablock. (Declaration in %s, line %u)" % (datablock.type, datablock.filepath, datablock.line))

    def process(self): 
        result = None
        
        # Process each directory sequentially
        target_files = { }
        for index, target_directory in enumerate(self._target_directories):        
            if (os.path.isdir(target_directory) is False):
                raise IOError("No such directory to recurse (#%u): '%s'" % (index, target_directory))

            print("INFO: Building file list for directory '%s' ..." % target_directory)      
            current_files = self.get_file_list(target_directory)
            
            # Does a previous entry exist in the target file list?
            for current_absolute_path, current_relative_path in current_files:
                target_files[current_relative_path] = current_absolute_path
                
        # Build the list now
        target_file_list = [ ]
        
        for current_relative_file in target_files.keys():                  
            target_file_list.append(target_files[current_relative_file])
        
        # Perform the initial parse
        print("INFO: Performing parse stage ...")      
        parse_results = self._parse_stage(target_file_list)
        
        # Perform the declaration analysis
        print("INFO: Performing declaration analysis. ...")
        datablock_list = self._declaration_stage(parse_results)
            
        # Perform DB inheritance analysis
        print("INFO: Performing datablock inheritance analysis ...")
        self._inheritance_stage(parse_results, datablock_list)
            
        # Perform DB reference analysis
        print("INFO: Performing datablock reference analysis ...")
        self._reference_stage(parse_results, datablock_list)
            
        # We're done, return the results
        print("INFO: Done.")
            
        return result
           
        