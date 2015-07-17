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
    name = None
    
    def __init__(self, name):
        self.name = name
        
    def __repr__(self):
        return "$%s" % self.name
        
class Datablock(object):
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

class Application(object):
    bound_function_pattern = re.compile("(?<!.)\s*function\s+(([A-z]|_)+::)([A-z]|_)+\(\s*(%[A-z]+(\s*,\s*%[A-z]+)*)*\s*\)")
    function_pattern = re.compile("(?<!.)\s*function\s+([A-z]|_)+\(\s*(%[A-z]+(\w*,\s*%[A-z]+)*)*\s*\)")
    datablock_pattern = re.compile("(?<!.)\s*datablock\s+[A-z]+\s*\(\s*\S+\s*\)\s*(:\s*[A-z]+)?\s*(//.*)?\s*\{(\s|\S)*?\s*(?<!.)\};")

    key_value_pattern = re.compile("(?<!.)\s*[A-z]+\s*=\s*(\S+);")
    
    #block_iterator = re.compile("function\s+[A-z]+\s*\(\s*(%[A-z]+(\w*,\s*%[A-z]+)*)*\s*\)\{\S*\}")
    
    # (?<!{)\s*\$[A-z]+(::([A-z]+))*?\s*(?!})
    global_usages = re.compile("\{.*\$[A-z]+(::([A-z]+))*?.*\}")
    global_pattern = re.compile("(?<!.)\s*$[A-z]+(::([A-z]+))*?")
    
    parameter_split = re.compile("\s*,\s*")
    assignment_split = re.compile("\s*=\s*")
    
    def print_usage(self):
        print("Usage: '%s <target directory> <exporter>'" % sys.argv[0])
        print("Or: '%s exporters' for a list of known exporters." % sys.argv[0])
    
    # Tables for checking datablock data
    datablock_reference_table = {
        "tracerprojectiledata": {
            "references": ["splash", "explosion", "sound"],
            "declared": [ ],
            "checks": {
                "fizzletimems": (lambda x: x >= 0, "Cannot use negative fizzle time!")
            }
        },
        
        "shapebaseimagedata": {
            "references": ["item", "projectile"],
            "declared": ["projectiletype"],
            "checks": { 
            }
        },
            
        "itemdata": {
            "references": [ ],
            "declared": [ ],
            "checks": { }
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
    }
    
    """
        TracerProjectileData:
            splash
            explosion
            sound
            
        ShapeBaseImageData:
            item
            projectile
            projectileType == projectile.type
    """
    def check_datablock_references(self, data, known_datablocks):
        
         # For each file entry
        for file in data:
            # For each datablock
            for datablock in file.datablocks:
                if (datablock.type in self.datablock_reference_table):
                    # Flip through each reference in the table
                    for reference in self.datablock_reference_table[datablock.type]["references"]:
                        if (reference not in datablock.properties):
                            print("Reference Warning: %s datablock '%s' has no '%s' declaration! (Declaration in %s, line %u)" % (datablock.type, datablock.name, reference, datablock.filepath, datablock.line))
                        else:
                            if (datablock.properties[reference] not in known_datablocks.keys()):
                                print("Reference Warning: %s Datablock '%s' references '%s' in property '%s', which does not exist! (Declaration in %s, line %u)" % (datablock.type, datablock.name, datablock.properties[reference], reference, datablock.filepath, datablock.line))
                    
                    # Check each declaration
                    for declaration in self.datablock_reference_table[datablock.type]["declared"]:
                        if (declaration not in datablock.properties):
                            print("Declaration Warning: %s Datablock '%s' required property '%s' not declared! (Declaration in %s, line %u)" % (datablock.type, datablock.name, declaration, datablock.filepath, datablock.line))
                        
                    # Run custom checks
                    for check in self.datablock_reference_table[datablock.type]["checks"].keys():
                        # Is it declared?
                        if (check not in datablock.properties):
                            print("Property Warning: %s Datablock %s '%s' property not declared! (Declaration in %s, line %u)" % (datablock.type, datablock.name, check, datablock.filepath, datablock.line))
                        else:
                            method, message = self.datablock_reference_table[datablock.type]["checks"][check]
  
                            if (not method(datablock.properties[check])):
                                print("Property Warning (Datablock '%s', type %s. Declaration in %s, line %u): %s" % (datablock.name, datablock.type, datablock.filepath, datablock.line, message))
                else:
                    print("Program Error: Unknown datablock type '%s'! This means the software does not know how to check this datablock. (Declaration in %s, line %u)" % (datablock.type, datablock.filepath, datablock.line))

    def resolve_datablock_parents(self, data, known_datablocks):      
        # For each file entry
        for file in data:
            # For each datablock
            for datablock in file.datablocks:
                if (datablock.derived is not None and datablock.derived not in known_datablocks.keys()):
                    print("Warning: Datablock '%s' derives from non-existent parent '%s'! (Declaration in %s, line %u)" % (datablock.name, datablock.derived,datablock.filepath, datablock.line))
                elif (datablock.derived is not None):
                    datablock.derived = known_datablocks[datablock.derived]
        
    def process_data(self, data):
        # Entries we've already processed
        processed_entries = { }
        
        # For each file entry
        for file in data:
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
            known_datablocks = { }
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

                # Only check TS files
                name, extension = os.path.splitext(filepath)
                if (extension != ".cs"):
                    continue
                
                with open(filepath, "r") as handle:
                    file_entry = FileEntry(filepath)
                    
                    file_data = handle.read()
                    
                    # Grab Global function definitions
                    for match in re.finditer(self.function_pattern, file_data):
                        line = file_data[0:match.start()].count("\n") + 1
                        match_split = match.group(0).lstrip().rstrip().lstrip("function ").split("(")
                        name = match_split[0].lower()
                        
                        match_split = re.split(self.parameter_split, match_split[1].replace(")", ""))
                        
                        parameters = [ ]
                        for parameter in match_split:
                            if (parameter == ""):
                                continue
                            
                            parameters.append(parameter.lstrip().rstrip())
                          
                        file_entry.global_functions.append(Function(name, None, parameters, filepath, line))
                        
                    # Grab bound function definitions
                    for match in re.finditer(self.bound_function_pattern, file_data):
                        line = file_data[0:match.start()].count("\n") + 1
                        
                        match_split = match.group(0).lstrip().rstrip().lstrip("function ").split("::")
                        type = match_split[0].lower()
                        
                        match_split = match_split[1].split("(")
                        name = match_split[0].lower()
                        match_split = match_split[1].replace(")", "").split(",")
                        
                        parameters = [ ]
                        for parameter in match_split:
                            if (parameter == ""):
                                continue
                            parameters.append(parameter.lstrip().rstrip())
                          
                        file_entry.bound_functions.setdefault(type, [])
                        file_entry.bound_functions[type].append(Function(name, type, parameters, filepath, line))

                    # Grab non-inherited DB definitions
                    for match in re.finditer(self.datablock_pattern, file_data):
                        line = file_data[0:match.start()].count("\n") + 1
                        match_text = match.group(0).lstrip().rstrip()
                        
                        header = match_text[0:match_text.find("{")]                        
                        type = header[len("datablock") + 1:header.find("(")].lstrip().rstrip().lower()
                        name = header[header.find("(") + 1:header.find(")")].lstrip().rstrip().lower()
                        
                        # Inherited?
                        inherited = None
                        inheritor = header.find(":")
                        if (inheritor != -1):
                            inherited = header[inheritor + 1:].lstrip().rstrip().lower()
                        
                        # Blow through key, values
                        properties = { }
                        for property_match in re.finditer(self.key_value_pattern, match_text):
                            property_text = property_match.group(0)
                            
                            key, value = re.split(self.assignment_split, property_text, 1)
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
                        
                        file_entry.datablocks.append(Datablock(name, type, properties, filepath, line, inherited))
 
                    # Stick in results
                    results.append(file_entry)
        
        known_datablocks = self.process_data(results)
        self.resolve_datablock_parents(results, known_datablocks)
        self.check_datablock_references(results, known_datablocks)
        
        # Init the DokuOutput
        output = exporter.Exporter(results)
        output.write()
    
if __name__ == "__main__":
    Application().main()
